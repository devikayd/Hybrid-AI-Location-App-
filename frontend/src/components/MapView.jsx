import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, ZoomControl } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { useMapStore } from '../stores/mapStore';
import CrimesLayer from './layers/CrimesLayer';
import EventsLayer from './layers/EventsLayer';
import NewsLayer from './layers/NewsLayer';
import POIsLayer from './layers/POIsLayer';
import TripRouteLayer from './layers/TripRouteLayer';

// Fix default icon paths in Leaflet when bundled
import marker2x from 'leaflet/dist/images/marker-icon-2x.png';
import marker from 'leaflet/dist/images/marker-icon.png';
import shadow from 'leaflet/dist/images/marker-shadow.png';

L.Icon.Default.mergeOptions({
  iconRetinaUrl: marker2x,
  iconUrl: marker,
  shadowUrl: shadow,
});

// Derive a sensible zoom level from the Nominatim bounding box size.
// Larger bbox = more zoomed out. This avoids flyToBounds which zooms out
// to show the whole city outline (wrong behaviour).
function zoomFromBbox(bbox) {
  if (!bbox || bbox.length !== 4) return 14;
  const deltaLat = Math.abs(Number(bbox[1]) - Number(bbox[0]));
  const deltaLon = Math.abs(Number(bbox[3]) - Number(bbox[2]));
  const maxDelta = Math.max(deltaLat, deltaLon);
  if (maxDelta > 5)    return 7;   // country / large region
  if (maxDelta > 1)    return 10;  // county / large area
  if (maxDelta > 0.3)  return 12;  // large city  (e.g. London)
  if (maxDelta > 0.1)  return 14;  // city / town (e.g. Liverpool)
  if (maxDelta > 0.02) return 15;  // suburb / district
  return 16;                        // street / postcode
}

function FlyToSearch() {
  const map = useMap();
  const searchId = useMapStore((s) => s.searchId);
  const center = useMapStore((s) => s.center);
  const boundingBox = useMapStore((s) => s.boundingBox);

  useEffect(() => {
    if (!searchId) return; // skip initial render — don't fly on page load
    const targetZoom = zoomFromBbox(boundingBox);
    map.flyTo([center.lat, center.lon], targetZoom, { animate: true, duration: 1.0 });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchId]);

  return null;
}

// Per-layer colour tokens — matches side panel and LocationDataList colours
const LAYER_CONFIG = {
  crimes:     { label: '👮 Crimes',     active: 'bg-red-600 text-white border-red-600',         inactive: 'bg-red-50 text-red-700 border-red-200 hover:bg-red-100' },
  events:     { label: '🎉 Events',     active: 'bg-blue-600 text-white border-blue-600',        inactive: 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100' },
  news:       { label: '📰 News',       active: 'bg-yellow-500 text-white border-yellow-500',    inactive: 'bg-yellow-50 text-yellow-700 border-yellow-200 hover:bg-yellow-100' },
  pois:       { label: '📍 POIs',       active: 'bg-green-600 text-white border-green-600',      inactive: 'bg-green-50 text-green-700 border-green-200 hover:bg-green-100' },
  trip_route: { label: '🗺️ Trip Route', active: 'bg-purple-600 text-white border-purple-600',    inactive: 'bg-purple-50 text-purple-700 border-purple-200 hover:bg-purple-100' },
};

export default function MapView() {
  const { center, zoom, layers, toggleLayer, showRecentSearches } = useMapStore();

  return (
    <div className="w-full rounded-lg overflow-hidden border border-gray-200">
      <div className="flex items-center gap-2 p-2 bg-white border-b border-gray-200 flex-wrap">
        {Object.keys(layers).map((k) => {
          const cfg = LAYER_CONFIG[k] ?? { label: k, active: 'bg-primary-600 text-white border-primary-600', inactive: 'bg-gray-50 text-gray-700 border-gray-200 hover:bg-gray-100' };
          return (
            <button
              key={k}
              onClick={() => toggleLayer(k)}
              className={`text-xs px-3 py-1.5 rounded-full border font-medium transition-colors duration-150 ${layers[k] ? cfg.active : cfg.inactive}`}
            >
              {cfg.label}
            </button>
          );
        })}
      </div>
      <div className="h-[80vh] relative">
        <MapContainer 
          center={[center.lat, center.lon]} 
          zoom={zoom} 
          style={{ height: '100%', width: '100%' }}
          zoomControl={false}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {!showRecentSearches && <ZoomControl position="topleft" />}
          
          <style>{`
            .leaflet-control-zoom {
              margin-top: 10px !important;
              margin-left: 10px !important;
            }
            .leaflet-control-zoom a {
              width: 30px !important;
              height: 30px !important;
              line-height: 30px !important;
              font-size: 18px !important;
            }
          `}</style>

          <Marker position={[center.lat, center.lon]}>
            <Popup>
              <div className="text-center">
                <div className="font-semibold text-primary-600">📍 Search Location</div>
                <div className="text-sm text-gray-600 mt-1">
                  {center.lat.toFixed(4)}, {center.lon.toFixed(4)}
                </div>
              </div>
            </Popup>
          </Marker>

          {layers.crimes && <CrimesLayer />}
          {layers.events && <EventsLayer />}
          {layers.news && <NewsLayer />}
          {layers.pois && <POIsLayer />}
          {layers.trip_route && <TripRouteLayer />}

          <FlyToSearch />
        </MapContainer>
      </div>
    </div>
  );
}
