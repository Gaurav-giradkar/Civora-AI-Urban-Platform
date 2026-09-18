"""Deterministic bus-observation correlation for Civora Phase 1.

An existing ``Incident`` row is used as the compatible Urban Issue aggregate.
This avoids disrupting Civora reports, tickets, or authority workflows
while observations provide the new evidence trail.
"""
from datetime import datetime, timedelta, timezone
from typing import Literal

from geoalchemy2.functions import ST_DWithin, ST_Distance, ST_MakePoint, ST_SetSRID
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.models import Incident, IssueReobservation, Observation
from app.services.priority_service import score_urban_issue_priority

CORRELATION_RADIUS_METERS = 200
CORRELATION_WINDOW_HOURS = 24
_REOBSERVATION_STATUSES = ("confirmed", "assigned", "dispatched", "in_progress", "resolved")
_EXCLUDED_STATUSES = ("rejected",)


def _point(lat: float, lng: float):
    return ST_SetSRID(ST_MakePoint(lng, lat), 4326)


def _find_nearby_issues(
    db: Session,
    *,
    detected_class: str,
    latitude: float,
    longitude: float,
    observed_at: datetime,
    recent_only: bool,
) -> list[Incident]:
    point = _point(latitude, longitude)
    query = select(Incident).where(
        Incident.category == detected_class,
        Incident.status.not_in(_EXCLUDED_STATUSES),
        ST_DWithin(Incident.location, point, CORRELATION_RADIUS_METERS),
    )
    if recent_only:
        cutoff = observed_at - timedelta(hours=CORRELATION_WINDOW_HOURS)
        query = query.where(Incident.last_observed_at >= cutoff)
    else:
        query = query.where(Incident.status.in_(_REOBSERVATION_STATUSES))
    query = query.order_by(ST_Distance(Incident.location, point).asc())
    return list(db.execute(query).scalars())


def correlate_observation(
    db: Session,
    observation: Observation,
    *,
    latitude: float,
    longitude: float,
) -> tuple[Incident, Literal["new_issue", "corroboration", "reobservation"]]:
    """Attach an observation to one Urban Issue and refresh its evidence score."""
    observed_at = observation.observed_at
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
        observation.observed_at = observed_at

    candidates = _find_nearby_issues(
        db,
        detected_class=observation.detected_class,
        latitude=latitude,
        longitude=longitude,
        observed_at=observed_at,
        recent_only=True,
    )

    if candidates:
        issue = candidates[0]
        correlation_type: Literal["new_issue", "corroboration", "reobservation"] = (
            "reobservation" if issue.status in _REOBSERVATION_STATUSES else "corroboration"
        )
    else:
        # A repair/verified issue can be revisited long after the normal
        # corroboration window.  Preserve that evidence on the same issue.
        revisits = _find_nearby_issues(
            db,
            detected_class=observation.detected_class,
            latitude=latitude,
            longitude=longitude,
            observed_at=observed_at,
            recent_only=False,
        )
        if revisits:
            issue = revisits[0]
            correlation_type = "reobservation"
        else:
            issue = Incident(
                title=f"{observation.detected_class.replace('_', ' ').title()} urban issue",
                category=observation.detected_class,
                location=f"SRID=4326;POINT({longitude} {latitude})",
                confidence=observation.confidence,
                report_count=0,
                observation_count=0,
                distinct_bus_count=0,
                reobservation_count=0,
                first_observed_at=observed_at,
                last_observed_at=observed_at,
            )
            db.add(issue)
            db.flush()
            correlation_type = "new_issue"

    prior_status = issue.status
    observation.urban_issue_id = issue.id
    db.add(observation)
    db.flush()

    issue.observation_count = db.scalar(
        select(func.count(Observation.id)).where(Observation.urban_issue_id == issue.id)
    ) or 0
    issue.distinct_bus_count = db.scalar(
        select(func.count(distinct(Observation.bus_id))).where(Observation.urban_issue_id == issue.id)
    ) or 0
    if issue.first_observed_at is None or observed_at < issue.first_observed_at:
        issue.first_observed_at = observed_at
    if issue.last_observed_at is None or observed_at > issue.last_observed_at:
        issue.last_observed_at = observed_at
    issue.confidence = max(issue.confidence or 0.0, observation.confidence)

    if correlation_type == "reobservation":
        db.add(
            IssueReobservation(
                urban_issue_id=issue.id,
                observation_id=observation.id,
                observed_at=observed_at,
                prior_issue_status=prior_status,
            )
        )
        issue.reobservation_count = (issue.reobservation_count or 0) + 1

    priority, priority_level = score_urban_issue_priority(
        issue.category,
        issue.confidence or observation.confidence,
        issue.observation_count,
        issue.distinct_bus_count,
        issue.reobservation_count or 0,
    )
    issue.priority_score = priority
    issue.severity = priority_level
    db.add(issue)
    db.flush()
    return issue, correlation_type
