"""Helper script to update backend schemas and routers for Phase 3 Civora Command Center."""
import os
import re

SCHEMAS_PATH = r"c:\My_stuff\Civora\backend\api\app\schemas.py"
OBSERVATIONS_ROUTER_PATH = r"c:\My_stuff\Civora\backend\api\app\routers\observations.py"
INCIDENTS_ROUTER_PATH = r"c:\My_stuff\Civora\backend\api\app\routers\admin_incidents.py"

# 1. Update schemas.py
with open(SCHEMAS_PATH, "r", encoding="utf-8") as f:
    schemas_content = f.read()

target_inc = """class IncidentAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: Optional[str] = None
    category: str
    status: str
    severity: Optional[str] = None
    priority_score: Optional[float] = None
    confidence: Optional[float] = None
    ward: Optional[str] = None
    department_id: Optional[UUID] = None
    report_count: int
    created_at: datetime
    resolved_at: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    image_url: Optional[str] = None
    description: Optional[str] = None"""

replacement_inc = """class IncidentAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: Optional[str] = None
    category: str
    status: str
    severity: Optional[str] = None
    priority_score: Optional[float] = None
    confidence: Optional[float] = None
    ward: Optional[str] = None
    department_id: Optional[UUID] = None
    report_count: int = 0
    observation_count: int = 0
    distinct_bus_count: int = 0
    reobservation_count: int = 0
    first_observed_at: Optional[datetime] = None
    last_observed_at: Optional[datetime] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    assigned_team_id: Optional[UUID] = None
    assigned_team_name: Optional[str] = None"""

extra_schemas = """

class BusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bus_id: str
    route_id: Optional[str] = None
    display_name: Optional[str] = None
    status: Optional[str] = None
    latest_observation_time: Optional[datetime] = None
    latest_detected_class: Optional[str] = None
    latest_latitude: Optional[float] = None
    latest_longitude: Optional[float] = None
    total_observations: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None


class ObservationDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: str
    bus_id: str
    route_id: Optional[str] = None
    urban_issue_id: Optional[UUID] = None
    observed_at: datetime
    latitude: float
    longitude: float
    detected_class: str
    confidence: float
    image_url: Optional[str] = None
    severity: Optional[str] = None
    gnss_accuracy_meters: Optional[float] = None
    is_reobservation: bool = False
    created_at: datetime


class CommandSummaryOut(BaseModel):
    active_buses_count: int
    total_observations: int
    total_urban_issues: int
    high_priority_issues: int
    critical_issues: int
    resolved_issues: int
    system_status: str = "online"
"""

# Normalize newlines for replacement
schemas_content_norm = schemas_content.replace("\r\n", "\n")
target_inc_norm = target_inc.replace("\r\n", "\n")

if target_inc_norm in schemas_content_norm:
    schemas_content_norm = schemas_content_norm.replace(target_inc_norm, replacement_inc.replace("\r\n", "\n"))
    if "class BusOut" not in schemas_content_norm:
        schemas_content_norm += extra_schemas.replace("\r\n", "\n")
    with open(SCHEMAS_PATH, "w", encoding="utf-8") as f:
        f.write(schemas_content_norm)
    print("Successfully updated schemas.py!")
else:
    print("Could not find target_inc in schemas.py")
