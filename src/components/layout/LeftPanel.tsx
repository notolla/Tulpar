import React from 'react'
import {
  Plane, Ship, Satellite, AlertTriangle, MapPin,
  Thermometer, Radio, Eye, Moon, Crosshair, Map,
  ChevronDown, ChevronRight, Play, Square, Layers,
} from 'lucide-react'
import type { ViewMode } from '@/types'

// ──────────────────────────────────────────────
// Katman tanımları
// ──────────────────────────────────────────────
interface LayerDef {
  id: string
  label: string
  icon: React.ElementType
  color: string
  children?: { id: string; label: string }[]
}

const LAYER_DEFS: LayerDef[] = [
  {
    id: 'hava', label: 'Hava Trafiği', icon: Plane, color: 'text-cyan-400',
    children: [
      { id: 'hava_sivil',      label: 'Sivil uçuşlar' },
      { id: 'hava_askeri',     label: 'Askeri / bilinmeyen' },
      { id: 'hava_helikopter', label: 'Helikopterler' },
    ],
  },
  {
    id: 'deniz', label: 'Deniz Trafiği', icon: Ship, color: 'text-blue-400',
    children: [
      { id: 'deniz_kargo',  label: 'Kargo / Tanker' },
      { id: 'deniz_yolcu',  label: 'Yolcu / Feribot' },
      { id: 'deniz_askeri', label: 'Askeri gemi' },
    ],
  },
  { id: 'anomaliler', label: 'Anomaliler',       icon: AlertTriangle, color: 'text-orange-400' },
  {
    id: 'stratejik', label: 'Stratejik Bölgeler', icon: MapPin, color: 'text-yellow-400',
    children: [
      { id: 'str_bogaz',  label: 'Boğazlar' },
      { id: 'str_fir',    label: 'FIR / Hava sahaları' },
      { id: 'str_deniz',  label: 'Deniz koridorları' },
      { id: 'str_catin',  label: 'Çatışma bölgeleri' },
    ],
  },
  { id: 'uydu',     label: 'Uydu Yörüngeleri',   icon: Satellite,   color: 'text-purple-400' },
  { id: 'yogunluk', label: 'Yoğunluk Haritası',  icon: Thermometer, color: 'text-red-400' },
  { id: 'kapsama',  label: 'AIS / ADS-B Kapsama', icon: Radio,       color: 'text-green-400' },
]

const VIEW_MODES: { id: ViewMode; label: string; icon: React.ElementType; color: string }[] = [
  { id: 'normal',      label: 'Normal',        icon: Eye,         color: 'text-cyan-400' },
  { id: 'gece_gorus',  label: 'Gece Görüşü',   icon: Moon,        color: 'text-green-400' },
  { id: 'termal',      label: 'Termal',         icon: Thermometer, color: 'text-red-400' },
  { id: 'radar',       label: 'Radar',          icon: Radio,       color: 'text-lime-400' },
  { id: 'taktik',      label: 'Taktik Harita',  icon: Map,         color: 'text-yellow-400' },
]

// ──────────────────────────────────────────────
// Props
// ──────────────────────────────────────────────
interface LeftPanelProps {
  viewMode: ViewMode
  onViewModeChange: (m: ViewMode) => void
  demoMode: boolean
  onDemoToggle: () => void
  activeLayers: Set<string>
  onLayersChange: (layers: Set<string>) => void
}

