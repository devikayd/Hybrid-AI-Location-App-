import React, { useState } from 'react';
import { useMutation, useQueryClient, useQuery } from '@tanstack/react-query';
import { Heart, X } from 'lucide-react';
import { addInteraction, getUserRecommendations } from '../services/api';
import { useMapStore } from '../stores/mapStore';
import { useLocationData } from '../hooks/useLocationData';

// Max visible items in scrollable container (3-4 items)
const MAX_VISIBLE_ITEMS = 4;
const ITEM_HEIGHT = 110; // Approximate height per item in pixels
const MAX_HEIGHT = MAX_VISIBLE_ITEMS * ITEM_HEIGHT; // ~440px for 4 items

export default function LocationDataList() {
  const { center } = useMapStore();
  const [filterType, setFilterType] = useState('all'); // for 'all', 'event', 'poi', 'news', 'crime', 'recommendations'
  const [selectedItem, setSelectedItem] = useState(null); // For modal
  
  // Get userId from sessionStorage (shared with useLocationData hook)
  const userId = React.useMemo(() => {
    let id = sessionStorage.getItem('userId');
    if (!id) {
      id = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      sessionStorage.setItem('userId', id);
    }
    return id;
  }, []);

  const queryClient = useQueryClient();
  
  // Use shared location data hook (prevents duplicate API calls)
  const { data, isLoading, error } = useLocationData();
  
  // Fetch recommendations - will automatically refetch when invalidated after interactions
  const { data: recommendationsData } = useQuery({
    queryKey: ['user-recommendations', center, userId],
    queryFn: () => getUserRecommendations(userId, {
      lat: center?.lat || 51.5074,
      lon: center?.lon || -0.1278,
      radius_km: 10,
      limit: 10
    }),
    enabled: !!(center && center.lat && center.lon),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
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
      // Also invalidate recommendations (invalidate all for this user regardless of center)
      queryClient.invalidateQueries({ queryKey: ['user-recommendations'], exact: false });
    }
  });

  // Early return if no center set (AFTER all hooks)
  if (!center || !center.lat || !center.lon) {
    return (
      <div className="card">
        <h3 className="text-sm font-medium mb-2">Location Data</h3>
        <div className="text-sm text-gray-500">Search for a location to see data</div>
      </div>
    );
  }

  const handleLike = (e, item) => {
    e.stopPropagation(); // Prevent opening modal when clicking like button
    
    // Optimistically update the UI immediately
    queryClient.setQueryData(['location-data', center, userId], (oldData) => {
      if (!oldData) return oldData;
      
      const updateItem = (items) => items.map(i => 
        i.id === item.id && i.type === item.type
          ? { ...i, is_liked: !i.is_liked }
          : i
      );
      
      return {
        ...oldData,
        events: updateItem(oldData.events || []),
        pois: updateItem(oldData.pois || []),
        news: updateItem(oldData.news || []),
        crimes: updateItem(oldData.crimes || [])
      };
    });
    
    // Also update selectedItem if modal is open
    if (selectedItem && selectedItem.id === item.id && selectedItem.type === item.type) {
      setSelectedItem({ ...selectedItem, is_liked: !selectedItem.is_liked });
    }
    
    // Then make the API call
    interactionMutation.mutate({ item, interactionType: 'like' });
  };

  const handleItemClick = (item) => {
    // Ensure all numeric fields are properly converted
    const processedItem = {
      ...item,
      lat: item.lat ? Number(item.lat) : null,
      lon: item.lon ? Number(item.lon) : null,
      distance_km: item.distance_km ? Number(item.distance_km) : null,
    };
    setSelectedItem(processedItem);
  };

  const closeModal = () => {
    setSelectedItem(null);
  };

  // Format time ago for past events
  const formatTimeAgo = (hoursAgo) => {
    if (!hoursAgo && hoursAgo !== 0) return null;
    
    if (hoursAgo < 1) {
      const minutes = Math.floor(hoursAgo * 60);
      return minutes <= 1 ? 'Just now' : `${minutes} min ago`;
    } else if (hoursAgo < 24) {
      const hours = Math.floor(hoursAgo);
      return `${hours} ${hours === 1 ? 'hour' : 'hours'} ago`;
    } else {
      const days = Math.floor(hoursAgo / 24);
      return `${days} ${days === 1 ? 'day' : 'days'} ago`;
    }
  };

  // Format time ahead for upcoming events
  const formatTimeAhead = (hoursAhead) => {
    if (!hoursAhead && hoursAhead !== 0) return null;
    
    if (hoursAhead < 1) {
      const minutes = Math.floor(hoursAhead * 60);
      // If event is happening now (within 1 hour), return null to show nothing
      if (minutes <= 1) return null;
      return `In ${minutes} min`;
    } else if (hoursAhead < 24) {
      const hours = Math.floor(hoursAhead);
      return `In ${hours} ${hours === 1 ? 'hour' : 'hours'}`;
    } else {
      const days = Math.floor(hoursAhead / 24);
      return `In ${days} ${days === 1 ? 'day' : 'days'}`;
    }
  };

  const getTypeIcon = (type) => {
    const icons = {
      event: '🎉',
      crime: '⚠️',
      news: '📰',
      poi: '📍',
      recommendation: '⭐',
    };
    return icons[type] || '📍';
  };

  const getTypeColor = (type) => {
    const colors = {
      event: 'text-blue-600 bg-blue-50 border-blue-200',
      crime: 'text-red-600 bg-red-50 border-red-200',
      news: 'text-yellow-600 bg-yellow-50 border-yellow-200',
      poi: 'text-green-600 bg-green-50 border-green-200',
      recommendation: 'text-purple-600 bg-purple-50 border-purple-200',
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
  const events = Array.isArray(data?.events) ? data.events : [];
  const pois = Array.isArray(data?.pois) ? data.pois : [];
  const news = Array.isArray(data?.news) ? data.news : [];
  const crimes = Array.isArray(data?.crimes) ? data.crimes : [];
  const recommendations = Array.isArray(recommendationsData?.recommendations) ? recommendationsData.recommendations : [];

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
    ...recommendations
      .filter(item => item && typeof item === 'object')
      .map(item => {
        try {
          return { 
            ...item, 
            section: 'Recommendations', 
            type: item.type || 'recommendation',
            id: item.id || `recommendation_${Math.random()}`,
            title: item.title || 'Untitled Recommendation',
            is_recommendation: true  // Flag to identify recommendations
          };
        } catch (e) {
          console.error('Error mapping recommendation item:', e, item);
          return null;
        }
      })
      .filter(Boolean),
  ];

  // Debug logging to help diagnose issues (after allItems is declared)
  if (process.env.NODE_ENV === 'development') {
    console.log('Location Data Debug:', {
      events: events.length,
      pois: pois.length,
      news: news.length,
      crimes: crimes.length,
      recommendations: recommendations.length,
      dataKeys: Object.keys(data || {}),
      rawData: data,
      error: error,
      allItemsLength: allItems.length,
      samplePOI: pois[0],
      sampleNews: news[0],
      sampleCrime: crimes[0]
    });
  }

  // Filter items by selected type
  const filteredItems = filterType === 'all' 
    ? allItems 
    : filterType === 'recommendations'
    ? allItems.filter(item => item.is_recommendation === true)
    : allItems.filter(item => item.type === filterType);

  // Count items by type for display
  const counts = {
    events: events.length,
    pois: pois.length,
    news: news.length,
    crimes: crimes.length,
    recommendations: recommendations.length,
  };

  if (allItems.length === 0) {
    return (
      <div className="card">
        <h3 className="text-sm font-medium mb-2">Results</h3>
        <div className="text-sm text-gray-500 mb-2">No data available for this location</div>
        <div className="text-xs text-gray-400 space-y-1">
          <p> Try searching a different location</p>
        </div>
      </div>
    );
  }
  return (
    <div className="card">
      <h3 className="text-sm font-medium mb-2">Results</h3>
      
      {/* Filter tabs */}
      <div className="flex flex-wrap gap-1 mb-3">
           {counts.recommendations > 0 && (
          <button
            onClick={() => setFilterType('recommendations')}
            className={`text-xs px-2 py-1 rounded transition-colors ${
              filterType === 'recommendations' 
                ? 'bg-purple-600 text-white' 
                : 'bg-purple-50 text-purple-700 hover:bg-purple-100'
            }`}
          >
            ⭐ Recommendations ({counts.recommendations})
          </button>
        )}
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

      {/* Items list - scrollable container showing 4-5 items */}
      {filteredItems.length === 0 ? (
        <div className="text-sm text-gray-500 py-4 text-center">
          No {filterType === 'all' ? '' : filterType === 'recommendations' ? 'recommendations' : filterType} items to display
        </div>
      ) : (
        <div 
          className="space-y-3 overflow-y-auto pr-2"
          style={{ maxHeight: `${MAX_HEIGHT}px` }}
        >
          {filteredItems.map((item, index) => (
          <div
            key={`${item.id}-${index}`}
            className={`p-3 border rounded-lg transition-colors cursor-pointer hover:shadow-md ${getTypeColor(item.type)}`}
            onClick={() => handleItemClick(item)}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-start gap-2 flex-1 min-w-0">
                <span className="text-lg flex-shrink-0">{getTypeIcon(item.type)}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-sm truncate">
                      {item.title}
                    </span>
                    {item.section && item.section !== 'Recommendations' && (
                      <span className="text-xs px-2 py-0.5 rounded bg-white/50">
                        {item.section}
                      </span>
                    )}
                    {item.is_recommendation && (
                      <span className="text-xs px-2 py-0.5 rounded bg-purple-100 text-purple-700">
                        ⭐ Rec
                      </span>
                    )}
                  </div>
                  {item.description && (
                    <p className="text-xs text-gray-700 line-clamp-2 mb-1">
                      {item.description}
                    </p>
                  )}
                  <div className="flex items-center gap-2 text-xs text-gray-600 flex-wrap">
                    {/* Time indicators */}
                    {item.metadata?.hours_ago !== undefined && item.metadata.hours_ago !== null && item.metadata.hours_ago > 0 && (
                      <span className="text-red-600 font-medium">
                        {formatTimeAgo(item.metadata.hours_ago)}
                      </span>
                    )}
                    {item.metadata?.hours_ahead !== undefined && item.metadata.hours_ahead !== null && item.metadata.hours_ahead > 0 && formatTimeAhead(item.metadata.hours_ahead) && (
                      <span className="text-blue-600 font-medium">
                        {formatTimeAhead(item.metadata.hours_ahead)}
                      </span>
                    )}
                    {item.distance_km && (
                      <span>📍 {Number(item.distance_km).toFixed(1)} km</span>
                    )}
                    {item.category && (
                      <span>• {item.category}</span>
                    )}
                    {item.date && !item.metadata?.hours_ago && !item.metadata?.hours_ahead && (
                      <span>• {new Date(item.date).toLocaleDateString()}</span>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1 flex-shrink-0">
                <button
                  onClick={(e) => handleLike(e, item)}
                  className={`p-1.5 rounded transition-colors ${
                    item.is_liked
                      ? 'text-red-600 hover:bg-red-100'
                      : 'text-gray-400 hover:text-red-600 hover:bg-gray-100'
                  }`}
                  title={item.is_liked ? 'Unlike' : 'Like'}
                  disabled={interactionMutation.isLoading}
                >
                  <Heart className={`w-4 h-4 ${item.is_liked ? 'fill-current' : ''}`} />
                </button>
              </div>
            </div>
          </div>
          ))}
        </div>
      )}

      {/* Modal for item details - small card popup */}
      {selectedItem && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-30 flex items-center justify-center z-[9999] p-4"
          onClick={closeModal}
        >
          <div 
            className={`bg-white rounded-lg shadow-2xl max-w-md w-full max-h-[80vh] overflow-y-auto z-[10000] ${getTypeColor(selectedItem.type || 'poi')}`}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-start justify-between p-4 border-b border-gray-200">
              <div className="flex items-start gap-3 flex-1 min-w-0">
                <span className="text-2xl flex-shrink-0">{getTypeIcon(selectedItem.type)}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h2 className="text-lg font-semibold text-gray-900 truncate">{selectedItem.title}</h2>
                    {selectedItem.section && selectedItem.section !== 'Recommendations' && (
                      <span className="text-xs px-2 py-0.5 rounded bg-white/50 flex-shrink-0">
                        {selectedItem.section}
                      </span>
                    )}
                    {selectedItem.is_recommendation && (
                      <span className="text-xs px-2 py-0.5 rounded bg-purple-100 text-purple-700 flex-shrink-0">
                        ⭐ Recommendation
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-600 flex-wrap">
                    {/* Time indicators in modal */}
                    {selectedItem.metadata?.hours_ago !== undefined && selectedItem.metadata.hours_ago !== null && selectedItem.metadata.hours_ago > 0 && (
                      <span className="text-red-600 font-medium">
                        {formatTimeAgo(selectedItem.metadata.hours_ago)}
                      </span>
                    )}
                    {selectedItem.metadata?.hours_ahead !== undefined && selectedItem.metadata.hours_ahead !== null && selectedItem.metadata.hours_ahead > 0 && formatTimeAhead(selectedItem.metadata.hours_ahead) && (
                      <span className="text-blue-600 font-medium">
                        {formatTimeAhead(selectedItem.metadata.hours_ahead)}
                      </span>
                    )}
                    {selectedItem.category && (
                      <span className="font-medium">Category: {selectedItem.category}</span>
                    )}
                    {selectedItem.subtype && (
                      <span>Type: {selectedItem.subtype}</span>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  onClick={(e) => handleLike(e, selectedItem)}
                  className={`p-1.5 rounded-full transition-colors ${
                    selectedItem.is_liked
                      ? 'text-red-600 hover:bg-red-100'
                      : 'text-gray-400 hover:text-red-600 hover:bg-gray-100'
                  }`}
                  title={selectedItem.is_liked ? 'Unlike' : 'Like'}
                  disabled={interactionMutation.isLoading}
                >
                  <Heart className={`w-5 h-5 ${selectedItem.is_liked ? 'fill-current' : ''}`} />
                </button>
                <button
                  onClick={closeModal}
                  className="p-1.5 hover:bg-gray-100 rounded-full transition-colors"
                  title="Close"
                >
                  <X className="w-5 h-5 text-gray-500" />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-4 space-y-3">
              {selectedItem.description && (
                <div>
                  <h3 className="text-sm font-semibold text-gray-700 mb-2">Description</h3>
                  <p className="text-sm text-gray-800 whitespace-pre-wrap">{selectedItem.description}</p>
                </div>
              )}

              <div className="grid grid-cols-1 gap-3">
                {selectedItem.distance_km && (
                  <div>
                    <h3 className="text-xs font-semibold text-gray-500 mb-1">Distance</h3>
                    <p className="text-sm text-gray-900">📍 {Number(selectedItem.distance_km).toFixed(1)} km</p>
                  </div>
                )}
                {/* Time status */}
                {((selectedItem.metadata?.hours_ago !== undefined && selectedItem.metadata.hours_ago !== null && selectedItem.metadata.hours_ago > 0) || 
                  (selectedItem.metadata?.hours_ahead !== undefined && selectedItem.metadata.hours_ahead !== null && selectedItem.metadata.hours_ahead > 0 && formatTimeAhead(selectedItem.metadata.hours_ahead))) && (
                  <div>
                    <h3 className="text-xs font-semibold text-gray-500 mb-1">Status</h3>
                    <div className="flex items-center gap-2 flex-wrap">
                      {selectedItem.metadata?.hours_ago !== undefined && selectedItem.metadata.hours_ago !== null && selectedItem.metadata.hours_ago > 0 && (
                        <span className="text-sm text-red-600 font-medium">
                          {formatTimeAgo(selectedItem.metadata.hours_ago)}
                        </span>
                      )}
                      {selectedItem.metadata?.hours_ahead !== undefined && selectedItem.metadata.hours_ahead !== null && selectedItem.metadata.hours_ahead > 0 && formatTimeAhead(selectedItem.metadata.hours_ahead) && (
                        <span className="text-sm text-blue-600 font-medium">
                          {formatTimeAhead(selectedItem.metadata.hours_ahead)}
                        </span>
                      )}
                    </div>
                  </div>
                )}
                {selectedItem.date && (
                  <div>
                    <h3 className="text-xs font-semibold text-gray-500 mb-1">Date</h3>
                    <p className="text-sm text-gray-900">
                      {(() => {
                        try {
                          return new Date(selectedItem.date).toLocaleDateString('en-GB', { 
                            year: 'numeric', 
                            month: 'long', 
                            day: 'numeric' 
                          });
                        } catch (e) {
                          return selectedItem.date;
                        }
                      })()}
                    </p>
                  </div>
                )}
                {selectedItem.location_name && (
                  <div>
                    <h3 className="text-xs font-semibold text-gray-500 mb-1">Address</h3>
                    <p className="text-sm text-gray-900">{selectedItem.location_name}</p>
                  </div>
                )}
              </div>

              {(selectedItem.url || selectedItem.metadata?.website) && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 mb-2">Link</h3>
                  <a 
                    href={selectedItem.url || selectedItem.metadata?.website} 
                    target="_blank" 
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:text-blue-800 underline break-all"
                  >
                    {selectedItem.url || selectedItem.metadata?.website}
                  </a>
                </div>
              )}

              {selectedItem.metadata && Object.keys(selectedItem.metadata).length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 mb-2">Additional Information</h3>
                  <div className="bg-gray-50 rounded-lg p-3">
                    <dl className="grid grid-cols-2 gap-2 text-sm">
                      {Object.entries(selectedItem.metadata)
                        .filter(([key]) => key !== 'hours_ahead' && key !== 'hours_ago') // Exclude hours_ahead and hours_ago as they're already displayed in formatted form above
                        .map(([key, value]) => (
                          value && (
                            <div key={key}>
                              <dt className="font-medium text-gray-700 capitalize">{key.replace(/_/g, ' ')}:</dt>
                              <dd className="text-gray-600">{String(value)}</dd>
                            </div>
                          )
                        ))}
                    </dl>
                  </div>
                </div>
              )}
            </div>

          </div>
        </div>
      )}
    </div>
  );
}

