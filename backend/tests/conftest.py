"""共有 fixture。pytest は backend/ を rootdir とし、tests/ パッケージの
親（backend/）を sys.path に入れるため `import app...` が解決する。
"""
import pytest

from app.data.loader import GameData


@pytest.fixture(scope="session")
def data() -> GameData:
    return GameData.load()
