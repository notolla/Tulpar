import React, { useState, useEffect } from 'react'
import { AlertTriangle, Newspaper, Brain, Filter } from 'lucide-react'
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
}

interface NewsItem {
  id: string
  title: string
  source: string
  time: string
  category: string
  region: string
  summary?: string
}

export const RightPanel: React.FC<RightPanelProps> = ({ stats }) => {
  const [activeTab, setActiveTab] = useState<'uyarilar' | 'haberler' | 'ozet'>('uyarilar')
  const [alerts, setAlerts] = useState<LiveAlert[]>([])
  const [news, setNews] = useState<NewsItem[]>([])

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const res = await fetch('/api/alerts')
        if (res.ok) setAlerts(await res.json())
      } catch { /* sessiz hata */ }
    }
    const fetchNews = async () => {
      try {
        const res = await fetch('/api/news')
        if (res.ok) setNews(await res.json())
      } catch { /* sessiz hata */ }
    }
    fetchAlerts()
    fetchNews()
    const iv1 = setInterval(fetchAlerts, 5_000)
    const iv2 = setInterval(fetchNews, 60_000)
    return () => { clearInterval(iv1); clearInterval(iv2) }
  }, [])

  const riskBorder = (r: string) =>
    r === 'Kritik' ? 'border-l-red-500' : r === 'Yüksek' ? 'border-l-orange-500' : 'border-l-yellow-500'

  const riskText = (r: string) =>
    r === 'Kritik' ? 'text-red-400' : r === 'Yüksek' ? 'text-orange-400' : r === 'Orta' ? 'text-yellow-400' : 'text-green-400'

  const typeIcon = (t: string) =>
    t === 'hava' ? '✈' : t === 'deniz' ? '⛵' : '⚠'

  const tabs = [
    { id: 'uyarilar', label: 'Uyarılar', icon: AlertTriangle, badge: alerts.length },
    { id: 'haberler', label: 'OSINT', icon: Newspaper, badge: news.length },
    { id: 'ozet',     label: 'Özet',    icon: Brain, badge: 0 },
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
        {/* UYARILAR */}
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
                  <div
                    key={alert.id}
                    className={`border border-gray-800 border-l-4 ${riskBorder(alert.risk_level)} p-3 bg-gray-950/50`}
                  >
                    <div className="flex items-start justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="text-sm">{typeIcon(alert.type)}</span>
                        <div>
                          <div className="text-white text-xs font-bold font-mono">{alert.entity_name}</div>
                          <div className="text-gray-500 text-[10px] font-mono">{alert.title}</div>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className={`text-[10px] font-bold ${riskText(alert.risk_level)}`}>
                          {alert.risk_level}
                        </div>
                        <div className="text-gray-700 text-[9px]">
                          {alert.anomaly_score}/100
                        </div>
                      </div>
                    </div>
                    <p className="text-[10px] text-gray-500 leading-relaxed">{alert.description}</p>
                    <div className="mt-1.5 text-[9px] text-gray-700 font-mono">
                      {alert.coordinates.lat.toFixed(2)}°K {alert.coordinates.lon.toFixed(2)}°D
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* HABERLER */}
        {activeTab === 'haberler' && (
          <div className="h-full overflow-y-auto">
            <div className="flex items-center justify-between px-3 py-2 border-b border-gray-900">
              <span className="text-[10px] font-mono text-gray-500 uppercase">OSINT Haber Akışı</span>
            </div>
            <div className="p-2 space-y-2">
              {news.map(n => (
                <div key={n.id} className="border border-gray-800 p-3 bg-gray-950/50 hover:border-gray-700 transition-colors">
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
              ))}
            </div>
          </div>
        )}

        {/* ÖZET */}
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
                { label: 'Uçak', value: stats.aircraftCount, color: 'text-cyan-400' },
                { label: 'Gemi',  value: stats.vesselCount,  color: 'text-blue-400' },
                { label: 'Anomali', value: stats.anomalyCount, color: 'text-orange-400' },
                { label: 'Kritik', value: stats.criticalCount, color: 'text-red-400' },
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
                stats.dataSource === 'live' ? 'text-green-400'
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
