"""Script to update observations.py and admin_incidents.py with Phase 3 endpoints."""
import os

OBS_ROUTER_PATH = r"c:\My_stuff\Civora\backend\api\app\routers\observations.py"
INC_ROUTER_PATH = r"c:\My_stuff\Civora\backend\api\app\routers\admin_incidents.py"

obs_code = '''"""Authenticated ingestion and query endpoints used by Civora's fleet intelligence system."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models import Bus, Incident, IssueReobservation, Observation, User
from app.schemas import (
    BusOut,
    CommandSummaryOut,
    ObservationCreate,
    ObservationDetailOut,
    ObservationIngestOut,
)
from app.services.corroboration_service import correlate_observation

router = APIRouter(prefix="/api/observations", tags=["observations"])
_SIMULATOR_ROLES = ("admin", "control_room", "department_officer")
_VIEW_ROLES = ("admin", "control_room", "department_officer", "field_team")


@router.get("/summary", response_model=CommandSummaryOut)
def get_command_summary(
    current_user: User = Depends(require_role(*_VIEW_ROLES)),
    db: Session = Depends(get_db),
) -> CommandSummaryOut:
    """Return live system operational state metrics directly from the database."""
    active_buses = db.query(Bus).count()
    total_obs = db.query(Observation).count()
    total_issues = db.query(Incident).count()
    high_priority = db.query(Incident).filter(Incident.severity.in_(["high", "critical"])).count()
    critical_issues = db.query(Incident).filter(Incident.severity == "critical").count()
    resolved_issues = db.query(Incident).filter(Incident.status == "resolved").count()

    return CommandSummaryOut(
        active_buses_count=active_buses,
        total_observations=total_obs,
        total_urban_issues=total_issues,
        high_priority_issues=high_priority,
        critical_issues=critical_issues,
        resolved_issues=resolved_issues,
        system_status="online",
    )


@router.get("/buses", response_model=list[BusOut])
def list_buses(
    current_user: User = Depends(require_role(*_VIEW_ROLES)),
    db: Session = Depends(get_db),
) -> list[BusOut]:
    """Return real bus sensing units with latest observation telemetry and status."""
    buses = db.query(Bus).order_by(Bus.bus_id.asc()).all()
    results: list[BusOut] = []

    for bus in buses:
        obs_count = db.query(Observation).filter(Observation.bus_id == bus.bus_id).count()
        latest_obs = (
            db.query(Observation)
            .filter(Observation.bus_id == bus.bus_id)
            .order_by(Observation.observed_at.desc())
            .first()
        )

        lat = None
        lng = None
        latest_time = None
        latest_class = None

        if latest_obs is not None:
            latest_time = latest_obs.observed_at
            latest_class = latest_obs.detected_class
            try:
                pt = to_shape(latest_obs.location)
                lat = pt.y
                lng = pt.x
            except Exception:
                pass

        results.append(
            BusOut(
                id=bus.id,
                bus_id=bus.bus_id,
                route_id=bus.route_id or "Route-12",
                display_name=bus.display_name or bus.bus_id,
                status=bus.status or "active",
                latest_observation_time=latest_time,
                latest_detected_class=latest_class,
                latest_latitude=lat,
                latest_longitude=lng,
                total_observations=obs_count,
                created_at=bus.created_at,
                updated_at=bus.updated_at,
            )
        )

    return results


@router.get("", response_model=list[ObservationDetailOut])
def list_observations(
    urban_issue_id: Optional[UUID] = Query(default=None),
    bus_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
    current_user: User = Depends(require_role(*_VIEW_ROLES)),
    db: Session = Depends(get_db),
) -> list[ObservationDetailOut]:
    """Return historical and live telemetry observations with coordinates."""
    query = db.query(Observation)
    if urban_issue_id:
        query = query.filter(Observation.urban_issue_id == urban_issue_id)
    if bus_id:
        query = query.filter(Observation.bus_id == bus_id)

    raw_obs = query.order_by(Observation.observed_at.desc()).limit(limit).all()

    # Query reobservation IDs to set flag
    reobs_ids = set(
        db.query(IssueReobservation.observation_id).filter(
            IssueReobservation.observation_id.in_([o.id for o in raw_obs])
        ).all()
    ) if raw_obs else set()
    reobs_ids_flat = {r[0] for r in reobs_ids}

    out_list: list[ObservationDetailOut] = []
    for o in raw_obs:
        lat = 0.0
        lng = 0.0
        if o.location is not None:
            try:
                pt = to_shape(o.location)
                lat = pt.y
                lng = pt.x
            except Exception:
                pass

        out_list.append(
            ObservationDetailOut(
                id=o.id,
                event_id=o.event_id,
                bus_id=o.bus_id,
                route_id=o.route_id,
                urban_issue_id=o.urban_issue_id,
                observed_at=o.observed_at,
                latitude=lat,
                longitude=lng,
                detected_class=o.detected_class,
                confidence=o.confidence,
                image_url=o.image_url,
                severity=o.severity,
                gnss_accuracy_meters=o.gnss_accuracy_meters,
                is_reobservation=o.id in reobs_ids_flat,
                created_at=o.created_at,
            )
        )

    return out_list


@router.post("", response_model=ObservationIngestOut, status_code=status.HTTP_201_CREATED)
def ingest_observation(
    payload: ObservationCreate,
    current_user: User = Depends(require_role(*_SIMULATOR_ROLES)),
    db: Session = Depends(get_db),
) -> ObservationIngestOut:
    """Persist one bus event and deterministically correlate it to an Urban Issue."""
    if db.query(Observation).filter(Observation.event_id == payload.event_id).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="event_id has already been ingested")

    bus = db.query(Bus).filter(Bus.bus_id == payload.bus_id).first()
    if bus is None:
        bus = Bus(
            bus_id=payload.bus_id,
            route_id=payload.route_id,
            display_name=payload.bus_display_name or payload.bus_id,
            status=payload.bus_status or "active",
        )
        db.add(bus)
    else:
        if payload.route_id is not None:
            bus.route_id = payload.route_id
        if payload.bus_display_name is not None:
            bus.display_name = payload.bus_display_name
        if payload.bus_status is not None:
            bus.status = payload.bus_status
        db.add(bus)
    db.flush()

    observation = Observation(
        event_id=payload.event_id,
        bus_id=payload.bus_id,
        route_id=payload.route_id,
        observed_at=payload.observed_at,
        location=f"SRID=4326;POINT({payload.longitude} {payload.latitude})",
        detected_class=payload.detected_class,
        confidence=payload.confidence,
        image_url=payload.image_url,
        severity=payload.severity,
        source_metadata=payload.source_metadata,
        gnss_accuracy_meters=payload.gnss_accuracy_meters,
    )
    db.add(observation)
    db.flush()
    issue, correlation_type = correlate_observation(
        db, observation, latitude=payload.latitude, longitude=payload.longitude
    )
    db.commit()
    db.refresh(observation)
    db.refresh(issue)

    return ObservationIngestOut(
        observation_id=observation.id,
        event_id=observation.event_id,
        bus_id=observation.bus_id,
        detected_class=observation.detected_class,
        confidence=observation.confidence,
        latitude=payload.latitude,
        longitude=payload.longitude,
        urban_issue_id=issue.id,
        observation_count=issue.observation_count,
        distinct_bus_count=issue.distinct_bus_count,
        priority_score=issue.priority_score or 0.0,
        priority_level=issue.severity or "low",
        correlation_type=correlation_type,
    )
'''

with open(OBS_ROUTER_PATH, "w", encoding="utf-8") as f:
    f.write(obs_code)
print("Updated observations.py successfully!")
