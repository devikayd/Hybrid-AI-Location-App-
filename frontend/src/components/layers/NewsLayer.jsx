import React, { useEffect, useRef } from 'react';
import { Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import { useLocationData } from '../../hooks/useLocationData';
import { useMapStore } from '../../stores/mapStore';

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

const newsIcon = createEmojiPinIcon('📰', '#eab308');
const newsIconHighlighted = createEmojiPinIcon('📰', '#3b82f6');

function HighlightableMarker({ position, icon, isHighlighted, children, ...props }) {
  const markerRef = useRef(null);

  useEffect(() => {
    if (markerRef.current) {
      const iconElement = markerRef.current.getElement();
      if (iconElement) {
        if (isHighlighted) {
          iconElement.classList.add('highlighted');
        } else {
          iconElement.classList.remove('highlighted');
        }
      }
    }
  }, [isHighlighted]);

  return (
    <Marker ref={markerRef} position={position} icon={icon} {...props}>
      {children}
    </Marker>
  );
}

export default function NewsLayer() {
  const { data, isLoading } = useLocationData();
  const highlightedItems = useMapStore((state) => state.highlightedItems);

  if (isLoading || !data?.news?.length) return null;

  return (
    <>
      {data.news.map((a, idx) => {
        const lat = Number(a?.lat);
        const lon = Number(a?.lon);
        if (!lat || !lon) return null;

        const itemId = `news_${a.id || idx}`;
        const isHighlighted = highlightedItems.includes(itemId) || highlightedItems.includes(a.id);

        return (
          <HighlightableMarker
            key={a.id || idx}
            position={[lat, lon]}
            icon={isHighlighted ? newsIconHighlighted : newsIcon}
            isHighlighted={isHighlighted}
          >
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
          </HighlightableMarker>
        );
      })}
    </>
  );
}





