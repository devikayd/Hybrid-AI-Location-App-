import { create } from 'zustand';

export const useMapStore = create((set, get) => ({
  // Map state
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

  // Chat-triggered map actions
  highlightedItems: [],
  flyToTarget: null,
  fitBoundsTarget: null,

  // Map actions
  setCenter: (lat, lon) => set({ center: { lat, lon } }),
  setZoom: (zoom) => set({ zoom }),
  setShowRecentSearches: (show) => set({ showRecentSearches: show }),
  toggleLayer: (key) => set((state) => ({ layers: { ...state.layers, [key]: !state.layers[key] } })),

  // Recent searches
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

  // Chat action handlers
  setHighlightedItems: (ids) => set({ highlightedItems: ids }),
  clearHighlightedItems: () => set({ highlightedItems: [] }),
  setFlyToTarget: (target) => set({ flyToTarget: target }),
  setFitBoundsTarget: (bounds) => set({ fitBoundsTarget: bounds }),
  clearMapActions: () => set({ flyToTarget: null, fitBoundsTarget: null }),

  // Get current bbox from center and zoom (approximate)
  getBbox: () => {
    const { center, zoom } = get();
    // Approximate bbox calculation based on zoom level
    const latDelta = 180 / Math.pow(2, zoom);
    const lngDelta = 360 / Math.pow(2, zoom);
    return [
      center.lon - lngDelta, // west
      center.lat - latDelta, // south
      center.lon + lngDelta, // east
      center.lat + latDelta, // north
    ];
  },
}));






