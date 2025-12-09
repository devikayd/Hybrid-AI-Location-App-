import { create } from 'zustand';

export const useMapStore = create((set, get) => ({
  center: { lat: 51.5074, lon: -0.1278 },
  zoom: 13,
  recentSearches: [],
  showRecentSearches: false,
  layers: {
    crimes: true,
    events: true,
    news: true,
    pois: true,
  },
  setCenter: (lat, lon) => set({ center: { lat, lon } }),
  setZoom: (zoom) => set({ zoom }),
  setShowRecentSearches: (show) => set({ showRecentSearches: show }),
  toggleLayer: (key) => set((state) => ({ layers: { ...state.layers, [key]: !state.layers[key] } })),
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






