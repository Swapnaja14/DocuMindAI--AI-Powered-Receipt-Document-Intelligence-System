import pytest

from app.services.cache_service import (
    make_cache_key,
    cache_answer,
    get_cached_answer,
    invalidate_user_cache,
)


@pytest.mark.asyncio
async def test_cache_hit_and_invalidation():
    user_id = "test-user-phase10"

    key = make_cache_key(
        user_id,
        "What was my highest expense?",
    )

    answer = {
        "answer": "Your highest expense was 500.",
    }

    await cache_answer(key, answer, ttl=60)

    cached = await get_cached_answer(key)
    assert cached == answer

    deleted = await invalidate_user_cache(user_id)
    assert deleted >= 1

    cached_after_delete = await get_cached_answer(key)
    assert cached_after_delete is None


def test_cache_keys_are_user_isolated():
    key_a = make_cache_key(
        "user-a",
        "What was my highest expense?",
    )
    key_b = make_cache_key(
        "user-b",
        "What was my highest expense?",
    )

    assert key_a != key_b


def test_normalized_queries_share_a_key():
    key_a = make_cache_key(
        "user-a",
        "What was my highest expense?",
    )
    key_b = make_cache_key(
        "user-a",
        "  WHAT WAS MY HIGHEST EXPENSE?  ",
    )

    assert key_a == key_b
