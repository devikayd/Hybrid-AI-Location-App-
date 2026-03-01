import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { geocode } from '../services/api';
import { useMapStore } from '../stores/mapStore';

export default function SearchBar() {
  const [query, setQuery] = useState('');
  const [showRecent, setShowRecent] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const setCenter = useMapStore((s) => s.setCenter);
  const setZoom = useMapStore((s) => s.setZoom);
  const setBoundingBox = useMapStore((s) => s.setBoundingBox);
  const incrementSearchId = useMapStore((s) => s.incrementSearchId);
  const setSelectedLocation = useMapStore((s) => s.setSelectedLocation);
  const addRecentSearch = useMapStore((s) => s.addRecentSearch);
  const recentSearches = useMapStore((s) => s.recentSearches);
  const setShowRecentSearches = useMapStore((s) => s.setShowRecentSearches);

  const { mutate, isLoading } = useMutation({
    mutationFn: (q) => geocode(q, 1, 'gb'),
    onSuccess: (data) => {
      if (data?.results?.length) {
        const { lat, lon, display_name, boundingbox } = data.results[0];
        const latNum = Number(lat);
        const lonNum = Number(lon);

        setCenter(latNum, lonNum);
        setBoundingBox(boundingbox ?? null);
        incrementSearchId();
        setSelectedLocation({ lat: latNum, lon: lonNum, name: display_name || query });
        addRecentSearch({ query: display_name || query, lat: latNum, lon: lonNum, ts: Date.now() });
        setShowRecent(false);
        setShowRecentSearches(false);
        setSuccessMessage(`Found: ${display_name || query}`);
        setTimeout(() => setSuccessMessage(''), 3000);
      }
    },
    onError: (error) => {
      console.error('Geocoding error:', error);
      setSuccessMessage('Location not found. Try a different search term.');
      setTimeout(() => setSuccessMessage(''), 3000);
    },
  });

  const onSubmit = (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    mutate(query.trim());
  };

  const handleRecentClick = (search) => {
    setQuery(search.query);
    setCenter(search.lat, search.lon);
    setZoom(13);
    setBoundingBox(null);
    incrementSearchId();
    setSelectedLocation({ lat: search.lat, lon: search.lon, name: search.query });
    setShowRecent(false);
    setShowRecentSearches(false);
  };

  const formatTime = (ts) => {
    const now = Date.now();
    const diff = now - ts;
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  return (
    <div className="relative w-full space-y-2 z-[1000]">
      <form onSubmit={onSubmit} className="flex w-full gap-2">
        <div className="relative flex-1">
          <input
            className="input-field w-full pr-10"
            placeholder="Search by place or postcode (UK)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => {
              setShowRecent(true);
              setShowRecentSearches(true);
            }}
            onBlur={() => {
              setTimeout(() => {
                setShowRecent(false);
                setShowRecentSearches(false);
              }, 200);
            }}
          />
          {recentSearches.length > 0 && (
            <button
              type="button"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              onClick={() => {
                const newState = !showRecent;
                setShowRecent(newState);
                setShowRecentSearches(newState);
              }}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          )}
        </div>
        <button className="btn-primary" type="submit" disabled={isLoading}>
          {isLoading ? 'Searching...' : 'Search'}
        </button>
      </form>

      {/* Success/Error Message */}
      {successMessage && (
        <div className={`text-sm px-3 py-2 rounded-lg ${
          successMessage.startsWith('Found:') 
            ? 'bg-success-100 text-success-800 border border-success-200' 
            : 'bg-danger-100 text-danger-800 border border-danger-200'
        }`}>
          {successMessage}
        </div>
      )}

      {/* Recent Searches Dropdown */}
      {showRecent && recentSearches.length > 0 && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-[1001] overflow-hidden">
          <div className="p-2 text-xs text-gray-500 border-b border-gray-100">
            Recent searches
          </div>
          <div>
            {recentSearches.slice(0, 4).map((search, index) => (
              <button
                key={index}
                className="w-full text-left px-3 py-2 hover:bg-gray-50 flex justify-between items-center border-b border-gray-50 last:border-b-0"
                onClick={() => handleRecentClick(search)}
              >
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-gray-900 truncate">{search.query}</div>
                  <div className="text-xs text-gray-500">
                    {search.lat.toFixed(4)}, {search.lon.toFixed(4)}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}





