"""run_id_unique — run_id をseed非依存の一意ID化し、DBでも衝突を拒否する

game_engine.new_run() の run_id 生成を f"run-{seed}" から f"run-{uuid4().hex}" へ変更した
（seedはクライアントが任意指定でき、同一seedの複数ランでrun_idが衝突するとRunRecord/
run_actions/検死レポートの取り違え・crud.run_record_exists によるfinalizeスキップの
サイレント欠落につながるため）。run_records / postmortems / run_actions の run_id 列に
UNIQUE制約を追加し、DBレベルでも衝突を拒否する。

既存データに重複run_idが残っている場合はこの版の適用が失敗する（意図的なフェイルファスト。
重複が実在するなら先に手動で調査・統合すべきため自動マージはしない）。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_run_id_unique"
down_revision = "0003_active_sessions"
branch_labels = None
depends_on = None

_TARGETS = [
    ("run_records", "ix_run_records_run_id"),
    ("postmortems", "ix_postmortems_run_id"),
    ("run_actions", "ix_run_actions_run_id"),
]


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    for table, index_name in _TARGETS:
        if table not in insp.get_table_names():
            continue
        existing = {ix["name"]: ix for ix in insp.get_indexes(table)}
        if existing.get(index_name, {}).get("unique"):
            continue  # 既にunique化済み（create_allフォールバックが先に作った場合含む）
        if index_name in existing:
            op.drop_index(index_name, table_name=table)
        op.create_index(index_name, table, ["run_id"], unique=True)


def downgrade() -> None:
    for table, index_name in _TARGETS:
        op.drop_index(index_name, table_name=table)
        op.create_index(index_name, table, ["run_id"], unique=False)
