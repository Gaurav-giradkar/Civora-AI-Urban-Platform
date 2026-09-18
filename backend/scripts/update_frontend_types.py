"""Update frontend types and endpoints for Phase 3 Civora Command Center."""

TYPES_PATH = r"c:\My_stuff\Civora\frontend\src\types\index.ts"
ENDPOINTS_PATH = r"c:\My_stuff\Civora\frontend\src\api\endpoints.ts"

with open(TYPES_PATH, "r", encoding="utf-8") as f:
    types_content = f.read().replace("\r\n", "\n")

target_incident = """export interface Incident {
  id: string;
  title: string;
  description: string;
  category: HazardCategory;
  severity: IncidentSeverity;
  status: IncidentStatus;
  location: {
    lat: number;
    lng: number;
    address: string;
    ward: string;
  };
  department: string;
  ai_confidence: number;
  report_count: number;
  image_url: string;
  reported_at: string;
  updated_at: string;
  assigned_team_id?: string;
  assigned_team_name?: string;
  timeline?: {
    time: string;
    status: IncidentStatus;
    note: string;
    actor: string;
  }[];
}"""

replacement_incident = """export interface Incident {
  id: string;
  title: string;
  description: string;
  category: HazardCategory;
  severity: IncidentSeverity;
  status: IncidentStatus;
  location: {
    lat: number;
    lng: number;
    address: string;
    ward: string;
  };
  department: string;
  ai_confidence: number;
  report_count: number;
  observation_count?: number;
  distinct_bus_count?: number;
  reobservation_count?: number;
  first_observed_at?: string;
  last_observed_at?: string;
  image_url: string;
  reported_at: string;
  updated_at: string;
  assigned_team_id?: string;
  assigned_team_name?: string;
  timeline?: {
    time: string;
    status: IncidentStatus;
    note: string;
    actor: string;
  }[];
}"""

extra_types = """

export interface BusUnit {
  id: string;
  bus_id: string;
  route_id?: string;
  display_name?: string;
  status: string;
  latest_observation_time?: string;
  latest_detected_class?: string;
  latest_latitude?: number;
  latest_longitude?: number;
  total_observations: number;
  created_at?: string;
  updated_at?: string;
}

export interface ObservationDetail {
  id: string;
  event_id: string;
  bus_id: string;
  route_id?: string;
  urban_issue_id?: string;
  observed_at: string;
  latitude: number;
  longitude: number;
  detected_class: string;
  confidence: number;
  image_url?: string;
  severity?: string;
  gnss_accuracy_meters?: number;
  is_reobservation: boolean;
  created_at?: string;
}

export interface CommandSummary {
  active_buses_count: number;
  total_observations: number;
  total_urban_issues: number;
  high_priority_issues: number;
  critical_issues: number;
  resolved_issues: number;
  system_status: string;
}
"""

if target_incident in types_content:
    types_content = types_content.replace(target_incident, replacement_incident)
    if "export interface BusUnit" not in types_content:
        types_content += extra_types
    with open(TYPES_PATH, "w", encoding="utf-8") as f:
        f.write(types_content)
    print("Updated types/index.ts successfully!")
else:
    print("Target incident not found in types/index.ts")
