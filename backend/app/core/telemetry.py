import threading
import time
from collections import deque
from typing import Any, Dict, List


class TelemetryCollector:
    """
    Thread-safe in-memory telemetry collector for API request metrics.
    Tracks request throughput, latency percentiles, and error rates.
    Privacy guarantee: Never logs or stores query payloads, document text, or PII.
    """

    def __init__(self, max_samples: int = 1000):
        self._lock = threading.Lock()
        self._total_requests = 0
        self._status_2xx = 0
        self._status_3xx = 0
        self._status_4xx = 0
        self._status_5xx = 0
        self._latencies: deque = deque(maxlen=max_samples)
        self._started_at = time.time()

    def record_request(self, status_code: int, latency_ms: float) -> None:
        """Record an API request event."""
        with self._lock:
            self._total_requests += 1
            if 200 <= status_code < 300:
                self._status_2xx += 1
            elif 300 <= status_code < 400:
                self._status_3xx += 1
            elif 400 <= status_code < 500:
                self._status_4xx += 1
            elif status_code >= 500:
                self._status_5xx += 1

            self._latencies.append(latency_ms)

    def get_metrics(self) -> Dict[str, Any]:
        """Compute snapshot metrics including average and percentile latencies."""
        with self._lock:
            total = self._total_requests
            s2xx = self._status_2xx
            s3xx = self._status_3xx
            s4xx = self._status_4xx
            s5xx = self._status_5xx
            samples: List[float] = list(self._latencies)

        uptime_seconds = round(time.time() - self._started_at, 2)
        error_rate_5xx = round((s5xx / total * 100), 2) if total > 0 else 0.0
        client_error_rate_4xx = round((s4xx / total * 100), 2) if total > 0 else 0.0

        if samples:
            sorted_samples = sorted(samples)
            count = len(sorted_samples)
            avg_latency = round(sum(sorted_samples) / count, 2)
            p50_idx = int(0.50 * count)
            p95_idx = min(int(0.95 * count), count - 1)
            p99_idx = min(int(0.99 * count), count - 1)
            p50_latency = round(sorted_samples[p50_idx], 2)
            p95_latency = round(sorted_samples[p95_idx], 2)
            p99_latency = round(sorted_samples[p99_idx], 2)
        else:
            avg_latency = 0.0
            p50_latency = 0.0
            p95_latency = 0.0
            p99_latency = 0.0

        return {
            "uptime_seconds": uptime_seconds,
            "total_requests": total,
            "status_counts": {
                "2xx": s2xx,
                "3xx": s3xx,
                "4xx": s4xx,
                "5xx": s5xx,
            },
            "error_rate_5xx_percent": error_rate_5xx,
            "client_error_rate_4xx_percent": client_error_rate_4xx,
            "latency_ms": {
                "avg": avg_latency,
                "p50": p50_latency,
                "p95": p95_latency,
                "p99": p99_latency,
            },
        }

    def reset(self) -> None:
        """Reset telemetry counters (useful for test suites)."""
        with self._lock:
            self._total_requests = 0
            self._status_2xx = 0
            self._status_3xx = 0
            self._status_4xx = 0
            self._status_5xx = 0
            self._latencies.clear()
            self._started_at = time.time()


# Global singleton instance
telemetry_collector = TelemetryCollector()
