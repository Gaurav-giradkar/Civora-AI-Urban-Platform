import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Bus,
  Camera,
  Cpu,
  Navigation,
  Radio,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Play,
  Shield,
  Activity,
  Layers,
  Clock,
  MapPin,
  RefreshCw,
  Sliders,
  Zap,
} from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup, Circle, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

import { useAuth } from '../context/AuthContext';
import { ingestObservationApi, verifyIncidentApi } from '../api/endpoints';
import {
  ObservationCreatePayload,
  ObservationIngestResponse,
  SimulatorTimelineEvent,
} from '../types';

// Map recentering helper
function MapRecenter({ lat, lng }: { lat: number; lng: number }) {
  const map = useMap();
  useEffect(() => {
    if (lat && lng) {
      map.setView([lat, lng], 16, { animate: true });
    }
  }, [lat, lng, map]);
  return null;
}

// Custom Leaflet DivIcons
function createBusMarker(busId: string, color: string) {
  const html = `
    <div style="
      background: ${color};
      color: #ffffff;
      padding: 3px 8px;
      border-radius: 9999px;
      font-weight: 700;
      font-size: 11px;
      font-family: system-ui, -apple-system, sans-serif;
      display: flex;
      align-items: center;
      gap: 4px;
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.45);
      border: 2px solid #ffffff;
      white-space: nowrap;
      cursor: pointer;
    ">
      <span>🚌</span>
      <span>${busId}</span>
    </div>
  `;
  return L.divIcon({
    html,
    className: 'custom-bus-marker',
    iconSize: [80, 24],
    iconAnchor: [40, 12],
  });
}

function createIssueMarker(issueId: string) {
  const shortId = issueId.slice(0, 8);
  const html = `
    <div style="
      background: #cf202f;
      color: #ffffff;
      padding: 4px 10px;
      border-radius: 8px;
      font-weight: 800;
      font-size: 11px;
      font-family: system-ui, -apple-system, sans-serif;
      display: flex;
      align-items: center;
      gap: 5px;
      box-shadow: 0 0 20px rgba(207, 32, 47, 0.6);
      border: 2px solid #ffffff;
      white-space: nowrap;
    ">
      <span>⚠️</span>
      <span>URBAN ISSUE #${shortId}</span>
    </div>
  `;
  return L.divIcon({
    html,
    className: 'custom-issue-marker',
    iconSize: [160, 28],
    iconAnchor: [80, 14],
  });
}

// Pipeline stages definition
const PIPELINE_STAGES = [
  { id: 'bus', label: 'BUS', sub: 'Fleet Node', icon: Bus },
  { id: 'camera', label: 'CAMERA', sub: '1080p Optical', icon: Camera },
  { id: 'ai', label: 'AI DETECTION', sub: 'YOLOv8 Edge', icon: Cpu },
  { id: 'gnss', label: 'GNSS', sub: 'RTK Geo-tag', icon: Navigation },
  { id: 'observation', label: 'OBSERVATION', sub: 'Civora Ingest', icon: Radio },
  { id: 'corroboration', label: 'CORROBORATION', sub: '200m Spatio-Temporal', icon: Layers },
  { id: 'issue', label: 'URBAN ISSUE', sub: 'Corroborated Hazard', icon: Shield },
];

