import { useState } from 'react';
import { useMapStore } from '../stores/mapStore';
import { getTripPlan } from '../services/api';

function SafetyBadge({ score }) {
  if (score >= 7) return (
    <span className="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-800">
      Safe {score}/10
    </span>
  );
  if (score >= 5) return (
    <span className="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800">
      Moderate {score}/10
    </span>
  );
  return (
    <span className="inline-block px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-800">
      Caution {score}/10
    </span>
  );
}

function StopCard({ stop }) {
  return (
    <div className="flex gap-3 py-3 border-b border-gray-100 last:border-0">
      {/* Stop number badge */}
      <div className="flex-shrink-0 w-7 h-7 rounded-full bg-blue-600 text-white text-xs font-bold flex items-center justify-center">
        {stop.stop_index}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-semibold text-gray-800 leading-tight truncate">
            {stop.name}
          </p>
          <SafetyBadge score={stop.safety_score} />
        </div>

        <p className="text-xs text-gray-500 mt-0.5 capitalize">{stop.category}</p>

        {stop.travel_time_text && (
          <p className="text-xs text-blue-600 mt-1">
            {stop.stop_index === 1 ? 'First stop' : `↑ ${stop.travel_time_text} from previous`}
          </p>
        )}

        {stop.description && (
          <p className="text-xs text-gray-600 mt-1 line-clamp-2">{stop.description}</p>
        )}
      </div>
    </div>
  );
}

export default function TripPlanner() {
  const center = useMapStore((s) => s.center);
  const tripPlan = useMapStore((s) => s.tripPlan);
  const setTripPlan = useMapStore((s) => s.setTripPlan);
  const clearTripPlan = useMapStore((s) => s.clearTripPlan);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const userId = (() => {
    try {
      let id = sessionStorage.getItem('userId');
      if (!id) {
        id = `user_${Math.random().toString(36).slice(2, 10)}`;
        sessionStorage.setItem('userId', id);
      }
      return id;
    } catch {
      return 'anonymous';
    }
  })();

  async function handlePlan() {
    setLoading(true);
    setError(null);
    try {
      const plan = await getTripPlan({
        lat: center.lat,
        lon: center.lon,
        user_id: userId,
        max_stops: 5,
      });
      setTripPlan(plan);
    } catch (err) {
      setError('Could not generate a trip plan for this location. Try a busier area.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 mt-3">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-bold text-gray-800">Day Trip Planner</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Safety-aware itinerary for this area
          </p>
        </div>

        {tripPlan ? (
          <button
            onClick={clearTripPlan}
            className="text-xs text-gray-400 hover:text-red-500 transition-colors"
          >
            Clear
          </button>
        ) : (
          <button
            onClick={handlePlan}
            disabled={loading}
            className="px-3 py-1.5 rounded-md text-xs font-semibold bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Planning...' : 'Plan Day Trip'}
          </button>
        )}
      </div>

      {error && (
        <p className="text-xs text-red-500 bg-red-50 rounded p-2">{error}</p>
      )}

      {loading && (
        <div className="text-xs text-gray-500 text-center py-4">
          Finding the best places to visit...
        </div>
      )}

      {tripPlan && !loading && (
        <>
          {tripPlan.stops && tripPlan.stops.length > 0 ? (
            <>
              <div className="text-xs text-gray-500 mb-2 flex items-center justify-between">
                <span>
                  {tripPlan.total_stops} stops · {tripPlan.total_duration_text}
                </span>
                <span className="text-blue-500">{tripPlan.location_name}</span>
              </div>

              <div>
                {tripPlan.stops.map((stop) => (
                  <StopCard key={stop.stop_index} stop={stop} />
                ))}
              </div>

              <p className="text-xs text-gray-400 mt-2 text-center">
                Tap any numbered marker on the map for details
              </p>
            </>
          ) : (
            <p className="text-xs text-gray-500 text-center py-3">
              No places found for this area. Try zooming out or searching a different location.
            </p>
          )}
        </>
      )}

      {!tripPlan && !loading && !error && (
        <p className="text-xs text-gray-400 text-center py-2">
          Click "Plan Day Trip" to get a personalised itinerary based on safety and popularity scores.
        </p>
      )}
    </div>
  );
}
