import React from 'react';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { Marker, Popup } from 'react-leaflet';
import { usePOIs } from '../../hooks/useDataHooks';

export default function POIsLayer() {
  const { data, isLoading } = usePOIs();
  if (isLoading || !data?.pois?.length) return null;

  return (
    <MarkerClusterGroup chunkedLoading>
      {data.pois.map((p) => {
        const lat = Number(p.lat);
        const lon = Number(p.lon);
        if (!lat || !lon) return null;
        return (
          <Marker key={p.id} position={[lat, lon]}>
            <Popup>
              <div className="text-sm">
                <div className="font-medium">{p.tags?.name || p.type}</div>
                <div className="text-gray-600">{p.type}</div>
              </div>
            </Popup>
          </Marker>
        );
      })}
    </MarkerClusterGroup>
  );
}





