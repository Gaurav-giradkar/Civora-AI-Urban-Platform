export type UserRole = 'admin' | 'control_room' | 'department_officer' | 'field_team';

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  department?: string;
  created_at?: string;
}

export type IncidentStatus = 'REPORTED' | 'VERIFIED' | 'IN_PROGRESS' | 'RESOLVED' | 'REJECTED';
export type IncidentSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

export type HazardCategory =
  | 'POTHOLE'
  | 'FLOODED_ROAD'
  | 'BROKEN_STREETLIGHT'
  | 'FALLEN_TREE'
  | 'GARBAGE_DUMP'
  | 'GARBAGE_PILE'
  | 'WATER_LEAK'
  | 'TRAFFIC_SIGNAL_OUT'
  | 'OPEN_MANHOLE'
  | 'STRUCTURAL_DAMAGE'
  | 'ROAD_OBSTRUCTION'
  | 'DAMAGED_ROAD';


export interface Incident {
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
}

export interface Team {
  id: string;
  name: string;
  department: string;
  lead_name: string;
  contact_phone: string;
  status: 'AVAILABLE' | 'DISPATCHED' | 'OFF_DUTY';
  active_ticket_id?: string;
  active_ticket_title?: string;
  members_count: number;
  last_location: {
    lat: number;
    lng: number;
    address: string;
    updated_at: string;
  };
}

export interface Alert {
  id: string;
  title: string;
  message: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM';
  area: string;
  ward?: string;
  created_by: string;
  created_at: string;
  expires_at: string;
  active: boolean;
}

export interface RiskPrediction {
  id: string;
  ward: string;
  area_name: string;
  risk_type: string;
  risk_score: number; // 0-100 percentage
  risk_level: 'CRITICAL' | 'HIGH' | 'MEDIUM';
  forecast_time: string;
  weather_factor: string;
  recommended_action: string;
}

export interface AnalyticsSummary {
  active_incidents: number;
  critical_count: number;
  critical_incidents?: number;
  delayed_incidents?: number;
  average_resolution_hours?: number;
  teams_available: number;
  resolved_today: number;
  total_incidents: number;
  avg_response_minutes: number;
  resolution_rate_percent: number;
  department_breakdown: {
    department: string;
    active: number;
    resolved: number;
  }[];
  severity_distribution: {
    severity: IncidentSeverity;
    count: number;
  }[];
  weekly_trend: {
    day: string;
    reported: number;
    resolved: number;
  }[];
}


export interface FieldAssignment {
  ticket_id: string;
  incident_id: string;
  title: string;
  category: HazardCategory;
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  status: 'ACKNOWLEDGED' | 'EN_ROUTE' | 'ON_SITE' | 'RESOLVED';
  assigned_at: string;
  location: {
    lat: number;
    lng: number;
    address: string;
    ward: string;
  };
  image_url: string;
  description: string;
  notes?: string;
}

// ----------------- Civora Bus Observation Types (Phase 1 Contract) -----------------
export type DetectedCivicClass = 'pothole' | 'flooded_road' | 'garbage_pile' | 'damaged_road';

export interface ObservationCreatePayload {
  event_id: string;
  bus_id: string;
  route_id?: string;
  bus_display_name?: string;
  bus_status?: string;
  observed_at: string;
  latitude: number;
  longitude: number;
  detected_class: DetectedCivicClass;
  confidence: number;
  image_url?: string;
  severity?: string;
  source_metadata?: Record<string, any>;
  gnss_accuracy_meters?: number;
}

export type CorrelationType = 'new_issue' | 'corroboration' | 'reobservation';

export interface ObservationIngestResponse {
  observation_id: string;
  event_id: string;
  bus_id: string;
  detected_class: string;
  confidence: number;
  latitude: number;
  longitude: number;
  urban_issue_id: string;
  observation_count: number;
  distinct_bus_count: number;
  priority_score: number;
  priority_level: string;
  correlation_type: CorrelationType;
}

export interface SimulatorTimelineEvent {
  id: string;
  bus_id: string;
  route_id: string;
  detected_class: string;
  confidence: number;
  latitude: number;
  longitude: number;
  observed_at: string;
  correlation_type: CorrelationType;
  urban_issue_id: string;
  observation_count: number;
  distinct_bus_count: number;
  priority_score: number;
  priority_level: string;
}


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
