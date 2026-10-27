'use client';

import 'leaflet/dist/leaflet.css';
import { CircleMarker, LayersControl, MapContainer, TileLayer, useMapEvents } from 'react-leaflet';


// Paramètres
const CENTRE: [number, number] = [48.8566, 2.3522];
const ZOOM = 12;
const ZOOM_MIN = 11;
const LIMITES: [[number, number], [number, number]] = [[48.78, 2.18], [48.94, 2.52]];
const ZOOM_MAX = 19;
const COUCHE_FOND = 'GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2';
const COUCHE_CADASTRE = 'CADASTRALPARCELS.PARCELLAIRE_EXPRESS';   // autre choix : CADASTRALPARCELS.PARCELS (noir et blanc)
const ATTRIBUTION = '&copy; <a href="https://www.ign.fr/">IGN</a>';

// Tuiles WMTS de la Géoplateforme (Web Mercator), sans clé
const urlTuiles = (couche: string) =>
  `https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=${couche}&STYLE=normal&FORMAT=image/png` +
  '&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}';

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
      maxZoom={ZOOM_MAX}
      maxBounds={LIMITES}
      className="h-80 w-full rounded-lg z-0"
    >
      <TileLayer url={urlTuiles(COUCHE_FOND)} attribution={ATTRIBUTION} maxZoom={ZOOM_MAX} />
      <LayersControl position="topright">
        <LayersControl.Overlay name="Cadastre">
          <TileLayer url={urlTuiles(COUCHE_CADASTRE)} maxZoom={ZOOM_MAX} />
        </LayersControl.Overlay>
      </LayersControl>
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
