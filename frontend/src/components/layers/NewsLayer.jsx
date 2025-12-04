import React from 'react';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { Marker, Popup } from 'react-leaflet';
import { useNews } from '../../hooks/useDataHooks';

export default function NewsLayer() {
  const { data, isLoading } = useNews();
  if (isLoading || !data?.articles?.length) return null;

  return (
    <MarkerClusterGroup chunkedLoading>
      {data.articles.map((a, idx) => {
        // Articles are placed with small offsets around center in backend clustering
        const lat = Number(a._lat || a.lat || a.latitude || 0);
        const lon = Number(a._lon || a.lon || a.longitude || 0);
        if (!lat || !lon) return null;
        return (
          <Marker key={idx} position={[lat, lon]}>
            <Popup>
              <div className="text-sm">
                <a href={a.url} target="_blank" rel="noreferrer" className="font-medium hover:underline">
                  {a.title}
                </a>
                <div className="text-gray-600">{a.source?.name}</div>
              </div>
            </Popup>
          </Marker>
        );
      })}
    </MarkerClusterGroup>
  );
}





