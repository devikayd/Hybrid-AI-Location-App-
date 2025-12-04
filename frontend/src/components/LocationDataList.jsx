import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Heart, ChevronLeft, ChevronRight } from 'lucide-react';
import { getLocationData, addInteraction } from '../services/api';
import { useMapStore } from '../stores/mapStore';

const ITEMS_PER_PAGE = 13;

export default function LocationDataList() {
  const { center } = useMapStore();
  const [filterType, setFilterType] = useState('all'); // 'all', 'event', 'poi', 'news', 'crime'
  const [currentPage, setCurrentPage] = useState(1);
  const [userId] = useState(() => {
    // Generate or retrieve user ID (for academic purposes, use session storage)
    let id = sessionStorage.getItem('userId');
    if (!id) {
      id = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      sessionStorage.setItem('userId', id);
    }
    return id;
  });

  const queryClient = useQueryClient();

  // Fetch location data
  const { data, isLoading, error } = useQuery({
    queryKey: ['location-data', center, userId],
    queryFn: () => getLocationData({
      lat: center?.lat || 51.5074,
      lon: center?.lon || -0.1278,
      radius_km: 10,
      user_id: userId
    }),
    enabled: !!(center && center.lat && center.lon),
    staleTime: 60_000, // 1 minute
  });

  // Mutation for like/save interactions - MUST be before any conditional returns
  const interactionMutation = useMutation({
    mutationFn: ({ item, interactionType }) => addInteraction(userId, {
      item_id: item.id,
      item_type: item.type,
      interaction_type: interactionType,
      item_title: item.title,
      item_category: item.category,
      item_subtype: item.subtype,
      lat: item.lat,
      lon: item.lon,
      location_name: data?.location_name
    }),
    onSuccess: () => {
      // Refetch location data to update like/save status
      queryClient.invalidateQueries(['location-data', center, userId]);
      // Also invalidate recommendations
      queryClient.invalidateQueries(['user-recommendations', userId]);
    }
  });

  // Reset to page 1 when filter changes or center changes - MUST be before conditional returns
  useEffect(() => {
    setCurrentPage(1);
  }, [filterType, center?.lat, center?.lon]);

  // Ensure currentPage is valid - MUST be before conditional returns
  useEffect(() => {
    if (!data) return;
    
    // Calculate totalPages here since we need it for the effect
    const events = Array.isArray(data.events) ? data.events : [];
    const pois = Array.isArray(data.pois) ? data.pois : [];
    const news = Array.isArray(data.news) ? data.news : [];
    const crimes = Array.isArray(data.crimes) ? data.crimes : [];
    
    const allItems = [
      ...events.map(item => ({ ...item, type: item.type || 'event' })),
      ...pois.map(item => ({ ...item, type: item.type || 'poi' })),
      ...news.map(item => ({ ...item, type: item.type || 'news' })),
      ...crimes.map(item => ({ ...item, type: item.type || 'crime' })),
    ];
    
    const filteredItems = filterType === 'all' 
      ? allItems 
      : allItems.filter(item => item.type === filterType);
    
    const totalPages = filteredItems.length > 0 
      ? Math.max(1, Math.ceil(filteredItems.length / ITEMS_PER_PAGE))
      : 1;
    
    if (currentPage > totalPages && totalPages > 0) {
      setCurrentPage(1);
    }
  }, [currentPage, filterType, data]);

  // Early return if no center set (AFTER all hooks)
  if (!center || !center.lat || !center.lon) {
    return (
      <div className="card">
        <h3 className="text-sm font-medium mb-2">Location Data</h3>
        <div className="text-sm text-gray-500">Search for a location to see data</div>
      </div>
    );
  }

  const handleLike = (item) => {
    interactionMutation.mutate({ item, interactionType: 'like' });
  };

  const getTypeIcon = (type) => {
    const icons = {
      event: '🎉',
      crime: '⚠️',
      news: '📰',
      poi: '📍',
    };
    return icons[type] || '📍';
  };

  const getTypeColor = (type) => {
    const colors = {
      event: 'text-blue-600 bg-blue-50 border-blue-200',
      crime: 'text-red-600 bg-red-50 border-red-200',
      news: 'text-yellow-600 bg-yellow-50 border-yellow-200',
      poi: 'text-green-600 bg-green-50 border-green-200',
    };
    return colors[type] || 'text-gray-600 bg-gray-50 border-gray-200';
  };

  if (isLoading) {
    return (
      <div className="card">
        <h3 className="text-sm font-medium mb-2">Location Data</h3>
        <div className="text-sm text-gray-500">Loading data...</div>
      </div>
    );
  }

  if (error) {
    console.error('LocationDataList error:', error);
    return (
      <div className="card">
        <h3 className="text-sm font-medium mb-2">Location Data</h3>
        <div className="text-sm text-danger-600">Failed to load data: {error.message || 'Unknown error'}</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="card">
        <h3 className="text-sm font-medium mb-2">Location Data</h3>
        <div className="text-sm text-gray-500">Loading...</div>
      </div>
    );
  }

  // Safely combine all items with defensive checks
  const events = Array.isArray(data.events) ? data.events : [];
  const pois = Array.isArray(data.pois) ? data.pois : [];
  const news = Array.isArray(data.news) ? data.news : [];
  const crimes = Array.isArray(data.crimes) ? data.crimes : [];

  // Debug logging (remove in production)
  if (process.env.NODE_ENV === 'development') {
    console.log('Location Data Debug:', {
      events: events.length,
      pois: pois.length,
      news: news.length,
      crimes: crimes.length,
      dataKeys: Object.keys(data || {})
    });
  }

  // Safely map items with error handling
  const allItems = [
    ...events
      .filter(item => item && typeof item === 'object')
      .map(item => {
        try {
          return { 
            ...item, 
            section: 'Events', 
            type: item.type || 'event',
            id: item.id || `event_${Math.random()}`,
            title: item.title || 'Untitled Event'
          };
        } catch (e) {
          console.error('Error mapping event item:', e, item);
          return null;
        }
      })
      .filter(Boolean),
    ...pois
      .filter(item => item && typeof item === 'object')
      .map(item => {
        try {
          return { 
            ...item, 
            section: 'POIs', 
            type: item.type || 'poi',
            id: item.id || `poi_${Math.random()}`,
            title: item.title || 'Untitled POI'
          };
        } catch (e) {
          console.error('Error mapping POI item:', e, item);
          return null;
        }
      })
      .filter(Boolean),
    ...news
      .filter(item => item && typeof item === 'object')
      .map(item => {
        try {
          return { 
            ...item, 
            section: 'News', 
            type: item.type || 'news',
            id: item.id || `news_${Math.random()}`,
            title: item.title || 'Untitled News'
          };
        } catch (e) {
          console.error('Error mapping news item:', e, item);
          return null;
        }
      })
      .filter(Boolean),
    ...crimes
      .filter(item => item && typeof item === 'object')
      .map(item => {
        try {
          return { 
            ...item, 
            section: 'Crimes', 
            type: item.type || 'crime',
            id: item.id || `crime_${Math.random()}`,
            title: item.title || 'Untitled Crime'
          };
        } catch (e) {
          console.error('Error mapping crime item:', e, item);
          return null;
        }
      })
      .filter(Boolean),
  ];

  // Filter items by selected type
  const filteredItems = filterType === 'all' 
    ? allItems 
    : allItems.filter(item => item.type === filterType);

  // Pagination logic - handle edge cases
  const totalPages = filteredItems.length > 0 
    ? Math.max(1, Math.ceil(filteredItems.length / ITEMS_PER_PAGE))
    : 1;
  const startIndex = Math.max(0, (currentPage - 1) * ITEMS_PER_PAGE);
  const endIndex = Math.min(filteredItems.length, startIndex + ITEMS_PER_PAGE);
  const paginatedItems = filteredItems.slice(startIndex, endIndex);

  const handlePreviousPage = () => {
    setCurrentPage(prev => Math.max(1, prev - 1));
  };

  const handleNextPage = () => {
    setCurrentPage(prev => Math.min(totalPages, prev + 1));
  };

  // Count items by type for display
  const counts = {
    events: events.length,
    pois: pois.length,
    news: news.length,
    crimes: crimes.length,
  };

  if (allItems.length === 0) {
    return (
      <div className="card">
        <h3 className="text-sm font-medium mb-2">Location Data</h3>
        <div className="text-sm text-gray-500 mb-2">No data available for this location</div>
        <div className="text-xs text-gray-400 space-y-1">
          <div>Events: {counts.events}</div>
          <div>POIs: {counts.pois}</div>
          <div>News: {counts.news}</div>
          <div>Crimes: {counts.crimes}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <h3 className="text-sm font-medium mb-2">Location Data</h3>
      
      {/* Filter tabs */}
      <div className="flex flex-wrap gap-1 mb-3">
        <button
          onClick={() => setFilterType('all')}
          className={`text-xs px-2 py-1 rounded transition-colors ${
            filterType === 'all' 
              ? 'bg-primary-600 text-white' 
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          All ({allItems.length})
        </button>
        {counts.events > 0 && (
          <button
            onClick={() => setFilterType('event')}
            className={`text-xs px-2 py-1 rounded transition-colors ${
              filterType === 'event' 
                ? 'bg-blue-600 text-white' 
                : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
            }`}
          >
            🎉 Events ({counts.events})
          </button>
        )}
        {counts.pois > 0 && (
          <button
            onClick={() => setFilterType('poi')}
            className={`text-xs px-2 py-1 rounded transition-colors ${
              filterType === 'poi' 
                ? 'bg-green-600 text-white' 
                : 'bg-green-50 text-green-700 hover:bg-green-100'
            }`}
          >
            📍 POIs ({counts.pois})
          </button>
        )}
        {counts.news > 0 && (
          <button
            onClick={() => setFilterType('news')}
            className={`text-xs px-2 py-1 rounded transition-colors ${
              filterType === 'news' 
                ? 'bg-yellow-600 text-white' 
                : 'bg-yellow-50 text-yellow-700 hover:bg-yellow-100'
            }`}
          >
            📰 News ({counts.news})
          </button>
        )}
        {counts.crimes > 0 && (
          <button
            onClick={() => setFilterType('crime')}
            className={`text-xs px-2 py-1 rounded transition-colors ${
              filterType === 'crime' 
                ? 'bg-red-600 text-white' 
                : 'bg-red-50 text-red-700 hover:bg-red-100'
            }`}
          >
            ⚠️ Crimes ({counts.crimes})
          </button>
        )}
      </div>

      {/* Items list */}
      {filteredItems.length === 0 ? (
        <div className="text-sm text-gray-500 py-4 text-center">
          No {filterType === 'all' ? '' : filterType} items to display
        </div>
      ) : (
        <>
          <div className="space-y-3 max-h-[600px] overflow-y-auto">
            {paginatedItems.map((item, index) => (
          <div
            key={`${item.id}-${index}`}
            className={`p-3 border rounded-lg transition-colors ${getTypeColor(item.type)}`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-start gap-2 flex-1 min-w-0">
                <span className="text-lg flex-shrink-0">{getTypeIcon(item.type)}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-sm truncate">
                      {item.title}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded bg-white/50">
                      {item.section}
                    </span>
                  </div>
                  {item.description && (
                    <p className="text-xs text-gray-700 line-clamp-2 mb-1">
                      {item.description}
                    </p>
                  )}
                  <div className="flex items-center gap-2 text-xs text-gray-600">
                    {item.distance_km && (
                      <span>📍 {item.distance_km.toFixed(1)} km</span>
                    )}
                    {item.category && (
                      <span>• {item.category}</span>
                    )}
                    {item.date && (
                      <span>• {new Date(item.date).toLocaleDateString()}</span>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                <button
                  onClick={() => handleLike(item)}
                  className={`p-1.5 rounded transition-colors ${
                    item.is_liked
                      ? 'text-red-600 hover:bg-red-100'
                      : 'text-gray-400 hover:text-red-600 hover:bg-gray-100'
                  }`}
                  title={item.is_liked ? 'Unlike' : 'Like'}
                  disabled={interactionMutation.isLoading}
                >
                  {item.is_liked ? (
                    <Heart className="w-4 h-4 fill-current" />
                  ) : (
                    <Heart className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>
          </div>
          ))}
          </div>

          {/* Pagination controls */}
          {filteredItems.length > ITEMS_PER_PAGE && (
            <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-200">
              <button
                onClick={handlePreviousPage}
                disabled={currentPage === 1}
                className={`flex items-center gap-1 px-3 py-1.5 rounded text-sm transition-colors ${
                  currentPage === 1
                    ? 'text-gray-400 cursor-not-allowed'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
                title="Previous page"
              >
                <ChevronLeft className="w-4 h-4" />
                Previous
              </button>
              
              <span className="text-sm text-gray-600">
                Page {currentPage} of {totalPages}
              </span>
              
              <button
                onClick={handleNextPage}
                disabled={currentPage === totalPages}
                className={`flex items-center gap-1 px-3 py-1.5 rounded text-sm transition-colors ${
                  currentPage === totalPages
                    ? 'text-gray-400 cursor-not-allowed'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
                title="Next page"
              >
                Next
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

