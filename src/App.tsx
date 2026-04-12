import { useState, useEffect } from 'react'
import { TopBar } from '@/components/layout/TopBar'
import { LeftPanel } from '@/components/layout/LeftPanel'
import { RightPanel } from '@/components/layout/RightPanel'
import { BottomPanel } from '@/components/layout/BottomPanel'
import { CommandCenterMap } from '@/components/map/CommandCenterMap'
import type { ViewMode, SystemStats } from '@/types'

export type { ViewMode, SystemStats }

// Varsayılan aktif katmanlar
const DEFAULT_LAYERS = new Set<string>(['hava', 'deniz', 'stratejik', 'anomaliler'])

function App() {
  const [viewMode, setViewMode]       = useState<ViewMode>('normal')
  const [demoMode, setDemoMode]       = useState(false)
  const [activeLayers, setActiveLayers] = useState<Set<string>>(DEFAULT_LAYERS)
  const [stats, setStats] = useState<SystemStats>({
    aircraftCount: 0,
    vesselCount: 0,
    anomalyCount: 0,
    criticalCount: 0,
    dataSource: 'test',
    dataLabel: 'Bağlanıyor…',
    lastUpdate: null,
  })

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const [statsRes, liveRes, vesselRes] = await Promise.all([
          fetch('/api/stats'),
          fetch('/api/aircraft/live-count'),
          fetch('/api/vessels/live-count'),
        ])
        if (statsRes.ok) {
          const s  = await statsRes.json()
          const lc = liveRes.ok   ? await liveRes.json()   : null
          const vc = vesselRes.ok ? await vesselRes.json() : null
          setStats({
            aircraftCount: s.aircraft_count ?? 0,
            vesselCount:   vc?.count ?? s.vessel_count ?? 0,
            anomalyCount:  s.anomaly_count ?? 0,
            criticalCount: s.critical_count ?? 0,
            dataSource:    lc?.status ?? s.data_source ?? 'test',
            dataLabel:     lc?.label ?? `${s.aircraft_count} uçak`,
            lastUpdate:    new Date(),
          })
        }
      } catch { /* backend henüz hazır değil */ }
    }
    fetchStats()
    const iv = setInterval(fetchStats, 10_000)
    return () => clearInterval(iv)
  }, [])

  return (
    <div className="h-screen w-screen bg-black flex flex-col overflow-hidden">
      <TopBar stats={stats} />
      <div className="flex-1 flex overflow-hidden">
        <LeftPanel
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          demoMode={demoMode}
          onDemoToggle={() => setDemoMode(v => !v)}
          activeLayers={activeLayers}
          onLayersChange={setActiveLayers}
        />
        <div className="flex-1 relative min-h-0">
          <CommandCenterMap
            viewMode={viewMode}
            demoMode={demoMode}
            activeLayers={activeLayers}
          />
        </div>
        <RightPanel stats={stats} />
      </div>
      <BottomPanel />
    </div>
  )
}

export default App
