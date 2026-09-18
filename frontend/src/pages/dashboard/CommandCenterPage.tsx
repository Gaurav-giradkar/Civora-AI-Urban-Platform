import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Incident,
  BusUnit,
  ObservationDetail,
  CommandSummary,
  IncidentSeverity,
} from '../../types';
import {
  getIncidentsApi,
  getCommandSummaryApi,
  getBusesApi,
  getIncidentObservationsApi,
  verifyIncidentApi,
  rejectIncidentApi,
} from '../../api/endpoints';
import { IncidentMap } from '../../components/map/IncidentMap';
import { StatCard } from '../../components/common/StatCard';
import { BadgePill } from '../../components/common/BadgePill';
import { Button } from '../../components/common/Button';
import {
  AlertTriangle,
  Flame,
  CheckCircle,
  ArrowRight,
  Filter,
  RefreshCw,
  MapPin,
  Bus,
  Eye,
  Layers,
  Activity,
  Wifi,
  WifiOff,
  Clock,
  RotateCcw,
  Shield,
  TrendingUp,
  ChevronRight,
  AlertCircle,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { guestStore } from '../../api/seedData';

// ─── helpers ────────────────────────────────────────────────────────────────
function fmtTime(iso?: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return '—';
  }
}

function fmtShortTime(iso?: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '—';
  }
}

function classLabel(cls: string) {
  return cls.replace(/_/g, ' ');
}

const AUTO_REFRESH_INTERVAL_MS = 6000;

