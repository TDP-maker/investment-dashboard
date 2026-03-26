"""
File-based data caching to reduce API calls and improve load times.
"""

import os
import json
import pickle
import hashlib
from datetime import datetime, timedelta
from config import CACHE_DIR, CACHE_TTL_HOURS


def _ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    os.makedirs(CACHE_DIR, exist_ok=True)


def _cache_path(key: str) -> str:
    """Get the file path for a cache key."""
    safe_key = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{safe_key}.json")


def _is_cache_valid(path: str) -> bool:
    """Check if a cache file exists and is still within TTL."""
    if not os.path.exists(path):
        return False
    modified = datetime.fromtimestamp(os.path.getmtime(path))
    return datetime.now() - modified < timedelta(hours=CACHE_TTL_HOURS)


def cached_fetch(key: str, fetch_fn, ttl_hours: int = None):
    """
    Return cached data if available and fresh, otherwise call fetch_fn and cache the result.

    Args:
        key: Cache key identifier
        fetch_fn: Callable that returns data to cache
        ttl_hours: Override default TTL for this specific fetch
    """
    _ensure_cache_dir()
    path = _cache_path(key)

    # Check for valid cache
    if _is_cache_valid(path):
        try:
            with open(path, "r") as f:
                cached = json.load(f)
            if ttl_hours:
                modified = datetime.fromtimestamp(os.path.getmtime(path))
                if datetime.now() - modified > timedelta(hours=ttl_hours):
                    raise ValueError("Custom TTL expired")
            return cached["data"]
        except (json.JSONDecodeError, KeyError, ValueError):
            pass

    # Fetch fresh data
    data = fetch_fn()

    # Cache it
    try:
        with open(path, "w") as f:
            json.dump({"data": data, "cached_at": datetime.now().isoformat()}, f, default=str)
    except (TypeError, OSError) as e:
        print(f"Cache write warning for '{key}': {e}")

    return data


def clear_cache(key: str = None):
    """Clear a specific cache entry or all cached data."""
    if key:
        path = _cache_path(key)
        if os.path.exists(path):
            os.remove(path)
    else:
        _ensure_cache_dir()
        for f in os.listdir(CACHE_DIR):
            if f.endswith(".json"):
                os.remove(os.path.join(CACHE_DIR, f))
