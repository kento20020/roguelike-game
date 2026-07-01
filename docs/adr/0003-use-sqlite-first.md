# 0003. DB は SQLite 先行・SQLAlchemy 経由とする

## Status

Accepted

## Context

- ローカル開発を設定ゼロで始めたい一方、将来的な PostgreSQL 移行の余地を残したい（§22.2 技術選定一覧）。
- DB 切り替えのコストを最小化するため、DB アクセス方法を統一する必要がある（§22.3 設計原則）。

## Decision

- DB は **SQLite を先行採用**し、将来の移行先を **PostgreSQL** とする（§22.2）。
- DB 操作は**すべて SQLAlchemy 経由**とし、生 SQL を書かない（§22.3）。

## Consequences

- 設定ゼロでローカル開発を始められる（§22.2 選定理由）。
- ORM を挟むことで DB 切り替え時のコード変更を最小化できる（§22.2/§22.3）。
- ただし PostgreSQL への移行は「1 行で済む」という表現は**楽観**であり撤回済み。型・並行性差（JSON 列 / `server_default` / autoincrement など）の検証が別途必要になる（§22.3）。
