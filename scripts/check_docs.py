#!/usr/bin/env python3
"""docs 整合の最小チェック（doc-CI）。

1. docs/schemas/*.json が有効な JSON としてパースできる
2. docs/**/*.md の相対リンク（[..](path)）がリポジトリ内の実在ファイル/ディレクトリを指す
3. docs/schemas/ のミラー4本が backend/app/data/ と JSON レベルで一致する（drift 検知）
4. docs/api_contract.md の契約表が backend/app/api/routes.py の実装と一致する（drift 検知）

外部URL・アンカー(#)・mailto はスキップ。失敗があれば非ゼロ終了。
標準ライブラリのみ（追加依存なし）。FastAPI アプリの import はしない
（DB 作成の副作用と fastapi/sqlalchemy 依存を CI に持ち込まないため、AST 静的解析で抽出する）。
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
LINK = re.compile(r"\]\(([^)]+)\)")

# 3) の対象: backend/app/data の正本を docs/schemas にミラーしているファイルのみ。
#    *_example.json / mod_interactions.json は doc 専用のため対象外。
MIRRORED = ("config.json", "enemies.json", "floors.json", "mods.json")
DATA_DIR = ROOT / "backend" / "app" / "data"

# 4) の前提: ルーターは routes.py 単一ファイル・prefix 1個。
#    複数ファイルに分割したら backend/app/api/*.py を glob して集約する。
ROUTES_PY = ROOT / "backend" / "app" / "api" / "routes.py"
API_DOC = DOCS / "api_contract.md"
HTTP_METHODS = {"get", "post", "put", "delete", "patch"}
DOC_ROW = re.compile(r"^\|\s*(GET|POST|PUT|DELETE|PATCH)\s*\|\s*`([^`]+)`", re.MULTILINE)

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

# 3) schemas ミラー ⟷ backend/app/data の一致
#    バイト比較ではなく JSON レベルで比較する（改行・空白差での誤検知を避ける）
for name in MIRRORED:
    try:
        src = json.loads((DATA_DIR / name).read_text(encoding="utf-8"))
        mirror = json.loads((DOCS / "schemas" / name).read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        errors.append(f"[MIRROR] {name}: 読み込み/パースに失敗: {e}")
        continue
    if src != mirror:
        errors.append(
            f"[MIRROR] docs/schemas/{name} が backend/app/data/{name} と不一致"
            "（正本は backend 側。docs/schemas を更新すること）"
        )


# 4) api_contract.md の契約表 ⟷ routes.py の実装
def routes_from_code() -> set[tuple[str, str]]:
    tree = ast.parse(ROUTES_PY.read_text(encoding="utf-8"))
    prefix = ""
    found: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "APIRouter":
            for kw in node.keywords:
                if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                    prefix = kw.value.value
        elif (
            isinstance(func, ast.Attribute)
            and func.attr in HTTP_METHODS
            and isinstance(func.value, ast.Name)
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            found.add((func.attr.upper(), node.args[0].value))
    return {(method, prefix + path) for method, path in found}


def routes_from_doc() -> set[tuple[str, str]]:
    return {(m.group(1), m.group(2)) for m in DOC_ROW.finditer(API_DOC.read_text(encoding="utf-8"))}


code_routes = routes_from_code()
doc_routes = routes_from_doc()
# fail-loud: 抽出0件は前提（デコレータ/表の形式）が崩れたサイン。静かに素通りさせない
if not code_routes:
    errors.append(f"[API] {ROUTES_PY.relative_to(ROOT)} からルートを抽出できない（構造変更?）")
if not doc_routes:
    errors.append(f"[API] {API_DOC.relative_to(ROOT)} の契約表からルートを抽出できない（表形式変更?）")
if code_routes and doc_routes:
    for method, path in sorted(code_routes - doc_routes):
        errors.append(f"[API] 実装にあるが api_contract.md の契約表に無い: {method} {path}")
    for method, path in sorted(doc_routes - code_routes):
        errors.append(f"[API] 契約表にあるが実装に無い: {method} {path}")

if errors:
    print("docs check FAILED:")
    for e in errors:
        print("  " + e)
    sys.exit(1)

print("docs check OK")
