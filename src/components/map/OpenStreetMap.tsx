import React, { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import { AircraftLayer } from './AircraftLayer'
import { VesselLayer } from './VesselLayer'
import { StrategicZoneLayer } from './StrategicZoneLayer'
import { MilitaryZoneLayer } from './MilitaryZoneLayer'
import type { ViewMode } from '@/types'
import type { Aircraft } from '@/services/api'

delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

const VIEW_FILTERS: Record<ViewMode, string> = {
  normal:     'none',
  gece_gorus: 'grayscale(1) brightness(0.65) sepia(1) hue-rotate(85deg) saturate(6)',
  termal:     'invert(1) hue-rotate(180deg) saturate(2.5) brightness(0.85)',
  radar:      'grayscale(1) brightness(0.45) contrast(2.2) invert(1) sepia(1) hue-rotate(85deg) saturate(8)',
  taktik:     'sepia(0.7) brightness(0.8) contrast(1.3) saturate(0.8)',
}

const VIEW_BG: Record<ViewMode, string> = {
  normal:     '#0a0a0a',
  gece_gorus: '#001a00',
  termal:     '#0d0005',
  radar:      '#000d00',
  taktik:     '#0d0c08',
}

interface OpenStreetMapProps {
  viewMode?: ViewMode
  demoMode?: boolean
  demoAircraft?: Aircraft[]
  activeLayers?: Set<string>
}

export const OpenStreetMap: React.FC<OpenStreetMapProps> = ({
  viewMode = 'normal',
  demoMode = false,
  demoAircraft,
  activeLayers,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef       = useRef<L.Map | null>(null)
  const [mapReady, setMapReady] = useState(false)

  // Katman görünürlük yardımcıları
  const layerOn = (id: string) => !activeLayers || activeLayers.has(id)
  const showAircraft    = layerOn('hava') || activeLayers?.has('anomaliler') || activeLayers?.has('kritik') || activeLayers?.has('yuksek_risk') || activeLayers?.has('askeri')
  const showVessels     = layerOn('deniz')
  const showZones       = layerOn('stratejik')
  const showMilZones    = layerOn('hava_askeri') || activeLayers?.has('askeri')

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return

    mapRef.current = L.map(containerRef.current, {
      // Genişletilmiş merkez: tüm bölgeyi görmek için Doğu Akdeniz
      center: [36.0, 36.0],
      zoom: 5,
      zoomControl: false,
      attributionControl: false,
    })

    L.control.zoom({ position: 'bottomright' }).addTo(mapRef.current)

    L.tileLayer(
      'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png',
      { maxZoom: 20, opacity: 0.95 }
    ).addTo(mapRef.current)

    setMapReady(true)

    return () => {
      mapRef.current?.remove()
      mapRef.current = null
    }
  }, [])

  // Tile filter görünüm modu değişince
  useEffect(() => {
    if (!mapRef.current) return
    const pane = mapRef.current.getPanes().tilePane as HTMLElement
    if (pane) pane.style.filter = VIEW_FILTERS[viewMode]
  }, [viewMode])

  return (
    <div className="relative w-full h-full" style={{ background: VIEW_BG[viewMode] }}>
      <div ref={containerRef} className="absolute inset-0" />

      {/* Gece görüşü vignette */}
      {viewMode === 'gece_gorus' && (
        <div
          className="absolute inset-0 pointer-events-none z-10"
          style={{ background: 'radial-gradient(ellipse at center, transparent 40%, rgba(0,30,0,0.7) 100%)' }}
        />
      )}

      {/* Radar grid */}
      {viewMode === 'radar' && (
        <div className="absolute inset-0 pointer-events-none z-10">
          <div style={{ position: 'absolute', inset: 0, background: 'repeating-linear-gradient(0deg, transparent, transparent 39px, rgba(0,255,0,0.04) 40px)' }} />
          <div style={{ position: 'absolute', inset: 0, background: 'repeating-linear-gradient(90deg, transparent, transparent 39px, rgba(0,255,0,0.04) 40px)' }} />
        </div>
      )}

      {/* Katmanlar — activeLayers'a göre göster/gizle */}
      {mapReady && mapRef.current && (
        <>
          {showAircraft && (
            <AircraftLayer
              map={mapRef.current}
              demoOverride={demoMode ? demoAircraft : undefined}
              activeLayers={activeLayers}
            />
          )}
          {showVessels  && <VesselLayer map={mapRef.current} activeLayers={activeLayers} />}
          {showZones    && <StrategicZoneLayer map={mapRef.current} />}
          {showMilZones && <MilitaryZoneLayer map={mapRef.current} />}
        </>
      )}

      {/* Sol alt gösterge */}
      <div className="absolute bottom-4 left-4 z-20 pointer-events-none">
        <div className="bg-black/80 border border-gray-800 px-3 py-2 font-mono text-xs space-y-1">
          {[
            { color: '#00e676', label: 'Normal' },
            { color: '#ffd600', label: 'Orta Risk' },
            { color: '#ff6d00', label: 'Yüksek Risk' },
            { color: '#ff1744', label: 'Kritik / Squawk' },
            { color: '#ff1744', label: 'Askeri Exclusion', dash: true },
          ].map(({ color, label, dash }) => (
            <div key={label} className="flex items-center gap-2">
              {dash
                ? <div className="w-2.5 h-0 border-t-2 border-dashed" style={{ borderColor: color }} />
                : <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
              }
              <span style={{ color: '#888' }}>{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Görünüm modu etiketi */}
      {viewMode !== 'normal' && (
        <div className="absolute top-3 left-3 z-20 pointer-events-none">
          <div
            className="font-mono text-[10px] uppercase tracking-widest px-2 py-1 border"
            style={
              viewMode === 'gece_gorus' ? { color: '#00ff41', borderColor: '#00ff41', background: 'rgba(0,40,0,0.7)' }
              : viewMode === 'termal'   ? { color: '#ff4444', borderColor: '#ff4444', background: 'rgba(40,0,0,0.7)' }
              : viewMode === 'radar'    ? { color: '#39ff14', borderColor: '#39ff14', background: 'rgba(0,30,0,0.7)' }
              : { color: '#d4b800', borderColor: '#d4b800', background: 'rgba(30,25,0,0.7)' }
            }
          >
            {viewMode === 'gece_gorus' ? '● GECE GÖRÜŞÜ'
              : viewMode === 'termal'  ? '● TERMAL'
              : viewMode === 'radar'   ? '● RADAR'
              : '● TAKTİK HARİTA'}
          </div>
        </div>
      )}

      {/* Demo göstergesi */}
      {demoMode && (
        <div className="absolute top-3 right-12 z-20 pointer-events-none">
          <div className="font-mono text-[10px] uppercase tracking-widest px-2 py-1 border border-red-600 text-red-400 bg-red-950/70 animate-pulse">
            ● DEMO MOD
          </div>
        </div>
      )}

      {/* Yükleniyor */}
      {!mapReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-black z-30">
          <div className="text-center">
            <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <p className="text-cyan-400 text-sm font-mono">Harita Yükleniyor…</p>
          </div>
        </div>
      )}

      <style>{`
        @keyframes tulpar-pulse {
          0%   { transform: scale(1);   opacity: .6; }
          100% { transform: scale(2.5); opacity: 0;  }
        }
        .tulpar-popup .leaflet-popup-content-wrapper {
          background: transparent !important;
          border: none !important;
          box-shadow: none !important;
          padding: 0 !important;
        }
        .tulpar-popup .leaflet-popup-content { margin: 0 !important; }
        .tulpar-popup .leaflet-popup-tip { background: #222 !important; }
      `}</style>
    </div>
  )
}
