from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Optional


TEMPORAL_VALIDITY_POLICY_VERSION = (
    "SM3_PLATFORM_TEMPORAL_VALIDITY_POLICY_V1"
)

TEMPORAL_VALIDITY_ENGINE_VERSION = (
    "SM3_PLATFORM_TEMPORAL_VALIDITY_ENGINE_V1"
)


class TemporalValidityError(ValueError):
    def __init__(
        self,
        code: str,
        field: Optional[str] = None,
    ) -> None:
        self.code = code
        self.field = field

        message = (
            code
            if field is None
            else f"{code}:{field}"
        )

        super().__init__(message)


def _parse_timestamp(
    value: Any,
    field: str,
) -> datetime:

    raw = str(
        value or ""
    ).strip()

    if not raw:
        raise TemporalValidityError(
            "PLATFORM_TEMPORAL_TIMESTAMP_REQUIRED",
            field,
        )

    try:
        parsed = datetime.fromisoformat(
            raw.replace(
                "Z",
                "+00:00",
            )
        )

    except ValueError as exc:
        raise TemporalValidityError(
            "PLATFORM_TEMPORAL_TIMESTAMP_INVALID",
            field,
        ) from exc

    if parsed.tzinfo is None:
        raise TemporalValidityError(
            "PLATFORM_TEMPORAL_TIMESTAMP_TZ_REQUIRED",
            field,
        )

    return parsed.astimezone(
        timezone.utc
    )


def _iso(
    value: datetime,
) -> str:

    return value.astimezone(
        timezone.utc
    ).isoformat()


def validate_evidence_temporal(
    evidence: dict[str, Any],
    as_of: str,
) -> dict[str, Any]:

    record = deepcopy(
        evidence
    )

    snapshot_time = _parse_timestamp(
        as_of,
        "as_of",
    )

    source_date = _parse_timestamp(
        record.get(
            "source_date"
        ),
        "source_date",
    )

    observed_at = _parse_timestamp(
        record.get(
            "observed_at"
        ),
        "observed_at",
    )

    if source_date > snapshot_time:
        raise TemporalValidityError(
            "PLATFORM_TEMPORAL_EVIDENCE_SOURCE_DATE_FUTURE",
            "source_date",
        )

    if observed_at > snapshot_time:
        raise TemporalValidityError(
            "PLATFORM_TEMPORAL_EVIDENCE_OBSERVED_AT_FUTURE",
            "observed_at",
        )

    valid_until_raw = record.get(
        "valid_until"
    )

    valid_until = None

    if (
        valid_until_raw is not None
        and
        str(
            valid_until_raw
        ).strip()
    ):
        valid_until = _parse_timestamp(
            valid_until_raw,
            "valid_until",
        )

        if snapshot_time > valid_until:
            raise TemporalValidityError(
                "PLATFORM_TEMPORAL_EVIDENCE_EXPIRED",
                "valid_until",
            )

    source_age_seconds = int(
        (
            snapshot_time
            - source_date
        ).total_seconds()
    )

    observation_age_seconds = int(
        (
            snapshot_time
            - observed_at
        ).total_seconds()
    )

    return {
        "eligible":
            True,

        "policy_version":
            TEMPORAL_VALIDITY_POLICY_VERSION,

        "engine_version":
            TEMPORAL_VALIDITY_ENGINE_VERSION,

        "evidence_id":
            record.get(
                "evidence_id"
            ),

        "as_of":
            _iso(
                snapshot_time
            ),

        "source_date":
            _iso(
                source_date
            ),

        "observed_at":
            _iso(
                observed_at
            ),

        "valid_until":
            (
                _iso(
                    valid_until
                )
                if valid_until
                else None
            ),

        "source_age_seconds":
            source_age_seconds,

        "observation_age_seconds":
            observation_age_seconds,

        "hard_expiry_present":
            valid_until
            is not None,

        "hard_expired":
            False,
    }


def validate_signal_temporal(
    signal: dict[str, Any],
    as_of: str,
) -> dict[str, Any]:

    record = deepcopy(
        signal
    )

    snapshot_time = _parse_timestamp(
        as_of,
        "as_of",
    )

    started = _parse_timestamp(
        record.get(
            "window_started_at"
        ),
        "window_started_at",
    )

    ended = _parse_timestamp(
        record.get(
            "window_ended_at"
        ),
        "window_ended_at",
    )

    if started >= ended:
        raise TemporalValidityError(
            "PLATFORM_TEMPORAL_SIGNAL_WINDOW_INVALID"
        )

    if ended > snapshot_time:
        raise TemporalValidityError(
            "PLATFORM_TEMPORAL_SIGNAL_WINDOW_FUTURE",
            "window_ended_at",
        )

    window_duration_seconds = int(
        (
            ended
            - started
        ).total_seconds()
    )

    window_age_seconds = int(
        (
            snapshot_time
            - ended
        ).total_seconds()
    )

    return {
        "eligible":
            True,

        "policy_version":
            TEMPORAL_VALIDITY_POLICY_VERSION,

        "engine_version":
            TEMPORAL_VALIDITY_ENGINE_VERSION,

        "signal_id":
            record.get(
                "signal_id"
            ),

        "as_of":
            _iso(
                snapshot_time
            ),

        "window_started_at":
            _iso(
                started
            ),

        "window_ended_at":
            _iso(
                ended
            ),

        "window_duration_seconds":
            window_duration_seconds,

        "window_age_seconds":
            window_age_seconds,
    }


def validate_snapshot_temporal_inputs(
    *,
    as_of: str,
    evidence: list[dict[str, Any]],
    signals: list[dict[str, Any]],
) -> dict[str, Any]:

    snapshot_time = _parse_timestamp(
        as_of,
        "as_of",
    )

    evidence_results = [
        validate_evidence_temporal(
            item,
            _iso(
                snapshot_time
            ),
        )
        for item in evidence
    ]

    signal_results = [
        validate_signal_temporal(
            item,
            _iso(
                snapshot_time
            ),
        )
        for item in signals
    ]

    evidence_results = sorted(
        evidence_results,
        key=lambda item: str(
            item.get(
                "evidence_id"
            )
            or ""
        ),
    )

    signal_results = sorted(
        signal_results,
        key=lambda item: str(
            item.get(
                "signal_id"
            )
            or ""
        ),
    )

    return {
        "eligible":
            True,

        "policy_version":
            TEMPORAL_VALIDITY_POLICY_VERSION,

        "engine_version":
            TEMPORAL_VALIDITY_ENGINE_VERSION,

        "as_of":
            _iso(
                snapshot_time
            ),

        "evidence_count":
            len(
                evidence_results
            ),

        "signal_count":
            len(
                signal_results
            ),

        "evidence":
            evidence_results,

        "signals":
            signal_results,

        "confidence_decay_applied":
            False,

        "confidence_decay_reason":
            "NUMERIC_POLICY_DEFERRED",
    }
