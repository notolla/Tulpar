import React, { useState, useEffect, useCallback } from 'react'
import { AlertTriangle, Newspaper, Brain, Filter, RefreshCw, Crosshair } from 'lucide-react'
import type { SystemStats } from '@/types'

interface RightPanelProps {
  stats: SystemStats
}

interface LiveAlert {
  id: string
  type: string
  entity_name: string
  title: string
  risk_level: string
  description: string
  anomaly_score: number
  coordinates: { lat: number; lon: number }
  region?: string
}

interface NewsItem {
  id: string
  title: string
  source: string
  time: string
  category: string
  region: string
  summary?: string
  url?: string
}

function unique(arr: (string | undefined)[]): string[] {
  return [...new Set(arr.filter((v): v is string => !!v))].sort()
}

export const RightPanel: React.FC<RightPanelProps> = ({ stats }) => {
  const [activeTab, setActiveTab] = useState<'uyarilar' | 'haberler' | 'ozet'>('uyarilar')
  const [alerts, setAlerts]           = useState<LiveAlert[]>([])
  const [news, setNews]               = useState<NewsItem[]>([])
  const [newsLoading, setNewsLoading] = useState(true)
  const [refreshing, setRefreshing]   = useState(false)
  const [showFilters, setShowFilters] = useState(false)

  // Filtre state
  const [filterCategory, setFilterCategory] = useState('')
  const [filterSource,   setFilterSource]   = useState('')
  const [filterRegion,   setFilterRegion]   = useState('')
  const [anomalyMode,    setAnomalyMode]    = useState(false)

  // ── Haber fetch — filtreler tamamen client-side ────────────────────────────
  const fetchNews = useCallback(async () => {
    try {
      const res = await fetch('/api/news')
      if (res.ok) {
        const data = await res.json()
        setNews(data)
        if (data.length > 0) setNewsLoading(false)
      }
    } catch { /* sessiz */ }
  }, [])

  // İlk yükleme + periyodik poll
  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const res = await fetch('/api/alerts')
        if (res.ok) setAlerts(await res.json())
      } catch { /* sessiz */ }
    }
    fetchAlerts()
    fetchNews()
    const iv1 = setInterval(fetchAlerts, 5_000)
    const iv2 = setInterval(fetchNews, 60_000)
    return () => { clearInterval(iv1); clearInterval(iv2) }
  }, [fetchNews])

  // Görüntülenecek haberler — filtreleri news üzerine uygula
  const anomalyRegions = anomalyMode
    ? new Set(alerts.map(a => a.region?.toLowerCase()).filter(Boolean))
    : null

  const visibleNews = news.filter(n => {
    if (filterCategory && n.category !== filterCategory) return false
    if (filterSource   && n.source   !== filterSource)   return false
    if (filterRegion   && n.region   !== filterRegion)   return false
    if (anomalyRegions && anomalyRegions.size > 0 && !anomalyRegions.has(n.region?.toLowerCase())) return false
    return true
  })

  // Loading sırasında 3s'de bir kontrol
  useEffect(() => {
    if (!newsLoading) return
    const iv = setInterval(async () => {
      try {
        const res = await fetch('/api/news')
        if (res.ok) {
          const data = await res.json()
          if (data.length > 0) { setNews(data); setNewsLoading(false) }
        }
      } catch { /* sessiz */ }
    }, 3_000)
    return () => clearInterval(iv)
  }, [newsLoading])

  // ── Manuel refresh ─────────────────────────────────────────────────────────
  const handleRefresh = async () => {
    if (refreshing) return
    setRefreshing(true)
    try {
      await fetch('/api/news/refresh', { method: 'POST' })
      await new Promise(r => setTimeout(r, 1500))
      await fetchNews()
    } finally {
      setRefreshing(false)
    }
  }

  // ── Render yardımcıları ────────────────────────────────────────────────────
  const riskBorder = (r: string) =>
    r === 'Kritik' ? 'border-l-red-500' : r === 'Yüksek' ? 'border-l-orange-500' : 'border-l-yellow-500'

  const riskText = (r: string) =>
    r === 'Kritik' ? 'text-red-400' : r === 'Yüksek' ? 'text-orange-400' : r === 'Orta' ? 'text-yellow-400' : 'text-green-400'

  const typeIcon = (t: string) =>
    t === 'hava' ? '✈' : t === 'deniz' ? '⛵' : '⚠'

  const activeFilters = [filterCategory, filterSource, filterRegion, anomalyMode ? 'x' : ''].filter(Boolean).length

  const tabs = [
    { id: 'uyarilar', label: 'Uyarılar', icon: AlertTriangle, badge: alerts.length },
    { id: 'haberler', label: 'OSINT',    icon: Newspaper,     badge: visibleNews.length },
    { id: 'ozet',     label: 'Özet',     icon: Brain,         badge: 0 },
  ]

  return (
    <div className="w-80 bg-black border-l border-gray-900 flex flex-col shrink-0">
      {/* Tab bar */}
      <div className="flex border-b border-gray-900 shrink-0">
        {tabs.map(tab => {
          const Icon = tab.icon
          const isActive = activeTab === tab.id
          return (
            <button
              key={tab.id}
              className={`flex-1 flex items-center justify-center gap-1 py-2.5 text-xs font-mono uppercase transition-colors ${
                isActive
                  ? 'text-cyan-400 border-b-2 border-cyan-500 bg-gray-950'
                  : 'text-gray-600 hover:text-gray-400'
              }`}
              onClick={() => setActiveTab(tab.id as any)}
            >
              <Icon className="w-3 h-3" />
              <span>{tab.label}</span>
              {tab.badge > 0 && (
                <span className={`text-[9px] font-bold px-1 rounded-sm ${isActive ? 'bg-cyan-800 text-cyan-200' : 'bg-gray-800 text-gray-400'}`}>
                  {tab.badge}
                </span>
              )}
            </button>
          )
        })}
      </div>

      <div className="flex-1 overflow-hidden">

        {/* ── UYARILAR ─────────────────────────────────────────────────────── */}
        {activeTab === 'uyarilar' && (
          <div className="h-full overflow-y-auto">
            <div className="flex items-center justify-between px-3 py-2 border-b border-gray-900">
              <span className="text-[10px] font-mono text-gray-500 uppercase">
                {alerts.length} aktif anomali
              </span>
              <Filter className="w-3 h-3 text-gray-600" />
            </div>
            {alerts.length === 0 ? (
              <div className="flex items-center justify-center h-32 text-gray-700 text-xs font-mono">
                Anomali tespit edilmedi
              </div>
            ) : (
              <div className="p-2 space-y-2">
                {alerts.map(alert => (
                  <div key={alert.id} className={`border border-gray-800 border-l-4 ${riskBorder(alert.risk_level)} p-3 bg-gray-950/50`}>
                    <div className="flex items-start justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="text-sm">{typeIcon(alert.type)}</span>
                        <div>
                          <div className="text-white text-xs font-bold font-mono">{alert.entity_name}</div>
                          <div className="text-gray-500 text-[10px] font-mono">{alert.title}</div>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className={`text-[10px] font-bold ${riskText(alert.risk_level)}`}>{alert.risk_level}</div>
                        <div className="text-gray-700 text-[9px]">{alert.anomaly_score}/100</div>
                      </div>
                    </div>
                    <p className="text-[10px] text-gray-500 leading-relaxed">{alert.description}</p>
                    <div className="mt-1.5 flex items-center justify-between text-[9px] text-gray-700 font-mono">
                      <span>{alert.coordinates.lat.toFixed(2)}°K {alert.coordinates.lon.toFixed(2)}°D</span>
                      {alert.region && <span className="text-gray-600">📍 {alert.region}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── HABERLER ─────────────────────────────────────────────────────── */}
        {activeTab === 'haberler' && (
          <div className="h-full flex flex-col">

            {/* Araç çubuğu */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-gray-900 shrink-0">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono text-gray-500 uppercase">OSINT</span>
                {newsLoading && <span className="text-[9px] font-mono text-cyan-700 animate-pulse">SYNC...</span>}
                {activeFilters > 0 && (
                  <span className="text-[9px] font-bold px-1 rounded-sm bg-cyan-900 text-cyan-300">
                    {activeFilters} filtre
                  </span>
                )}
              </div>
              <div className="flex items-center gap-1.5">
                {/* Anomali bölgesi butonu */}
                <button
                  onClick={() => setAnomalyMode(v => !v)}
                  title="Anomali bölgelerini filtrele"
                  className={`flex items-center gap-1 px-1.5 py-1 text-[9px] font-mono font-bold uppercase rounded-sm transition-colors ${
                    anomalyMode
                      ? 'bg-orange-900 text-orange-300 border border-orange-700'
                      : 'text-gray-600 hover:text-orange-400 border border-transparent'
                  }`}
                >
                  <Crosshair className="w-3 h-3" />
                  <span>Anomali</span>
                </button>
                {/* Filtreler */}
                <button
                  onClick={() => setShowFilters(v => !v)}
                  className={`p-1 rounded-sm transition-colors ${
                    showFilters || activeFilters > 0
                      ? 'text-cyan-400'
                      : 'text-gray-600 hover:text-gray-400'
                  }`}
                >
                  <Filter className="w-3.5 h-3.5" />
                </button>
                {/* Yenile */}
                <button
                  onClick={handleRefresh}
                  disabled={refreshing}
                  className="p-1 text-gray-600 hover:text-cyan-400 transition-colors disabled:opacity-40"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-cyan-500' : ''}`} />
                </button>
              </div>
            </div>

            {/* Filtre paneli */}
            {showFilters && (
              <div className="px-3 py-2 border-b border-gray-900 bg-gray-950 space-y-1.5 shrink-0">
                <div className="text-[9px] font-mono text-gray-700 uppercase mb-1">Tür</div>
                <select
                  value={filterCategory}
                  onChange={e => setFilterCategory(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-800 text-[10px] font-mono text-gray-300 px-2 py-1 rounded-sm"
                >
                  <option value="">Tümü</option>
                  {unique(news.map(n => n.category)).map(c => <option key={c} value={c}>{c}</option>)}
                </select>
                <div className="text-[9px] font-mono text-gray-700 uppercase mt-1">Kaynak</div>
                <select
                  value={filterSource}
                  onChange={e => setFilterSource(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-800 text-[10px] font-mono text-gray-300 px-2 py-1 rounded-sm"
                >
                  <option value="">Tümü</option>
                  {unique(news.map(n => n.source)).map(s => <option key={s} value={s}>{s}</option>)}
                </select>
                <div className="text-[9px] font-mono text-gray-700 uppercase mt-1">Bölge</div>
                <select
                  value={filterRegion}
                  onChange={e => setFilterRegion(e.target.value)}
                  disabled={anomalyMode}
                  className="w-full bg-gray-900 border border-gray-800 text-[10px] font-mono text-gray-300 px-2 py-1 rounded-sm disabled:opacity-40"
                >
                  <option value="">Tümü</option>
                  {unique(news.map(n => n.region)).map(r => <option key={r} value={r}>{r}</option>)}
                </select>
                {(filterCategory || filterSource || filterRegion) && (
                  <button
                    onClick={() => { setFilterCategory(''); setFilterSource(''); setFilterRegion('') }}
                    className="text-[9px] font-mono text-red-800 hover:text-red-400 uppercase mt-1"
                  >
                    Filtreleri temizle
                  </button>
                )}
              </div>
            )}

            {/* Anomali bilgi bandı */}
            {anomalyMode && (
              <div className="px-3 py-1.5 bg-orange-950/40 border-b border-orange-900/50 shrink-0">
                <div className="text-[9px] font-mono text-orange-400 uppercase">
                  {alerts.length > 0
                    ? `${[...new Set(alerts.map(a => a.region).filter(Boolean))].length} anomali bölgesi taranıyor`
                    : 'Aktif anomali yok — tüm haberler gösteriliyor'}
                </div>
              </div>
            )}

            {/* İçerik */}
            <div className="flex-1 overflow-y-auto">
              {newsLoading ? (
                <div className="flex flex-col items-center justify-center h-48 gap-3">
                  <svg className="w-6 h-6 text-cyan-600 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                  </svg>
                  <span className="text-[10px] font-mono text-gray-600 uppercase tracking-widest">
                    İstihbarat akışı bekleniyor
                  </span>
                </div>
              ) : visibleNews.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-32 gap-2 text-gray-700">
                  <span className="text-xs font-mono">Bu filtre için haber yok</span>
                </div>
              ) : (
                <div className="p-2 space-y-2">
                  {visibleNews.map(n => (
                    n.url ? (
                      <a
                        key={n.id}
                        href={n.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block border border-gray-800 p-3 bg-gray-950/50 hover:border-cyan-800 hover:bg-gray-900/60 transition-colors cursor-pointer"
                      >
                        <h4 className="text-white text-xs font-bold mb-1 leading-tight">{n.title}</h4>
                        <div className="flex items-center gap-2 text-[10px] text-gray-600 mb-1.5">
                          <span>{n.source}</span>
                          <span>·</span>
                          <span>{n.time}</span>
                          <span>·</span>
                          <span className="text-cyan-600">{n.category}</span>
                        </div>
                        {n.summary && (
                          <p className="text-[10px] text-gray-600 leading-relaxed">{n.summary}</p>
                        )}
                        <div className="mt-1.5 text-[9px] text-gray-700 font-mono">📍 {n.region}</div>
                      </a>
                    ) : (
                      <div
                        key={n.id}
                        className="border border-gray-800 p-3 bg-gray-950/50"
                      >
                        <h4 className="text-white text-xs font-bold mb-1 leading-tight">{n.title}</h4>
                        <div className="flex items-center gap-2 text-[10px] text-gray-600 mb-1.5">
                          <span>{n.source}</span>
                          <span>·</span>
                          <span>{n.time}</span>
                          <span>·</span>
                          <span className="text-cyan-600">{n.category}</span>
                        </div>
                        {n.summary && (
                          <p className="text-[10px] text-gray-600 leading-relaxed">{n.summary}</p>
                        )}
                        <div className="mt-1.5 text-[9px] text-gray-700 font-mono">📍 {n.region}</div>
                      </div>
                    )
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── ÖZET ─────────────────────────────────────────────────────────── */}
        {activeTab === 'ozet' && (
          <div className="h-full overflow-y-auto p-3 space-y-3">
            <div className="border border-gray-800 p-3">
              <h4 className="text-cyan-400 text-xs font-mono font-bold mb-2 uppercase">İstihbarat Özeti</h4>
              <p className="text-gray-400 text-xs leading-relaxed">
                {stats.aircraftCount} uçak ve {stats.vesselCount} gemi aktif izleme altında.
                {stats.anomalyCount > 0
                  ? ` ${stats.anomalyCount} anomali tespit edildi, ${stats.criticalCount} kritik durum değerlendirme gerektiriyor.`
                  : ' Belirgin anomali tespit edilmedi.'}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: 'Uçak',    value: stats.aircraftCount, color: 'text-cyan-400' },
                { label: 'Gemi',    value: stats.vesselCount,   color: 'text-blue-400' },
                { label: 'Anomali', value: stats.anomalyCount,  color: 'text-orange-400' },
                { label: 'Kritik',  value: stats.criticalCount, color: 'text-red-400' },
              ].map(s => (
                <div key={s.label} className="border border-gray-800 p-2">
                  <div className={`text-xl font-bold font-mono ${s.color}`}>{s.value}</div>
                  <div className="text-[10px] text-gray-600 uppercase font-mono">{s.label}</div>
                </div>
              ))}
            </div>
            <div className="border border-gray-800 p-3">
              <h4 className="text-gray-500 text-[10px] font-mono uppercase mb-2">Veri Kaynağı</h4>
              <p className={`text-xs font-mono ${
                stats.dataSource === 'live'  ? 'text-green-400'
                : stats.dataSource === 'cache' ? 'text-yellow-400'
                : 'text-orange-400'
              }`}>
                {stats.dataLabel}
              </p>
              {stats.lastUpdate && (
                <p className="text-[10px] text-gray-700 mt-1 font-mono">
                  Son güncelleme: {stats.lastUpdate.toLocaleTimeString('tr-TR', { timeZone: 'UTC' })} UTC
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
