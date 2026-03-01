import { create } from 'zustand';

export const useMapStore = create((set, get) => ({
  center: { lat: 51.5074, lon: -0.1278 },
  zoom: 13,
  boundingBox: null,   // [minLat, maxLat, minLon, maxLon] from Nominatim
  searchId: 0,         // increments on every search — used as reliable useEffect trigger
  recentSearches: [],
  showRecentSearches: false,
  selectedLocation: null,
  tripPlan: null,
  layers: {
    crimes: false,
    events: false,
    news: false,
    pois: false,
    trip_route: false,
  },
  setCenter: (lat, lon) => set({ center: { lat, lon } }),
  setZoom: (zoom) => set({ zoom }),
  setBoundingBox: (bbox) => set({ boundingBox: bbox }),
  incrementSearchId: () => set((state) => ({ searchId: state.searchId + 1 })),
  setShowRecentSearches: (show) => set({ showRecentSearches: show }),
  setSelectedLocation: (location) => set({ selectedLocation: location }),
  toggleLayer: (key) => set((state) => ({ layers: { ...state.layers, [key]: !state.layers[key] } })),
  setLayerVisibility: (key, visible) => set((state) => ({ layers: { ...state.layers, [key]: visible } })),
  setTripPlan: (plan) => set({ tripPlan: plan, layers: { ...get().layers, trip_route: !!plan } }),
  clearTripPlan: () => set({ tripPlan: null, layers: { ...get().layers, trip_route: false } }),
  addRecentSearch: (item) => set((state) => {
    const exists = state.recentSearches.find((s) => s.query === item.query);
    const list = exists ? state.recentSearches : [item, ...state.recentSearches].slice(0, 8);
    try { localStorage.setItem('recentSearches', JSON.stringify(list)); } catch {}
    return { recentSearches: list };
  }),
  hydrate: () => {
    try {
      const stored = JSON.parse(localStorage.getItem('recentSearches') || '[]');
      set({ recentSearches: stored });
    } catch {}
  },
}));






