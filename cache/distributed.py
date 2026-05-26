"""Distributed cache with Redis for scalability."""

from typing import Any, Optional
import json
import hashlib


class DistributedCache:
    """Redis-based distributed cache for scan results and state."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """
        Initialize distributed cache.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self._client = None

    def _get_client(self):
        """Get or create Redis client."""
        if self._client is None:
            try:
                import redis
                self._client = redis.from_url(self.redis_url)
            except ImportError:
                raise ImportError("redis package required for distributed cache")

        return self._client

    def cache_scan_result(
        self,
        file_path: str,
        content_hash: str,
        scan_result: dict,
        ttl: int = 3600
    ):
        """
        Cache scan result for a file.

        Args:
            file_path: File path
            content_hash: Hash of file content
            scan_result: Scan result to cache
            ttl: Time to live in seconds
        """
        client = self._get_client()

        cache_key = self._make_cache_key(file_path, content_hash)
        client.setex(
            cache_key,
            ttl,
            json.dumps(scan_result)
        )

    def get_cached_scan(
        self,
        file_path: str,
        content_hash: str
    ) -> Optional[dict]:
        """
        Get cached scan result.

        Args:
            file_path: File path
            content_hash: Hash of file content

        Returns:
            Cached scan result or None
        """
        client = self._get_client()

        cache_key = self._make_cache_key(file_path, content_hash)
        cached = client.get(cache_key)

        if cached:
            return json.loads(cached)

        return None

    def _make_cache_key(self, file_path: str, content_hash: str) -> str:
        """Generate cache key."""
        return f"kiwi:scan:{file_path}:{content_hash}"

    def acquire_lock(
        self,
        resource: str,
        timeout: int = 30
    ) -> bool:
        """
        Acquire distributed lock.

        Args:
            resource: Resource to lock
            timeout: Lock timeout in seconds

        Returns:
            True if lock acquired
        """
        client = self._get_client()

        lock_key = f"kiwi:lock:{resource}"
        return client.set(lock_key, "1", nx=True, ex=timeout)

    def release_lock(self, resource: str):
        """Release distributed lock."""
        client = self._get_client()

        lock_key = f"kiwi:lock:{resource}"
        client.delete(lock_key)

    def publish_event(self, channel: str, message: dict):
        """
        Publish event to Redis pub/sub.

        Args:
            channel: Channel name
            message: Message dict
        """
        client = self._get_client()
        client.publish(channel, json.dumps(message))

    def subscribe_events(self, channel: str):
        """
        Subscribe to events.

        Args:
            channel: Channel name

        Yields:
            Event messages
        """
        client = self._get_client()
        pubsub = client.pubsub()
        pubsub.subscribe(channel)

        for message in pubsub.listen():
            if message['type'] == 'message':
                yield json.loads(message['data'])