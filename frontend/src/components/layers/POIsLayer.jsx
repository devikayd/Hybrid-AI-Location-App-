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

const poiIcon = createEmojiPinIcon('📍', '#16a34a');

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





