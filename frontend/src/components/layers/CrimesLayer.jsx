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

const crimeIcon = createEmojiPinIcon('👮', '#dc2626');

export default function CrimesLayer() {
  // Use shared location data hook
  const { data, isLoading } = useLocationData();

  if (isLoading || !data?.crimes?.length) return null;

  return (
    <>
      {data.crimes.map((c) => {
        const lat = Number(c?.lat);
        const lon = Number(c?.lon);
        if (!lat || !lon) return null;
        return (
          <Marker key={c.id} position={[lat, lon]} icon={crimeIcon}>
            <Popup>
              <div className="text-sm">
                <div className="font-medium">{c.title || c.category}</div>
                {c.category && <div className="text-gray-600">{c.category}</div>}
                {c.date && <div className="text-xs text-gray-500">{new Date(c.date).toLocaleDateString()}</div>}
              </div>
            </Popup>
          </Marker>
        );
      })}
    </>
  );
}





