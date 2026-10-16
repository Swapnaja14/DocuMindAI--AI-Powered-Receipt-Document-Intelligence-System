import asyncio
import pytest

from app.services.cache_service import (
    acquire_lock,
    cache_answer,
    get_cached_answer,
    get_user_generation,
    increment_user_generation,
    invalidate_user_cache,
    make_cache_key,
    release_lock,
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


@pytest.mark.asyncio
async def test_cache_entry_expires_after_ttl():
    user_id = "ttl-test-user"
    key = make_cache_key(
        user_id,
        "TTL expiration test",
    )

    await cache_answer(
        key,
        {"answer": "temporary"},
        ttl=1,
    )

    assert await get_cached_answer(key) == {
        "answer": "temporary"
    }

    await asyncio.sleep(1.5)

    assert await get_cached_answer(key) is None


def test_cache_keys_differ_for_different_context():
    key_a = make_cache_key(
        "user-a",
        "What was my highest expense?",
        context={"document_ids": ["invoice-a"]},
    )

    key_b = make_cache_key(
        "user-a",
        "What was my highest expense?",
        context={"document_ids": ["invoice-b"]},
    )

    assert key_a != key_b


def test_cache_keys_same_for_differently_ordered_context():
    key_a = make_cache_key(
        "user-a",
        "What was my highest expense?",
        context={"document_ids": ["invoice-a", "invoice-b"]},
    )

    key_b = make_cache_key(
        "user-a",
        "What was my highest expense?",
        context={"document_ids": ["invoice-b", "invoice-a"]},
    )

    assert key_a == key_b


@pytest.mark.asyncio
async def test_generation_change_invalidates_old_cache_keys():
    user_id = "test-user-gen-change"
    await invalidate_user_cache(user_id)

    gen0 = await get_user_generation(user_id)
    key_gen0 = make_cache_key(user_id, "What is my invoice amount?", generation=gen0)
    answer = {"answer": "Your invoice is $200."}

    success = await cache_answer(
        key_gen0,
        answer,
        ttl=60,
        user_id=user_id,
        expected_generation=gen0,
    )
    assert success is True
    assert await get_cached_answer(key_gen0) == answer

    # Mutation happens: generation is incremented
    new_gen = await increment_user_generation(user_id)
    assert new_gen > gen0

    # New cache key computed with new generation
    key_gen1 = make_cache_key(user_id, "What is my invoice amount?", generation=new_gen)
    assert key_gen0 != key_gen1

    # Looking up the question with current generation results in a cache miss
    cached = await get_cached_answer(key_gen1)
    assert cached is None


@pytest.mark.asyncio
async def test_old_inflight_request_cannot_write_after_invalidation():
    user_id = "test-user-inflight"
    await invalidate_user_cache(user_id)

    # 1. Request begins when user is at generation G
    captured_gen = await get_user_generation(user_id)
    key = make_cache_key(user_id, "What are my total expenses?", generation=captured_gen)

    # 2. While retrieval is in-flight, a document is deleted/uploaded/reindexed -> invalidation happens
    await invalidate_user_cache(user_id)
    current_gen = await get_user_generation(user_id)
    assert current_gen > captured_gen

    # 3. Old in-flight request finishes and attempts to write its stale answer
    stale_answer = {"answer": "Old stale calculation: $100"}
    write_result = await cache_answer(
        key,
        stale_answer,
        ttl=60,
        user_id=user_id,
        expected_generation=captured_gen,
    )

    # 4. Write must be rejected!
    assert write_result is False

    # 5. Stale answer must NOT be cached under the old key or anywhere
    assert await get_cached_answer(key) is None


@pytest.mark.asyncio
async def test_current_generation_can_cache_successful_answer():
    user_id = "test-user-current-gen"
    await invalidate_user_cache(user_id)

    current_gen = await get_user_generation(user_id)
    key = make_cache_key(user_id, "What is my hotel receipt?", generation=current_gen)

    fresh_answer = {"answer": "Hotel stay was $450."}
    write_result = await cache_answer(
        key,
        fresh_answer,
        ttl=60,
        user_id=user_id,
        expected_generation=current_gen,
    )

    # Write must succeed!
    assert write_result is True
    assert await get_cached_answer(key) == fresh_answer


@pytest.mark.asyncio
async def test_lock_acquisition_and_safe_release():
    lock_key = "documindai:rag:lock:test_user:stampede_test"
    token_1 = "token_aaa_111"
    token_2 = "token_bbb_222"

    # Clean up lock key before test
    await release_lock(lock_key, token_1)
    await release_lock(lock_key, token_2)

    # 1. First requester acquires lock
    assert await acquire_lock(lock_key, token_1, ttl=10) is True

    # 2. Second requester fails to acquire (lock held)
    assert await acquire_lock(lock_key, token_2, ttl=10) is False

    # 3. Requester 2 cannot delete Requester 1's lock (compare-and-delete Lua safety)
    assert await release_lock(lock_key, token_2) is False

    # 4. Requester 1 safely releases lock
    assert await release_lock(lock_key, token_1) is True

    # 5. Now Requester 2 can acquire
    assert await acquire_lock(lock_key, token_2, ttl=10) is True
    assert await release_lock(lock_key, token_2) is True
