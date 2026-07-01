#!/usr/bin/env python3
"""docs 整合の最小チェック（doc-CI）。

1. docs/schemas/*.json が有効な JSON としてパースできる
2. docs/**/*.md の相対リンク（[..](path)）がリポジトリ内の実在ファイル/ディレクトリを指す

外部URL・アンカー(#)・mailto はスキップ。失敗があれば非ゼロ終了。
標準ライブラリのみ（追加依存なし）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
LINK = re.compile(r"\]\(([^)]+)\)")

errors: list[str] = []

# 1) schemas の JSON 妥当性
for jf in sorted(DOCS.glob("schemas/*.json")):
    try:
        json.loads(jf.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        errors.append(f"[JSON] {jf.relative_to(ROOT)}: {e}")

# 2) 相対 markdown リンク切れ
for md in sorted(DOCS.rglob("*.md")):
    text = md.read_text(encoding="utf-8")
    for m in LINK.finditer(text):
        target = m.group(1).strip()
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        path_part = target.split("#", 1)[0].strip()
        if not path_part:
            continue
        if not (md.parent / path_part).exists():
            errors.append(f"[LINK] {md.relative_to(ROOT)} -> {target}（見つからない）")

if errors:
    print("docs check FAILED:")
    for e in errors:
        print("  " + e)
    sys.exit(1)

print("docs check OK")
