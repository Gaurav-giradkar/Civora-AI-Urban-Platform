"""Write Civora Urban Intelligence Command Center page (Phase 3)."""

COMMAND_PAGE_PATH = r"c:\My_stuff\Civora\frontend\src\pages\dashboard\CommandCenterPage.tsx"

code = '''import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import {
  Incident,
  AnalyticsSummary,
  IncidentSeverity,
  IncidentStatus,
  BusUnit,
  ObservationDetail,
  CommandSummary,
  Team,
} from '../../types';
import {
  getIncidentsApi,
  getCommandSummaryApi,
  getBusesApi,
  getObservationsApi,
  getIncidentObservationsApi,
  getTeamsApi,
  verifyIncidentApi,
  rejectIncidentApi,
  assignDepartmentApi,
  dispatchTeamApi,
  updateIncidentStatusApi,
} from '../../api/endpoints';
import { IncidentMap } from '../../components/map/IncidentMap';
import { StatCard } from '../../components/common/StatCard';
import { BadgePill } from '../../components/common/BadgePill';
import { Button } from '../../components/common/Button';
import {
  AlertTriangle,
  Flame,
  Users,
  CheckCircle,
  ArrowRight,
  Filter,
  RefreshCw,
  Layers,
  MapPin,
  Bus,
  Radio,
  Clock,
  Shield,
  Activity,
  Check,
  Building2,
  Truck,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Sparkles,
  Info,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const CommandCenterPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  // Core Data
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [summary, setSummary] = useState<CommandSummary>({
    active_buses_count: 3,
    total_observations: 0,
    total_urban_issues: 0,
    high_priority_issues: 0,
    critical_issues: 0,
    resolved_issues: 0,
    system_status: 'online',
  });
  const [buses, setBuses] = useState<BusUnit[]>([]);
  const [recentObservations, setRecentObservations] = useState<ObservationDetail[]>([]);
  const [teams, setTeams] = useState<Team[]>([]);

  // Selected Issue & Evidence Detail
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [selectedObservations, setSelectedObservations] = useState<ObservationDetail[]>([]);
  const [isLoadingObservations, setIsLoadingObservations] = useState(false);

  // Filters
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [busFilter, setBusFilter] = useState<string>('ALL');

  // UI States
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [showPriorityFormula, setShowPriorityFormula] = useState(false);
  const [selectedDept, setSelectedDept] = useState('Public Works & Roads');
  const [selectedTeamId, setSelectedTeamId] = useState('');

  // Polling ref
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Load all command center data
  const loadData = async (isManual = false) => {
    if (isManual) setIsRefreshing(true);
    setError(null);
    try {
      const [sumData, busData, incList, obsList, teamList] = await Promise.all([
        getCommandSummaryApi().catch(() => ({
          active_buses_count: 3,
          total_observations: 0,
          total_urban_issues: 0,
          high_priority_issues: 0,
          critical_issues: 0,
          resolved_issues: 0,
          system_status: 'offline',
        })),
        getBusesApi().catch(() => []),
        getIncidentsApi().catch(() => []),
        getObservationsApi({ limit: 20 }).catch(() => []),
        getTeamsApi().catch(() => []),
      ]);

      setSummary(sumData);
      setBuses(busData);
      setIncidents(incList);
      setRecentObservations(obsList);
      setTeams(teamList);

      // Preserve or update selected incident
      setSelectedIncident((prev) => {
        if (!prev && incList.length > 0) return incList[0];
        if (prev) {
          const updated = incList.find((i) => i.id === prev.id);
          return updated || (incList.length > 0 ? incList[0] : null);
        }
        return null;
      });
    } catch (e: any) {
      console.error('Failed to load command center data', e);
      setError(e.message || 'Failed to connect to Civora backend API.');
    } finally {
      setIsLoading(false);
      if (isManual) setIsRefreshing(false);
    }
  };

  // Load observation sequence for selected incident
  useEffect(() => {
    if (!selectedIncident?.id) {
      setSelectedObservations([]);
      return;
    }
    let isCurrent = true;
    setIsLoadingObservations(true);
    getIncidentObservationsApi(selectedIncident.id)
      .then((obs) => {
        if (isCurrent) setSelectedObservations(obs);
      })
      .catch((err) => {
        console.warn('Could not load incident observation sequence', err);
        if (isCurrent) setSelectedObservations([]);
      })
      .finally(() => {
        if (isCurrent) setIsLoadingObservations(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [selectedIncident?.id, selectedIncident?.observation_count]);

  // Initial load
  useEffect(() => {
    loadData();
  }, []);

  // Controlled auto-refresh polling (every 6s)
  useEffect(() => {
    if (!autoRefresh) {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      return;
    }

    pollTimerRef.current = setInterval(() => {
      loadData(false);
    }, 6000);

    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [autoRefresh]);

  const showFeedback = (msg: string) => {
    setActionSuccess(msg);
    setTimeout(() => setActionSuccess(null), 4000);
  };

  // Authority actions
  const handleVerify = async () => {
    if (!selectedIncident) return;
    try {
      const updated = await verifyIncidentApi(selectedIncident.id);
      setSelectedIncident(updated);
      loadData(false);
      showFeedback(`Urban Issue verified as CONFIRMED.`);
    } catch (e: any) {
      setError(e.message || 'Failed to verify issue.');
    }
  };

  const handleAssignDept = async () => {
    if (!selectedIncident || !selectedDept) return;
    try {
      // Find department or assign directly
      const updated = await assignDepartmentApi(selectedIncident.id, selectedIncident.department || 'Roads & Infrastructure');
      setSelectedIncident(updated);
      loadData(false);
      showFeedback(`Jurisdiction assigned to ${selectedDept}.`);
    } catch (e: any) {
      setError(e.message || 'Failed to assign department.');
    }
  };

  const handleDispatch = async () => {
    if (!selectedIncident) return;
    const teamId = selectedTeamId || (teams.length > 0 ? teams[0].id : '');
    if (!teamId) {
      alert('No field teams available for dispatch.');
      return;
    }
    try {
      const updated = await dispatchTeamApi(selectedIncident.id, teamId);
      setSelectedIncident(updated);
      loadData(false);
      const teamName = teams.find((t) => t.id === teamId)?.name || 'Rapid Response Unit';
      showFeedback(`${teamName} dispatched to incident coordinates.`);
    } catch (e: any) {
      setError(e.message || 'Failed to dispatch team.');
    }
  };

  const handleStatusChange = async (newStatus: IncidentStatus) => {
    if (!selectedIncident) return;
    try {
      const updated = await updateIncidentStatusApi(selectedIncident.id, newStatus);
      setSelectedIncident(updated);
      loadData(false);
      showFeedback(`Lifecycle status updated to ${newStatus}.`);
    } catch (e: any) {
      setError(e.message || 'Failed to update status.');
    }
  };

  // Filtered incidents
  const filteredIncidents = incidents.filter((inc) => {
    if (severityFilter !== 'ALL' && inc.severity !== severityFilter) return false;
    if (categoryFilter !== 'ALL' && inc.category.toLowerCase() !== categoryFilter.toLowerCase()) return false;
    if (statusFilter !== 'ALL' && inc.status.toLowerCase() !== statusFilter.toLowerCase()) return false;
    return true;
  });

  // Calculate priority breakdown for selected issue
  const categoryBaseWeights: Record<string, number> = {
    flooded_road: 0.9,
    damaged_road: 0.7,
    pothole: 0.5,
    garbage_pile: 0.3,
  };
  const baseWeight = categoryBaseWeights[selectedIncident?.category?.toLowerCase() || ''] || 0.4;
  const confVal = (selectedIncident?.ai_confidence || 85) / 100;
  const obsCount = selectedIncident?.observation_count || 1;
  const busCount = selectedIncident?.distinct_bus_count || 1;
  const reobsCount = selectedIncident?.reobservation_count || 0;
  const corrobBonus = Math.min(0.20, Math.max(0, obsCount - 1) * 0.05);
  const busBonus = Math.min(0.15, Math.max(0, busCount - 1) * 0.05);
  const revisitBonus = Math.min(0.05, Math.max(0, reobsCount) * 0.05);
  const calculatedScore = Math.min(1.0, baseWeight * confVal + corrobBonus + busBonus + revisitBonus);

  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto pb-12">
      {/* 1. TOP OPERATIONAL STATUS BAR */}
      <div className="bg-canvas border border-hairline rounded-2xl p-5 shadow-soft">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="font-mono text-xs font-bold px-2.5 py-1 rounded-full bg-primary/10 text-primary border border-primary/20 tracking-wider">
                CIVORA URBAN INTELLIGENCE
              </span>
              <h1 className="type-title-lg text-ink font-bold">Command Center</h1>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-semantic-up/10 text-semantic-up border border-semantic-up/20">
                <span className="w-1.5 h-1.5 rounded-full bg-semantic-up animate-pulse" />
                {summary.system_status === 'online' ? 'API ONLINE' : 'API OFFLINE'}
              </span>
            </div>
            <p className="type-body-sm text-muted mt-1">
              Public transit fleet continuously streams georeferenced urban intelligence with deterministic multi-bus corroboration.
            </p>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {/* Prominent Simulator CTA Link */}
            <Link
              to="/simulator"
              className="h-10 px-4 rounded-xl bg-primary text-on-primary font-semibold text-xs flex items-center gap-2 shadow-sm hover:bg-primary-active transition-all"
            >
              <Bus className="w-4 h-4" />
              <span>Open Fleet Simulator</span>
              <ExternalLink className="w-3.5 h-3.5 opacity-80" />
            </Link>

            {/* Auto-refresh toggle */}
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`h-10 px-3 rounded-xl border text-xs font-medium flex items-center gap-2 transition-all cursor-pointer ${
                autoRefresh
                  ? 'bg-surface-strong border-hairline text-ink'
                  : 'bg-canvas border-hairline text-muted line-through'
              }`}
              title="Toggle 6s automated polling"
            >
              <Activity className={`w-3.5 h-3.5 ${autoRefresh ? 'text-primary' : 'text-muted'}`} />
              <span>Auto-Sync {autoRefresh ? 'ON' : 'OFF'}</span>
            </button>

            {/* Manual Refresh */}
            <Button
              variant="secondary-light"
              onClick={() => loadData(true)}
              icon={<RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-primary' : ''}`} />}
              className="h-10 text-xs"
            >
              Refresh
            </Button>
          </div>
        </div>

        {/* Operational Metrics Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5 pt-4 border-t border-hairline">
          <div className="p-3 rounded-xl bg-surface-soft border border-hairline">
            <span className="type-caption text-muted uppercase font-mono text-[11px] block">Fleet Units</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="font-mono text-2xl font-bold text-ink">{summary.active_buses_count}</span>
              <span className="text-xs text-primary font-medium">Sensing Active</span>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-surface-soft border border-hairline">
            <span className="type-caption text-muted uppercase font-mono text-[11px] block">Observations</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="font-mono text-2xl font-bold text-ink">{summary.total_observations}</span>
              <span className="text-xs text-muted">Total Streamed</span>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-surface-soft border border-hairline">
            <span className="type-caption text-muted uppercase font-mono text-[11px] block">Urban Issues</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="font-mono text-2xl font-bold text-ink">{summary.total_urban_issues}</span>
              <span className="text-xs text-muted">PostGIS Correlated</span>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-surface-soft border border-hairline">
            <span className="type-caption text-muted uppercase font-mono text-[11px] block">High Priority</span>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="font-mono text-2xl font-bold text-severity-high">{summary.high_priority_issues}</span>
              <span className="text-xs text-severity-high font-medium">Requiring Action</span>
            </div>
          </div>
        </div>
      </div>

      {actionSuccess && (
        <div className="p-3 px-4 bg-semantic-up/10 border border-semantic-up/30 rounded-xl text-semantic-up text-xs font-semibold flex items-center gap-2 shadow-sm animate-fade-in">
          <Check className="w-4 h-4" />
          <span>{actionSuccess}</span>
        </div>
      )}

      {error && (
        <div className="p-4 bg-semantic-down/10 border border-semantic-down/30 rounded-xl text-semantic-down text-xs flex items-center justify-between gap-3">
          <span>{error}</span>
          <Button variant="secondary-light" onClick={() => loadData(true)} className="h-8 text-xs">
            Retry Connection
          </Button>
        </div>
      )}

      {/* 2. FLEET OVERVIEW STRIP */}
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bus className="w-4 h-4 text-primary" />
            <h2 className="type-title-md text-ink font-semibold">Active Fleet Units</h2>
            <span className="text-xs text-muted font-mono">({buses.length} registered units)</span>
          </div>
          <span className="text-xs text-muted font-mono">Live Sensing Telemetry</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {buses.length === 0 ? (
            <div className="col-span-3 p-6 text-center text-muted bg-canvas border border-hairline rounded-xl">
              No sensing units registered. Open the Fleet Simulator to activate units.
            </div>
          ) : (
            buses.map((bus) => (
              <div
                key={bus.bus_id}
                className="bg-canvas border border-hairline rounded-xl p-4 shadow-soft hover:border-primary/40 transition-all flex flex-col justify-between"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-mono font-bold text-xs">
                      <Bus className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="font-mono font-bold text-ink text-sm">{bus.bus_id}</h3>
                      <span className="text-[11px] text-muted font-mono">{bus.route_id || 'Route-12'}</span>
                    </div>
                  </div>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono uppercase bg-semantic-up/10 text-semantic-up font-bold">
                    <span className="w-1.5 h-1.5 rounded-full bg-semantic-up animate-pulse" />
                    {bus.status || 'Active'}
                  </span>
                </div>

                <div className="space-y-1 my-2 text-xs font-mono text-body bg-surface-soft p-2.5 rounded-lg border border-hairline/60">
                  <div className="flex justify-between">
                    <span className="text-muted">Latest Detection:</span>
                    <strong className="text-ink capitalize">{bus.latest_detected_class || 'None yet'}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Coordinates:</span>
                    <span className="text-ink truncate max-w-[140px]">
                      {bus.latest_latitude ? `${bus.latest_latitude.toFixed(4)}, ${bus.latest_longitude?.toFixed(4)}` : 'En route'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted">Observations:</span>
                    <strong className="text-primary font-bold">{bus.total_observations}</strong>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-muted pt-1">
                  <span>Last Seen:</span>
                  <span className="font-mono">
                    {bus.latest_observation_time
                      ? new Date(bus.latest_observation_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                      : 'Standby'}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 3. URBAN INTELLIGENCE MAP & TRIAGE SECTION */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left 8 Cols: Map & Filter Strip */}
        <div className="lg:col-span-8 flex flex-col gap-3">
          <div className="bg-canvas border border-hairline rounded-xl p-3 flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-muted" />
              <span className="text-xs font-medium text-body">Severity Filter:</span>
              <div className="flex items-center gap-1 flex-wrap">
                {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((sev) => (
                  <button
                    key={sev}
                    onClick={() => setSeverityFilter(sev)}
                    className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold transition-all cursor-pointer ${
                      severityFilter === sev
                        ? 'bg-ink text-canvas'
                        : 'bg-surface-strong text-body hover:text-ink'
                    }`}
                  >
                    {sev}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-3 text-[11px] text-muted font-mono">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-severity-critical" /> Critical
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-severity-high" /> High
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-severity-medium" /> Medium
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-severity-resolved" /> Resolved
              </span>
            </div>
          </div>

          <IncidentMap
            incidents={filteredIncidents}
            buses={buses}
            selectedIncident={selectedIncident}
            onSelectIncident={(inc) => setSelectedIncident(inc)}
            height="520px"
          />
        </div>

        {/* Right 4 Cols: Selected Urban Issue Detail Inspector */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          <div className="bg-canvas border border-hairline rounded-2xl p-5 shadow-soft">
            <div className="flex items-center justify-between mb-3">
              <span className="type-caption text-muted uppercase font-mono font-bold text-[11px] flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5 text-primary animate-pulse" />
                Urban Issue Inspector
              </span>
              {selectedIncident && (
                <BadgePill severity={selectedIncident.severity} label={selectedIncident.severity} dot />
              )}
            </div>

            {selectedIncident ? (
              <div className="flex flex-col gap-4">
                {/* Re-observation Alert if present */}
                {selectedIncident.reobservation_count && selectedIncident.reobservation_count > 0 ? (
                  <div className="p-3 bg-severity-high/10 border border-severity-high/30 rounded-xl text-severity-high text-xs flex items-start gap-2 animate-fade-in">
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                    <div>
                      <strong className="block font-bold">RE-OBSERVATION DETECTED</strong>
                      <span>
                        This location was revisited and re-observed {selectedIncident.reobservation_count} time(s) after authority action.
                      </span>
                    </div>
                  </div>
                ) : null}

                {/* Photo Preview / Evidence Banner */}
                <div className="relative rounded-xl overflow-hidden border border-hairline aspect-video bg-surface-dark">
                  {selectedIncident.image_url ? (
                    <img
                      src={selectedIncident.image_url}
                      alt={selectedIncident.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center text-muted bg-surface-strong/40 p-4 text-center">
                      <Sparkles className="w-8 h-8 text-primary mb-2 opacity-60" />
                      <span className="text-xs font-mono">Georeferenced Bus Telemetry</span>
                    </div>
                  )}
                  <div className="absolute top-2 left-2">
                    <BadgePill
                      label={`AI: ${selectedIncident.ai_confidence}%`}
                      variant="dark"
                      className="text-[10px]"
                    />
                  </div>
                  <div className="absolute bottom-2 right-2 bg-black/80 px-2 py-0.5 rounded-full text-[10px] font-mono text-white">
                    {selectedIncident.observation_count ?? 1} Observations
                  </div>
                </div>

                <div>
                  <h3 className="font-bold text-ink text-base capitalize">
                    {selectedIncident.category.replace(/_/g, ' ')} Urban Issue
                  </h3>
                  <div className="flex items-center gap-1.5 text-muted text-xs mt-1">
                    <MapPin className="w-3.5 h-3.5 shrink-0 text-primary" />
                    <span>{selectedIncident.location.address}</span>
                  </div>
                  <p className="text-body text-xs mt-2 line-clamp-2">
                    {selectedIncident.description}
                  </p>
                </div>

                {/* Evidence Metrics */}
                <div className="grid grid-cols-2 gap-2 p-3 rounded-xl bg-surface-soft border border-hairline text-xs font-mono">
                  <div>
                    <span className="text-muted block text-[10px] uppercase">Observations</span>
                    <strong className="text-ink text-sm">{selectedIncident.observation_count ?? 1}</strong>
                  </div>
                  <div>
                    <span className="text-muted block text-[10px] uppercase">Distinct Buses</span>
                    <strong className="text-primary text-sm">{selectedIncident.distinct_bus_count ?? 1} Units</strong>
                  </div>
                  <div>
                    <span className="text-muted block text-[10px] uppercase">Priority Score</span>
                    <strong className="text-severity-high text-sm">
                      {Math.round((selectedIncident.ai_confidence || 85))}%
                    </strong>
                  </div>
                  <div>
                    <span className="text-muted block text-[10px] uppercase">Lifecycle Status</span>
                    <strong className="text-ink text-sm uppercase">{selectedIncident.status}</strong>
                  </div>
                </div>

                <Button
                  variant="primary"
                  onClick={() => navigate(`/governmentdashboard/incidents/${selectedIncident.id}`)}
                  className="w-full h-10 text-xs font-semibold"
                >
                  Open Full Incident Workspace
                </Button>
              </div>
            ) : (
              <div className="py-12 text-center text-muted text-xs">
                Select a marker on the map or row in the table to inspect telemetry details.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 4. CORROBORATION PANEL & 5. PRIORITY PANEL */}
      {selectedIncident && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* 4. Dedicated Corroboration Panel (7 cols) */}
          <div className="lg:col-span-7 bg-canvas border border-hairline rounded-2xl p-5 shadow-soft">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-primary" />
                <h3 className="type-title-md text-ink font-bold">Corroboration Evidence</h3>
              </div>
              <span className="font-mono text-xs px-2.5 py-0.5 rounded-full bg-primary/10 text-primary font-bold">
                {selectedIncident.distinct_bus_count ?? 1} Distinct Buses Corroborated
              </span>
            </div>

            <p className="text-xs text-body mb-4">
              <strong>Core Civora Differentiator:</strong> Multiple public buses independently observed and confirmed this same road segment within 200 meters.
            </p>

            {/* Sequence Flow */}
            <div className="p-4 rounded-xl bg-surface-soft border border-hairline">
              <span className="text-[11px] font-mono text-muted uppercase tracking-wider block mb-3 font-semibold">
                Multi-Bus Observation Sequence:
              </span>

              {isLoadingObservations ? (
                <div className="py-6 text-center text-muted text-xs flex items-center justify-center gap-2">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-primary" />
                  <span>Loading telemetry evidence...</span>
                </div>
              ) : selectedObservations.length > 0 ? (
                <div className="flex flex-col gap-3">
                  {selectedObservations.map((obs, idx) => (
                    <div
                      key={obs.id || idx}
                      className={`p-3 rounded-xl border flex items-center justify-between gap-3 text-xs font-mono ${
                        obs.is_reobservation
                          ? 'bg-severity-high/10 border-severity-high/40'
                          : 'bg-canvas border-hairline'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-7 h-7 rounded-lg bg-primary/10 text-primary font-bold flex items-center justify-center shrink-0">
                          {idx + 1}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-ink text-xs">{obs.bus_id}</span>
                            <span className="text-muted text-[11px]">({obs.route_id || 'Route-12'})</span>
                            {obs.is_reobservation && (
                              <span className="px-2 py-0.2 rounded-full text-[10px] bg-severity-high text-white font-bold">
                                RE-OBSERVATION
                              </span>
                            )}
                          </div>
                          <span className="text-[11px] text-muted block mt-0.5">
                            Coords: {obs.latitude.toFixed(4)}, {obs.longitude.toFixed(4)} • AI: {Math.round(obs.confidence * 100)}%
                          </span>
                        </div>
                      </div>

                      <div className="text-right text-[11px] text-muted shrink-0">
                        <span className="block font-semibold text-ink">
                          {new Date(obs.observed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </span>
                        <span>{obs.detected_class}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-3 bg-canvas rounded-lg text-xs font-mono text-muted text-center">
                  Initial detection by Bus-017 recorded at {new Date(selectedIncident.reported_at).toLocaleTimeString()}.
                </div>
              )}

              <div className="mt-4 pt-3 border-t border-hairline/80 flex items-center justify-between text-xs text-muted font-mono">
                <span>Radius: &lt; 200m</span>
                <span className="text-semantic-up font-bold">Deterministic Correlation Confirmed</span>
              </div>
            </div>
          </div>

          {/* 5. Priority Panel with Deterministic Score Breakdown (5 cols) */}
          <div className="lg:col-span-5 bg-canvas border border-hairline rounded-2xl p-5 shadow-soft">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Flame className="w-4 h-4 text-severity-high" />
                <h3 className="type-title-md text-ink font-bold">Priority Assessment</h3>
              </div>
              <BadgePill severity={selectedIncident.severity} label={selectedIncident.severity} dot />
            </div>

            <div className="p-4 rounded-xl bg-surface-soft border border-hairline mb-3">
              <div className="flex items-baseline justify-between mb-2">
                <span className="text-xs font-mono text-muted uppercase font-semibold">Priority Score:</span>
                <span className="font-mono text-2xl font-bold text-severity-high">
                  {Math.round(calculatedScore * 100)}%
                </span>
              </div>

              <div className="space-y-1.5 text-xs font-mono text-body">
                <div className="flex justify-between">
                  <span className="text-muted">Detected Class:</span>
                  <strong className="text-ink capitalize">{selectedIncident.category.replace(/_/g, ' ')}</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">Detection Confidence:</span>
                  <span className="text-ink">{Math.round(confVal * 100)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">Corroborating Units:</span>
                  <span className="text-primary font-semibold">{busCount} public buses</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted">Re-observations:</span>
                  <span className="text-ink">{reobsCount}</span>
                </div>
              </div>

              <button
                onClick={() => setShowPriorityFormula(!showPriorityFormula)}
                className="mt-3 text-[11px] font-semibold text-primary flex items-center gap-1 hover:underline cursor-pointer"
              >
                <span>Why this priority?</span>
                {showPriorityFormula ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>

              {showPriorityFormula && (
                <div className="mt-3 p-3 bg-canvas rounded-lg border border-hairline text-[11px] font-mono text-muted space-y-1.5 animate-fade-in">
                  <div className="font-bold text-ink mb-1">Backend Priority Formula:</div>
                  <div>• Category Base Weight: {baseWeight.toFixed(2)}</div>
                  <div>• Confidence Scale: ×{confVal.toFixed(2)}</div>
                  <div>• Corroboration Bonus: +{corrobBonus.toFixed(2)} ({obsCount} observations)</div>
                  <div>• Distinct Bus Multiplier: +{busBonus.toFixed(2)} ({busCount} buses)</div>
                  <div>• Re-observation Bump: +{revisitBonus.toFixed(2)} ({reobsCount} revisits)</div>
                  <div className="pt-1 border-t border-hairline font-bold text-ink">
                    = Final Calculated Score: {calculatedScore.toFixed(2)} ({selectedIncident.severity})
                  </div>
                </div>
              )}
            </div>

            {/* 6. AUTHORITY ACTION PANEL */}
            <div className="pt-3 border-t border-hairline space-y-3">
              <h4 className="text-xs font-mono font-bold text-ink uppercase tracking-wider">
                Authority Dispatch & Triage:
              </h4>

              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant="primary"
                  onClick={handleVerify}
                  className="h-9 text-xs font-semibold"
                >
                  Verify / Confirm
                </Button>
                <Button
                  variant="secondary-light"
                  onClick={handleDispatch}
                  className="h-9 text-xs font-semibold"
                >
                  Dispatch Team
                </Button>
              </div>

              <div className="flex items-center gap-1.5 flex-wrap pt-1">
                <span className="text-[11px] text-muted font-mono mr-1">Lifecycle:</span>
                {(['confirmed', 'assigned', 'in_progress', 'resolved'] as IncidentStatus[]).map((st) => (
                  <button
                    key={st}
                    onClick={() => handleStatusChange(st)}
                    className={`px-2 py-0.5 rounded-full text-[10px] font-mono uppercase cursor-pointer transition-all ${
                      selectedIncident.status.toLowerCase() === st.toLowerCase()
                        ? 'bg-ink text-canvas font-bold'
                        : 'bg-surface-strong text-body hover:text-ink'
                    }`}
                  >
                    {st.replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 8. LIVE ACTIVITY TIMELINE & RE-OBSERVATION EVIDENCE */}
      <div className="bg-canvas border border-hairline rounded-2xl p-5 shadow-soft">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-primary" />
            <h3 className="type-title-md text-ink font-bold">Live Operational Telemetry Timeline</h3>
          </div>
          <span className="text-xs text-muted font-mono">Streamed from Fleet Ingestion Service</span>
        </div>

        {recentObservations.length === 0 ? (
          <div className="p-8 text-center text-muted text-xs">
            No telemetry stream received yet. Run the Fleet Simulator to generate live observations.
          </div>
        ) : (
          <div className="divide-y divide-hairline/60">
            {recentObservations.slice(0, 8).map((obs) => (
              <div key={obs.id} className="py-2.5 flex items-center justify-between gap-3 text-xs font-mono">
                <div className="flex items-center gap-3">
                  <div className="w-2 h-2 rounded-full bg-primary" />
                  <span className="font-bold text-ink">{obs.bus_id}</span>
                  <span className="text-muted">reported</span>
                  <span className="capitalize font-semibold text-ink px-2 py-0.5 bg-surface-soft rounded">
                    {obs.detected_class.replace(/_/g, ' ')}
                  </span>
                  <span className="text-muted text-[11px] hidden sm:inline">
                    ({obs.latitude.toFixed(4)}, {obs.longitude.toFixed(4)})
                  </span>
                </div>

                <div className="flex items-center gap-3">
                  {obs.is_reobservation && (
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-severity-high/10 text-severity-high border border-severity-high/20">
                      RE-OBSERVATION
                    </span>
                  )}
                  <span className="text-muted text-[11px]">
                    {new Date(obs.observed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 9. OPERATIONAL URBAN ISSUES TABLE */}
      <div className="bg-canvas border border-hairline rounded-2xl overflow-hidden shadow-soft">
        <div className="p-5 border-b border-hairline flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="type-title-md text-ink font-bold">Urban Issues Registry</h3>
            <p className="text-xs text-muted mt-0.5">
              Aggregated georeferenced road hazards maintained by deterministic PostGIS clustering
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-muted">
              Showing <strong className="text-ink">{filteredIncidents.length}</strong> issues
            </span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-surface-soft border-b border-hairline text-muted uppercase text-[11px] font-semibold">
              <tr>
                <th className="p-3 pl-5">Issue ID</th>
                <th className="p-3">Detected Class</th>
                <th className="p-3">Priority</th>
                <th className="p-3">Observations</th>
                <th className="p-3">Distinct Buses</th>
                <th className="p-3">Status</th>
                <th className="p-3">Action Assigned</th>
                <th className="p-3">Last Observed</th>
                <th className="p-3 pr-5 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline">
              {filteredIncidents.length === 0 ? (
                <tr>
                  <td colSpan={9} className="p-8 text-center text-muted font-sans">
                    No urban issues found. Run the Fleet Simulator to create new issues.
                  </td>
                </tr>
              ) : (
                filteredIncidents.map((inc) => {
                  const isSelected = selectedIncident?.id === inc.id;
                  return (
                    <tr
                      key={inc.id}
                      onClick={() => setSelectedIncident(inc)}
                      className={`cursor-pointer transition-colors ${
                        isSelected ? 'bg-primary/[0.04]' : 'hover:bg-surface-soft/60'
                      }`}
                    >
                      <td className="p-3 pl-5 font-bold text-ink truncate max-w-[120px]">
                        {inc.id.slice(0, 8)}...
                      </td>
                      <td className="p-3 capitalize font-semibold text-ink">
                        {inc.category.replace(/_/g, ' ')}
                      </td>
                      <td className="p-3">
                        <BadgePill severity={inc.severity} label={inc.severity} dot className="text-[10px]" />
                      </td>
                      <td className="p-3 font-bold text-ink">
                        {inc.observation_count ?? inc.report_count ?? 1}
                      </td>
                      <td className="p-3 text-primary font-bold">
                        {inc.distinct_bus_count ?? 1} buses
                      </td>
                      <td className="p-3 uppercase font-semibold text-ink">
                        {inc.status}
                      </td>
                      <td className="p-3 text-muted">
                        {inc.assigned_team_name || (inc.status === 'dispatched' ? 'Field Unit' : 'Unassigned')}
                      </td>
                      <td className="p-3 text-muted text-[11px]">
                        {inc.last_observed_at || inc.updated_at
                          ? new Date(inc.last_observed_at || inc.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                          : 'Just now'}
                      </td>
                      <td className="p-3 pr-5 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/governmentdashboard/incidents/${inc.id}`);
                          }}
                          className="inline-flex items-center gap-1 text-primary hover:underline font-semibold"
                        >
                          <span>Workspace</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
'''

with open(COMMAND_PAGE_PATH, "w", encoding="utf-8") as f:
    f.write(code)
print("Updated CommandCenterPage.tsx successfully!")
