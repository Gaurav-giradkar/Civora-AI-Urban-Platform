"""Script to update admin_incidents.py with full Civora serialization and observation details."""
INC_ROUTER_PATH = r"c:\My_stuff\Civora\backend\api\app\routers\admin_incidents.py"

inc_code = '''from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models import Incident, IssueReobservation, Observation, Report, Team, Ticket, User
from app.schemas import (
    IncidentAdminOut,
    IncidentAssign,
    IncidentDispatch,
    IncidentStatusUpdate,
    ObservationDetailOut,
)
from app.services.ticket_service import generate_ticket

router = APIRouter(prefix="/api/admin/incidents", tags=["admin-incidents"])

_OFFICIAL_ROLES = ("admin", "control_room", "department_officer")


def _get_incident_or_404(db: Session, incident_id: UUID) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident


def _serialize_incident(inc: Incident, db: Session) -> IncidentAdminOut:
    lat = None
    lng = None
    if inc.location is not None:
        try:
            pt = to_shape(inc.location)
            lat = pt.y
            lng = pt.x
        except Exception:
            pass

    latest_report = (
        db.query(Report)
        .filter(Report.incident_id == inc.id)
        .order_by(Report.created_at.desc())
        .first()
    )

    image_url = latest_report.image_url if latest_report else None
    description = latest_report.description if latest_report else None

    # If no citizen report, fallback to observation evidence
    if not image_url:
        latest_obs = (
            db.query(Observation)
            .filter(Observation.urban_issue_id == inc.id)
            .order_by(Observation.observed_at.desc())
            .first()
        )
        if latest_obs and latest_obs.image_url:
            image_url = latest_obs.image_url

    if not description:
        bus_cnt = inc.distinct_bus_count or 1
        obs_cnt = inc.observation_count or 1
        description = (
            f"Georeferenced urban issue corroborated by {bus_cnt} public sensing unit{'s' if bus_cnt > 1 else ''} "
            f"with {obs_cnt} independent observation{'s' if obs_cnt > 1 else ''}."
        )

    # Check assigned ticket and team
    ticket = db.query(Ticket).filter(Ticket.incident_id == inc.id).first()
    assigned_team_id = ticket.assigned_team_id if ticket else None
    assigned_team_name = None
    if assigned_team_id:
        team = db.query(Team).filter(Team.id == assigned_team_id).first()
        if team:
            assigned_team_name = team.name

    return IncidentAdminOut(
        id=inc.id,
        title=inc.title or f"{inc.category.replace('_', ' ').title()} Urban Issue",
        category=inc.category,
        status=inc.status,
        severity=inc.severity or "medium",
        priority_score=inc.priority_score or (round((inc.confidence or 0.85) * 100, 1)),
        confidence=inc.confidence or 0.85,
        ward=inc.ward or "Central Zone",
        department_id=inc.department_id,
        report_count=inc.report_count or 0,
        observation_count=inc.observation_count or 0,
        distinct_bus_count=inc.distinct_bus_count or 0,
        reobservation_count=inc.reobservation_count or 0,
        first_observed_at=inc.first_observed_at,
        last_observed_at=inc.last_observed_at,
        created_at=inc.created_at,
        resolved_at=inc.resolved_at,
        latitude=lat,
        longitude=lng,
        image_url=image_url,
        description=description,
        assigned_team_id=assigned_team_id,
        assigned_team_name=assigned_team_name,
    )


@router.get("", response_model=list[IncidentAdminOut])
def list_incidents(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    severity: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    ward: Optional[str] = Query(default=None),
    department_id: Optional[UUID] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    current_user: User = Depends(require_role(*_OFFICIAL_ROLES)),
    db: Session = Depends(get_db),
) -> list[IncidentAdminOut]:
    query = db.query(Incident)

    if status_filter:
        query = query.filter(Incident.status == status_filter)
    if severity:
        query = query.filter(Incident.severity == severity)
    if category:
        query = query.filter(Incident.category == category)
    if ward:
        query = query.filter(Incident.ward == ward)
    if department_id:
        query = query.filter(Incident.department_id == department_id)
    if date_from:
        query = query.filter(Incident.created_at >= date_from)
    if date_to:
        query = query.filter(Incident.created_at <= date_to)

    incidents = query.order_by(Incident.created_at.desc()).all()
    return [_serialize_incident(inc, db) for inc in incidents]


@router.get("/{incident_id}", response_model=IncidentAdminOut)
def get_incident(
    incident_id: UUID,
    current_user: User = Depends(require_role(*_OFFICIAL_ROLES)),
    db: Session = Depends(get_db),
) -> IncidentAdminOut:
    inc = _get_incident_or_404(db, incident_id)
    return _serialize_incident(inc, db)


@router.get("/{incident_id}/observations", response_model=list[ObservationDetailOut])
def get_incident_observations(
    incident_id: UUID,
    current_user: User = Depends(require_role(*_OFFICIAL_ROLES)),
    db: Session = Depends(get_db),
) -> list[ObservationDetailOut]:
    """Return chronological observation sequence supporting the Corroboration Panel."""
    _get_incident_or_404(db, incident_id)
    raw_obs = (
        db.query(Observation)
        .filter(Observation.urban_issue_id == incident_id)
        .order_by(Observation.observed_at.asc())
        .all()
    )
    reobs_ids = set(
        db.query(IssueReobservation.observation_id)
        .filter(IssueReobservation.urban_issue_id == incident_id)
        .all()
    ) if raw_obs else set()
    reobs_ids_flat = {r[0] for r in reobs_ids}

    results: list[ObservationDetailOut] = []
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
        results.append(
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
    return results


@router.post("/{incident_id}/verify", response_model=IncidentAdminOut)
def verify_incident(
    incident_id: UUID,
    current_user: User = Depends(require_role(*_OFFICIAL_ROLES)),
    db: Session = Depends(get_db),
) -> IncidentAdminOut:
    incident = _get_incident_or_404(db, incident_id)
    incident.status = "confirmed"
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return _serialize_incident(incident, db)


@router.post("/{incident_id}/reject", response_model=IncidentAdminOut)
def reject_incident(
    incident_id: UUID,
    current_user: User = Depends(require_role(*_OFFICIAL_ROLES)),
    db: Session = Depends(get_db),
) -> IncidentAdminOut:
    incident = _get_incident_or_404(db, incident_id)
    incident.status = "rejected"
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return _serialize_incident(incident, db)


@router.post("/{incident_id}/assign", response_model=IncidentAdminOut)
def assign_incident(
    incident_id: UUID,
    payload: IncidentAssign,
    current_user: User = Depends(require_role(*_OFFICIAL_ROLES)),
    db: Session = Depends(get_db),
) -> IncidentAdminOut:
    incident = _get_incident_or_404(db, incident_id)
    incident.department_id = payload.department_id
    incident.status = "assigned"
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return _serialize_incident(incident, db)


@router.post("/{incident_id}/dispatch", response_model=IncidentAdminOut)
def dispatch_incident(
    incident_id: UUID,
    payload: IncidentDispatch,
    current_user: User = Depends(require_role(*_OFFICIAL_ROLES)),
    db: Session = Depends(get_db),
) -> IncidentAdminOut:
    incident = _get_incident_or_404(db, incident_id)

    existing_ticket = db.query(Ticket).filter(Ticket.incident_id == incident.id).first()
    if existing_ticket is None:
        ticket_data = generate_ticket(
            {
                "category": incident.category,
                "severity": incident.severity,
                "ward": incident.ward,
                "report_count": incident.report_count,
                "confidence": incident.confidence,
            }
        )
        ticket = Ticket(
            incident_id=incident.id,
            department_id=incident.department_id,
            assigned_team_id=payload.team_id,
            title=ticket_data["title"],
            summary=ticket_data["summary"],
            recommended_action=ticket_data["recommended_action"],
        )
        db.add(ticket)
    else:
        existing_ticket.assigned_team_id = payload.team_id
        db.add(existing_ticket)

    incident.status = "dispatched"
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return _serialize_incident(incident, db)


@router.patch("/{incident_id}/status", response_model=IncidentAdminOut)
def update_incident_status(
    incident_id: UUID,
    payload: IncidentStatusUpdate,
    current_user: User = Depends(require_role(*_OFFICIAL_ROLES)),
    db: Session = Depends(get_db),
) -> IncidentAdminOut:
    incident = _get_incident_or_404(db, incident_id)
    incident.status = payload.status
    if payload.status == "resolved":
        incident.resolved_at = datetime.now(timezone.utc)
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return _serialize_incident(incident, db)
'''

with open(INC_ROUTER_PATH, "w", encoding="utf-8") as f:
    f.write(inc_code)
print("Updated admin_incidents.py successfully!")