// ──────────────────────────────────────────────
// Component
// ──────────────────────────────────────────────
export const LeftPanel: React.FC<LeftPanelProps> = ({
  viewMode, onViewModeChange,
  demoMode, onDemoToggle,
  activeLayers, onLayersChange,
}) => {
  const [expanded, setExpanded] = React.useState<Set<string>>(new Set(['hava', 'stratejik']))

  const toggleLayer = (id: string) => {
    const next = new Set(activeLayers)
    next.has(id) ? next.delete(id) : next.add(id)
    onLayersChange(next)
  }

  const toggleExpand = (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    const next = new Set(expanded)
    next.has(id) ? next.delete(id) : next.add(id)
    setExpanded(next)
  }

  const activeCount = LAYER_DEFS.filter(l => activeLayers.has(l.id)).length

  return (
    <div className="w-56 bg-black border-r border-gray-900 flex flex-col text-xs font-mono shrink-0 overflow-y-auto select-none">

      {/* KATMANLAR başlık */}
      <div className="px-3 pt-3 pb-1 flex items-center justify-between">
        <span className="text-[9px] uppercase text-gray-600 tracking-widest flex items-center gap-1">
          <Layers className="w-3 h-3" /> Katmanlar
        </span>
        <span className="text-[9px] text-gray-700">{activeCount} aktif</span>
      </div>

      {/* Katman listesi */}
      <div className="px-2 pb-2 space-y-0.5">
        {LAYER_DEFS.map(layer => {
          const Icon = layer.icon
          const isActive  = activeLayers.has(layer.id)
          const isExpanded = expanded.has(layer.id)
          const hasChildren = !!layer.children?.length
          const dotColor = layer.color.replace('text-', 'bg-')

          return (
            <div key={layer.id}>
              {/* Ana satır */}
              <div
                role="button"
                tabIndex={0}
                className={`flex items-center gap-2 px-2 py-1.5 rounded-sm cursor-pointer transition-colors ${
                  isActive ? 'bg-gray-900' : 'hover:bg-gray-950'
                }`}
                onClick={() => toggleLayer(layer.id)}
                onKeyDown={e => e.key === 'Enter' && toggleLayer(layer.id)}
              >
                {/* Expand chevron */}
                {hasChildren ? (
                  <span
                    className="w-3 h-3 shrink-0 text-gray-600 hover:text-gray-400 flex items-center justify-center"
                    onClick={e => toggleExpand(layer.id, e)}
                  >
                    {isExpanded
                      ? <ChevronDown className="w-3 h-3" />
                      : <ChevronRight className="w-3 h-3" />}
                  </span>
                ) : (
                  <span className="w-3 shrink-0" />
                )}

                {/* Toggle dot */}
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 transition-colors ${isActive ? dotColor : 'bg-gray-700'}`} />

                <Icon className={`w-3 h-3 shrink-0 ${isActive ? layer.color : 'text-gray-600'}`} />
                <span className={`flex-1 text-[11px] leading-none ${isActive ? 'text-gray-200' : 'text-gray-600'}`}>
                  {layer.label}
                </span>
              </div>

              {/* Alt katmanlar */}
              {hasChildren && isExpanded && (
                <div className="ml-6 space-y-0.5 mb-0.5">
                  {layer.children!.map(child => {
                    const childActive = activeLayers.has(child.id)
                    return (
                      <div
                        key={child.id}
                        role="button"
                        tabIndex={0}
                        className={`flex items-center gap-1.5 px-2 py-0.5 cursor-pointer rounded-sm text-[10px] transition-colors ${
                          childActive ? 'text-gray-300' : 'text-gray-700 hover:text-gray-500'
                        }`}
                        onClick={() => toggleLayer(child.id)}
                        onKeyDown={e => e.key === 'Enter' && toggleLayer(child.id)}
                      >
                        <span className={`w-1 h-1 rounded-full shrink-0 ${childActive ? 'bg-gray-400' : 'bg-gray-700'}`} />
                        {child.label}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* GÖRÜNTÜLEME MODU */}
      <div className="px-3 pt-2 pb-1 border-t border-gray-900">
        <span className="text-[9px] uppercase text-gray-600 tracking-widest">Görüntüleme Modu</span>
      </div>
      <div className="px-2 pb-2 space-y-0.5">
        {VIEW_MODES.map(vm => {
          const Icon = vm.icon
          const isActive = viewMode === vm.id
          const borderColor = vm.color.replace('text-', 'border-')
          return (
            <button
              key={vm.id}
              className={`w-full flex items-center gap-2 px-2 py-1.5 text-left rounded-sm transition-colors ${
                isActive
                  ? `bg-gray-900 border-l-2 ${borderColor}`
                  : 'text-gray-600 hover:bg-gray-950 hover:text-gray-400'
              }`}
              onClick={() => onViewModeChange(vm.id)}
            >
              <Icon className={`w-3 h-3 shrink-0 ${isActive ? vm.color : 'text-gray-600'}`} />
              <span className={`text-[11px] flex-1 ${isActive ? vm.color : ''}`}>{vm.label}</span>
              {isActive && <span className={`text-[9px] ${vm.color} opacity-60`}>●</span>}
            </button>
          )
        })}
      </div>

      {/* DEMO MODU */}
      <div className="px-3 pt-2 pb-1 border-t border-gray-900">
        <span className="text-[9px] uppercase text-gray-600 tracking-widest">Demo Senaryosu</span>
      </div>
      <div className="px-2 pb-2">
        <button
          className={`w-full flex items-center justify-center gap-2 px-3 py-2 text-[11px] font-bold uppercase transition-all rounded-sm ${
            demoMode
              ? 'bg-red-950 border border-red-600 text-red-400 animate-pulse'
              : 'bg-gray-900 border border-gray-700 text-cyan-400 hover:border-cyan-600'
          }`}
          onClick={onDemoToggle}
        >
          {demoMode ? <><Square className="w-3 h-3" /> Durdur</> : <><Play className="w-3 h-3" /> Demo Başlat</>}
        </button>
      </div>

      {/* HIZLI FİLTRE */}
      <div className="px-3 pt-2 pb-1 border-t border-gray-900">
        <span className="text-[9px] uppercase text-gray-600 tracking-widest">Hızlı Filtre</span>
      </div>
      <div className="px-2 pb-3 space-y-0.5">
        {[
          { id: 'kritik',          label: 'Kritik Uyarılar',         color: 'text-red-400' },
          { id: 'yuksek_risk',     label: 'Yüksek Risk',             color: 'text-orange-400' },
          { id: 'askeri',          label: 'Askeri / Bilinmeyen',      color: 'text-yellow-400' },
          { id: 'stratejik_yakin', label: 'Stratejik Bölge Yakını',   color: 'text-purple-400' },
        ].map(f => {
          const isActive = activeLayers.has(f.id)
          return (
            <button
              key={f.id}
              className={`w-full text-left px-2 py-1 text-[10px] flex items-center gap-1.5 rounded-sm transition-all ${
                isActive ? `${f.color} bg-gray-900` : `${f.color} opacity-40 hover:opacity-70 hover:bg-gray-950`
              }`}
              onClick={() => toggleLayer(f.id)}
            >
              <Crosshair className="w-3 h-3 shrink-0" />
              {f.label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
