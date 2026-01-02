/**
 * Action Executor for Chat UI Actions
 *
 * Processes UI actions returned from the chat API and executes them
 * by updating the map store or triggering data refreshes.
 */

/**
 * Execute an array of UI actions from chat response
 * @param {Array} actions - Array of UI action objects
 * @param {Object} store - Zustand store with map actions
 * @param {Object} queryClient - React Query client for cache invalidation
 */
export function executeActions(actions, store, queryClient) {
  if (!actions || !Array.isArray(actions)) return;

  actions.forEach((action) => {
    try {
      executeAction(action, store, queryClient);
    } catch (error) {
      console.error('Failed to execute action:', action.type, error);
    }
  });
}

/**
 * Execute a single UI action
 * @param {Object} action - UI action object with type and payload
 * @param {Object} store - Zustand store
 * @param {Object} queryClient - React Query client
 */
function executeAction(action, store, queryClient) {
  const { type, payload } = action;

  switch (type) {
    case 'SET_VIEWPORT':
      handleSetViewport(payload, store);
      break;

    case 'FIT_BOUNDS':
      handleFitBounds(payload, store);
      break;

    case 'HIGHLIGHT_RESULTS':
      handleHighlightResults(payload, store);
      break;

    case 'CLEAR_HIGHLIGHTS':
      handleClearHighlights(store);
      break;

    case 'REFRESH_DATA':
      handleRefreshData(payload, queryClient);
      break;

    case 'SET_FILTERS':
      handleSetFilters(payload, store);
      break;

    default:
      console.warn('Unknown action type:', type);
  }
}

/**
 * Navigate map to specific location
 */
function handleSetViewport(payload, store) {
  const { lat, lng, zoom, animate = true } = payload;

  if (lat !== undefined && lng !== undefined) {
    store.setFlyToTarget({
      lat,
      lng,
      zoom: zoom || null,
      animate,
    });
  }
}

/**
 * Fit map to show specified bounds
 */
function handleFitBounds(payload, store) {
  const { bbox, padding = 50, max_zoom } = payload;

  if (bbox && Array.isArray(bbox) && bbox.length === 4) {
    store.setFitBoundsTarget({
      bbox,
      padding,
      maxZoom: max_zoom,
    });
  }
}

/**
 * Highlight specific items on the map
 */
function handleHighlightResults(payload, store) {
  const { ids, scroll_to_first = false } = payload;

  if (ids && Array.isArray(ids) && ids.length > 0) {
    store.setHighlightedItems(ids);

    // Optional: scroll to first highlighted item in list
    if (scroll_to_first) {
      const firstId = ids[0];
      const element = document.getElementById(`item-${firstId}`);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }
}

/**
 * Clear all highlights
 */
function handleClearHighlights(store) {
  store.clearHighlightedItems();
}

/**
 * Refresh location data
 */
function handleRefreshData(payload, queryClient) {
  const { types, force = false } = payload || {};

  if (types && Array.isArray(types)) {
    // Refresh specific data types
    types.forEach((type) => {
      queryClient.invalidateQueries({ queryKey: [type] });
    });
  } else {
    // Refresh all location data
    queryClient.invalidateQueries({ queryKey: ['location-data'] });
  }

  if (force) {
    // Force refetch by also clearing stale data
    queryClient.refetchQueries({ queryKey: ['location-data'] });
  }
}

/**
 * Update active filters (placeholder for future implementation)
 */
function handleSetFilters(payload, store) {
  // Future: Implement filter state management
  console.log('SET_FILTERS action received:', payload);
  // store.setFilters(payload);
}

export default executeActions;
