import React, { useEffect, useState } from 'react'
import type { SystemStats } from '@/types'

interface TopBarProps {
  stats: SystemStats
}

export const TopBar: React.FC<TopBarProps> = ({ stats }) => {
  const [utcTime, setUtcTime] = useState('')

  useEffect(() => {
    const tick = () => {
      setUtcTime(
        new Date().toLocaleTimeString('tr-TR', {
          hour: '2-digit', minute: '2-digit', second: '2-digit',
          hour12: false, timeZone: 'UTC',
        })
      )
    }
    tick()
    const iv = setInterval(tick, 1000)
    return () => clearInterval(iv)
  }, [])

  const sourceColor =
    stats.dataSource === 'live'
      ? 'text-green-400'
      : stats.dataSource === 'cache'
      ? 'text-yellow-400'
      : 'text-orange-400'

  const sourceDot =
    stats.dataSource === 'live'
      ? 'bg-green-500'
      : stats.dataSource === 'cache'
      ? 'bg-yellow-500'
      : 'bg-orange-500'

  const sourceText =
    stats.dataSource === 'live'
      ? 'Canlı Veri'
      : stats.dataSource === 'cache'
      ? 'Önbellek'
      : 'Test Verisi'

  return (
    <div className="h-12 bg-black border-b border-gray-900 flex items-center justify-between px-4 shrink-0">
      {/* Sol — Marka */}
      <div className="flex items-center gap-3">
        <div className="w-6 h-6 bg-cyan-500 opacity-90" style={{ clipPath: 'polygon(50% 0%, 100% 100%, 0% 100%)' }} />
        <div>
          <h1 className="text-sm font-bold text-cyan-400 font-mono uppercase tracking-widest leading-none">
            TULPAR
          </h1>
          <p className="text-[9px] text-gray-600 font-mono uppercase tracking-wider leading-none mt-0.5">
            Erken Uyarı ve İstihbarat Platformu
          </p>
        </div>
      </div>

      {/* Orta — Sistem durumu + sayaçlar */}
      <div className="flex items-center gap-6">
        {/* Sistem aktif */}
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${sourceDot} animate-pulse`} />
          <span className={`font-mono text-xs uppercase ${sourceColor}`}>
            {sourceText}
          </span>
        </div>

        {/* Sayaçlar */}
        <div className="flex items-center gap-4 font-mono text-xs">
          <span className="text-cyan-400">
            ✈ <span className="font-bold">{stats.aircraftCount}</span> uçak
          </span>
          <span className="text-gray-700">|</span>
          <span className="text-blue-400">
            ⛵ <span className="font-bold">{stats.vesselCount}</span> gemi
          </span>
          <span className="text-gray-700">|</span>
          <span className="text-orange-400">
            ⚠ <span className="font-bold">{stats.anomalyCount}</span> anomali
          </span>
          {stats.criticalCount > 0 && (
            <>
              <span className="text-gray-700">|</span>
              <span className="text-red-400 animate-pulse">
                🔴 <span className="font-bold">{stats.criticalCount}</span> kritik
              </span>
            </>
          )}
        </div>

        {/* Veri etiketi */}
        <div className={`font-mono text-[10px] ${sourceColor} opacity-70`}>
          {stats.dataLabel}
        </div>
      </div>

      {/* Sağ — Saat */}
      <div className="flex items-center gap-3">
        <span className="text-cyan-400 font-mono text-sm font-bold tabular-nums">
          {utcTime}
        </span>
        <span className="text-gray-600 font-mono text-[10px]">UTC</span>
      </div>
    </div>
  )
}
