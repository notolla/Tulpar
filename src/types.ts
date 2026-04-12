export type ViewMode = 'normal' | 'gece_gorus' | 'termal' | 'radar' | 'taktik'

export interface SystemStats {
  aircraftCount: number
  vesselCount: number
  anomalyCount: number
  criticalCount: number
  dataSource: 'live' | 'cache' | 'test'
  dataLabel: string
  lastUpdate: Date | null
}
