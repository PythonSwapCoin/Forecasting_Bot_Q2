import sys
from pathlib import Path


def pytest_configure():
    root = Path(__file__).resolve().parents[1]
    bot_path = root / "Bot"
    if str(bot_path) not in sys.path:
        sys.path.insert(0, str(bot_path))
