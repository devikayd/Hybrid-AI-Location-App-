import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useMapStore } from '../stores/mapStore';
import { getUserRecommendations } from '../services/api';

export default function Recommendations() {
  const { center } = useMapStore();
  
  // Generate user ID (same as other components for consistency)
  const userId = React.useMemo(() => {
    let id = sessionStorage.getItem('userId');
    if (!id) {
      id = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      sessionStorage.setItem('userId', id);
    }
    return id;
  }, []);

  // Fetch recommendations based on user interactions
  const { data: recommendationsData, isLoading, isError } = useQuery({
    queryKey: ['user-recommendations', center, userId],
    queryFn: () => getUserRecommendations(userId, {
      lat: center?.lat || 51.5074,
      lon: center?.lon || -0.1278,
      radius_km: 10,
      limit: 10
    }),
    enabled: !!(center && center.lat && center.lon),
    staleTime: 60_000,
  });

  // Don't show if no center or no interactions
  if (!center || !center.lat || !center.lon) {
    return null;
  }

  // Show message if no interactions yet
  if (!isLoading && !isError && recommendationsData?.based_on_interactions === 0) {
    return (
      <div className="card">
        <h3 className="text-sm font-medium mb-2">Recommendations</h3>
        <p className="text-sm text-gray-600">
          Start liking items to get personalized recommendations!
        </p>
      </div>
    );
  }

  // Show loading state
  if (isLoading) {
    return (
      <div className="card">
        <h3 className="text-sm font-medium mb-2">Recommendations</h3>
        <p className="text-sm text-gray-600">Loading recommendations...</p>
      </div>
    );
  }

  // Show error state
  if (isError) {
    return (
      <div className="card">
        <h3 className="text-sm font-medium mb-2">Recommendations</h3>
        <p className="text-sm text-red-600">Failed to load recommendations</p>
      </div>
    );
  }

  const recommendations = recommendationsData?.recommendations || [];
  const totalInteractions = recommendationsData?.based_on_interactions || 0;

  // Don't show if no recommendations
  if (recommendations.length === 0) {
    return (
      <div className="card">
        <h3 className="text-sm font-medium mb-2">Recommendations</h3>
        <p className="text-sm text-gray-600">
          No recommendations available for this location yet.
        </p>
      </div>
    );
  }

  // Helper function to get type color
  const getTypeColor = (type) => {
    const colors = {
      event: 'bg-blue-100 text-blue-800',
      poi: 'bg-green-100 text-green-800',
      news: 'bg-yellow-100 text-yellow-800',
      crime: 'bg-red-100 text-red-800',
    };
    return colors[type] || 'bg-gray-100 text-gray-800';
  };

  // Helper function to format match score
  const formatMatchScore = (score) => {
    return (score * 100).toFixed(0);
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium">Recommendations</h3>
        {totalInteractions > 0 && (
          <span className="text-xs text-gray-500">
            Based on {totalInteractions} {totalInteractions === 1 ? 'interaction' : 'interactions'}
          </span>
        )}
      </div>

      <div className="space-y-3">
        {recommendations.map((item) => (
          <div
            key={item.id}
            className="p-3 border border-gray-200 rounded-lg hover:border-primary-300 hover:shadow-sm transition-all"
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs px-2 py-0.5 rounded ${getTypeColor(item.type)}`}>
                    {item.type.toUpperCase()}
                  </span>
                  {item.category && (
                    <span className="text-xs text-gray-500">{item.category}</span>
                  )}
                </div>
                <h4 className="text-sm font-medium text-gray-900 truncate">
                  {item.title}
                </h4>
              </div>
              <div className="flex-shrink-0">
                <span className="text-xs font-medium text-primary-600">
                  {formatMatchScore(item.match_score)}% match
                </span>
              </div>
            </div>

            {item.description && (
              <p className="text-xs text-gray-600 mb-2 line-clamp-2">
                {item.description}
              </p>
            )}

            <div className="flex items-center justify-between">
              <p className="text-xs text-gray-500 italic">
                {item.relevance_reason}
              </p>
              <div className="text-xs text-gray-400">
                {Number(item.lat).toFixed(3)}, {Number(item.lon).toFixed(3)}
              </div>
            </div>
          </div>
        ))}
      </div>

      {recommendations.length >= 10 && (
        <p className="text-xs text-gray-500 mt-3 text-center">
          Showing top 10 recommendations
        </p>
      )}
    </div>
  );
}



