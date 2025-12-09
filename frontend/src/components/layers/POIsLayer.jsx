import React from 'react';
import { Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { useLocationData } from '../../hooks/useLocationData';

function svgToBase64(svg) {
  return btoa(unescape(encodeURIComponent(svg)));
}

function createEmojiPinIcon(emoji, fill = '#2563eb') {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="25" height="41" viewBox="0 0 25 41">
      <path fill="${fill}" d="M12.5 0C5.6 0 0 5.6 0 12.5c0 8.4 12.5 28.5 12.5 28.5S25 20.9 25 12.5C25 5.6 19.4 0 12.5 0z"/>
      <text x="12.5" y="16" font-size="12" text-anchor="middle" alignment-baseline="central">${emoji}</text>
    </svg>
  `;

  return new L.Icon({
    iconUrl: 'data:image/svg+xml;base64,' + svgToBase64(svg),
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [0, -41],
    shadowUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png',
    shadowSize: [41, 41],
    shadowAnchor: [12, 41],
  });
}

/**
 * Get icon configuration for POI based on category/subtype
 * Returns { emoji, color } for the POI category
 */
function getPOIIconConfig(poi) {
  const category = poi?.category?.toLowerCase() || '';
  const subtype = poi?.subtype?.toLowerCase() || '';
  const amenity = poi?.metadata?.amenity?.toLowerCase() || '';
  const tourism = poi?.metadata?.tourism?.toLowerCase() || '';
  const shop = poi?.metadata?.shop?.toLowerCase() || '';
  
  // Check amenity types first
  if (amenity || category.includes('restaurant') || category.includes('food')) {
    if (amenity === 'restaurant' || category.includes('restaurant')) return { emoji: '🍽️', color: '#dc2626' };
    if (amenity === 'cafe' || category.includes('cafe')) return { emoji: '☕', color: '#92400e' };
    if (amenity === 'bar' || amenity === 'pub') return { emoji: '🍺', color: '#7c2d12' };
    if (amenity === 'fast_food') return { emoji: '🍔', color: '#ea580c' };
    if (amenity === 'ice_cream') return { emoji: '🍦', color: '#fbbf24' };
  }
  
  // Essential services
  if (amenity === 'hospital' || category.includes('hospital')) return { emoji: '🏥', color: '#dc2626' };
  if (amenity === 'pharmacy') return { emoji: '💊', color: '#dc2626' };
  if (amenity === 'bank' || amenity === 'atm') return { emoji: '🏦', color: '#1e40af' };
  if (amenity === 'fuel') return { emoji: '⛽', color: '#f59e0b' };
  if (amenity === 'police') return { emoji: '🚔', color: '#1e40af' };
  if (amenity === 'fire_station') return { emoji: '🚒', color: '#dc2626' };
  if (amenity === 'post_office') return { emoji: '📮', color: '#1e40af' };
  
  // Education
  if (amenity === 'school' || amenity === 'kindergarten') return { emoji: '🏫', color: '#059669' };
  if (amenity === 'university' || amenity === 'college') return { emoji: '🎓', color: '#059669' };
  if (amenity === 'library') return { emoji: '📚', color: '#059669' };
  
  // Entertainment
  if (amenity === 'cinema') return { emoji: '🎬', color: '#7c3aed' };
  if (amenity === 'theatre') return { emoji: '🎭', color: '#7c3aed' };
  if (amenity === 'community_centre') return { emoji: '🏛️', color: '#6366f1' };
  
  // Accommodation
  if (amenity === 'hotel') return { emoji: '🏨', color: '#0891b2' };
  if (amenity === 'hostel' || amenity === 'guesthouse') return { emoji: '🛏️', color: '#0891b2' };
  
  // Tourism
  if (tourism === 'attraction' || tourism === 'museum' || category.includes('museum')) return { emoji: '🏛️', color: '#7c3aed' };
  if (tourism === 'gallery') return { emoji: '🖼️', color: '#7c3aed' };
  if (tourism === 'zoo') return { emoji: '🦁', color: '#059669' };
  if (tourism === 'theme_park') return { emoji: '🎢', color: '#dc2626' };
  if (tourism === 'viewpoint') return { emoji: '👁️', color: '#0891b2' };
  if (tourism === 'monument' || tourism === 'memorial') return { emoji: '🗿', color: '#6366f1' };
  if (tourism === 'artwork') return { emoji: '🎨', color: '#7c3aed' };
  if (tourism === 'castle') return { emoji: '🏰', color: '#7c3aed' };
  
  // Shops
  if (shop === 'supermarket' || shop === 'convenience') return { emoji: '🛒', color: '#16a34a' };
  if (shop === 'clothes' || shop === 'fashion') return { emoji: '👕', color: '#ec4899' };
  if (shop === 'electronics') return { emoji: '📱', color: '#6366f1' };
  if (shop === 'books') return { emoji: '📖', color: '#059669' };
  if (shop === 'bakery') return { emoji: '🥖', color: '#f59e0b' };
  if (shop === 'butcher') return { emoji: '🥩', color: '#dc2626' };
  if (shop === 'florist') return { emoji: '🌸', color: '#ec4899' };
  if (shop === 'jewelry') return { emoji: '💍', color: '#fbbf24' };
  
  // Default fallback
  return { emoji: '📍', color: '#16a34a' };
}

export default function POIsLayer() {
  // Use shared location data hook (prevents duplicate API calls)
  const { data, isLoading } = useLocationData();

  if (isLoading || !data?.pois?.length) return null;

  return (
    <>
      {data.pois.map((p) => {
        const lat = Number(p?.lat);
        const lon = Number(p?.lon);
        if (!lat || !lon) return null;
        
        // Get icon configuration based on POI category
        const iconConfig = getPOIIconConfig(p);
        const poiIcon = createEmojiPinIcon(iconConfig.emoji, iconConfig.color);
        
        return (
          <Marker key={p.id} position={[lat, lon]} icon={poiIcon}>
            <Popup>
              <div className="text-sm">
                <div className="font-medium">{p.title || p.tags?.name || p.type}</div>
                {p.category && <div className="text-gray-600">{p.category}</div>}
                {p.description && <div className="text-xs text-gray-500 mt-1">{p.description.substring(0, 80)}...</div>}
                {p.url && (
                  <a href={p.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline text-xs mt-1 block">
                    View Details
                  </a>
                )}
              </div>
            </Popup>
          </Marker>
        );
      })}
    </>
  );
}





