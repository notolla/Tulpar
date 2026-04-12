/**
 * EFES — veri katmanı (legacy uyumluluk).
 * Yeni özellikler için: `hooks/useSitrepData`, `services/api`.
 */

import { API_BASE_URL } from './api'

export interface AircraftData {
  id: string
  callsign: string
  lat: number
  lon: number
  altitude: number
  speed: number
  heading: number
  timestamp: string
  source: 'cache' | 'live' | 'fallback'
  anomaly_score: number
  risk_level: string
  anomaly_reason: string
  flags: string[]
}

export interface VesselData {
  id: string
  mmsi: string
  name: string
  lat: number
  lon: number
  speed: number
  heading: number
  timestamp: string
  source: 'cache' | 'live' | 'fallback'
}

export interface StrategicZone {
  id: string
  name: string
  type: string
  coordinates: Array<{ lat: number; lon: number }>
  risk_level: string
  description: string
}

export const API_CONFIG = {
  BASE_URL: API_BASE_URL,
  SCALABLE_URL: API_BASE_URL,
  CACHE_TTL: 60_000,
} as const

let wsConnection: WebSocket | null = null

/** Gateway WebSocket: `/ws/sitrep` */
export class DataLayer {
  static connectWebSocket(): void {
    if (wsConnection) return
    try {
      const u = new URL(API_BASE_URL)
      u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
      u.pathname = '/ws/sitrep'
      u.search = ''
      wsConnection = new WebSocket(u.toString())
      wsConnection.onopen = () => {
        console.log('📡 WebSocket (sitrep) açıldı')
      }
      wsConnection.onmessage = (event) => {
        const data = JSON.parse(event.data as string)
        window.dispatchEvent(
          new CustomEvent('aircraft_update', { detail: data.aircraft }),
        )
        window.dispatchEvent(
          new CustomEvent('vessel_update', { detail: data.vessels }),
        )
      }
      wsConnection.onerror = () => {
        wsConnection?.close()
      }
      wsConnection.onclose = () => {
        wsConnection = null
      }
    } catch (e) {
      console.error('WebSocket:', e)
    }
  }

  static disconnectWebSocket(): void {
    wsConnection?.close()
    wsConnection = null
  }
}
