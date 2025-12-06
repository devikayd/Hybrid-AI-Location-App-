import { useQuery } from '@tanstack/react-query';
import { getLocationData } from '../services/api';
import { useMapStore } from '../stores/mapStore';
import { useMemo } from 'react';

/**
 * Shared hook for location data - prevents duplicate API calls
 * All components should use this hook instead of calling getLocationData directly
 */
export function useLocationData() {
  const { center } = useMapStore();
  
  // Generate stable user ID (shared across all components)
  const userId = useMemo(() => {
    let id = sessionStorage.getItem('userId');
    if (!id) {
      id = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      sessionStorage.setItem('userId', id);
    }
    return id;
  }, []);

  return useQuery({
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
}

