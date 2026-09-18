"""
SQLAlchemy ORM models for every table described in the spec (section 5).

- Every model has an explicit __tablename__.
- Every primary key is a UUID with a server-side default (gen_random_uuid()),
  not a Python-side default, so rows created directly via SQL/migrations also
  get a valid id.
- Location columns use GeoAlchemy2's Geography type (PostGIS GEOGRAPHY(Point, 4326)).
"""
import uuid

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Null for citizens who only ever authenticate via OTP.
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    # citizen | admin | control_room | department_officer | field_team
    role: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True
    )
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    device_tokens: Mapped[list["DeviceToken"]] = relationship(back_populates="user")


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    contact_email: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    # available | busy | offline | en_route
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    fcm_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    # endpoint + keys, from the browser PushSubscription object
    web_push_subscription: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="device_tokens")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=True
    )
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    device_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # pending | approved | held
    moderation_status: Mapped[str] = mapped_column(Text, server_default="pending")
    is_blurred: Mapped[bool] = mapped_column(Boolean, server_default="false")
    status: Mapped[str] = mapped_column(Text, server_default="submitted")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    # under_review | confirmed | assigned | dispatched | in_progress | resolved | rejected
    status: Mapped[str] = mapped_column(Text, server_default="under_review")
    # critical | high | medium | low
    severity: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    ward: Mapped[str | None] = mapped_column(Text, nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    report_count: Mapped[int] = mapped_column(Integer, server_default="1")
    # Civora adds machine-observation evidence without changing the legacy
    # citizen-report relationship above.  Existing incidents continue to work
    # as Urban Issues; these fields are populated only by the observation flow.
    observation_count: Mapped[int] = mapped_column(Integer, server_default="0")
    distinct_bus_count: Mapped[int] = mapped_column(Integer, server_default="0")
    reobservation_count: Mapped[int] = mapped_column(Integer, server_default="0")
    first_observed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_observed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Bus(Base):
    __tablename__ = "buses"

    id: Mapped[uuid.UUID] = _uuid_pk()
    # The operational bus identifier (for example, Bus-017) is intentionally
    # stable and is the value observations preserve and expose to the UI.
    bus_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    route_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Observation(Base):
    __tablename__ = "observations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    event_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # References the externally meaningful bus identifier, rather than a
    # hidden surrogate, so source identity remains durable in exports.
    bus_id: Mapped[str] = mapped_column(Text, ForeignKey("buses.bus_id"), nullable=False)
    route_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    urban_issue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=True
    )
    observed_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    detected_class: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    gnss_accuracy_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IssueReobservation(Base):
    __tablename__ = "issue_reobservations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    urban_issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("incidents.id"), nullable=False
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("observations.id"), unique=True, nullable=False
    )
    observed_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    prior_issue_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = _uuid_pk()
    incident_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("incidents.id"))
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    assigned_team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    sla_due_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # open | en_route | in_progress | resolved
    status: Mapped[str] = mapped_column(Text, server_default="open")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    title: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    area: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_until: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    ward: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    forecast_time: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rainfall_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    historical_incident_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    log_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OTPCode(Base):
    __tablename__ = "otp_codes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