// ─── component ──────────────────────────────────────────────────────────────
export const CommandCenterPage: React.FC = () => {
  const { isGuestMode } = useAuth();
  const navigate = useNavigate();

  // ── state ─────────────────────────────────────────────────────────────────
  const [commandSummary, setCommandSummary] = useState<CommandSummary | null>(null);
  const [buses, setBuses] = useState<BusUnit[]>([]);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [selectedObs, setSelectedObs] = useState<ObservationDetail[]>([]);
  const [severityFilter, setSeverityFilter] = useState<string>('ALL');
  const [isLoading, setIsLoading] = useState(true);
  const [obsLoading, setObsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAutoRefresh, setIsAutoRefresh] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const selectedIncidentIdRef = useRef<string | null>(null);

  // ── data loading ──────────────────────────────────────────────────────────

  const loadAll = useCallback(async (isManual = false) => {
    if (isManual) setIsLoading(true);
    setError(null);
    try {
      if (isGuestMode) {
        // Guest demo mode — read-only seed store, no backend requests
        const incList = guestStore.getIncidents();
        setIncidents(incList);
        if (incList.length > 0 && !selectedIncidentIdRef.current) {
          setSelectedIncident(incList[0]);
          selectedIncidentIdRef.current = incList[0].id;
        }
      } else {
        const [summary, busData, incData] = await Promise.all([
          getCommandSummaryApi(),
          getBusesApi(),
          getIncidentsApi(),
        ]);
        setCommandSummary(summary);
        setBuses(busData);
        setIncidents(incData);

        // Preserve selected incident if still present; auto-select first if none
        if (incData.length > 0 && !selectedIncidentIdRef.current) {
          setSelectedIncident(incData[0]);
          selectedIncidentIdRef.current = incData[0].id;
        } else if (selectedIncidentIdRef.current) {
          const refreshed = incData.find((i) => i.id === selectedIncidentIdRef.current);
          if (refreshed) setSelectedIncident(refreshed);
        }
      }
      setLastRefreshed(new Date());
    } catch (e: any) {
      const status = e?.response?.status;
      if (status === 401 || status === 403) {
        setError('Session expired or access denied. Please log in again.');
      } else if (status === 500) {
        setError('Backend server error. Please check API logs.');
      } else if (e?.code === 'ERR_NETWORK' || e?.message?.includes('Network')) {
        setError('Cannot reach backend — is the FastAPI server running on localhost:8000?');
      } else {
        setError(e.message || 'Failed to load Command Center data.');
      }
    } finally {
      if (isManual) setIsLoading(false);
      else setIsLoading(false);
    }
  }, [isGuestMode]);

  // Load observation sequence whenever a different incident is selected
  const loadIncidentObservations = useCallback(async (incidentId: string) => {
    if (isGuestMode) {
      setSelectedObs([]);
      return;
    }
    setObsLoading(true);
    try {
      const obs = await getIncidentObservationsApi(incidentId);
      setSelectedObs(obs);
    } catch {
      setSelectedObs([]);
    } finally {
      setObsLoading(false);
    }
  }, [isGuestMode]);

  // Select incident handler — update ref + load its observations
  const handleSelectIncident = useCallback((inc: Incident) => {
    setSelectedIncident(inc);
    selectedIncidentIdRef.current = inc.id;
    loadIncidentObservations(inc.id);
  }, [loadIncidentObservations]);

  // Initial load
  useEffect(() => {
    loadAll(true);
  }, [loadAll]);

  // Auto-refresh polling
  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (isAutoRefresh && !isGuestMode) {
      intervalRef.current = setInterval(() => {
        loadAll(false);
        if (selectedIncidentIdRef.current) {
          loadIncidentObservations(selectedIncidentIdRef.current);
        }
      }, AUTO_REFRESH_INTERVAL_MS);
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [isAutoRefresh, isGuestMode, loadAll, loadIncidentObservations]);

  // Reload observations when selected incident changes externally
  useEffect(() => {
    if (selectedIncident?.id) {
      loadIncidentObservations(selectedIncident.id);
    }
  }, [selectedIncident?.id, loadIncidentObservations]);

  // ── derived ───────────────────────────────────────────────────────────────
  const filteredIncidents = incidents.filter((inc) => {
    if (severityFilter === 'ALL') return true;
    return inc.severity === (severityFilter as IncidentSeverity);
  });

  const hasReobservation =
    (selectedIncident?.reobservation_count ?? 0) > 0;

  const reobsObs = selectedObs.filter((o) => o.is_reobservation);
  const corrobObs = selectedObs.filter((o) => !o.is_reobservation);

  // ── render helpers ────────────────────────────────────────────────────────
  const summaryCards = commandSummary
    ? [
        {
          label: 'Active Buses',
          value: commandSummary.active_buses_count,
          subtext: 'Sensing units online',
          icon: <Bus className="w-4 h-4 text-primary" />,
        },
        {
          label: 'Total Observations',
          value: commandSummary.total_observations,
          subtext: 'Bus telemetry events',
          icon: <Eye className="w-4 h-4 text-primary" />,
        },
        {
          label: 'Urban Issues',
          value: commandSummary.total_urban_issues,
          subtext: 'Corroborated by fleet',
          icon: <AlertTriangle className="w-4 h-4 text-severity-high" />,
        },
        {
          label: 'High Priority',
          value: commandSummary.high_priority_issues,
          subtext: 'High + Critical issues',
          icon: <Flame className="w-4 h-4 text-severity-critical" />,
          highlight: commandSummary.high_priority_issues > 0,
        },
        {
          label: 'Critical',
          value: commandSummary.critical_issues,
          subtext: 'Immediate response',
          icon: <AlertCircle className="w-4 h-4 text-severity-critical" />,
        },
        {
          label: 'Resolved',
          value: commandSummary.resolved_issues,
          subtext: 'Verified proof of repair',
          icon: <CheckCircle className="w-4 h-4 text-semantic-up" />,
        },
      ]
    : null;

  // ── component ─────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-6 max-w-7xl mx-auto">

      {/* ── Header ── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-primary" />
            <h1 className="type-title-lg text-ink font-semibold">
              Civora Urban Intelligence Command Center
            </h1>
            <BadgePill label="LIVE" variant="neutral" dot />
          </div>
          <p className="type-body-sm text-muted mt-1">
            Real-time geospatial telemetry from fleet sensing units · corroboration · authority actions
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Auto-refresh toggle */}
          <button
            onClick={() => setIsAutoRefresh((v) => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-pill text-[12px] font-semibold border transition-all cursor-pointer ${
              isAutoRefresh
                ? 'bg-semantic-up/10 border-semantic-up/40 text-semantic-up'
                : 'bg-surface-strong border-hairline text-muted'
            }`}
            title={`Auto-refresh every ${AUTO_REFRESH_INTERVAL_MS / 1000}s — click to ${isAutoRefresh ? 'pause' : 'resume'}`}
          >
            {isAutoRefresh ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
            {isAutoRefresh ? `Auto·${AUTO_REFRESH_INTERVAL_MS / 1000}s` : 'Paused'}
          </button>

          {lastRefreshed && (
            <span className="text-[11px] text-muted font-mono hidden sm:block">
              {fmtShortTime(lastRefreshed.toISOString())}
            </span>
          )}

          <Button
            variant="secondary-light"
            onClick={() => loadAll(true)}
            icon={<RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />}
            className="h-10 text-[13px]"
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            onClick={() => navigate('/governmentdashboard/incidents')}
            icon={<ArrowRight className="w-4 h-4" />}
            iconPosition="right"
            className="h-10 text-[13px]"
          >
            Incidents Feed
          </Button>
        </div>
      </div>

      {/* ── Error Banner ── */}
      {error && (
        <div className="p-4 bg-semantic-down/10 border border-semantic-down/30 rounded-xl text-semantic-down text-[13px] flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <Button variant="secondary-light" onClick={() => loadAll(true)} className="h-8 text-[12px]">
            Retry
          </Button>
        </div>
      )}

      {/* ── Guest mode notice ── */}
      {isGuestMode && (
        <div className="p-3 bg-surface-strong border border-hairline rounded-xl text-[13px] text-muted flex items-center gap-2">
          <Activity className="w-4 h-4 text-primary shrink-0" />
          <span>Viewing demo data — fleet + corroboration metrics are simulated. Log in for real backend data.</span>
        </div>
      )}

      {/* ── Command Summary Strip (real backend) ── */}
      {!isGuestMode && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4 text-primary" />
            <span className="text-[13px] font-semibold text-ink">Fleet Intelligence Summary</span>
            <span className={`ml-auto text-[11px] font-mono px-2 py-0.5 rounded-full ${
              commandSummary?.system_status === 'online'
                ? 'bg-semantic-up/10 text-semantic-up'
                : 'bg-surface-strong text-muted'
            }`}>
              {commandSummary?.system_status?.toUpperCase() ?? 'CONNECTING…'}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {summaryCards
              ? summaryCards.map((card) => (
                  <StatCard
                    key={card.label}
                    label={card.label}
                    value={card.value}
                    subtext={card.subtext}
                    icon={card.icon}
                    highlight={card.highlight}
                  />
                ))
              : Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="h-20 rounded-xl bg-surface-strong animate-pulse" />
                ))}
          </div>
        </div>
      )}

      {/* ── Map + Inspector Grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">

        {/* Left: Severity filter + Map */}
        <div className="lg:col-span-8 flex flex-col gap-3">
          {/* Severity filter */}
          <div className="bg-canvas border border-hairline rounded-lg p-3 flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-muted" />
              <span className="text-[13px] font-medium text-body">Severity:</span>
              <div className="flex items-center gap-1.5 flex-wrap">
                {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((sev) => (
                  <button
                    key={sev}
                    onClick={() => setSeverityFilter(sev)}
                    className={`px-2.5 py-1 rounded-pill text-[11px] font-semibold transition-all cursor-pointer ${
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
            <div className="flex items-center gap-3 text-[12px] text-muted">
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-severity-critical" /> Critical</span>
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-severity-high" /> High</span>
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-severity-medium" /> Medium</span>
              <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-severity-resolved" /> Resolved</span>
            </div>
          </div>

          {/* Leaflet Map — receives real buses + incidents */}
          <IncidentMap
            incidents={filteredIncidents}
            buses={isGuestMode ? [] : buses}
            selectedIncident={selectedIncident}
            onSelectIncident={handleSelectIncident}
            height="540px"
          />
        </div>

        {/* Right: Pin Inspector + Corroboration Panel */}
        <div className="lg:col-span-4 flex flex-col gap-4">

          {/* Pin Inspector */}
          <div className="bg-canvas border border-hairline rounded-xl p-5 shadow-soft">
            <div className="flex items-center justify-between mb-3">
              <span className="type-caption text-muted uppercase font-semibold">Pin Inspector</span>
              {selectedIncident && (
                <BadgePill severity={selectedIncident.severity} label={selectedIncident.severity} dot />
              )}
            </div>

            {selectedIncident ? (
              <div className="flex flex-col gap-4">
                {/* Photo */}
                <div className="relative rounded-lg overflow-hidden border border-hairline aspect-video bg-surface-dark">
                  <img
                    src={selectedIncident.image_url}
                    alt={selectedIncident.title}
                    className="w-full h-full object-cover"
                  />
                  <div className="absolute top-2 left-2">
                    <BadgePill label={`AI: ${selectedIncident.ai_confidence}%`} variant="dark" className="text-[10px]" />
                  </div>
                  <div className="absolute bottom-2 right-2 bg-black/70 px-2 py-0.5 rounded text-[11px] font-mono text-white">
                    {selectedIncident.observation_count ?? selectedIncident.report_count} obs
                  </div>
                </div>

                <div>
                  <h3 className="font-semibold text-ink text-[15px] leading-snug">{selectedIncident.title}</h3>
                  <div className="flex items-center gap-1.5 text-muted text-[13px] mt-1">
                    <MapPin className="w-3.5 h-3.5 shrink-0" />
                    <span>{selectedIncident.location.address}</span>
                  </div>
                </div>

                {/* Evidence quick row */}
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="bg-surface-strong rounded-lg p-2">
                    <div className="text-[11px] text-muted">Buses</div>
                    <div className="font-mono font-bold text-ink text-[15px]">
                      {selectedIncident.distinct_bus_count ?? '—'}
                    </div>
                  </div>
                  <div className="bg-surface-strong rounded-lg p-2">
                    <div className="text-[11px] text-muted">Observations</div>
                    <div className="font-mono font-bold text-ink text-[15px]">
                      {selectedIncident.observation_count ?? '—'}
                    </div>
                  </div>
                  <div className="bg-surface-strong rounded-lg p-2">
                    <div className="text-[11px] text-muted">Re-obs</div>
                    <div className={`font-mono font-bold text-[15px] ${hasReobservation ? 'text-semantic-down' : 'text-muted'}`}>
                      {selectedIncident.reobservation_count ?? 0}
                    </div>
                  </div>
                </div>

                {/* Priority badge */}
                <div className="flex items-center justify-between text-[13px] pt-2 border-t border-hairline">
                  <span className="text-muted">Priority score:</span>
                  <span className="font-mono font-bold text-primary">{selectedIncident.ai_confidence}% · {selectedIncident.severity}</span>
                </div>

                <Button
                  variant="primary"
                  onClick={() => navigate(`/governmentdashboard/incidents/${selectedIncident.id}`)}
                  className="w-full h-11 text-[14px]"
                >
                  Open Incident Workspace
                </Button>
              </div>
            ) : (
              <div className="py-12 text-center text-muted text-[14px]">
                Select a marker on the map to inspect telemetry.
              </div>
            )}
          </div>

          {/* Corroboration Panel */}
          <div className="bg-canvas border border-hairline rounded-xl p-5 shadow-soft">
            <div className="flex items-center gap-2 mb-3">
              <Layers className="w-4 h-4 text-primary" />
              <span className="type-caption text-muted uppercase font-semibold">Corroboration Evidence</span>
            </div>

            {!selectedIncident ? (
              <p className="text-[13px] text-muted text-center py-6">Select an Urban Issue to view its observation sequence.</p>
            ) : obsLoading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-12 rounded-lg bg-surface-strong animate-pulse" />
                ))}
              </div>
            ) : selectedObs.length === 0 ? (
              <p className="text-[13px] text-muted text-center py-6">
                {isGuestMode ? 'Observation data unavailable in demo mode.' : 'No observations recorded for this issue yet.'}
              </p>
            ) : (
              <div className="flex flex-col gap-0">
                {/* Summary line */}
                {selectedIncident.distinct_bus_count && selectedIncident.distinct_bus_count > 0 && (
                  <div className="mb-3 px-3 py-2 rounded-lg bg-primary/8 border border-primary/20 text-[12px] font-semibold text-primary">
                    {selectedIncident.distinct_bus_count} bus{selectedIncident.distinct_bus_count > 1 ? 'es' : ''}
                    {' '}independently observed this location
                  </div>
                )}

                {/* Observation sequence */}
                <div className="relative pl-5 border-l-2 border-hairline flex flex-col gap-3 max-h-72 overflow-y-auto pr-1">
                  {corrobObs.map((obs, idx) => (
                    <div key={obs.id} className="relative">
                      <div className={`absolute -left-[23px] top-1.5 w-2.5 h-2.5 rounded-full border-2 border-canvas ${
                        idx === 0 ? 'bg-primary' : 'bg-severity-high'
                      }`} />
                      <div className="bg-surface-strong rounded-lg p-2.5 text-[12px]">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="font-mono font-bold text-primary flex items-center gap-1">
                            <Bus className="w-3 h-3" /> {obs.bus_id}
                          </span>
                          <span className="font-mono text-muted text-[10px]">{fmtTime(obs.observed_at)}</span>
                        </div>
                        <div className="text-body capitalize">{classLabel(obs.detected_class)}</div>
                        <div className="text-muted text-[11px]">
                          Confidence: <span className="font-mono text-ink">{Math.round(obs.confidence * 100)}%</span>
                          {obs.gnss_accuracy_meters && (
                            <span className="ml-2">GNSS: ±{obs.gnss_accuracy_meters}m</span>
                          )}
                        </div>
                        {idx === 0 && (
                          <span className="inline-block mt-1 text-[10px] font-semibold uppercase text-primary bg-primary/10 px-1.5 py-0.5 rounded">
                            First Observation
                          </span>
                        )}
                        {idx > 0 && (
                          <span className="inline-block mt-1 text-[10px] font-semibold uppercase text-severity-high bg-severity-high/10 px-1.5 py-0.5 rounded">
                            Corroboration #{idx}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}

                  {/* Re-observation entries */}
                  {reobsObs.length > 0 && (
                    <>
                      <div className="relative">
                        <div className="absolute -left-[23px] top-1.5 w-2.5 h-2.5 rounded-full bg-semantic-down border-2 border-canvas" />
                        <div className="bg-semantic-down/10 border border-semantic-down/20 rounded-lg p-2.5 text-[12px]">
                          <div className="font-semibold text-semantic-down mb-1 flex items-center gap-1">
                            <RotateCcw className="w-3 h-3" /> Re-observation{reobsObs.length > 1 ? 's' : ''} ({reobsObs.length})
                          </div>
                          {reobsObs.map((obs) => (
                            <div key={obs.id} className="text-[11px] text-body flex items-center gap-2 mt-1">
                              <span className="font-mono text-primary">{obs.bus_id}</span>
                              <span>·</span>
                              <span>{classLabel(obs.detected_class)}</span>
                              <span>·</span>
                              <span className="text-muted font-mono">{fmtShortTime(obs.observed_at)}</span>
                            </div>
                          ))}
                          <p className="text-[11px] text-semantic-down mt-1.5 font-medium">
                            Issue was previously actioned — re-appeared on fleet scan.
                          </p>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Fleet Overview ── */}
      {!isGuestMode && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Bus className="w-4 h-4 text-primary" />
              <span className="text-[14px] font-semibold text-ink">Active Fleet Sensing Units</span>
            </div>
            <span className="text-[12px] text-muted font-mono">{buses.length} unit{buses.length !== 1 ? 's' : ''} registered</span>
          </div>

          {buses.length === 0 ? (
            <div className="bg-canvas border border-hairline rounded-xl p-8 text-center text-muted text-[14px]">
              No fleet units registered yet. Use the{' '}
              <button
                onClick={() => navigate('/simulator')}
                className="text-primary font-semibold hover:underline cursor-pointer"
              >
                Fleet Simulator
              </button>{' '}
              to send the first observation.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {buses.map((bus) => (
                <div key={bus.id} className="bg-canvas border border-hairline rounded-xl p-4 shadow-soft flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                        <Bus className="w-4 h-4 text-primary" />
                      </div>
                      <div>
                        <div className="font-mono font-bold text-ink text-[14px]">{bus.bus_id}</div>
                        <div className="text-[11px] text-muted">{bus.route_id ?? 'Route N/A'}</div>
                      </div>
                    </div>
                    <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full font-mono ${
                      (bus.status ?? '').toLowerCase() === 'active'
                        ? 'bg-semantic-up/10 text-semantic-up'
                        : 'bg-surface-strong text-muted'
                    }`}>
                      {bus.status ?? 'Unknown'}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-[12px]">
                    <div>
                      <div className="text-muted text-[10px] uppercase">Latest Detection</div>
                      <div className="text-ink font-medium capitalize">
                        {bus.latest_detected_class ? classLabel(bus.latest_detected_class) : '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-muted text-[10px] uppercase">Total Obs.</div>
                      <div className="font-mono font-bold text-ink">{bus.total_observations}</div>
                    </div>
                    <div>
                      <div className="text-muted text-[10px] uppercase">Coordinates</div>
                      <div className="font-mono text-[11px] text-body">
                        {bus.latest_latitude != null
                          ? `${bus.latest_latitude.toFixed(4)}, ${bus.latest_longitude?.toFixed(4)}`
                          : '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-muted text-[10px] uppercase">Last Ping</div>
                      <div className="font-mono text-[11px] text-body flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {fmtShortTime(bus.latest_observation_time)}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── Re-observation Alert (full-width when active) ── */}
      {!isGuestMode && hasReobservation && selectedIncident && (
        <div className="bg-semantic-down/8 border border-semantic-down/30 rounded-xl p-5 flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <RotateCcw className="w-4 h-4 text-semantic-down" />
            <span className="text-[14px] font-semibold text-semantic-down">Re-observation Alert</span>
            <span className="ml-auto text-[11px] font-mono bg-semantic-down/20 text-semantic-down px-2 py-0.5 rounded-full">
              {selectedIncident.reobservation_count} re-obs
            </span>
          </div>
          <p className="text-[13px] text-body">
            This Urban Issue (<span className="font-mono text-ink">{selectedIncident.id.slice(0, 8)}…</span>) was
            previously actioned but has been re-detected by a fleet sensing unit. Review the evidence and confirm
            whether repair was incomplete.
          </p>
          <div className="text-[12px] text-muted font-mono space-y-0.5">
            <div>First observed: <span className="text-ink">{fmtShortTime(selectedIncident.first_observed_at)}</span></div>
            <div>Last observed:  <span className="text-ink">{fmtShortTime(selectedIncident.last_observed_at)}</span></div>
          </div>
          <div className="flex gap-2 pt-1">
            <Button
              variant="primary"
              onClick={() => navigate(`/governmentdashboard/incidents/${selectedIncident.id}`)}
              icon={<ChevronRight className="w-4 h-4" />}
              iconPosition="right"
              className="h-9 text-[13px]"
            >
              Review Incident Workspace
            </Button>
          </div>
        </div>
      )}

    </div>
  );
};
