import { useQuery } from '@tanstack/react-query';
import { getCrimes, getEvents, getNews, getPOIs, getSummary, getScores } from '../services/api';
import { useMapStore } from '../stores/mapStore';

export function useCrimes({ months = 12, category, limit = 300 } = {}) {
  const { center } = useMapStore();
  return useQuery({
    queryKey: ['crimes', center, months, category, limit],
    queryFn: () => getCrimes({ lat: center.lat, lon: center.lon, months, category, limit }),
    staleTime: 60_000,
    enabled: !!center,
  });
}

export function useEvents({ within_km = 10, q, limit = 200 } = {}) {
  const { center } = useMapStore();
  return useQuery({
    queryKey: ['events', center, within_km, q, limit],
    queryFn: () => getEvents({ lat: center.lat, lon: center.lon, within_km, q, limit }),
    staleTime: 60_000,
    enabled: !!center,
  });
}

export function useNews({ radius_km = 50, q, limit = 50 } = {}) {
  const { center } = useMapStore();
  return useQuery({
    queryKey: ['news', center, radius_km, q, limit],
    queryFn: () => getNews({ lat: center.lat, lon: center.lon, radius_km, q, limit }),
    staleTime: 60_000,
    enabled: !!center,
  });
}

export function usePOIs({ radius_km = 5, types, limit = 300 } = {}) {
  const { center } = useMapStore();
  return useQuery({
    queryKey: ['pois', center, radius_km, types, limit],
    queryFn: () => getPOIs({ lat: center.lat, lon: center.lon, radius_km, types, limit }),
    staleTime: 60_000,
    enabled: !!center,
  });
}

export function useSummary({ radius_km = 5, include_crimes = true, include_events = true, include_news = true, include_pois = true, max_items_per_type = 50 } = {}) {
  const { center } = useMapStore();
  return useQuery({
    queryKey: ['summary', center, radius_km, include_crimes, include_events, include_news, include_pois, max_items_per_type],
    queryFn: () => getSummary({
      lat: center.lat,
      lon: center.lon,
      radius_km,
      include_crimes,
      include_events,
      include_news,
      include_pois,
      max_items_per_type,
    }),
    staleTime: 5 * 60_000,
    enabled: !!center,
    retry: 1,
    retryDelay: 2000,
  });
}

export function useScores({ radius_km = 5 } = {}) {
  const { center } = useMapStore();
  return useQuery({
    queryKey: ['scores', center, radius_km],
    queryFn: () => getScores({ lat: center.lat, lon: center.lon, radius_km }),
    staleTime: 5 * 60_000,
    enabled: !!center,
    retry: 1,
    retryDelay: 2000,
  });
}




