import React from 'react';
import MarkerClusterGroup from 'react-leaflet-cluster';
import { Marker, Popup } from 'react-leaflet';
import { useEvents } from '../../hooks/useDataHooks';

export default function EventsLayer() {
  const { data, isLoading } = useEvents();
  if (isLoading || !data?.events?.length) return null;

  return (
    <MarkerClusterGroup chunkedLoading>
      {data.events.map((e) => {
        const lat = Number(e?.venue?.latitude);
        const lon = Number(e?.venue?.longitude);
        if (!lat || !lon) return null;
        return (
          <Marker key={e.id} position={[lat, lon]}>
            <Popup>
              <div className="text-sm">
                <a href={e.url} target="_blank" rel="noreferrer" className="font-medium hover:underline">
                  {e.name?.text || 'Event'}
                </a>
                <div className="text-gray-600">{e.is_free ? 'Free' : 'Paid'}</div>
              </div>
            </Popup>
          </Marker>
        );
      })}
    </MarkerClusterGroup>
  );
}





