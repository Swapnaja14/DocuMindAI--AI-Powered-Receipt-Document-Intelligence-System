import logging
import threading
from typing import Any

logger = logging.getLogger("app.rag_cache_metrics")


class CacheMetrics:
    """Thread-safe collector for RAG Redis cache observability metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.hits: int = 0
        self.misses: int = 0
        self.read_errors: int = 0
        self.write_errors: int = 0
        self.invalidations: int = 0
        self.invalid_entries: int = 0
        self.hit_latencies_ms: list[float] = []
        self.miss_latencies_ms: list[float] = []

    def record_hit(self, latency_ms: float = 0.0) -> None:
        """Record a successful cache hit with latency in milliseconds."""
        with self._lock:
            self.hits += 1
            if latency_ms >= 0:
                self.hit_latencies_ms.append(latency_ms)

        logger.info(
            "rag_cache_hit latency_ms=%.2f",
            latency_ms,
            extra={
                "metric_event": "cache_hit",
                "latency_ms": round(latency_ms, 2),
            },
        )

    def record_miss(self, latency_ms: float = 0.0) -> None:
        """Record an ordinary cache miss with end-to-end generation latency in milliseconds."""
        with self._lock:
            self.misses += 1
            if latency_ms >= 0:
                self.miss_latencies_ms.append(latency_ms)

        logger.info(
            "rag_cache_miss latency_ms=%.2f",
            latency_ms,
            extra={
                "metric_event": "cache_miss",
                "latency_ms": round(latency_ms, 2),
            },
        )

    def record_read_error(self, error: Exception | str) -> None:
        """Record a Redis read error (kept separate from normal misses)."""
        err_msg = str(error)
        with self._lock:
            self.read_errors += 1

        logger.error(
            "rag_cache_read_error: %s",
            err_msg,
            extra={
                "metric_event": "read_error",
                "error": err_msg,
            },
        )

    def record_write_error(self, error: Exception | str) -> None:
        """Record a Redis write error."""
        err_msg = str(error)
        with self._lock:
            self.write_errors += 1

        logger.error(
            "rag_cache_write_error: %s",
            err_msg,
            extra={
                "metric_event": "write_error",
                "error": err_msg,
            },
        )

    def record_invalidation(self, count: int = 1) -> None:
        """Record a cache invalidation event."""
        with self._lock:
            self.invalidations += count

        logger.info(
            "rag_cache_invalidation count=%d",
            count,
            extra={
                "metric_event": "invalidation",
                "count": count,
            },
        )

    def record_invalid_entry(self) -> None:
        """Record a corrupted or schema-invalid cached entry."""
        with self._lock:
            self.invalid_entries += 1

        logger.warning(
            "rag_cache_invalid_entry",
            extra={
                "metric_event": "invalid_entry",
            },
        )

    @property
    def hit_ratio(self) -> float:
        """
        Calculate Hit Ratio = hits / (hits + misses) * 100%.
        Cache errors are kept separate from ordinary misses.
        """
        with self._lock:
            total = self.hits + self.misses
            return (self.hits / total * 100.0) if total > 0 else 0.0

    def get_summary(self) -> dict[str, Any]:
        """Return a structured dictionary snapshot of current metrics."""
        with self._lock:
            avg_hit_lat = (
                sum(self.hit_latencies_ms) / len(self.hit_latencies_ms)
                if self.hit_latencies_ms
                else 0.0
            )
            avg_miss_lat = (
                sum(self.miss_latencies_ms) / len(self.miss_latencies_ms)
                if self.miss_latencies_ms
                else 0.0
            )
            total_lookups = self.hits + self.misses
            hit_ratio_val = (self.hits / total_lookups * 100.0) if total_lookups > 0 else 0.0

            return {
                "hits": self.hits,
                "misses": self.misses,
                "read_errors": self.read_errors,
                "write_errors": self.write_errors,
                "invalidations": self.invalidations,
                "invalid_entries": self.invalid_entries,
                "hit_ratio_percent": round(hit_ratio_val, 2),
                "avg_hit_latency_ms": round(avg_hit_lat, 2),
                "avg_miss_latency_ms": round(avg_miss_lat, 2),
            }

    def format_report(self) -> str:
        """Format an operational text report."""
        summary = self.get_summary()
        return (
            "RAG cache metrics\n"
            "-----------------\n"
            f"Cache hits:          {summary['hits']}\n"
            f"Cache misses:        {summary['misses']}\n"
            f"Cache read errors:   {summary['read_errors']}\n"
            f"Cache write errors:  {summary['write_errors']}\n"
            f"Invalidations:       {summary['invalidations']}\n"
            f"Invalid entries:     {summary['invalid_entries']}\n"
            f"Hit ratio:           {summary['hit_ratio_percent']:.1f}%\n"
            f"Avg hit latency:     {summary['avg_hit_latency_ms']:.2f} ms\n"
            f"Avg miss latency:    {summary['avg_miss_latency_ms']:.2f} ms"
        )

    def reset(self) -> None:
        """Reset all metrics (primarily for test isolation)."""
        with self._lock:
            self.hits = 0
            self.misses = 0
            self.read_errors = 0
            self.write_errors = 0
            self.invalidations = 0
            self.invalid_entries = 0
            self.hit_latencies_ms.clear()
            self.miss_latencies_ms.clear()


# Shared singleton instance
cache_metrics = CacheMetrics()
