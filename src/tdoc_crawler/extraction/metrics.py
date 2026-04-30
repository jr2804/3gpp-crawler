"""Performance metrics tracking for extraction operations."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class MetricType(Enum):
    """Types of performance metrics."""

    CONVERSION = "conversion"


@dataclass
class DocumentMetric:
    """Single metric measurement."""

    document_id: str
    metric_type: MetricType
    duration_seconds: float
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    error: str | None = None
    cache_hit: bool = False


@dataclass
class TimedOperationResult:
    """Mutable operation timing state exposed by timed_operation."""

    success: bool = False
    duration_seconds: float = 0.0


class MetricsTracker:
    """Aggregate metrics for reporting."""

    def __init__(self) -> None:
        """Initialize the tracker with an empty metrics list."""
        self._metrics: list[DocumentMetric] = []

    def record(self, metric: DocumentMetric) -> None:
        """Record a new metric.

        Args:
            metric: The metric to record.
        """
        self._metrics.append(metric)

    def record_success(
        self,
        document_id: str,
        metric_type: MetricType,
        duration_seconds: float,
        *,
        cache_hit: bool = False,
    ) -> None:
        """Convenience method to record a successful operation.

        Args:
            document_id: Document identifier.
            metric_type: Type of operation.
            duration_seconds: Operation duration.
            cache_hit: Whether result was served from cache.
        """
        self.record(
            DocumentMetric(
                document_id=document_id,
                metric_type=metric_type,
                duration_seconds=duration_seconds,
                success=True,
                cache_hit=cache_hit,
            ),
        )

    def record_failure(
        self,
        document_id: str,
        metric_type: MetricType,
        duration_seconds: float,
        error: str,
    ) -> None:
        """Convenience method to record a failed operation.

        Args:
            document_id: Document identifier.
            metric_type: Type of operation.
            duration_seconds: Operation duration.
            error: Error message or type.
        """
        self.record(
            DocumentMetric(
                document_id=document_id,
                metric_type=metric_type,
                duration_seconds=duration_seconds,
                success=False,
                error=error,
            ),
        )

    def summary(self) -> dict:
        """Generate summary statistics.

        Returns:
            Dictionary with aggregated metrics.
        """
        if not self._metrics:
            return {
                "total_operations": 0,
                "success_rate": 0.0,
                "cache_hit_rate": 0.0,
                "avg_duration": 0.0,
            }

        total = len(self._metrics)
        successes = sum(1 for m in self._metrics if m.success)
        cache_hits = sum(1 for m in self._metrics if m.cache_hit)
        total_duration = sum(m.duration_seconds for m in self._metrics)

        return {
            "total_operations": total,
            "success_rate": successes / total if total > 0 else 0.0,
            "cache_hit_rate": cache_hits / total if total > 0 else 0.0,
            "avg_duration": total_duration / total if total > 0 else 0.0,
        }

    def clear(self) -> None:
        """Clear all recorded metrics."""
        self._metrics.clear()


_default_tracker = MetricsTracker()


def get_metrics_tracker() -> MetricsTracker:
    """Get the process-wide metrics tracker used by extraction operations."""
    return _default_tracker


@contextmanager
def timed_operation(
    tracker: MetricsTracker | None,
    document_id: str,
    metric_type: MetricType,
) -> Iterator[TimedOperationResult]:
    """Context manager helper for timing operations.

    Usage:
        tracker = get_metrics_tracker()
        with timed_operation(tracker, "S4-260001", MetricType.CONVERSION) as result:
            # do work
            print(result.success, result.duration_seconds)

    Args:
        tracker: MetricsTracker instance (can be None to skip tracking).
        document_id: Document identifier.
        metric_type: Type of operation.

    Yields:
        Mutable timing result object populated on context exit.
    """
    start = time.monotonic()
    result = TimedOperationResult()

    try:
        yield result
    except Exception as exc:
        result.duration_seconds = time.monotonic() - start
        result.success = False
        if tracker is not None:
            tracker.record_failure(
                document_id=document_id,
                metric_type=metric_type,
                duration_seconds=result.duration_seconds,
                error=f"{type(exc).__name__}: {exc}",
            )
        raise
    else:
        result.duration_seconds = time.monotonic() - start
        result.success = True
        if tracker is not None:
            tracker.record_success(
                document_id=document_id,
                metric_type=metric_type,
                duration_seconds=result.duration_seconds,
            )


__all__ = [
    "DocumentMetric",
    "MetricType",
    "MetricsTracker",
    "TimedOperationResult",
    "get_metrics_tracker",
    "timed_operation",
]
