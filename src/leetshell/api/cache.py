import json
import time
from pathlib import Path

from leetshell.constants import CACHE_DIR


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def get_cached(key: str, ttl: float) -> dict | None:
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        age = time.time() - path.stat().st_mtime
        if age > ttl:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def set_cached(key: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(key)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def invalidate(key: str) -> None:
    path = _cache_path(key)
    if path.exists():
        path.unlink()
