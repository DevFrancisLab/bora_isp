import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { AREA_LABEL } from '../../domain/labels';
import { areaHealth, incidentForArea, siteHealth } from '../../domain/network';
import { formatClock, timeAgo } from '../../domain/format';
import type { FieldReport, Incident, NetworkSite, ServiceArea } from '../../types';

const DEFAULT_STREET = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
const DEFAULT_SATELLITE = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

export interface MapLayers {
  areas: boolean;
  sites: boolean;
  reports: boolean;
  outages: boolean;
}

function line(parent: HTMLElement, text: string, className: string) {
  const node = document.createElement('div');
  node.className = className;
  node.textContent = text;
  parent.appendChild(node);
}

function popup(rows: string[], button?: { label: string; onClick: () => void }) {
  const wrap = document.createElement('div');
  rows.forEach((text, index) => line(wrap, text, index === 0 ? 'map-title' : 'map-line'));
  if (button) {
    const action = document.createElement('button');
    action.type = 'button';
    action.className = 'map-btn';
    action.textContent = button.label;
    action.addEventListener('click', button.onClick);
    wrap.appendChild(action);
  }
  return wrap;
}

export function NetworkMap({
  areas,
  sites,
  reports,
  incidents,
  focusNonce,
  focusArea,
  onViewIncident,
  onOpenCase,
  onViewSite,
}: {
  areas: ServiceArea[];
  sites: NetworkSite[];
  reports: FieldReport[];
  incidents: Incident[];
  focusNonce: number;
  focusArea: string | null;
  onViewIncident: (id: string) => void;
  onOpenCase: (id: string) => void;
  onViewSite: (id: string) => void;
}) {
  const holder = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const groups = useRef<{ areas: L.LayerGroup; sites: L.LayerGroup; reports: L.LayerGroup; outages: L.LayerGroup; street: L.TileLayer; satellite: L.TileLayer } | null>(null);
  const callbacks = useRef({ onViewIncident, onOpenCase, onViewSite });
  callbacks.current = { onViewIncident, onOpenCase, onViewSite };
  const [basemap, setBasemap] = useState<'street' | 'satellite'>('street');
  const [layers, setLayers] = useState<MapLayers>({ areas: true, sites: true, reports: true, outages: true });
  const [tileNote, setTileNote] = useState('');

  useEffect(() => {
    const element = holder.current;
    if (!element || mapRef.current) return;
    const host = element as HTMLElement & { _leaflet_id?: number };
    if (host._leaflet_id) delete host._leaflet_id;
    const streetUrl = import.meta.env.VITE_MAP_STREET_URL || DEFAULT_STREET;
    const satelliteUrl = import.meta.env.VITE_MAP_SATELLITE_URL || DEFAULT_SATELLITE;
    const map = L.map(element, { zoomControl: false, attributionControl: true }).setView([-1.296, 36.8], 12);
    L.control.zoom({ position: 'bottomright' }).addTo(map);
    const street = L.tileLayer(streetUrl, { attribution: '&copy; OpenStreetMap &copy; CARTO', maxZoom: 19 });
    const satellite = L.tileLayer(satelliteUrl, { attribution: 'Tiles &copy; Esri', maxZoom: 19 });
    street.on('tileerror', () => setTileNote('Street tiles are unavailable. Boundaries and markers are still shown.'));
    satellite.on('tileerror', () => setTileNote('Satellite tiles are unavailable. Switch back to Street.'));
    street.addTo(map);
    const bundle = {
      areas: L.layerGroup().addTo(map),
      sites: L.layerGroup().addTo(map),
      reports: L.layerGroup().addTo(map),
      outages: L.layerGroup().addTo(map),
      street,
      satellite,
    };
    mapRef.current = map;
    groups.current = bundle;
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(element);
    window.setTimeout(() => map.invalidateSize(), 200);
    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
      groups.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const bundle = groups.current;
    if (!map || !bundle) return;
    if (basemap === 'street') {
      bundle.satellite.remove();
      bundle.street.addTo(map);
    } else {
      bundle.street.remove();
      bundle.satellite.addTo(map);
    }
    bundle.areas.clearLayers();
    bundle.sites.clearLayers();
    bundle.reports.clearLayers();
    bundle.outages.clearLayers();

    const styleFor = (health: string) => {
      if (health === 'outage') return { color: '#EF4444', weight: 2, fillColor: '#EF4444', fillOpacity: 0.28 };
      if (health === 'degraded') return { color: '#F59E0B', weight: 2, fillColor: '#F59E0B', fillOpacity: 0.22 };
      return { color: '#22C55E', weight: 1.5, fillColor: '#22C55E', fillOpacity: 0.1 };
    };

    if (layers.areas || layers.outages) {
      areas.forEach((area) => {
        const health = areaHealth(area.id, incidents);
        const incident = incidentForArea(area.id, incidents);
        const showArea = layers.areas || (layers.outages && health !== 'operational');
        if (!showArea) return;
        const polygon = L.polygon(area.polygon, styleFor(layers.outages || layers.areas ? health : 'operational'));
        if (incident && health !== 'operational') {
          polygon.bindPopup(
            popup(
              [incident.title, incident.status, `${incident.affectedSubscribers} affected subscribers`, `${incident.reportCount} customer reports`, `Started ${formatClock(incident.startedAt)}`],
              { label: 'View Incident', onClick: () => callbacks.current.onViewIncident(incident.id) },
            ),
          );
        } else {
          polygon.bindPopup(popup([area.name, 'Operational', 'No active incident in this zone']));
        }
        (layers.outages && !layers.areas && health !== 'operational' ? bundle.outages : bundle.areas).addLayer(polygon);
      });
    }

    if (layers.outages) {
      incidents
        .filter((incident) => incident.status !== 'resolved')
        .forEach((incident) => {
          const area = areas.find((item) => item.id === incident.area);
          if (!area) return;
          const [lat, lng] = area.polygon.reduce((acc, point) => [acc[0] + point[0], acc[1] + point[1]], [0, 0]).map((value) => value / area.polygon.length) as [number, number];
          const marker = L.marker([lat, lng], {
            icon: L.divIcon({
              className: 'site-pin-wrap',
              html: `<div class="site-pin"><span class="dot" style="background:${incident.severity === 'critical' ? '#EF4444' : '#F59E0B'}"></span><span class="name">${incident.code}</span></div>`,
              iconSize: [120, 24],
            }),
          });
          marker.bindPopup(
            popup(
              [incident.title, incident.status[0].toUpperCase() + incident.status.slice(1), `${incident.affectedSubscribers} affected subscribers`, `${incident.reportCount} customer reports`, `Started ${formatClock(incident.startedAt)}`],
              { label: 'View Incident', onClick: () => callbacks.current.onViewIncident(incident.id) },
            ),
          );
          bundle.outages.addLayer(marker);
        });
    }

    if (layers.sites) {
      sites.forEach((site) => {
        const health = siteHealth(site, incidents);
        const color = health === 'outage' ? '#EF4444' : health === 'degraded' ? '#F59E0B' : '#22C55E';
        const marker = L.marker([site.lat, site.lng], {
          icon: L.divIcon({
            className: 'site-pin-wrap',
            html: `<div class="site-pin"><span class="dot" style="background:${color}"></span><span class="name">${site.name}</span></div>`,
            iconSize: [140, 24],
          }),
        });
        marker.bindPopup(
          popup(
            [site.name, `Status: ${health[0].toUpperCase()}${health.slice(1)}`, `Connected subscribers: ${site.served}`, `Area: ${site.areaIds.map((id) => AREA_LABEL[id]).join(', ')}`],
            { label: 'View Site', onClick: () => callbacks.current.onViewSite(site.id) },
          ),
        );
        bundle.sites.addLayer(marker);
      });
    }

    if (layers.reports) {
      reports.forEach((report) => {
        const marker = L.circleMarker([report.lat, report.lng], { radius: 6, color: '#22D3EE', weight: 2, fillColor: '#22D3EE', fillOpacity: 0.85 });
        const rows = ['Customer Report', report.issue, `Channel: ${report.channel === 'whatsapp' ? 'WhatsApp' : report.channel.toUpperCase()}`, `Received: ${timeAgo(report.at)}`];
        marker.bindPopup(
          popup(rows, report.caseId ? { label: 'Open Support Case', onClick: () => callbacks.current.onOpenCase(report.caseId!) } : undefined),
        );
        bundle.reports.addLayer(marker);
      });
    }
  }, [areas, sites, reports, incidents, layers, basemap]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focusArea) return;
    const area = areas.find((item) => item.id === focusArea);
    if (!area) return;
    map.fitBounds(L.latLngBounds(area.polygon), { padding: [36, 36], maxZoom: 15 });
  }, [focusNonce, focusArea, areas]);

  const toggle = (key: keyof MapLayers) => setLayers((current) => ({ ...current, [key]: !current[key] }));

  return (
    <div className="surface relative h-[380px] overflow-hidden md:h-[480px] xl:h-[620px]">
      <div ref={holder} className="absolute inset-0" />
      <div className="absolute left-3 top-3 z-[500] max-w-[210px] rounded-lg border border-line bg-card/95 p-2 text-xs shadow-lg">
        {([
          ['areas', 'Service Areas'],
          ['sites', 'Network Sites'],
          ['reports', 'Customer Reports'],
          ['outages', 'Outages'],
        ] as const).map(([key, label]) => (
          <label key={key} className="flex items-center gap-2 px-1 py-1 text-muted">
            <input type="checkbox" checked={layers[key]} onChange={() => toggle(key)} />
            <span className="text-ink">{label}</span>
          </label>
        ))}
      </div>
      <div className="absolute right-3 top-3 z-[500] flex overflow-hidden rounded-lg border border-line bg-card/95 text-xs">
        <button type="button" aria-pressed={basemap === 'street'} className={`px-3 py-2 ${basemap === 'street' ? 'bg-brand text-[#05210F]' : 'text-muted'}`} onClick={() => setBasemap('street')}>Street</button>
        <button type="button" aria-pressed={basemap === 'satellite'} className={`px-3 py-2 ${basemap === 'satellite' ? 'bg-brand text-[#05210F]' : 'text-muted'}`} onClick={() => setBasemap('satellite')}>Satellite</button>
      </div>
      {tileNote ? <p className="absolute bottom-3 left-3 z-[500] max-w-xs rounded-md bg-card/95 px-2 py-1 text-xs text-warn">{tileNote}</p> : null}
    </div>
  );
}
