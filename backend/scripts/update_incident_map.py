"""Update IncidentMap.tsx with Civora Fleet markers, Urban Issue popups, and observation telemetry."""

MAP_PATH = r"c:\My_stuff\Civora\frontend\src\components\map\IncidentMap.tsx"

map_code = '''import React, { useState, useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import { Incident, BusUnit, ObservationDetail } from '../../types';
import { BadgePill } from '../common/BadgePill';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Crosshair, Bus, AlertTriangle, Layers, Clock, Shield } from 'lucide-react';

// Custom SVG pin generator for Urban Issues
function createIssuePin(severity: string, observationCount: number = 1, isSelected = false) {
  let color = '#cf202f'; // default critical
  const sev = (severity || '').toUpperCase();
  if (sev === 'HIGH') color = '#f4780a';
  else if (sev === 'MEDIUM') color = '#f4b000';
  else if (sev === 'LOW') color = '#7c828a';
  else if (sev === 'RESOLVED') color = '#05b169';

  const size = isSelected ? 38 : 30;
  const countBadge = observationCount > 1 ? `
    <span style="position: absolute; top: -6px; right: -6px; background: #0a0b0d; color: #ffffff; font-size: 10px; font-weight: 700; padding: 1px 5px; border-radius: 9999px; border: 1.5px solid #ffffff; font-family: monospace;">
      ${observationCount}
    </span>
  ` : '';

  const svg = `
    <div style="position: relative; width: ${size}px; height: ${size}px;">
      <svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 24 24" fill="${color}" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
        <circle cx="12" cy="10" r="3" fill="#ffffff"></circle>
      </svg>
      ${countBadge}
    </div>
  `;

  return L.divIcon({
    html: svg,
    className: 'custom-map-marker',
    iconSize: [size, size],
    iconAnchor: [size / 2, size],
    popupAnchor: [0, -size],
  });
}

// Custom Bus Sensing Unit Icon
function createBusPin(busId: string, status: string = 'active') {
  const isSensing = status.toLowerCase() === 'active' || status.toLowerCase() === 'sensing';
  const pulseHtml = isSensing
    ? '<span style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border-radius: 9999px; background: rgba(0, 82, 255, 0.3); animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;"></span>'
    : '';

  const html = `
    <div style="position: relative; display: flex; align-items: center; justify-content: center; transform: translate(-50%, -50%);">
      ${pulseHtml}
      <div style="display: flex; align-items: center; gap: 4px; background: #0a0b0d; color: #ffffff; border: 2px solid #0052ff; border-radius: 9999px; padding: 3px 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); font-size: 11px; font-weight: 700; white-space: nowrap; font-family: 'JetBrains Mono', monospace;">
        <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #0052ff;"></span>
        <span>${busId}</span>
      </div>
    </div>
  `;

  return L.divIcon({
    html,
    className: 'custom-bus-marker',
    iconSize: [70, 26],
    iconAnchor: [35, 13],
    popupAnchor: [0, -14],
  });
}

// User current location pulsing pin
function createUserLocationPin() {
  const svg = `
    <div style="position: relative; width: 24px; height: 24px;">
      <div style="position: absolute; width: 24px; height: 24px; border-radius: 50%; background: rgba(0, 82, 255, 0.4); animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;"></div>
      <div style="position: absolute; top: 4px; left: 4px; width: 16px; height: 16px; border-radius: 50%; background: #0052ff; border: 3px solid #ffffff; box-shadow: 0 2px 6px rgba(0,0,0,0.3);"></div>
    </div>
  `;

  return L.divIcon({
    html: svg,
    className: 'user-location-marker',
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -12],
  });
}

function RecenterMap({ lat, lng, zoom }: { lat: number; lng: number; zoom?: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView([lat, lng], zoom || map.getZoom(), { animate: true });
  }, [lat, lng, zoom, map]);
  return null;
}

interface IncidentMapProps {
  incidents: Incident[];
  buses?: BusUnit[];
  observations?: ObservationDetail[];
  selectedIncident?: Incident | null;
  onSelectIncident?: (incident: Incident) => void;
  center?: [number, number];
  zoom?: number;
  height?: string;
  interactive?: boolean;
}

export const IncidentMap: React.FC<IncidentMapProps> = ({
  incidents,
  buses = [],
  observations = [],
  selectedIncident,
  onSelectIncident,
  center = [19.2183, 72.9781], // Civora default coordinates (Thane / Central sector)
  zoom = 14,
  height = '500px',
}) => {
  const navigate = useNavigate();
  const [userLocation, setUserLocation] = useState<[number, number] | null>(null);
  const [targetCenter, setTargetCenter] = useState<[number, number] | null>(null);

  useEffect(() => {
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const coords: [number, number] = [pos.coords.latitude, pos.coords.longitude];
          setUserLocation(coords);
        },
        () => {},
        { enableHighAccuracy: false, timeout: 5000 }
      );
    }
  }, []);

  const handleLocateMe = () => {
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const coords: [number, number] = [pos.coords.latitude, pos.coords.longitude];
          setUserLocation(coords);
          setTargetCenter(coords);
        },
        (err) => {
          alert('Could not access your location: ' + err.message);
        },
        { enableHighAccuracy: true }
      );
    }
  };

  // Find dynamic center if incidents or buses exist
  const initialMapCenter: [number, number] = selectedIncident && selectedIncident.location?.lat
    ? [selectedIncident.location.lat, selectedIncident.location.lng]
    : incidents.length > 0 && incidents[0].location?.lat
    ? [incidents[0].location.lat, incidents[0].location.lng]
    : buses.find((b) => b.latest_latitude)
    ? [buses.find((b) => b.latest_latitude)!.latest_latitude!, buses.find((b) => b.latest_longitude)!.latest_longitude!]
    : center;

  return (
    <div style={{ height }} className="w-full relative rounded-xl overflow-hidden border border-hairline shadow-soft bg-surface-soft">
      {/* Floating Controls */}
      <div className="absolute top-3 right-3 z-[1000] flex items-center gap-2">
        <button
          onClick={handleLocateMe}
          title="Center on my location"
          className="bg-canvas text-ink px-3 py-1.5 rounded-lg shadow-md border border-hairline flex items-center gap-1.5 text-xs font-semibold hover:bg-surface-soft active:scale-95 transition-all cursor-pointer"
        >
          <Crosshair className="w-3.5 h-3.5 text-primary" />
          <span>Locate</span>
        </button>
      </div>

      <MapContainer
        center={initialMapCenter}
        zoom={zoom}
        scrollWheelZoom={true}
        className="w-full h-full"
      >
        <TileLayer
          attribution=\'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors\'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {targetCenter && (
          <RecenterMap lat={targetCenter[0]} lng={targetCenter[1]} zoom={15} />
        )}

        {selectedIncident && selectedIncident.location?.lat && (
          <RecenterMap
            lat={selectedIncident.location.lat}
            lng={selectedIncident.location.lng}
            zoom={15}
          />
        )}

        {/* User Real-Time Location Marker */}
        {userLocation && (
          <Marker position={userLocation} icon={createUserLocationPin()}>
            <Popup>
              <div className="text-center font-medium text-xs py-1">
                📍 You are here (Live GPS)
              </div>
            </Popup>
          </Marker>
        )}

        {/* Active Fleet Sensing Units */}
        {buses
          .filter((b) => b.latest_latitude && b.latest_longitude)
          .map((bus) => (
            <Marker
              key={`bus-${bus.bus_id}`}
              position={[bus.latest_latitude!, bus.latest_longitude!]}
              icon={createBusPin(bus.bus_id, bus.status)}
            >
              <Popup className="custom-leaflet-popup">
                <div className="p-2 min-w-[220px]">
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <span className="font-mono text-[12px] font-bold text-primary flex items-center gap-1">
                      <Bus className="w-3.5 h-3.5" />
                      {bus.bus_id}
                    </span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-mono uppercase bg-primary/10 text-primary font-bold">
                      {bus.status || 'Active'}
                    </span>
                  </div>
                  <div className="text-[12px] text-body mb-2">
                    <div>Route: <strong className="text-ink">{bus.route_id || 'Route-12'}</strong></div>
                    {bus.latest_detected_class && (
                      <div>Latest Detection: <strong className="text-ink capitalize">{bus.latest_detected_class.replace(/_/g, ' ')}</strong></div>
                    )}
                    <div>Total Observations: <strong className="text-ink font-mono">{bus.total_observations}</strong></div>
                    {bus.latest_observation_time && (
                      <div className="text-[11px] text-muted mt-1 font-mono">
                        {new Date(bus.latest_observation_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </div>
                    )}
                  </div>
                </div>
              </Popup>
            </Marker>
          ))}

        {/* Urban Issues */}
        {incidents
          .filter((inc) => inc.location && inc.location.lat && inc.location.lng)
          .map((incident) => {
            const isSelected = selectedIncident?.id === incident.id;
            const obsCount = incident.observation_count ?? incident.report_count ?? 1;
            const icon = createIssuePin(
              incident.status === 'RESOLVED' ? 'RESOLVED' : incident.severity,
              obsCount,
              isSelected
            );

            return (
              <Marker
                key={`incident-${incident.id}`}
                position={[incident.location.lat, incident.location.lng]}
                icon={icon}
                eventHandlers={{
                  click: () => {
                    if (onSelectIncident) onSelectIncident(incident);
                  },
                }}
              >
                <Popup className="custom-leaflet-popup">
                  <div className="p-2 max-w-xs min-w-[240px]">
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <BadgePill severity={incident.severity} label={incident.severity} dot className="text-[10px]" />
                      <span className="font-mono text-[10px] text-muted truncate max-w-[100px]">{incident.id}</span>
                    </div>

                    <h4 className="font-bold text-[14px] text-ink line-clamp-1 leading-tight capitalize">
                      {incident.category.replace(/_/g, ' ')}
                    </h4>

                    {/* Urban Intelligence Evidence Card in Popup */}
                    <div className="my-2 p-2 rounded-lg bg-surface-strong/80 text-[11px] font-mono space-y-1">
                      <div className="flex justify-between">
                        <span className="text-muted">Evidence:</span>
                        <strong className="text-ink">{incident.observation_count ?? 1} obs / {incident.distinct_bus_count ?? 1} buses</strong>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted">Priority:</span>
                        <strong className="text-primary font-bold">
                          {Math.round((incident.ai_confidence || 85))}% ({incident.severity})
                        </strong>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted">Status:</span>
                        <span className="font-semibold text-ink uppercase">{incident.status}</span>
                      </div>
                      {incident.reobservation_count && incident.reobservation_count > 0 ? (
                        <div className="text-semantic-down font-bold pt-1 border-t border-hairline">
                          ● {incident.reobservation_count} Re-observation(s)
                        </div>
                      ) : null}
                    </div>

                    <div className="flex items-center justify-between mt-2 pt-2 border-t border-hairline text-[12px]">
                      <button
                        onClick={() => {
                          if (onSelectIncident) onSelectIncident(incident);
                        }}
                        className="text-[12px] font-semibold text-primary hover:underline cursor-pointer"
                      >
                        Inspect Evidence
                      </button>
                      <button
                        onClick={() => navigate(`/governmentdashboard/incidents/${incident.id}`)}
                        className="inline-flex items-center gap-1 text-ink font-semibold hover:text-primary text-[12px] cursor-pointer"
                      >
                        <span>Workspace</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </Popup>
              </Marker>
            );
          })}
      </MapContainer>
    </div>
  );
};
'''

with open(MAP_PATH, "w", encoding="utf-8") as f:
    f.write(map_code)
print("Updated IncidentMap.tsx successfully!")
