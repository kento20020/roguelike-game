"""DB操作。生SQLは書かない（SQLAlchemy経由）。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TypeVar

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session

from app.data.loader import get_data
from app.db.models import (
    ActiveSessionRow,
    ObservationRow,
    PostmortemRow,
    ProfileRow,
    RunActionsRow,
    RunRecordRow,
)

UPGRADE_ITEMS = ["max_hp", "attack", "init_gold", "gold_drop", "sink_cost"]

_Row = TypeVar("_Row")

logger = logging.getLogger("casino_tower.crud")


class UpgradeError(ValueError):
    """ポイント不足 / 上限到達 / 不正項目。route で 400 に対応。"""


def _commit(db: Session, row: _Row) -> _Row:
    """commit→refresh の定型シーケンス（生成/更新後にDB確定値を積み直して返す）。"""
    db.commit()
    db.refresh(row)
    return row


# ── RunRecord ──
def save_run_record(db: Session, snap: dict, *, strategy_version: str | None = None) -> RunRecordRow:
    row = RunRecordRow(
        run_id=snap["run_id"], seed=snap["seed"], bot_type=snap["bot_type"],
        cleared=snap["cleared"], floor_reached=snap["floor_reached"],
        total_turns=snap["total_turns"], final_hp=snap["final_hp"],
        mods_acquired=snap["mods_acquired"], gold_earned=snap["gold_earned"],
        gold_spent=snap["gold_spent"], enemies_defeated=snap["enemies_defeated"],
        death_cause=snap["death_cause"], death_floor=snap["death_floor"],
        permanent_upgrades_state=snap["permanent_upgrades_state"],
        gate_guarantee_stacks=snap.get("gate_guarantee_stacks", 0),
        # OPEN-024: 保存時点の正本データ世代を刻印（全統計クエリの版フィルタ用）
        data_version=get_data().data_version,
        strategy_version=strategy_version,
        sink_use_counts=snap.get("sink_use_counts", {}),
        gate_results=snap.get("gate_results", []),
        action_counts=snap.get("action_counts", {}),
    )
    db.add(row)
    return _commit(db, row)


def save_run_actions(db: Session, run_id: str, turn_history: list) -> RunActionsRow:
    """全ラン共通の操作履歴を終局時に一括保存（improvement_ideas アイディア1 の基盤）。"""
    row = RunActionsRow(run_id=run_id, actions_json=turn_history)
    db.add(row)
    return _commit(db, row)


def list_run_records(db: Session, limit: int = 50) -> list[RunRecordRow]:
    return list(db.execute(
        select(RunRecordRow).order_by(desc(RunRecordRow.id)).limit(limit)
    ).scalars())


def run_record_exists(db: Session, run_id: str) -> bool:
    """指定 run_id の RunRecord が既に確定済みか（復元経路での二重 finalize 防止・OPEN-007）。"""
    return db.execute(
        select(RunRecordRow.id).where(RunRecordRow.run_id == run_id).limit(1)
    ).first() is not None


# ── ActiveSession（進行中ランの再現用・アクションログ再生方式・OPEN-007）──
def create_active_session(db: Session, session_id: str, seed: int, bot_type: str,
                           upgrades: dict, run_id: str) -> ActiveSessionRow:
    row = ActiveSessionRow(
        session_id=session_id, seed=seed, bot_type=bot_type,
        upgrades_json=upgrades, actions_json=[], run_id=run_id,
    )
    db.add(row)
    return _commit(db, row)


def record_action(db: Session, session_id: str, action: dict) -> ActiveSessionRow | None:
    """actions_json に1件追記する。JSON列の変更検知のため必ず再代入する
    （list.append の in-place 変更は SQLAlchemy に検知されない）。
    last_seen_at はモデルの onupdate=func.now() に任せる（このUPDATEで自動更新される）。"""
    row = db.get(ActiveSessionRow, session_id)
    if row is None:
        # 通常到達しない: get_engine_or_404 が行の存在をリクエスト冒頭で確認して404にするため。
        # ここに来た場合はエンジンだけ進んでログが残らない乖離（再生不能化）なので必ず痕跡を残す。
        logger.warning("record_action: active_sessions row missing for %s; "
                       "action %r NOT recorded (live/replay divergence risk)",
                       session_id, action.get("type"))
        return None
    row.actions_json = [*row.actions_json, action]
    return _commit(db, row)


def load_active_session(db: Session, session_id: str) -> ActiveSessionRow | None:
    return db.get(ActiveSessionRow, session_id)


def _naive_utc_now() -> datetime:
    """SQLite の func.now()（CURRENT_TIMESTAMP=UTC・naive文字列）と比較可能な形式で現在時刻を返す。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def delete_stale_active_sessions(db: Session, max_age_hours: int = 24 * 7) -> int:
    """TTL超過分の掃除。終局後の行もここでいずれ消える
    （RunRecordRow/RunActionsRowが正の記録として既に確定しているため実害なし）。"""
    cutoff = _naive_utc_now() - timedelta(hours=max_age_hours)
    result = db.execute(delete(ActiveSessionRow).where(ActiveSessionRow.last_seen_at < cutoff))
    db.commit()
    return result.rowcount or 0


