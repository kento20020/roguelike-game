"""baseline — Phase4 以前の既存4テーブル（run_records / postmortems / observations / profiles）

既存の game.db に適用する場合はテーブルが既にあるため `alembic stamp 0001_baseline` で
この版を「適用済み」と記録してから `alembic upgrade head` を実行する（runbook.md 参照）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "run_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("bot_type", sa.String(), nullable=False),
        sa.Column("cleared", sa.Boolean(), nullable=False),
        sa.Column("floor_reached", sa.Integer(), nullable=False),
        sa.Column("total_turns", sa.Integer(), nullable=False),
        sa.Column("final_hp", sa.Integer(), nullable=False),
        sa.Column("mods_acquired", sa.JSON(), nullable=False),
        sa.Column("gold_earned", sa.Integer(), nullable=False),
        sa.Column("gold_spent", sa.JSON(), nullable=False),
        sa.Column("enemies_defeated", sa.JSON(), nullable=False),
        sa.Column("death_cause", sa.String(), nullable=True),
        sa.Column("death_floor", sa.Integer(), nullable=True),
        sa.Column("permanent_upgrades_state", sa.JSON(), nullable=False),
        sa.Column("gate_guarantee_stacks", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_run_records_run_id", "run_records", ["run_id"])

    op.create_table(
        "postmortems",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("turn_history_json", sa.JSON(), nullable=False),
        sa.Column("fatal_turn_index", sa.Integer(), nullable=False),
        sa.Column("counterfactual_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_postmortems_run_id", "postmortems", ["run_id"])

    op.create_table(
        "observations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("enemy_id", sa.String(), nullable=False),
        sa.Column("behavior", sa.String(), nullable=False),
        sa.Column("data_version", sa.String(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.UniqueConstraint("enemy_id", "behavior", "data_version",
                            name="uq_observation_enemy_behavior_version"),
    )
    op.create_index("ix_observations_enemy_id", "observations", ["enemy_id"])

    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("max_hp", sa.Integer(), nullable=False),
        sa.Column("attack", sa.Integer(), nullable=False),
        sa.Column("init_gold", sa.Integer(), nullable=False),
        sa.Column("gold_drop", sa.Integer(), nullable=False),
        sa.Column("sink_cost", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("profiles")
    op.drop_index("ix_observations_enemy_id", table_name="observations")
    op.drop_table("observations")
    op.drop_index("ix_postmortems_run_id", table_name="postmortems")
    op.drop_table("postmortems")
    op.drop_index("ix_run_records_run_id", table_name="run_records")
    op.drop_table("run_records")
