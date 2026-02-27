import { Polyline, CircleMarker, Popup } from 'react-leaflet';
import { useMapStore } from '../../stores/mapStore';

const ROUTE_COLOUR = '#2563eb'; // blue-600
const STOP_COLOURS = {
  safe: '#16a34a',    // green — safety >= 7
  moderate: '#d97706', // amber — safety 5–7
  caution: '#dc2626',  // red — safety < 5
};

function stopColour(safetyScore) {
  if (safetyScore >= 7) return STOP_COLOURS.safe;
  if (safetyScore >= 5) return STOP_COLOURS.moderate;
  return STOP_COLOURS.caution;
}

export default function TripRouteLayer() {
  const tripPlan = useMapStore((s) => s.tripPlan);

  if (!tripPlan || !tripPlan.stops || tripPlan.stops.length === 0) return null;

  const { stops, total_duration_text, location_name } = tripPlan;

  // Build polyline positions: [lat, lon] pairs for each stop
  const positions = stops.map((s) => [parseFloat(s.lat), parseFloat(s.lon)]);

  return (
    <>
      {/* Route line connecting all stops */}
      <Polyline
        positions={positions}
        pathOptions={{ color: ROUTE_COLOUR, weight: 4, opacity: 0.8, dashArray: '8 4' }}
      />

      {/* Numbered marker for each stop */}
      {stops.map((stop) => (
        <CircleMarker
          key={stop.stop_index}
          center={[parseFloat(stop.lat), parseFloat(stop.lon)]}
          radius={14}
          pathOptions={{
            color: '#ffffff',
            weight: 2,
            fillColor: stopColour(stop.safety_score),
            fillOpacity: 1,
          }}
        >
          <Popup>
            <div style={{ minWidth: 180 }}>
              <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 4 }}>
                {stop.stop_index}. {stop.name}
              </div>
              <div style={{ fontSize: 12, color: '#555', marginBottom: 6 }}>
                {stop.category}
              </div>
              {stop.description && (
                <div style={{ fontSize: 12, marginBottom: 6 }}>{stop.description}</div>
              )}
              <div style={{ fontSize: 12, display: 'flex', gap: 8 }}>
                <span>
                  Safety:{' '}
                  <strong style={{ color: stopColour(stop.safety_score) }}>
                    {stop.safety_score}/10
                  </strong>
                </span>
                {stop.travel_time_text && (
                  <span>| {stop.travel_time_text}</span>
                )}
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
        </CircleMarker>
      ))}
    </>
  );
}
