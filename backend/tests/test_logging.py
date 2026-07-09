"""構造化ログ + request_id 伝播（app.logging_setup / main.request_id_middleware）のテスト。

test_api.py の in-memory SQLite + TestClient の作法に合わせる。
"""
import json
import logging

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from app.db.session import Base, get_db
from app.logging_setup import (
    JsonFormatter,
    RequestIdFilter,
    request_id_var,
    setup_logging,
)
from app.session_store import store


def _make_record(msg: str = "hello", *, exc_info=None) -> logging.LogRecord:
    return logging.LogRecord(
        name="casino_tower", level=logging.INFO, pathname=__file__, lineno=1,
        msg=msg, args=None, exc_info=exc_info,
    )


def test_json_formatter_emits_parseable_object_with_required_keys():
    rec = _make_record("json line")
    RequestIdFilter().filter(rec)  # record.request_id を埋める（Formatter が参照する）
    out = JsonFormatter().format(rec)

    parsed = json.loads(out)  # 1 行 JSON としてパースできること
    for key in ("ts", "level", "logger", "msg", "request_id"):
        assert key in parsed
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "casino_tower"
    assert parsed["msg"] == "json line"


def test_json_formatter_includes_exc_on_exception():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        rec = _make_record("failed", exc_info=sys.exc_info())
    RequestIdFilter().filter(rec)
    parsed = json.loads(JsonFormatter().format(rec))
    assert "exc" in parsed
    assert "ValueError: boom" in parsed["exc"]


def test_request_id_filter_reads_contextvar():
    token = request_id_var.set("abc123def456")
    try:
        rec = _make_record()
        assert RequestIdFilter().filter(rec) is True  # 常に True（レコードを落とさない）
        assert rec.request_id == "abc123def456"
    finally:
        request_id_var.reset(token)


def test_request_id_filter_defaults_to_none_outside_request():
    # リクエスト文脈の外（set していない）では None を注入する。
    rec = _make_record()
    RequestIdFilter().filter(rec)
    assert rec.request_id is None


def test_request_id_in_log_matches_response_header(caplog):
    # TestClient 経由で 404 を起こし、レスポンスヘッダの X-Request-ID と
    # ミドルウェアが出した WARNING ログの request_id が一致することを確認する。
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=eng)
    TestSession = sessionmaker(bind=eng, autoflush=False, autocommit=False)

    def _override():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = _override
    store.clear()
    client = TestClient(main.app)
    # caplog のハンドラにも Filter を装着し、キャプチャ時点の request_id を注入させる
    # （setup_logging が張るのは root のストリームハンドラで、caplog のハンドラは別物のため）。
    caplog.handler.addFilter(RequestIdFilter())
    try:
        with caplog.at_level(logging.WARNING, logger="casino_tower"):
            r = client.get("/api/run/does-not-exist")
        assert r.status_code == 404
        header_id = r.headers["X-Request-ID"]

        recs = [rec for rec in caplog.records if rec.name == "casino_tower"]
        assert recs, "404 に対する WARNING ログが出ていること"
        assert getattr(recs[-1], "request_id", None) == header_id
    finally:
        main.app.dependency_overrides.clear()
        store.clear()


def test_setup_logging_text_format_is_plaintext(monkeypatch):
    # LOG_FORMAT=text を明示指定したとき、JSON ではなく従来のプレーンテキストで出力される。
    monkeypatch.setenv("LOG_FORMAT", "text")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    try:
        setup_logging()
        handler = root.handlers[0]
        assert not isinstance(handler.formatter, JsonFormatter)

        rec = _make_record("plain text line")
        for f in handler.filters:
            f.filter(rec)
        out = handler.formatter.format(rec)
        with pytest.raises(json.JSONDecodeError):
            json.loads(out)  # テキスト形式は JSON としてパースできない
        assert "plain text line" in out
        assert "casino_tower" in out
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)


def test_setup_logging_json_format_switches_formatter(monkeypatch):
    monkeypatch.setenv("LOG_FORMAT", "json")
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    try:
        setup_logging()
        assert isinstance(root.handlers[0].formatter, JsonFormatter)
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)
