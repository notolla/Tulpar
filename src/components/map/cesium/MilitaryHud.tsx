import React from 'react'

export type HudMode = 'normal' | 'nvg' | 'thermal' | 'radar'

type Props = {
  mode: HudMode
  onMode: (m: HudMode) => void
  coords: string
  alerts: string[]
  onDismissAlert: (index: number) => void
  onFollow: () => void
  selectedLabel: string
  detail?: string
  linkStatus: string
}

const modes: { id: HudMode; label: string }[] = [
  { id: 'normal', label: 'DAY' },
  { id: 'nvg', label: 'NVG' },
  { id: 'thermal', label: 'THERM' },
  { id: 'radar', label: 'RADAR' },
]

export const MilitaryHud: React.FC<Props> = ({
  mode,
  onMode,
  coords,
  alerts,
  onDismissAlert,
  onFollow,
  selectedLabel,
  detail,
  linkStatus,
}) => {
  return (
    <div className="pointer-events-none absolute inset-0 z-10">
      <div className="absolute inset-8 border border-cyan-500/25 rounded-sm" />
      <div className="absolute left-1/2 top-1/2 h-8 w-8 -translate-x-1/2 -translate-y-1/2 border border-cyan-400/40 rounded-full" />
      <div className="absolute left-1/2 top-1/2 h-px w-24 -translate-x-1/2 -translate-y-1/2 bg-cyan-400/30" />
      <div className="absolute left-1/2 top-1/2 h-24 w-px -translate-x-1/2 -translate-y-1/2 bg-cyan-400/30" />

      <div className="pointer-events-auto absolute left-3 top-3 flex flex-wrap gap-1">
        {modes.map((m) => (
          <button
            key={m.id}
            type="button"
            onClick={() => onMode(m.id)}
            className={`rounded border px-2 py-0.5 font-mono text-[10px] uppercase ${
              mode === m.id
                ? 'border-cyan-400 bg-cyan-950 text-cyan-200'
                : 'border-gray-800 bg-black/60 text-gray-500 hover:border-gray-600'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <div className="pointer-events-none absolute right-3 top-3 max-w-[14rem] text-right font-mono text-[10px] text-cyan-200/90">
        <div className="text-gray-500">LINK</div>
        <div>{linkStatus.toUpperCase()}</div>
        <div className="mt-2 text-gray-500">CAM</div>
        <div className="break-all">{coords}</div>
      </div>

      <div className="pointer-events-auto absolute bottom-3 left-3 right-3 flex flex-col gap-2 md:flex-row md:items-end">
        <div className="flex-1 space-y-1 font-mono text-[11px] text-cyan-100">
          {alerts.slice(0, 3).map((a, i) => (
            <div
              key={`${i}-${a}`}
              className="flex items-center justify-between gap-2 border border-orange-500/40 bg-black/70 px-2 py-1 text-orange-200"
            >
              <span className="truncate">{a}</span>
              <button
                type="button"
                className="shrink-0 text-[10px] text-gray-400 hover:text-white"
                onClick={() => onDismissAlert(i)}
              >
                OK
              </button>
            </div>
          ))}
        </div>
        <div className="flex shrink-0 flex-col gap-1 border border-gray-800 bg-black/75 px-3 py-2 font-mono text-[10px] text-gray-300">
          <div className="text-gray-500">TARGET</div>
          <div className="text-cyan-300">{selectedLabel}</div>
          {detail && <div className="text-gray-400">{detail}</div>}
          <button
            type="button"
            onClick={onFollow}
            className="mt-1 border border-cyan-700 px-2 py-1 text-cyan-300 hover:bg-cyan-950"
          >
            FOLLOW
          </button>
        </div>
      </div>

      {mode === 'radar' && (
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{
            background:
              'repeating-conic-gradient(from 0deg, #0f0 0deg 4deg, transparent 4deg 18deg)',
            animation: 'efes-spin 12s linear infinite',
          }}
        />
      )}
      <style>{`@keyframes efes-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
