import React from 'react';
import { Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { useQuery } from '@tanstack/react-query';
import { getLocationData } from '../../services/api';
import { useMapStore } from '../../stores/mapStore';

// Create custom red icon for crimes
const crimeIcon = new L.Icon({
  iconUrl: 'data:image/svg+xml;base64,' + btoa(`
    <svg xmlns="http://www.w3.org/2000/svg" width="25" height="41" viewBox="0 0 25 41">
      <path fill="#dc2626" d="M12.5 0C5.6 0 0 5.6 0 12.5c0 8.4 12.5 28.5 12.5 28.5S25 20.9 25 12.5C25 5.6 19.4 0 12.5 0z"/>
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

export default function CrimesLayer() {
  const { center } = useMapStore();
  const userId = React.useMemo(() => {
    let id = sessionStorage.getItem('userId');
    if (!id) {
      id = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      sessionStorage.setItem('userId', id);
    }
    return id;
  }, []);

  const { data, isLoading } = useQuery({
    queryKey: ['location-data', center, userId],
    queryFn: () => getLocationData({
      lat: center?.lat || 51.5074,
      lon: center?.lon || -0.1278,
      radius_km: 10,
      user_id: userId
    }),
    enabled: !!(center && center.lat && center.lon),
    staleTime: 60_000,
  });

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





