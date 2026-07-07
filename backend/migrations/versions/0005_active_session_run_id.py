"""active_session_run_id — active_sessions に run_id を追加し、再生後も安定させる

GameEngine.new_run() は呼ぶたびに新しいrun_id（uuid4）を発行する（0004でseed非依存化）。
そのため、キャッシュミス時に app.engine.replay.rebuild_engine() が new_run() を再実行すると、
再構築のたびに異なるrun_idが生成されてしまい、ライブ生成時に確定したRunRecord/postmortemの
参照キーとズレる。ライブ生成時のrun_idを active_sessions.run_id に保存しておき、
rebuild_engine() が同じ値へ上書きすることで、同一セッションは常に同じrun_idを指すようにする。

旧行（このカラム追加前に作られたactive_sessions行）は run_id=NULL のままで良い
（rebuild_engine()はNULLならnew_run()が発行した値をそのまま使う。実害はTTL掃除で自然解消）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_active_session_run_id"
down_revision = "0004_run_id_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    existing = {c["name"] for c in insp.get_columns("active_sessions")}
    if "run_id" not in existing:
        with op.batch_alter_table("active_sessions") as b:
            b.add_column(sa.Column("run_id", sa.String(), nullable=True))

    existing_indexes = {ix["name"]: ix for ix in insp.get_indexes("active_sessions")}
    if not existing_indexes.get("ix_active_sessions_run_id", {}).get("unique"):
        if "ix_active_sessions_run_id" in existing_indexes:
            op.drop_index("ix_active_sessions_run_id", table_name="active_sessions")
        op.create_index("ix_active_sessions_run_id", "active_sessions", ["run_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_active_sessions_run_id", table_name="active_sessions")
    with op.batch_alter_table("active_sessions") as b:
        b.drop_column("run_id")
