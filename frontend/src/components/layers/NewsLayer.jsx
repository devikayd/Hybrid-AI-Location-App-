import React from 'react';
import { Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { useLocationData } from '../../hooks/useLocationData';

// Create custom yellow icon for news
const newsIcon = new L.Icon({
  iconUrl: 'data:image/svg+xml;base64,' + btoa(`
    <svg xmlns="http://www.w3.org/2000/svg" width="25" height="41" viewBox="0 0 25 41">
      <path fill="#eab308" d="M12.5 0C5.6 0 0 5.6 0 12.5c0 8.4 12.5 28.5 12.5 28.5S25 20.9 25 12.5C25 5.6 19.4 0 12.5 0z"/>
      <circle fill="white" cx="12.5" cy="12.5" r="6"/>
    </svg>
  `),
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [0, -41],
  shadowUrl: 'https://unpkg.com/leaflet@1.7.1/dist/images/marker-shadow.png',
  shadowSize: [41, 41],
  shadowAnchor: [12, 41]
});

export default function NewsLayer() {
  // Use shared location data hook (prevents duplicate API calls)
  const { data, isLoading } = useLocationData();

  if (isLoading || !data?.news?.length) return null;

  return (
    <>
      {data.news.map((a, idx) => {
        const lat = Number(a?.lat);
        const lon = Number(a?.lon);
        if (!lat || !lon) return null;
        return (
          <Marker key={a.id || idx} position={[lat, lon]} icon={newsIcon}>
            <Popup>
              <div className="text-sm">
                <div className="font-medium">{a.title || 'News Article'}</div>
                {a.description && <div className="text-gray-600 text-xs mt-1">{a.description.substring(0, 100)}...</div>}
                {a.url && (
                  <a href={a.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline text-xs mt-1 block">
                    Read Article
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





