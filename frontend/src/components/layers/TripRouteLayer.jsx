import { Polyline, Marker, Tooltip, Popup } from 'react-leaflet';
import L from 'leaflet';
import { useMapStore } from '../../stores/mapStore';

const ROUTE_COLOUR = '#2563eb';

export const STOP_COLOURS = {
  start:    '#059669',
  end:      '#7c3aed',
  safe:     '#16a34a',
  moderate: '#d97706',
  caution:  '#dc2626',
};

export function resolveStopColour(stop, totalStops) {
  if (stop.stop_index === 1) return STOP_COLOURS.start;
  if (stop.stop_index === totalStops) return STOP_COLOURS.end;
  if (stop.safety_score >= 0.7) return STOP_COLOURS.safe;
  if (stop.safety_score >= 0.5) return STOP_COLOURS.moderate;
  return STOP_COLOURS.caution;
}

function makeStopIcon(number, colour) {
  return L.divIcon({
    className: '',
    html: `<div style="
      width:28px;height:28px;border-radius:50%;
      background:${colour};border:2.5px solid #fff;
      color:#fff;font-weight:700;font-size:13px;
      display:flex;align-items:center;justify-content:center;
      box-shadow:0 1px 4px rgba(0,0,0,0.35);
    ">${number}</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    tooltipAnchor: [0, -16],
  });
}

export default function TripRouteLayer() {
  const tripPlan = useMapStore((s) => s.tripPlan);

  if (!tripPlan?.stops?.length) return null;

  const { stops } = tripPlan;
  const totalStops = stops.length;
  const positions = stops.map((s) => [parseFloat(s.lat), parseFloat(s.lon)]);

  return (
    <>
      <Polyline
        positions={positions}
        pathOptions={{ color: ROUTE_COLOUR, weight: 4, opacity: 0.8, dashArray: '8 4' }}
      />

      {stops.map((stop) => {
        const colour = resolveStopColour(stop, totalStops);
        const isStart = stop.stop_index === 1;
        const isEnd = stop.stop_index === totalStops;

        return (
          <Marker
            key={stop.stop_index}
            position={[parseFloat(stop.lat), parseFloat(stop.lon)]}
            icon={makeStopIcon(stop.stop_index, colour)}
          >
            {isStart && (
              <Tooltip permanent direction="top" offset={[0, -2]} className="trip-stop-label">
                Start
              </Tooltip>
            )}
            {isEnd && (
              <Tooltip permanent direction="top" offset={[0, -2]} className="trip-stop-label">
                End
              </Tooltip>
            )}

            <Popup>
              <div style={{ minWidth: 180 }}>
                <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{
                    width: 20, height: 20, borderRadius: '50%',
                    background: colour, color: 'white',
                    fontSize: 11, fontWeight: 700,
                    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                    flexShrink: 0,
                  }}>
                    {stop.stop_index}
                  </span>
                  {stop.name}
                </div>
                <div style={{ fontSize: 12, color: '#555', marginBottom: 6 }}>
                  {stop.category}
                  {isStart && <span style={{ color: STOP_COLOURS.start, marginLeft: 6, fontWeight: 600 }}>· Start</span>}
                  {isEnd   && <span style={{ color: STOP_COLOURS.end,   marginLeft: 6, fontWeight: 600 }}>· End</span>}
                </div>
                {stop.description && (
                  <div style={{ fontSize: 12, marginBottom: 6 }}>{stop.description}</div>
                )}
                <div style={{ fontSize: 12, display: 'flex', gap: 8 }}>
                  <span>
                    Safety:{' '}
                    <strong style={{ color: colour }}>{(stop.safety_score * 10).toFixed(1)}/10</strong>
                  </span>
                  {stop.travel_time_text && <span>| {stop.travel_time_text}</span>}
                </div>
                {stop.url && (
                  <a
                    href={stop.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ fontSize: 11, color: ROUTE_COLOUR, marginTop: 4, display: 'block' }}
                  >
                    More info →
                  </a>
                )}
              </div>
            </Popup>
          </Marker>
        );
      })}
    </>
  );
}
