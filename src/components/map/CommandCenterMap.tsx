import React, { useState } from 'react'
import { OpenStreetMap } from '@/components/map/OpenStreetMap'
import { CommandGlobe } from '@/components/map/cesium/CommandGlobe'
import type { ViewMode } from '@/types'

type MapView = '3d' | '2d'

interface CommandCenterMapProps {
  viewMode?: ViewMode
  demoMode?: boolean
  activeLayers?: Set<string>
}

export const CommandCenterMap: React.FC<CommandCenterMapProps> = ({
  viewMode = 'normal',
  demoMode = false,
  activeLayers,
}) => {
  const [view, setView] = useState<MapView>('2d')

  return (
    <div className="relative h-full w-full min-h-0 bg-black">
      {/* Sağ üst toggle */}
      <div className="absolute right-3 top-3 z-20 flex gap-1 font-mono text-[10px]">
        <button
          onClick={() => setView('2d')}
          className={`rounded border px-2 py-1 uppercase transition-colors ${
            view === '2d'
              ? 'border-cyan-500 bg-cyan-950 text-cyan-200'
              : 'border-gray-800 bg-black/80 text-gray-500 hover:border-gray-600'
          }`}
        >
          2D HARİTA
        </button>
        <button
          onClick={() => setView('3d')}
          className={`rounded border px-2 py-1 uppercase transition-colors ${
            view === '3d'
              ? 'border-cyan-500 bg-cyan-950 text-cyan-200'
              : 'border-gray-800 bg-black/80 text-gray-500 hover:border-gray-600'
          }`}
        >
          3D KÜRE
        </button>
      </div>

      {view === '3d' ? (
        <CommandGlobe />
      ) : (
        <div className="absolute inset-0">
          <OpenStreetMap
            viewMode={viewMode}
            demoMode={demoMode}
            activeLayers={activeLayers}
          />
        </div>
      )}
    </div>
  )
}
