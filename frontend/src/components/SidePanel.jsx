import React from 'react';
import { useMapStore } from '../stores/mapStore';
import { useSummary, useScores } from '../hooks/useDataHooks';
import { useLocationData } from '../hooks/useLocationData';
import LocationDataList from './LocationDataList';
import Recommendations from './Recommendations';

function Chip({ label, value, color = 'info' }) {
  const colorClass = {
    info: 'badge-info',
    success: 'badge-success',
    warning: 'badge-warning',
    danger: 'badge-danger',
  }[color] || 'badge-info';
  return <span className={`badge ${colorClass}`}>{label}: {value}</span>;
}

export default function SidePanel() {
  const recent = useMapStore((s) => s.recentSearches);
  const { center } = useMapStore();
  const { data: summary } = useSummary();
  const { data: scores, error: scoresError, isLoading: scoresLoading } = useScores();
  
  // Use shared location data hook (prevents duplicate API calls)
  const { data: locationData } = useLocationData();

  // Extract counts from location data - use same logic as LocationDataList
  const events = Array.isArray(locationData?.events) ? locationData.events : [];
  const pois = Array.isArray(locationData?.pois) ? locationData.pois : [];
  const news = Array.isArray(locationData?.news) ? locationData.news : [];
  const crimes = Array.isArray(locationData?.crimes) ? locationData.crimes : [];
  
  const crimesCount = crimes.length;
  const eventsCount = events.length;
  const newsCount = news.length;
  const poisCount = pois.length;

  // Debug logging (remove in production)
  if (scoresError) {
    console.error('Scores API Error:', scoresError);
  }
  if (scoresLoading) {
    console.log('Scores loading...');
  }
  if (scores) {
    console.log('Scores data:', scores);
  }

  const safety = scores?.safety_score ?? null;
  const popularity = scores?.popularity_score ?? null;

  return (
    <aside className="space-y-4">
      <div className="card">
        <h2 className="text-base font-semibold mb-3">Overview</h2>
        <div className="flex flex-wrap gap-2 mb-3">
          <Chip label="Crimes" value={locationData ? crimesCount : '—'} />
          <Chip label="Events" value={locationData ? eventsCount : '—'} />
          <Chip label="News" value={locationData ? newsCount : '—'} />
          <Chip label="POIs" value={locationData ? poisCount : '—'} />
        </div>
        <div className="flex items-center gap-2">
          <Chip label="Safety" value={safety !== null ? (safety * 100).toFixed(0) + '%' : '—'} color="success" />
          <Chip label="Popularity" value={popularity !== null ? (popularity * 100).toFixed(0) + '%' : '—'} color="info" />
        </div>
      </div>

      <div className="card">
        <h3 className="text-sm font-medium mb-2">AI Summary</h3>
        <p className="text-sm text-gray-800 whitespace-pre-wrap">{summary?.narrative || 'Searching area for insights...'}</p>
      </div>

      <LocationDataList />

      <Recommendations />

      <div className="card">
        <h3 className="text-sm font-medium mb-2">Recent Searches</h3>
        <ul className="space-y-1 text-sm">
          {recent.length === 0 && <li className="text-gray-500">No recent searches yet.</li>}
          {recent.map((r, idx) => (
            <li key={idx} className="flex items-center justify-between">
              <span className="truncate pr-2">{r.query}</span>
              <span className="text-gray-500">{r.lat.toFixed(3)}, {r.lon.toFixed(3)}</span>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}




