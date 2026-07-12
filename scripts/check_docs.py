#!/usr/bin/env python3
"""docs 整合の最小チェック（doc-CI）。

1. docs/schemas/*.json が有効な JSON としてパースできる
2. docs/**/*.md の相対リンク（[..](path)）がリポジトリ内の実在ファイル/ディレクトリを指す
3. docs/schemas/ のミラー4本が backend/app/data/ と JSON レベルで一致する（drift 検知）
4. docs/api_contract.md の契約表が backend/app/api/routes.py の実装と一致する（drift 検知）
5. changelog.md 先頭エントリの版 == index（game_design_document.md）冒頭バナーの版（版分裂の検知）
6. index 構成表の OPEN 範囲上限 == operations.md の最大 OPEN-nnn
7. docs 内の OPEN-nnn 参照が operations.md §21.2 の表に実在する（宙吊り参照の検知）
8. 版の正本2箇所以外に現行版を直書きしない（architecture.md §0.1 の版管理ルール）

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

# 5) 版整合: changelog 先頭エントリ ⟷ index 冒頭バナー（版の正本は changelog・architecture.md §0.1）
CHANGELOG = DOCS / "changelog.md"
INDEX = DOCS / "game_design_document.md"
OPERATIONS = DOCS / "operations.md"

changelog_text = CHANGELOG.read_text(encoding="utf-8")
index_text = INDEX.read_text(encoding="utf-8")
operations_text = OPERATIONS.read_text(encoding="utf-8")

m_latest = re.search(r"^- \*\*v(\d+\.\d+)\*\*", changelog_text, re.MULTILINE)
m_banner = re.search(r"^> \*\*v(\d+\.\d+)\*\*", index_text, re.MULTILINE)
# fail-loud: 抽出0件は形式（エントリ/バナーの書式）が崩れたサイン
if not m_latest:
    errors.append("[VERSION] docs/changelog.md の先頭エントリから版を抽出できない（`- **vX.Y**` 形式変更?）")
if not m_banner:
    errors.append("[VERSION] docs/game_design_document.md 冒頭バナーから版を抽出できない（`> **vX.Y**` 形式変更?）")
if m_latest and m_banner and m_latest.group(1) != m_banner.group(1):
    errors.append(
        f"[VERSION] index 冒頭バナー v{m_banner.group(1)} ≠ changelog 先頭エントリ v{m_latest.group(1)}"
        "（正本は changelog。同一コミットで両方更新する＝architecture.md §0.1）"
    )

# 6) OPEN 範囲: index 構成表の上限 ⟷ operations.md の最大 OPEN-nnn
open_mentions = {int(n) for n in re.findall(r"OPEN-(\d{3})", operations_text)}
m_range = re.search(r"OPEN-001[〜～](\d{3})", index_text)
if not m_range:
    errors.append("[OPEN] index の構成表から OPEN 範囲（OPEN-001〜NNN）を抽出できない（表記変更?）")
elif open_mentions and int(m_range.group(1)) != max(open_mentions):
    errors.append(
        f"[OPEN] index の OPEN 範囲上限 OPEN-{m_range.group(1)} ≠ operations.md の最大 OPEN-{max(open_mentions):03d}"
    )

# 7) OPEN 参照整合: operations.md §21.2 の表に無い OPEN-nnn を docs が参照していない
#    （OPEN は解消後も行を表に残す慣行のため、正当な参照は必ず表に存在する）
defined_open = {int(n) for n in re.findall(r"^\| OPEN-(\d{3}) \|", operations_text, re.MULTILINE)}
if not defined_open:
    errors.append("[OPEN] operations.md §21.2 の表から OPEN ID を抽出できない（表形式変更?）")
else:
    for md in sorted(DOCS.rglob("*.md")):
        refs = {int(n) for n in re.findall(r"OPEN-(\d{3})", md.read_text(encoding="utf-8"))}
        for n in sorted(refs - defined_open):
            errors.append(f"[OPEN] {md.relative_to(ROOT)} が参照する OPEN-{n:03d} が operations.md §21.2 の表に無い")

# 8) 現行版の直書き禁止: 版を主張してよいのは changelog 先頭エントリと index 冒頭バナーのみ。
#    過去版への来歴注記（「v1.9 で追加」等）は対象外のパターンに限定して誤検知を避ける
NO_INLINE_VERSION = (ROOT / "CLAUDE.md", ROOT / "AGENTS.md", ROOT / "README.md", DOCS / "architecture.md")
INLINE_VERSION = re.compile(r"現行\s*v\d+\.\d+|\|\s*バージョン\s*\|\s*v\d+\.\d+")
for f in NO_INLINE_VERSION:
    if not f.exists():
        errors.append(f"[VERSION] {f.relative_to(ROOT)} が存在しない（直書き検査の対象ファイル変更?）")
        continue
    for m in INLINE_VERSION.finditer(f.read_text(encoding="utf-8")):
        errors.append(
            f"[VERSION] {f.relative_to(ROOT)}: 現行版の直書き『{m.group(0)}』は禁止"
            "（changelog.md 先頭エントリへの参照で示す＝architecture.md §0.1）"
        )

if errors:
    print("docs check FAILED:")
    for e in errors:
        print("  " + e)
    sys.exit(1)

print("docs check OK")