# ── Postmortem（検死レポート＋リプレイ）──
def save_postmortem(db: Session, run_id: str, turn_history: list, fatal_turn_index: int,
                     counterfactual: dict) -> PostmortemRow:
    row = PostmortemRow(
        run_id=run_id, turn_history_json=turn_history,
        fatal_turn_index=fatal_turn_index, counterfactual_json=counterfactual,
    )
    db.add(row)
    return _commit(db, row)


def get_postmortem(db: Session, run_id: str) -> PostmortemRow | None:
    return db.execute(
        select(PostmortemRow).where(PostmortemRow.run_id == run_id).order_by(desc(PostmortemRow.id))
    ).scalars().first()


# ── Profile（恒久強化）──
def get_or_create_profile(db: Session) -> ProfileRow:
    p = db.get(ProfileRow, 1)
    if p is None:
        p = ProfileRow(id=1, points=0, max_hp=0, attack=0, init_gold=0, gold_drop=0, sink_cost=0)
        db.add(p)
        p = _commit(db, p)
    return p


def profile_levels(p: ProfileRow) -> dict[str, int]:
    return {k: getattr(p, k) for k in UPGRADE_ITEMS}


def upgrade_maxes() -> dict[str, int]:
    items = get_data().config["permanent_upgrades"]["items"]
    return {k: items[k]["max_level"] for k in UPGRADE_ITEMS}


def award_points(db: Session, n: int = 1) -> ProfileRow:
    p = get_or_create_profile(db)
    p.points += n
    return _commit(db, p)


def increment_observation(db: Session, enemy_id: str, behavior: str, data_version: str) -> ObservationRow:
    """(enemy_id, behavior, data_version) の観測カウントを get-or-create して +1。"""
    row = db.execute(
        select(ObservationRow).where(
            ObservationRow.enemy_id == enemy_id,
            ObservationRow.behavior == behavior,
            ObservationRow.data_version == data_version,
        )
    ).scalar_one_or_none()
    if row is None:
        row = ObservationRow(enemy_id=enemy_id, behavior=behavior, data_version=data_version, count=0)
        db.add(row)
    row.count += 1
    return _commit(db, row)


def get_dossier(db: Session, data_version: str) -> list[ObservationRow]:
    """指定 data_version の観測行を全件返す（敵ごとの集約はAPI層で行う）。"""
    return list(db.execute(
        select(ObservationRow).where(ObservationRow.data_version == data_version)
    ).scalars())


def allocate_upgrade(db: Session, item: str) -> ProfileRow:
    if item not in UPGRADE_ITEMS:
        raise UpgradeError(f"unknown upgrade item: {item}")
    p = get_or_create_profile(db)
    max_lv = upgrade_maxes()[item]
    if p.points <= 0:
        raise UpgradeError("no upgrade points available")
    if getattr(p, item) >= max_lv:
        raise UpgradeError(f"{item} already at max level {max_lv}")
    setattr(p, item, getattr(p, item) + 1)
    p.points -= 1
    return _commit(db, p)
