"""DB操作。生SQLは書かない（SQLAlchemy経由）。"""
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.data.loader import get_data
from app.db.models import ProfileRow, RunRecordRow

UPGRADE_ITEMS = ["max_hp", "attack", "init_gold", "gold_drop", "sink_cost"]


class UpgradeError(ValueError):
    """ポイント不足 / 上限到達 / 不正項目。route で 400 に対応。"""


# ── RunRecord ──
def save_run_record(db: Session, snap: dict) -> RunRecordRow:
    row = RunRecordRow(
        run_id=snap["run_id"], seed=snap["seed"], bot_type=snap["bot_type"],
        cleared=snap["cleared"], floor_reached=snap["floor_reached"],
        total_turns=snap["total_turns"], final_hp=snap["final_hp"],
        mods_acquired=snap["mods_acquired"], gold_earned=snap["gold_earned"],
        gold_spent=snap["gold_spent"], enemies_defeated=snap["enemies_defeated"],
        death_cause=snap["death_cause"], death_floor=snap["death_floor"],
        permanent_upgrades_state=snap["permanent_upgrades_state"],
        gate_guarantee_stacks=snap.get("gate_guarantee_stacks", 0),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_run_records(db: Session, limit: int = 50) -> list[RunRecordRow]:
    return list(db.execute(
        select(RunRecordRow).order_by(desc(RunRecordRow.id)).limit(limit)
    ).scalars())


# ── Profile（恒久強化）──
def get_or_create_profile(db: Session) -> ProfileRow:
    p = db.get(ProfileRow, 1)
    if p is None:
        p = ProfileRow(id=1, points=0, max_hp=0, attack=0, init_gold=0, gold_drop=0, sink_cost=0)
        db.add(p)
        db.commit()
        db.refresh(p)
    return p


def profile_levels(p: ProfileRow) -> dict[str, int]:
    return {k: getattr(p, k) for k in UPGRADE_ITEMS}


def upgrade_maxes() -> dict[str, int]:
    items = get_data().config["permanent_upgrades"]["items"]
    return {k: items[k]["max_level"] for k in UPGRADE_ITEMS}


def award_points(db: Session, n: int = 1) -> ProfileRow:
    p = get_or_create_profile(db)
    p.points += n
    db.commit()
    db.refresh(p)
    return p


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
    db.commit()
    db.refresh(p)
    return p