export const FleetSimulatorPage: React.FC = () => {
  const { user, isAuthenticated, login } = useAuth();

  // Session state (unique per demo reset to guarantee clean NEW ISSUE on step 1)
  const [sessionIndex, setSessionIndex] = useState<number>(() => Date.now());
  const [activeStageIndex, setActiveStageIndex] = useState<number>(-1);
  const [pipelineMessage, setPipelineMessage] = useState<string>(
    'Ready. Select an action or execute "Run Full Scenario".'
  );

  // Simulation execution state
  const [isRunningScenario, setIsRunningScenario] = useState<boolean>(false);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Latest result and recorded timeline
  const [latestResponse, setLatestResponse] = useState<ObservationIngestResponse | null>(null);
  const [timeline, setTimeline] = useState<SimulatorTimelineEvent[]>([]);

  // Track simulated buses state
  const [busStates, setBusStates] = useState<{
    [key: string]: {
      status: 'idle' | 'transmitting' | 'corroborated' | 'reobserved';
      lastEventId?: string;
      lastObservationTime?: string;
      confidence?: number;
      lat: number;
      lng: number;
    };
  }>({
    'Bus-017': { status: 'idle', lat: 19.2183, lng: 72.9781 },
    'Bus-024': { status: 'idle', lat: 19.21835, lng: 72.97815 },
    'Bus-031': { status: 'idle', lat: 19.21832, lng: 72.97812 },
  });

  // Track created Urban Issue
  const [currentUrbanIssueId, setCurrentUrbanIssueId] = useState<string | null>(null);

  // Deterministic location offset for current session:
  // Each reset advances the base corridor by ~0.003 degrees (~330m) so repeated runs
  // don't collide with the 200m radius of previous demo sessions.
  const baseLat = 19.2183 + ((sessionIndex % 100) * 0.003);
  const baseLng = 72.9781 + ((sessionIndex % 100) * 0.003);

  const busLocations = {
    'Bus-017': { lat: baseLat, lng: baseLng },
    'Bus-024': { lat: baseLat + 0.00005, lng: baseLng + 0.00005 },
    'Bus-031': { lat: baseLat + 0.00002, lng: baseLng + 0.00002 },
    revisit: { lat: baseLat + 0.00001, lng: baseLng + 0.00001 },
  };

  // Map center coordinates
  const mapCenter: [number, number] = latestResponse
    ? [latestResponse.latitude, latestResponse.longitude]
    : [baseLat, baseLng];

  // Helper to safely format ISO strings
  const formatTime = (isoString?: string) => {
    if (!isoString) return new Date().toLocaleTimeString();
    try {
      return new Date(isoString).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  // Handle Quick Demo Login if unauthenticated
  const handleQuickLogin = async () => {
    try {
      setLoadingAction('login');
      setErrorMessage(null);
      await login('control@Civora.gov', 'password123');
    } catch (err: any) {
      setErrorMessage(
        'Failed to log in as Control Room officer. Please ensure backend is running at http://localhost:8000.'
      );
    } finally {
      setLoadingAction(null);
    }
  };

  // Reset simulator
  const handleResetDemo = () => {
    setSessionIndex(Date.now());
    setActiveStageIndex(-1);
    setPipelineMessage('Simulator state reset. Ready for clean Bus-017 ingestion.');
    setLatestResponse(null);
    setTimeline([]);
    setCurrentUrbanIssueId(null);
    setErrorMessage(null);
    setBusStates({
      'Bus-017': { status: 'idle', lat: baseLat, lng: baseLng },
      'Bus-024': { status: 'idle', lat: baseLat + 0.00005, lng: baseLng + 0.00005 },
      'Bus-031': { status: 'idle', lat: baseLat + 0.00002, lng: baseLng + 0.00002 },
    });
  };

  // Core API transmission function
  const sendBusObservation = async (
    busId: 'Bus-017' | 'Bus-024' | 'Bus-031',
    confidence: number,
    coords: { lat: number; lng: number },
    customTimestamp?: Date
  ): Promise<ObservationIngestResponse> => {
    const timestamp = customTimestamp || new Date();
    const eventId = `evt-sim-${sessionIndex}-${busId}-${Date.now().toString().slice(-6)}`;

    const payload: ObservationCreatePayload = {
      event_id: eventId,
      bus_id: busId,
      route_id: 'Route-12',
      bus_display_name: `Civora Fleet ${busId}`,
      bus_status: 'active',
      observed_at: timestamp.toISOString(),
      latitude: Number(coords.lat.toFixed(6)),
      longitude: Number(coords.lng.toFixed(6)),
      detected_class: 'pothole',
      confidence,
      image_url:
        'https://images.unsplash.com/photo-1515162816999-a0c47dc192f7?auto=format&fit=crop&w=600&q=80',
      severity: confidence > 0.85 ? 'high' : 'medium',
      source_metadata: {
        source: 'software_bus_simulator',
        simulator_version: '2.0',
        route: 'Route-12',
        session_id: sessionIndex,
        optical_sensor: 'front_camera_fhd',
      },
      gnss_accuracy_meters: 4.5,
    };

    // Update bus state to transmitting
    setBusStates((prev) => ({
      ...prev,
      [busId]: {
        ...prev[busId],
        status: 'transmitting',
        lat: coords.lat,
        lng: coords.lng,
      },
    }));

    const response = await ingestObservationApi(payload);

    // Update latest response and issue tracking
    setLatestResponse(response);
    setCurrentUrbanIssueId(response.urban_issue_id);

    // Update bus status
    setBusStates((prev) => ({
      ...prev,
      [busId]: {
        status: response.correlation_type === 'reobservation' ? 'reobserved' : 'corroborated',
        lastEventId: response.event_id,
        lastObservationTime: timestamp.toISOString(),
        confidence: response.confidence,
        lat: response.latitude,
        lng: response.longitude,
      },
    }));

    // Append to timeline
    const timelineEntry: SimulatorTimelineEvent = {
      id: response.observation_id,
      bus_id: response.bus_id,
      route_id: 'Route-12',
      detected_class: response.detected_class,
      confidence: response.confidence,
      latitude: response.latitude,
      longitude: response.longitude,
      observed_at: timestamp.toISOString(),
      correlation_type: response.correlation_type,
      urban_issue_id: response.urban_issue_id,
      observation_count: response.observation_count,
      distinct_bus_count: response.distinct_bus_count,
      priority_score: response.priority_score,
      priority_level: response.priority_level,
    };
    setTimeline((prev) => [timelineEntry, ...prev]);

    return response;
  };

  // Step 1: Bus-017
  const handleStep1 = async () => {
    try {
      setLoadingAction('bus-017');
      setErrorMessage(null);
      setActiveStageIndex(0); // Bus
      setPipelineMessage('Bus-017 on Route-12 transmitting optical telemetry...');

      // Animate pipeline
      setTimeout(() => setActiveStageIndex(2), 200); // AI
      setTimeout(() => setActiveStageIndex(4), 400); // Observation

      const resp = await sendBusObservation('Bus-017', 0.82, busLocations['Bus-017']);

      setActiveStageIndex(6); // Urban Issue
      setPipelineMessage(
        `Bus-017: Initial observation ingested. Created new Urban Issue (${resp.urban_issue_id.slice(
          0,
          8
        )}...).`
      );
    } catch (err: any) {
      console.error('Bus-017 failed', err);
      handleApiError(err);
    } finally {
      setLoadingAction(null);
    }
  };

  // Step 2: Bus-024
  const handleStep2 = async () => {
    try {
      setLoadingAction('bus-024');
      setErrorMessage(null);
      setActiveStageIndex(0);
      setPipelineMessage('Bus-024 approaching road segment, transmitting coordinates...');

      setTimeout(() => setActiveStageIndex(3), 200); // GNSS
      setTimeout(() => setActiveStageIndex(5), 400); // Corroboration

      const resp = await sendBusObservation('Bus-024', 0.86, busLocations['Bus-024']);

      setActiveStageIndex(5); // Corroboration established
      setPipelineMessage(
        `Bus-024: Corroborated existing issue within 200m! Count: ${resp.observation_count} | Distinct Buses: ${resp.distinct_bus_count}.`
      );
    } catch (err: any) {
      console.error('Bus-024 failed', err);
      handleApiError(err);
    } finally {
      setLoadingAction(null);
    }
  };

  // Step 3: Bus-031
  const handleStep3 = async () => {
    try {
      setLoadingAction('bus-031');
      setErrorMessage(null);
      setActiveStageIndex(0);
      setPipelineMessage('Bus-031 independent sensor reading transmitted...');

      setTimeout(() => setActiveStageIndex(2), 200);
      setTimeout(() => setActiveStageIndex(5), 400);

      const resp = await sendBusObservation('Bus-031', 0.89, busLocations['Bus-031']);

      setActiveStageIndex(6); // High confidence Urban Issue
      setPipelineMessage(
        `Bus-031: 3 independent buses corroborated! Priority score updated to ${resp.priority_score.toFixed(
          1
        )} (${resp.priority_level.toUpperCase()}).`
      );
    } catch (err: any) {
      console.error('Bus-031 failed', err);
      handleApiError(err);
    } finally {
      setLoadingAction(null);
    }
  };

  // Step 4: Simulate Re-observation
  // Explicit workflow: Authority confirms issue -> Later bus revisit -> Re-observation recorded
  const handleStep4Reobservation = async () => {
    if (!currentUrbanIssueId) {
      setErrorMessage('No Urban Issue exists yet. Please run Steps 1-3 first.');
      return;
    }

    try {
      setLoadingAction('reobservation');
      setErrorMessage(null);
      setActiveStageIndex(6);
      setPipelineMessage('Simulating workflow: Authority verifies & confirms Urban Issue...');

      // 1. Verify/confirm existing Urban Issue via authority endpoint
      await verifyIncidentApi(currentUrbanIssueId);

      setPipelineMessage('Authority confirmed issue. Bus-024 scheduled revisit to road segment...');

      // Short delay for UI realism
      await new Promise((r) => setTimeout(r, 800));

      setActiveStageIndex(0); // Bus
      setTimeout(() => setActiveStageIndex(4), 300); // Observation

      // 2. Submit later observation (revisit)
      const laterTime = new Date(Date.now() + 1000 * 60 * 30); // 30 mins later
      const resp = await sendBusObservation(
        'Bus-024',
        0.87,
        busLocations.revisit,
        laterTime
      );

      setActiveStageIndex(6); // Issue revisited
      setPipelineMessage(
        `Re-observation recorded! Existing issue #${resp.urban_issue_id.slice(
          0,
          8
        )} revisited by Bus-024. No duplicate issue created.`
      );
    } catch (err: any) {
      console.error('Reobservation failed', err);
      handleApiError(err);
    } finally {
      setLoadingAction(null);
    }
  };

  // Run Full Scenario
  const handleRunFullScenario = async () => {
    if (isRunningScenario) return;
    setIsRunningScenario(true);
    setErrorMessage(null);

    try {
      // Step 1: Bus-017
      await handleStep1();
      await new Promise((r) => setTimeout(r, 1400));

      // Step 2: Bus-024
      await handleStep2();
      await new Promise((r) => setTimeout(r, 1400));

      // Step 3: Bus-031
      await handleStep3();
      await new Promise((r) => setTimeout(r, 1400));

      // Step 4: Re-observation
      await handleStep4Reobservation();
    } catch (err: any) {
      console.error('Scenario run error', err);
    } finally {
      setIsRunningScenario(false);
    }
  };

  // Error parser
  const handleApiError = (err: any) => {
    if (err?.response?.status === 401) {
      setErrorMessage(
        '401 Unauthorized: Session token missing or expired. Please sign in with a Control Room / Admin account.'
      );
    } else if (err?.response?.status === 403) {
      setErrorMessage(
        '403 Forbidden: Your user account lacks the required simulator role (requires admin, control_room, or department_officer).'
      );
    } else if (err?.response?.status === 409) {
      setErrorMessage(
        '409 Conflict: Event ID already ingested. Click "Reset Demo" to start a clean simulation run.'
      );
    } else if (err?.message?.includes('Network Error')) {
      setErrorMessage(
        'Network Error: Unable to connect to FastAPI backend at http://localhost:8000. Please verify the backend service is running.'
      );
    } else {
      setErrorMessage(
        err?.response?.data?.detail || err?.message || 'An unexpected error occurred during API ingestion.'
      );
    }
  };

  return (
    <div className="min-h-screen bg-[#0d0e12] text-white flex flex-col font-sans selection:bg-[#0052ff] selection:text-white">
      {/* Top Header Bar */}
      <header className="w-full border-b border-white/10 bg-[#16181f]/90 backdrop-blur-md px-6 py-4 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Link
              to="/governmentdashboard"
              className="p-2 rounded-xl bg-white/5 hover:bg-white/10 text-white/70 hover:text-white transition-colors border border-white/10"
              title="Return to Command Center"
            >
              <Shield className="w-5 h-5 text-[#0052ff]" />
            </Link>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-extrabold text-lg tracking-tight text-white">
                  Civora <span className="text-[#0052ff]">Fleet Simulator</span>
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase bg-[#0052ff]/20 text-[#0052ff] border border-[#0052ff]/30">
                  Phase 2 Live
                </span>
              </div>
              <p className="text-white/60 text-xs">
                Simulate public buses generating georeferenced urban intelligence.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 self-end sm:self-auto">
            {/* Run Session Badge */}
            <div className="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs font-mono text-white/80">
              <Activity className="w-3.5 h-3.5 text-[#0052ff]" />
              <span>Corridor: Thane R-12</span>
            </div>

            {/* Auth Pill */}
            {isAuthenticated && user ? (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>
                  {user.name} ({user.role})
                </span>
              </div>
            ) : (
              <button
                onClick={handleQuickLogin}
                disabled={loadingAction === 'login'}
                className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-[#0052ff] hover:bg-[#0042cc] text-white font-semibold text-xs shadow-lg shadow-[#0052ff]/20 transition-all cursor-pointer"
              >
                {loadingAction === 'login' ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Shield className="w-3.5 h-3.5" />
                )}
                <span>Sign In to Control Room</span>
              </button>
            )}

            <Link
              to="/governmentdashboard/incidents"
              className="text-xs text-white/60 hover:text-white underline underline-offset-4 decoration-white/20 transition-colors"
            >
              View Feed
            </Link>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto w-full p-4 sm:p-6 flex flex-col gap-6">
        {/* Authentication Warning Banner if unauthenticated */}
        {!isAuthenticated && (
          <div className="w-full bg-amber-500/10 border border-amber-500/30 rounded-2xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 text-amber-200 text-sm">
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <strong className="text-white block">Authentication Required for Live API Ingestion</strong>
                <span>
                  The Phase 1 endpoint <code className="bg-black/30 px-1 py-0.5 rounded text-amber-300">POST /api/observations</code>{' '}
                  enforces JWT authorization for <span className="font-semibold">control_room</span> and{' '}
                  <span className="font-semibold">admin</span> roles.
                </span>
              </div>
            </div>
            <button
              onClick={handleQuickLogin}
              disabled={loadingAction === 'login'}
              className="px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-black font-bold text-xs shrink-0 cursor-pointer shadow-md transition-colors"
            >
              Quick Control Room Login
            </button>
          </div>
        )}

        {/* Global Error Banner */}
        {errorMessage && (
          <div className="w-full bg-red-500/10 border border-red-500/30 rounded-2xl p-4 flex items-center justify-between gap-3 text-red-300 text-sm">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
              <span>{errorMessage}</span>
            </div>
            <button
              onClick={() => setErrorMessage(null)}
              className="text-xs text-red-400 hover:text-white underline cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Live Pipeline Visualization */}
        <section className="bg-[#16181f] border border-white/10 rounded-2xl p-5 shadow-xl">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-[#0052ff] animate-pulse" />
              <h2 className="text-sm font-bold uppercase tracking-wider text-white/90">
                End-to-End Observation Pipeline
              </h2>
            </div>
            <span className="text-xs font-mono text-white/50">
              Corroboration Window: 200m / 24h
            </span>
          </div>

          {/* Pipeline Stepper */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 relative">
            {PIPELINE_STAGES.map((stage, idx) => {
              const Icon = stage.icon;
              const isActive = activeStageIndex >= idx;
              const isCurrent = activeStageIndex === idx;

              return (
                <div
                  key={stage.id}
                  className={`flex flex-col items-center justify-center p-3 rounded-xl border transition-all duration-300 ${
                    isCurrent
                      ? 'bg-[#0052ff]/20 border-[#0052ff] text-white shadow-lg shadow-[#0052ff]/20'
                      : isActive
                      ? 'bg-white/5 border-white/20 text-white'
                      : 'bg-white/[0.02] border-white/5 text-white/40'
                  }`}
                >
                  <div
                    className={`w-9 h-9 rounded-xl flex items-center justify-center mb-2 transition-colors ${
                      isCurrent
                        ? 'bg-[#0052ff] text-white'
                        : isActive
                        ? 'bg-white/10 text-white'
                        : 'bg-white/5 text-white/30'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  <span className="font-mono font-bold text-xs tracking-tight text-center">
                    {stage.label}
                  </span>
                  <span className="text-[10px] text-white/50 text-center mt-0.5">
                    {stage.sub}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Dynamic pipeline message banner */}
          <div className="mt-4 p-3 rounded-xl bg-white/[0.03] border border-white/10 flex items-center gap-3">
            <Zap className="w-4 h-4 text-[#0052ff] shrink-0" />
            <span className="text-xs font-mono text-white/80">{pipelineMessage}</span>
          </div>
        </section>

        {/* Action Controls & Simulation Trigger Deck */}
        <section className="bg-[#16181f] border border-white/10 rounded-2xl p-5 shadow-xl flex flex-col gap-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-white/10 pb-4">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Sliders className="w-4 h-4 text-[#0052ff]" />
                Simulation Control Deck
              </h3>
              <p className="text-white/60 text-xs mt-0.5">
                Execute individual bus passes or automate the deterministic 4-step scenario.
              </p>
            </div>

            <button
              onClick={handleResetDemo}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-white/70 hover:text-white text-xs font-medium transition-colors cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset Demo State</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {/* Step 1 Button */}
            <button
              onClick={handleStep1}
              disabled={loadingAction !== null || isRunningScenario}
              className={`p-3.5 rounded-xl border flex flex-col items-start gap-1 transition-all text-left cursor-pointer ${
                timeline.some((e) => e.bus_id === 'Bus-017')
                  ? 'bg-blue-950/20 border-blue-500/40 hover:bg-blue-950/40'
                  : 'bg-white/5 border-white/10 hover:bg-white/10'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <div className="flex items-center justify-between w-full">
                <span className="text-xs font-mono font-bold text-blue-400">STEP 1</span>
                {loadingAction === 'bus-017' ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-blue-400" />
                ) : (
                  <Bus className="w-3.5 h-3.5 text-blue-400" />
                )}
              </div>
              <span className="font-bold text-sm text-white">Send Bus-017</span>
              <span className="text-[11px] text-white/50">Expected: NEW ISSUE</span>
            </button>

            {/* Step 2 Button */}
            <button
              onClick={handleStep2}
              disabled={loadingAction !== null || isRunningScenario}
              className={`p-3.5 rounded-xl border flex flex-col items-start gap-1 transition-all text-left cursor-pointer ${
                timeline.some((e) => e.bus_id === 'Bus-024' && e.correlation_type === 'corroboration')
                  ? 'bg-emerald-950/20 border-emerald-500/40 hover:bg-emerald-950/40'
                  : 'bg-white/5 border-white/10 hover:bg-white/10'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <div className="flex items-center justify-between w-full">
                <span className="text-xs font-mono font-bold text-emerald-400">STEP 2</span>
                {loadingAction === 'bus-024' ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-400" />
                ) : (
                  <Bus className="w-3.5 h-3.5 text-emerald-400" />
                )}
              </div>
              <span className="font-bold text-sm text-white">Send Bus-024</span>
              <span className="text-[11px] text-white/50">Expected: CORROBORATION (2)</span>
            </button>

            {/* Step 3 Button */}
            <button
              onClick={handleStep3}
              disabled={loadingAction !== null || isRunningScenario}
              className={`p-3.5 rounded-xl border flex flex-col items-start gap-1 transition-all text-left cursor-pointer ${
                timeline.some((e) => e.bus_id === 'Bus-031')
                  ? 'bg-teal-950/20 border-teal-500/40 hover:bg-teal-950/40'
                  : 'bg-white/5 border-white/10 hover:bg-white/10'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <div className="flex items-center justify-between w-full">
                <span className="text-xs font-mono font-bold text-teal-400">STEP 3</span>
                {loadingAction === 'bus-031' ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-teal-400" />
                ) : (
                  <Bus className="w-3.5 h-3.5 text-teal-400" />
                )}
              </div>
              <span className="font-bold text-sm text-white">Send Bus-031</span>
              <span className="text-[11px] text-white/50">Expected: CORROBORATION (3)</span>
            </button>

            {/* Step 4 Button (Re-observation) */}
            <button
              onClick={handleStep4Reobservation}
              disabled={loadingAction !== null || isRunningScenario}
              className={`p-3.5 rounded-xl border flex flex-col items-start gap-1 transition-all text-left cursor-pointer ${
                timeline.some((e) => e.correlation_type === 'reobservation')
                  ? 'bg-purple-950/20 border-purple-500/40 hover:bg-purple-950/40'
                  : 'bg-white/5 border-white/10 hover:bg-white/10'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <div className="flex items-center justify-between w-full">
                <span className="text-xs font-mono font-bold text-purple-400">STEP 4</span>
                {loadingAction === 'reobservation' ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-purple-400" />
                ) : (
                  <Clock className="w-3.5 h-3.5 text-purple-400" />
                )}
              </div>
              <span className="font-bold text-sm text-white">Simulate Re-observation</span>
              <span className="text-[11px] text-white/50">Authority Confirm → Revisit</span>
            </button>

            {/* Run Full Scenario Button */}
            <button
              onClick={handleRunFullScenario}
              disabled={loadingAction !== null || isRunningScenario}
              className="p-3.5 rounded-xl bg-gradient-to-r from-[#0052ff] to-[#0038b8] hover:from-[#0047e0] hover:to-[#002f9c] text-white flex flex-col items-start gap-1 transition-all text-left cursor-pointer shadow-lg shadow-[#0052ff]/25 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="flex items-center justify-between w-full">
                <span className="text-xs font-mono font-bold text-blue-200">AUTO-RUN</span>
                {isRunningScenario ? (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-white" />
                ) : (
                  <Play className="w-3.5 h-3.5 text-white" />
                )}
              </div>
              <span className="font-bold text-sm text-white">Run Full Scenario</span>
              <span className="text-[11px] text-blue-200">Sequential Execution</span>
            </button>
          </div>
        </section>

        {/* Grid: Bus Fleet Panel (Left) & Live Map + Result Card (Right) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column (5 cols): Bus Fleet Cards & Result Card */}
          <div className="lg:col-span-5 flex flex-col gap-6">
            {/* Bus Fleet Cards */}
            <div className="bg-[#16181f] border border-white/10 rounded-2xl p-5 shadow-xl flex flex-col gap-4">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div className="flex items-center gap-2">
                  <Bus className="w-4 h-4 text-[#0052ff]" />
                  <h3 className="font-bold text-sm text-white">Active Bus Fleet (Route-12)</h3>
                </div>
                <span className="text-xs font-mono text-emerald-400 flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                  3 Sensing Nodes
                </span>
              </div>

              {/* Bus 017 */}
              <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10 flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-blue-500" />
                    <span className="font-bold text-sm text-white">Bus-017</span>
                    <span className="text-xs text-white/50 font-mono">Route-12</span>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                      busStates['Bus-017'].status === 'corroborated'
                        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                        : busStates['Bus-017'].status === 'transmitting'
                        ? 'bg-amber-500/20 text-amber-400 animate-pulse'
                        : 'bg-white/10 text-white/50'
                    }`}
                  >
                    {busStates['Bus-017'].status}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px] text-white/60 font-mono">
                  <div>Simulated GNSS: ±4.5 m</div>
                  <div>Camera: 1080p Optical</div>
                  <div>Target: Pothole (0.82)</div>
                  <div>
                    Last Transmit: {formatTime(busStates['Bus-017'].lastObservationTime)}
                  </div>
                </div>
              </div>

              {/* Bus 024 */}
              <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10 flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
                    <span className="font-bold text-sm text-white">Bus-024</span>
                    <span className="text-xs text-white/50 font-mono">Route-12</span>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                      busStates['Bus-024'].status === 'reobserved'
                        ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                        : busStates['Bus-024'].status === 'corroborated'
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        : busStates['Bus-024'].status === 'transmitting'
                        ? 'bg-amber-500/20 text-amber-400 animate-pulse'
                        : 'bg-white/10 text-white/50'
                    }`}
                  >
                    {busStates['Bus-024'].status}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px] text-white/60 font-mono">
                  <div>Simulated GNSS: ±4.5 m</div>
                  <div>Camera: 1080p Optical</div>
                  <div>Target: Pothole (0.86)</div>
                  <div>
                    Last Transmit: {formatTime(busStates['Bus-024'].lastObservationTime)}
                  </div>
                </div>
              </div>

              {/* Bus 031 */}
              <div className="p-3.5 rounded-xl bg-white/[0.03] border border-white/10 flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-teal-500" />
                    <span className="font-bold text-sm text-white">Bus-031</span>
                    <span className="text-xs text-white/50 font-mono">Route-12</span>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                      busStates['Bus-031'].status === 'corroborated'
                        ? 'bg-teal-500/20 text-teal-400 border border-teal-500/30'
                        : busStates['Bus-031'].status === 'transmitting'
                        ? 'bg-amber-500/20 text-amber-400 animate-pulse'
                        : 'bg-white/10 text-white/50'
                    }`}
                  >
                    {busStates['Bus-031'].status}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px] text-white/60 font-mono">
                  <div>Simulated GNSS: ±4.5 m</div>
                  <div>Camera: 1080p Optical</div>
                  <div>Target: Pothole (0.89)</div>
                  <div>
                    Last Transmit: {formatTime(busStates['Bus-031'].lastObservationTime)}
                  </div>
                </div>
              </div>
            </div>

            {/* Result Card */}
            <div className="bg-[#16181f] border border-white/10 rounded-2xl p-5 shadow-xl flex flex-col gap-4">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-[#0052ff]" />
                  <h3 className="font-bold text-sm text-white">Real API Ingestion Result</h3>
                </div>
                {latestResponse ? (
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase ${
                      latestResponse.correlation_type === 'new_issue'
                        ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                        : latestResponse.correlation_type === 'corroboration'
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        : 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                    }`}
                  >
                    {latestResponse.correlation_type.replace('_', ' ')}
                  </span>
                ) : (
                  <span className="text-xs text-white/40 font-mono">Awaiting event</span>
                )}
              </div>

              {latestResponse ? (
                <div className="flex flex-col gap-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-white/[0.02] border border-white/5 p-3 rounded-xl">
                      <span className="text-[10px] font-mono text-white/50 uppercase block">
                        Observations
                      </span>
                      <span className="text-2xl font-black text-white">
                        {latestResponse.observation_count}
                      </span>
                    </div>

                    <div className="bg-white/[0.02] border border-white/5 p-3 rounded-xl">
                      <span className="text-[10px] font-mono text-white/50 uppercase block">
                        Corroborating Buses
                      </span>
                      <span className="text-2xl font-black text-emerald-400">
                        {latestResponse.distinct_bus_count}
                      </span>
                    </div>

                    <div className="bg-white/[0.02] border border-white/5 p-3 rounded-xl">
                      <span className="text-[10px] font-mono text-white/50 uppercase block">
                        Priority Score
                      </span>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-xl font-black text-white">
                          {latestResponse.priority_score.toFixed(1)}
                        </span>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                            latestResponse.priority_level === 'critical'
                              ? 'bg-red-500/20 text-red-400'
                              : latestResponse.priority_level === 'high'
                              ? 'bg-amber-500/20 text-amber-400'
                              : 'bg-blue-500/20 text-blue-400'
                          }`}
                        >
                          {latestResponse.priority_level}
                        </span>
                      </div>
                    </div>

                    <div className="bg-white/[0.02] border border-white/5 p-3 rounded-xl">
                      <span className="text-[10px] font-mono text-white/50 uppercase block">
                        AI Confidence
                      </span>
                      <span className="text-xl font-black text-white">
                        {Math.round(latestResponse.confidence * 100)}%
                      </span>
                    </div>
                  </div>

                  <div className="p-3 rounded-xl bg-white/[0.02] border border-white/5 flex flex-col gap-1.5 text-xs font-mono">
                    <div className="flex justify-between items-center text-white/60">
                      <span>Urban Issue UUID:</span>
                      <span className="text-white font-semibold">
                        {latestResponse.urban_issue_id}
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-white/60">
                      <span>GNSS Coordinates:</span>
                      <span className="text-white">
                        {latestResponse.latitude.toFixed(5)}°, {latestResponse.longitude.toFixed(5)}°
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-white/60">
                      <span>Event ID:</span>
                      <span className="text-white/80">{latestResponse.event_id}</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-10 text-center text-white/40 text-xs font-mono">
                  No observation transmitted yet. Click one of the bus buttons above to start.
                </div>
              )}
            </div>
          </div>

          {/* Right Column (7 cols): Leaflet Map & Observation Timeline */}
          <div className="lg:col-span-7 flex flex-col gap-6">
            {/* Leaflet Corroboration Map */}
            <div className="bg-[#16181f] border border-white/10 rounded-2xl p-4 shadow-xl flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MapPin className="w-4 h-4 text-[#0052ff]" />
                  <h3 className="font-bold text-sm text-white">Geospatial Corroboration Map</h3>
                </div>
                <span className="text-xs font-mono text-white/50">
                  Circle = 200m Spatial Tolerance
                </span>
              </div>

              <div className="w-full h-[320px] rounded-xl overflow-hidden border border-white/10 relative z-10">
                <MapContainer
                  center={mapCenter}
                  zoom={16}
                  style={{ height: '100%', width: '100%', background: '#111319' }}
                  scrollWheelZoom={false}
                >
                  <TileLayer
                    attribution='&copy; <a href="https://carto.com/">CARTO</a>'
                    url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                  />
                  <MapRecenter lat={mapCenter[0]} lng={mapCenter[1]} />

                  {/* 200m Corroboration Radius around Urban Issue if established */}
                  {latestResponse && (
                    <Circle
                      center={[latestResponse.latitude, latestResponse.longitude]}
                      radius={200}
                      pathOptions={{
                        color: '#0052ff',
                        fillColor: '#0052ff',
                        fillOpacity: 0.12,
                        weight: 2,
                        dashArray: '6, 6',
                      }}
                    />
                  )}

                  {/* Bus-017 Observation Pin */}
                  {timeline.some((e) => e.bus_id === 'Bus-017') && (
                    <Marker
                      position={[busLocations['Bus-017'].lat, busLocations['Bus-017'].lng]}
                      icon={createBusMarker('Bus-017', '#2563eb')}
                    >
                      <Popup>
                        <div className="text-xs font-sans text-gray-900">
                          <strong>Bus-017 Observation</strong>
                          <br />
                          Route-12 · Pothole (82%)
                        </div>
                      </Popup>
                    </Marker>
                  )}

                  {/* Bus-024 Observation Pin */}
                  {timeline.some((e) => e.bus_id === 'Bus-024') && (
                    <Marker
                      position={[busLocations['Bus-024'].lat, busLocations['Bus-024'].lng]}
                      icon={createBusMarker('Bus-024', '#059669')}
                    >
                      <Popup>
                        <div className="text-xs font-sans text-gray-900">
                          <strong>Bus-024 Observation</strong>
                          <br />
                          Route-12 · Pothole (86%)
                        </div>
                      </Popup>
                    </Marker>
                  )}

                  {/* Bus-031 Observation Pin */}
                  {timeline.some((e) => e.bus_id === 'Bus-031') && (
                    <Marker
                      position={[busLocations['Bus-031'].lat, busLocations['Bus-031'].lng]}
                      icon={createBusMarker('Bus-031', '#0d9488')}
                    >
                      <Popup>
                        <div className="text-xs font-sans text-gray-900">
                          <strong>Bus-031 Observation</strong>
                          <br />
                          Route-12 · Pothole (89%)
                        </div>
                      </Popup>
                    </Marker>
                  )}

                  {/* Consolidated Urban Issue Marker */}
                  {currentUrbanIssueId && latestResponse && (
                    <Marker
                      position={[latestResponse.latitude, latestResponse.longitude]}
                      icon={createIssueMarker(currentUrbanIssueId)}
                    >
                      <Popup>
                        <div className="text-xs font-sans text-gray-900">
                          <strong>Consolidated Urban Issue</strong>
                          <br />
                          ID: {currentUrbanIssueId}
                          <br />
                          Buses: {latestResponse.distinct_bus_count} | Observations:{' '}
                          {latestResponse.observation_count}
                        </div>
                      </Popup>
                    </Marker>
                  )}
                </MapContainer>
              </div>

              <div className="flex flex-wrap items-center gap-4 text-[11px] text-white/50 font-mono pt-1">
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#2563eb]" />
                  <span>Bus-017</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#059669]" />
                  <span>Bus-024</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full bg-[#0d9488]" />
                  <span>Bus-031</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded bg-[#cf202f]" />
                  <span>Urban Issue Pin</span>
                </div>
              </div>
            </div>

            {/* Observation Timeline */}
            <div className="bg-[#16181f] border border-white/10 rounded-2xl p-5 shadow-xl flex flex-col gap-4">
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-[#0052ff]" />
                  <h3 className="font-bold text-sm text-white">Live Ingestion Event Stream</h3>
                </div>
                <span className="text-xs font-mono text-white/50">
                  {timeline.length} Events Logged
                </span>
              </div>

              {timeline.length === 0 ? (
                <div className="py-8 text-center text-white/40 text-xs font-mono">
                  No fleet events recorded in this session.
                </div>
              ) : (
                <div className="flex flex-col gap-2.5 max-h-[360px] overflow-y-auto pr-1">
                  {timeline.map((event, idx) => (
                    <div
                      key={event.id || idx}
                      className="p-3 rounded-xl bg-white/[0.02] border border-white/5 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs"
                    >
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-white/40 text-[11px] shrink-0">
                          {formatTime(event.observed_at)}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-white">{event.bus_id}</span>
                          <span className="text-white/50">·</span>
                          <span className="text-white/80 capitalize">{event.detected_class}</span>
                          <span className="text-white/40 font-mono">
                            ({Math.round(event.confidence * 100)}%)
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 self-end sm:self-auto">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                            event.correlation_type === 'new_issue'
                              ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                              : event.correlation_type === 'corroboration'
                              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                              : 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                          }`}
                        >
                          {event.correlation_type.replace('_', ' ')}
                        </span>
                        <span className="text-[11px] font-mono text-white/60">
                          {event.observation_count} obs / {event.distinct_bus_count} bus
                          {event.distinct_bus_count > 1 ? 'es' : ''}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default FleetSimulatorPage;
