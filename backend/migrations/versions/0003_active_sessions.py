"""active_sessions - OPEN-007: 進行中ランの再現用テーブル(アクションログ再生方式)

GameEngineの全状態はスナップショットせず、seed + 初期upgrades + 適用アクション列だけを
保持する。main.pyのcreate_all(開発/テスト用フォールバック)が先にテーブルを作っている
場合があるため、0002と同様に存在チェックしてから作成する。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_active_sessions"
down_revision = "0002_telemetry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if "active_sessions" not in insp.get_table_names():
        op.create_table(
            "active_sessions",
            sa.Column("session_id", sa.String(), primary_key=True),
            sa.Column("seed", sa.Integer(), nullable=False),
            sa.Column("bot_type", sa.String(), nullable=False),
            sa.Column("upgrades_json", sa.JSON(), nullable=False),
            sa.Column("actions_json", sa.JSON(), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("active_sessions")
