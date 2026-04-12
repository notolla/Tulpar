export const API_BASE_URL =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) ||
  'http://localhost:8000'

export interface Aircraft {
  id: string
  callsign: string
  cagriKodu?: string
  lat: number
  lon: number
  altitude: number
  irtifa?: number
  speed: number
  hiz?: number
  heading: number
  yon?: number
  timestamp: string
  aircraft_type?: string
  ucakTipi?: string
  anomaly_score: number
  anomaliSkoru?: number
  risk_score?: number
  risk_level: string
  riskSeviyesi?: string
  anomaly_flag?: boolean
  anomaly_reason: string
  anomaliNedeni?: string
  flags: string[]
  bayraklar?: string[]
  route?: Array<{ lat: number; lon: number; timestamp: string }>
}

export interface Vessel {
  id?: string
  name: string
  ad?: string
  mmsi: string
  lat: number
  lon: number
  speed: number
  hiz?: number
  heading: number
  rota?: number
  timestamp: string
  vessel_type: string
  gemiTipi?: string
  anomaly_score: number
  anomaliSkoru?: number
  risk_score?: number
  risk_level: string
  riskSeviyesi?: string
  anomaly_flag?: boolean
  anomaly_reason: string
  anomaliNedeni?: string
  flags: string[]
  bayraklar?: string[]
  route?: Array<{ lat: number; lon: number; timestamp: string }>
}

export interface Alert {
  id: string
  type: string
  entity_id: string
  entity_name: string
  title: string
  description: string
  risk_level: string
  timestamp: string
  coordinates: { lat: number; lon: number }
  category: string
}

class ApiService {
  readonly API_BASE_URL = API_BASE_URL

  private async fetch<T>(endpoint: string): Promise<T> {
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      return await response.json()
    } catch (error) {
      console.error(`API Error fetching ${endpoint}:`, error)
      throw error
    }
  }

  async getAircrafts(): Promise<Aircraft[]> {
    return this.fetch<Aircraft[]>('/api/aircraft')
  }

  async getVessels(): Promise<Vessel[]> {
    return this.fetch<Vessel[]>('/api/vessels')
  }

  async getAlerts(): Promise<Alert[]> {
    return this.fetch<Alert[]>('/api/alerts')
  }

  async getStrategicZones(): Promise<any> {
    return this.fetch<any>('/api/strategic-zones')
  }

  async getNews(): Promise<any[]> {
    return this.fetch<any[]>('/api/news')
  }

  async healthCheck(): Promise<{ status: string; timestamp: string }> {
    return this.fetch<{ status: string; timestamp: string }>('/health')
  }
}

export const apiService = new ApiService()
