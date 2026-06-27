# Stats TTL cache (plan-15 Phase 5 query optimization). TEST DATA — NOT REAL.

from modules import stats


def test_cached_returns_producer_value(temp_db):
    calls = {"n": 0}

    def producer():
        calls["n"] += 1
        return {"v": calls["n"]}

    stats.clear_cache()
    a = stats.cached("k", producer, ttl=60)
    b = stats.cached("k", producer, ttl=60)
    assert a == b == {"v": 1}
    assert calls["n"] == 1  # second call served from cache


def test_cache_disabled_with_zero_ttl(temp_db):
    calls = {"n": 0}

    def producer():
        calls["n"] += 1
        return calls["n"]

    stats.clear_cache()
    stats.cached("k2", producer, ttl=0)
    stats.cached("k2", producer, ttl=0)
    assert calls["n"] == 2  # no caching


def test_clear_cache(temp_db):
    stats.cached("k3", lambda: 1, ttl=60)
    stats.clear_cache()
    assert stats.cached("k3", lambda: 2, ttl=60) == 2
