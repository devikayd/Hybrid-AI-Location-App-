import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMap, ZoomControl } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { useMapStore } from '../stores/mapStore';
import CrimesLayer from './layers/CrimesLayer';
import EventsLayer from './layers/EventsLayer';
import NewsLayer from './layers/NewsLayer';
import POIsLayer from './layers/POIsLayer';

// Fix default icon paths in Leaflet when bundled
import marker2x from 'leaflet/dist/images/marker-icon-2x.png';
import marker from 'leaflet/dist/images/marker-icon.png';
import shadow from 'leaflet/dist/images/marker-shadow.png';

L.Icon.Default.mergeOptions({
  iconRetinaUrl: marker2x,
  iconUrl: marker,
  shadowUrl: shadow,
});

function RecenterOnChange({ lat, lon, zoom }) {
  const map = useMap();
  useEffect(() => {
    map.setView([lat, lon], zoom, { animate: true });
  }, [lat, lon, zoom, map]);
  return null;
}

export default function MapView() {
  const { center, zoom, layers, toggleLayer, showRecentSearches } = useMapStore();

  return (
    <div className="w-full rounded-lg overflow-hidden border border-gray-200">
      <div className="flex items-center gap-2 p-2 bg-white border-b border-gray-200">
        {Object.keys(layers).map((k) => (
          <button key={k} onClick={() => toggleLayer(k)} className={`text-xs px-2 py-1 rounded border ${layers[k] ? 'bg-primary-600 text-white border-primary-600' : 'bg-white text-gray-700 border-gray-300'}`}>
            {k}
          </button>
        ))}
      </div>
      <div className="h-[70vh] relative">
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

          <RecenterOnChange lat={center.lat} lon={center.lon} zoom={zoom} />
        </MapContainer>
      </div>
    </div>
  );
}
