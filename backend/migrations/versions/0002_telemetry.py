"""telemetry — OPEN-024/025: RunRecord へ世代札・テレメトリ列を追加し run_actions を新設

- data_version: 4つの正本JSONの内容ハッシュ（統計クエリの版フィルタ用・OPEN-024）
- strategy_version: bot 方策の版（human は NULL・OPEN-024）
- sink_use_counts / gate_results / action_counts: ROI 逆算用テレメトリ（OPEN-025）
- run_actions: 全ラン共通の操作履歴（improvement_ideas アイディア1 の共通基盤）
旧行は NULL のまま（API 層が既定値へ丸める）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_telemetry"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # main.py の Base.metadata.create_all（開発/テスト用フォールバック）が先に新テーブルだけ
    # 作っている場合がある（create_all は列追加をしない）ため、存在チェックで冪等にする。
    bind = op.get_bind()
    insp = sa.inspect(bind)

    existing = {c["name"] for c in insp.get_columns("run_records")}
    new_cols = [
        sa.Column("data_version", sa.String(), nullable=True),
        sa.Column("strategy_version", sa.String(), nullable=True),
        sa.Column("sink_use_counts", sa.JSON(), nullable=True),
        sa.Column("gate_results", sa.JSON(), nullable=True),
        sa.Column("action_counts", sa.JSON(), nullable=True),
    ]
    to_add = [c for c in new_cols if c.name not in existing]
    if to_add:
        with op.batch_alter_table("run_records") as b:
            for c in to_add:
                b.add_column(c)

    if "run_actions" not in insp.get_table_names():
        op.create_table(
            "run_actions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("run_id", sa.String(), nullable=False),
            sa.Column("actions_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        )
        op.create_index("ix_run_actions_run_id", "run_actions", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_run_actions_run_id", table_name="run_actions")
    op.drop_table("run_actions")
    with op.batch_alter_table("run_records") as b:
        b.drop_column("action_counts")
        b.drop_column("gate_results")
        b.drop_column("sink_use_counts")
        b.drop_column("strategy_version")
        b.drop_column("data_version")
