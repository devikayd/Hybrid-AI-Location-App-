import React from 'react';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { Marker, Popup } from 'react-leaflet';
import { useCrimes } from '../../hooks/useDataHooks';

export default function CrimesLayer() {
  const { data, isLoading } = useCrimes();
  if (isLoading || !data?.crimes?.length) return null;

  return (
    <MarkerClusterGroup chunkedLoading>
      {data.crimes.map((c) => {
        const lat = Number(c?.location?.latitude);
        const lon = Number(c?.location?.longitude);
        if (!lat || !lon) return null;
        return (
          <Marker key={c.id} position={[lat, lon]}>
            <Popup>
              <div className="text-sm">
                <div className="font-medium">{c.category}</div>
                <div className="text-gray-600">{c.month}</div>
              </div>
            </Popup>
          </Marker>
        );
      })}
    </MarkerClusterGroup>
  );
}





