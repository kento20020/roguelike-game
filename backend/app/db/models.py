"""SQLAlchemy ORM。RunRecord（統計・永続）と Profile（恒久強化・単一行）。

combat_log は永続化しない（表示専用・使い捨て）。RunRecord のみ統計用に残す。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RunRecordRow(Base):
    __tablename__ = "run_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    seed: Mapped[int] = mapped_column(Integer)
    bot_type: Mapped[str] = mapped_column(String, default="human")
    cleared: Mapped[bool] = mapped_column(Boolean)
    floor_reached: Mapped[int] = mapped_column(Integer)
    total_turns: Mapped[int] = mapped_column(Integer)
    final_hp: Mapped[int] = mapped_column(Integer)
    mods_acquired: Mapped[list] = mapped_column(JSON)
    gold_earned: Mapped[int] = mapped_column(Integer)
    gold_spent: Mapped[dict] = mapped_column(JSON)
    enemies_defeated: Mapped[list] = mapped_column(JSON)
    death_cause: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    death_floor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    permanent_upgrades_state: Mapped[dict] = mapped_column(JSON)
    gate_guarantee_stacks: Mapped[int] = mapped_column(Integer, default=0)
    # ── OPEN-024/025: 統計の世代札とテレメトリ（旧行は NULL のまま＝マイグレーション 0002 で追加）──
    data_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    strategy_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # bot方策版。human は NULL
    sink_use_counts: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    gate_results: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    action_counts: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id, "run_id": self.run_id, "seed": self.seed, "bot_type": self.bot_type,
            "cleared": self.cleared, "floor_reached": self.floor_reached,
            "total_turns": self.total_turns, "final_hp": self.final_hp,
            "mods_acquired": self.mods_acquired, "gold_earned": self.gold_earned,
            "gold_spent": self.gold_spent, "enemies_defeated": self.enemies_defeated,
            "death_cause": self.death_cause, "death_floor": self.death_floor,
            "permanent_upgrades_state": self.permanent_upgrades_state,
            "gate_guarantee_stacks": self.gate_guarantee_stacks,
            "data_version": self.data_version or "",
            "strategy_version": self.strategy_version,
            "sink_use_counts": self.sink_use_counts or {},
            "gate_results": self.gate_results or [],
            "action_counts": self.action_counts or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PostmortemRow(Base):
    """検死レポート（致命ターンの反実仮想＋ターンリプレイ）。run_id 単位で1行（RunRecordRowと対）。"""
    __tablename__ = "postmortems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    turn_history_json: Mapped[list] = mapped_column(JSON)
    fatal_turn_index: Mapped[int] = mapped_column(Integer)
    counterfactual_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id, "run_id": self.run_id,
            "turn_history": self.turn_history_json,
            "fatal_turn_index": self.fatal_turn_index,
            "counterfactual": self.counterfactual_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ObservationRow(Base):
    """ディーラー調書: プレイヤーが観測した (enemy_id, behavior) の頻度カウント。

    真のweight/確率は一切保持しない（観測回数のみ・開示不変条件はAPI層で担保）。
    data_version はバランス改定などでカウントを世代分けするための札。
    """
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("enemy_id", "behavior", "data_version", name="uq_observation_enemy_behavior_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enemy_id: Mapped[str] = mapped_column(String, index=True)
    behavior: Mapped[str] = mapped_column(String)
    data_version: Mapped[str] = mapped_column(String)
    count: Mapped[int] = mapped_column(Integer, default=0)


class RunActionsRow(Base):
    """全ラン共通の操作履歴（improvement_ideas アイディア1 の run_actions 基盤）。

    終局時に turn_history を一括保存する。PostmortemRow は戦闘死の検死専用で別物。
    """
    __tablename__ = "run_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    actions_json: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ActiveSessionRow(Base):
    """進行中ラン（未終局）の再現に必要な最小情報。GameEngine の全状態はスナップショット
    せず、「seed + 初期upgrades + 適用したアクション列」だけを保持する（アクションログ再生方式）。

    キャッシュミス時（サーバ再起動・LRU追い出し後の初回アクセス）に
    app.engine.replay.rebuild_engine() で GameEngine を再構築するための入力。
    終局（cleared/dead）後も TTL 掃除まではあえて残す（RunRecordRow/RunActionsRow が
    正の記録として既に確定しているため実害は無く、削除すると「クリア直後の再起動で
    GET /run/{id} が404になる」退行を生むため）。

    run_id はライブ生成時（new_run）に一度だけ uuid4 で決まる一意IDで、以後
    rebuild_engine() が何度呼ばれても同じ値を使い続ける必要がある（re-generateすると
    再構築のたびにRunRecord/postmortemの参照キーが変わり、crud.run_record_exists による
    二重finalize防止やpostmortem検索が壊れるため）。ここに保存し rebuild_engine() で
    上書き適用する。旧行（このカラム追加前）は None のままで良い（TTL掃除で自然消滅）。
    """
    __tablename__ = "active_sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    seed: Mapped[int] = mapped_column(Integer)
    bot_type: Mapped[str] = mapped_column(String, default="human")
    upgrades_json: Mapped[dict] = mapped_column(JSON)
    actions_json: Mapped[list] = mapped_column(JSON, default=list)
    run_id: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ProfileRow(Base):
    """単一プレイヤーの恒久強化プロファイル（id=1 固定）。"""
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    points: Mapped[int] = mapped_column(Integer, default=0)
    max_hp: Mapped[int] = mapped_column(Integer, default=0)
    attack: Mapped[int] = mapped_column(Integer, default=0)
    init_gold: Mapped[int] = mapped_column(Integer, default=0)
    gold_drop: Mapped[int] = mapped_column(Integer, default=0)
    sink_cost: Mapped[int] = mapped_column(Integer, default=0)
