'use client';

import 'leaflet/dist/leaflet.css';
import { CircleMarker, MapContainer, TileLayer, useMapEvents } from 'react-leaflet';

// Paramètres
const CENTRE: [number, number] = [48.8566, 2.3522];
const ZOOM = 12;
const ZOOM_MIN = 11;
const LIMITES: [[number, number], [number, number]] = [[48.78, 2.18], [48.94, 2.52]];
const URL_TUILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

export interface PointCarte {
  lat: number;
  lon: number;
}

interface Props {
  point: PointCarte | null;
  onChoix: (lat: number, lon: number) => void;
}

function Ecoute({ onChoix }: Pick<Props, 'onChoix'>) {
  useMapEvents({ click: e => onChoix(e.latlng.lat, e.latlng.lng) });
  return null;
}

export default function CarteClic({ point, onChoix }: Props) {
  return (
    <MapContainer
      center={CENTRE}
      zoom={ZOOM}
      minZoom={ZOOM_MIN}
      maxBounds={LIMITES}
      className="h-80 w-full rounded-lg z-0"
    >
      <TileLayer
        url={URL_TUILES}
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
      />
      <Ecoute onChoix={onChoix} />
      {point && (
        <CircleMarker
          center={[point.lat, point.lon]}
          radius={8}
          pathOptions={{ color: '#0b0b0b', fillColor: '#3987e5', fillOpacity: 0.9 }}
        />
      )}
    </MapContainer>
  );
}
