"""ログ基盤（構造化ログ + request_id 伝播）。

`X-Request-ID` はレスポンスヘッダには付くが、`contextvars` で全ログレコードへ自動注入
しないと「ヘッダの ID とログ行を突き合わせられない」問題が残る。ここでは:

- `request_id_var`（ContextVar）: main.py の request_id_middleware が set/reset する。
- `RequestIdFilter`: 全レコードへ `record.request_id` を注入する（text/json 両対応）。
- `JsonFormatter`: 標準ライブラリのみで 1 行 JSON を組む（外部依存を増やさない方針）。
- `setup_logging`: `LOG_FORMAT`（既定 text）/ `LOG_LEVEL`（既定 INFO）で root を構成する。

外部ライブラリ（python-json-logger 等）は使わない。ログ呼び出しが数件しかない現状に
外部依存は過剰なため（.env.example / docs/runbook.md 参照）。
"""
from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from datetime import UTC, datetime

# request_id_middleware が採番した ID を保持する。既定 None（リクエスト文脈外のログ）。
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# text 形式の書式（従来 basicConfig と同一）。ローカル開発のコンソール可読性を保つ。
_TEXT_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


class RequestIdFilter(logging.Filter):
    """全ログレコードへ現在の request_id を注入する Filter。

    Formatter は record 属性を参照するだけで済むよう、text/json どちらの形式でも
    このフィルタを装着する。フィルタとしては常に True を返し、レコードを落とさない。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """標準ライブラリのみの 1 行 JSON フォーマッタ。

    ログ集約基盤（`LOG_FORMAT=json`）で機械可読にするための最小実装。
    非 ASCII（日本語メッセージ）をエスケープしないよう ensure_ascii=False。
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    """root logger を LOG_FORMAT / LOG_LEVEL に従って構成する（basicConfig の代替）。

    basicConfig は既存 handler がある場合に何もしないため、複数回呼んでも冪等になるよう
    root の handler を明示的に張り替える。`RequestIdFilter` はどちらの形式でも装着する。
    """
    log_format = os.environ.get("LOG_FORMAT", "text").strip().lower()
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    formatter: logging.Formatter = (
        JsonFormatter() if log_format == "json" else logging.Formatter(_TEXT_FORMAT)
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.setLevel(log_level)
    # 既存 handler を外してから張り替える（この関数を複数回呼んでも二重出力しない）。
    for existing in root.handlers[:]:
        root.removeHandler(existing)
    root.addHandler(handler)
