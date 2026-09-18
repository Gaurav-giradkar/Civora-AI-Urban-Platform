"""Update endpoints.ts to export new Phase 3 endpoints and map observation counts."""

ENDPOINTS_PATH = r"c:\My_stuff\Civora\frontend\src\api\endpoints.ts"

with open(ENDPOINTS_PATH, "r", encoding="utf-8") as f:
    content = f.read().replace("\r\n", "\n")

# 1. Update imports
old_import = """  HazardCategory,
  ObservationCreatePayload,
  ObservationIngestResponse,
} from '../types';"""

new_import = """  HazardCategory,
  ObservationCreatePayload,
  ObservationIngestResponse,
  BusUnit,
  ObservationDetail,
  CommandSummary,
} from '../types';"""

content = content.replace(old_import, new_import)

# 2. Update mapBackendIncident
old_map = """    department: row.department_name || (row.department_id ? 'Assigned Department' : 'Roads & Infrastructure'),
    ai_confidence: Math.round((row.confidence ?? 0.95) * 100),
    report_count: row.report_count ?? 1,
    image_url:
      row.image_url ||
      'https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?auto=format&fit=crop&w=800&q=80',
    reported_at: row.created_at || new Date().toISOString(),
    updated_at: row.resolved_at || row.created_at || new Date().toISOString(),
    assigned_team_id: row.assigned_team_id,
    assigned_team_name: row.assigned_team_name,"""

new_map = """    department: row.department_name || (row.department_id ? 'Assigned Department' : 'Roads & Infrastructure'),
    ai_confidence: Math.round((row.confidence ?? 0.95) * 100),
    report_count: row.report_count ?? 0,
    observation_count: row.observation_count ?? 0,
    distinct_bus_count: row.distinct_bus_count ?? 0,
    reobservation_count: row.reobservation_count ?? 0,
    first_observed_at: row.first_observed_at,
    last_observed_at: row.last_observed_at,
    image_url:
      row.image_url ||
      'https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?auto=format&fit=crop&w=800&q=80',
    reported_at: row.first_observed_at || row.created_at || new Date().toISOString(),
    updated_at: row.last_observed_at || row.resolved_at || row.created_at || new Date().toISOString(),
    assigned_team_id: row.assigned_team_id,
    assigned_team_name: row.assigned_team_name,"""

content = content.replace(old_map, new_map)

# 3. Add API functions at the bottom
new_endpoints = """
// ----------------- Command Center Intelligence Endpoints (Phase 3) -----------------
export async function getCommandSummaryApi(): Promise<CommandSummary> {
  const res = await apiClient.get('/api/observations/summary');
  return res.data;
}

export async function getBusesApi(): Promise<BusUnit[]> {
  const res = await apiClient.get('/api/observations/buses');
  return res.data;
}

export async function getObservationsApi(params?: {
  urban_issue_id?: string;
  bus_id?: string;
  limit?: number;
}): Promise<ObservationDetail[]> {
  const res = await apiClient.get('/api/observations', { params });
  return res.data;
}

export async function getIncidentObservationsApi(
  incidentId: string
): Promise<ObservationDetail[]> {
  const res = await apiClient.get(`/api/admin/incidents/${incidentId}/observations`);
  return res.data;
}
"""

if "export async function getCommandSummaryApi" not in content:
    content += new_endpoints

with open(ENDPOINTS_PATH, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated endpoints.ts successfully!")
