"""
EFES-2026 Frontend Data Layer
Cache ve WebSocket ile veri yönetimi
"""

import { useEffect, useState, useCallback } from 'react'

// Types
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
  coordinates: Array<{lat: number, lon: number}>
  risk_level: string
  description: string
}

// API Configuration
const API_CONFIG = {
  BASE_URL: 'http://localhost:8000',
  SCALABLE_URL: 'http://localhost:8002',
  CACHE_TTL: 5 * 60 * 1000, // 5 dakika
}

// WebSocket connection
let wsConnection: WebSocket | null = null

export class DataLayer {
  // WebSocket bağlantısı
  static connectWebSocket(): void {
    if (wsConnection) return
    
    try {
      wsConnection = new WebSocket('ws://localhost:8000/ws')
      
      wsConnection.onopen = () => {
        console.log('📡 WebSocket bağlantısı kuruldu')
      }
      
      wsConnection.onmessage = (event) => {
        const data = JSON.parse(event.data)
        console.log('📡 WebSocket verisi alındı:', data)
        
        // Event dispatch
        window.dispatchEvent(new CustomEvent('aircraft_update', { detail: data.aircraft }))
        window.dispatchEvent(new CustomEvent('vessel_update', { detail: data.vessels }))
      }
      
      wsConnection.onerror = (error) => {
        console.error('❌ WebSocket hatası:', error)
      }
      
      wsConnection.onclose = () => {
        console.log('📡 WebSocket bağlantısı kapandı')
        wsConnection = null
      }
    } catch (error) {
      console.error('❌ WebSocket bağlantı hatası:', error)
    }
  }
  
  static disconnectWebSocket(): void {
    if (wsConnection) {
      wsConnection.close()
      wsConnection = null
    }
  }
  
  // Aircraft data management
  static useAircraftData() {
    const [aircraft, setAircraft] = useState<AircraftData[]>([])
    const [lastUpdate, setLastUpdate] = useState<string>('')
    
    // Cache'den veri çek
    const fetchAircraftData = useCallback(async () => {
      try {
        const response = await fetch(`${API_CONFIG.SCALABLE_URL}/api/scalable/aircraft`)
        const data = await response.json()
        
        setAircraft(data.data || [])
        setLastUpdate(data.timestamp || '')
        
        console.log('✅ Uçak verisi:', data)
        return data.data
      } catch (error) {
        console.error('❌ Uçak verisi hatası:', error)
        setAircraft([])
      }
    }, [])
    
    // Polling ile veri güncelleme
    useEffect(() => {
      const interval = setInterval(() => {
        fetchAircraftData()
      }, 30000) // 30 saniyede bir
      
      return () => clearInterval(interval)
    }, [])
    
    // Vessel data management
    static useVesselData() {
      const [vessels, setVessels] = useState<VesselData[]>([])
      const [lastVesselUpdate, setLastVesselUpdate] = useState<string>('')
      
      const fetchVesselData = useCallback(async () => {
        try {
          const response = await fetch(`${API_CONFIG.SCALABLE_URL}/api/scalable/vessels`)
          const data = await response.json()
          
          setVessels(data.data || [])
          setLastVesselUpdate(data.timestamp || '')
          
          console.log('✅ Gemi verisi:', data)
          return data.data
        } catch (error) {
          console.error('❌ Gemi verisi hatası:', error)
          setVessels([])
        }
      }, [])
      
      useEffect(() => {
        const interval = setInterval(() => {
          fetchVesselData()
        }, 60000) // 1 dakikada bir
        
        return () => clearInterval(interval)
      }, [])
      
      // Strategic zones data
      static useStrategicZones() {
        const [zones, setZones] = useState<StrategicZone[]>([])
        
        const fetchStrategicZones = useCallback(async () => {
          try {
            const response = await fetch(`${API_CONFIG.BASE_URL}/api/strategic-zones`)
            const data = await response.json()
            
            setZones(data || [])
            console.log('✅ Stratejik bölgeler:', data)
            return data
          } catch (error) {
            console.error('❌ Stratejik bölgeler hatası:', error)
            setZones([])
          }
        }, [])
        
        useEffect(() => {
          fetchStrategicZones()
        }, [])
        
        // Performance optimization
        static usePerformanceMonitor() {
          const [metrics, setMetrics] = useState({
            aircraftCount: 0,
            vesselCount: 0,
            lastUpdate: '',
            cacheHitRate: 0
          })
          
          useEffect(() => {
            const updateMetrics = () => {
              setMetrics(prev => ({
                ...prev,
                aircraftCount: aircraft.length,
                vesselCount: vessels.length,
                lastUpdate: new Date().toISOString()
              }))
            }
            
            // Aircraft ve vessel değişiklerini izle
            const interval = setInterval(() => {
              updateMetrics()
            }, 5000) // 5 saniyede bir
            
            return () => clearInterval(interval)
          }, [aircraft, vessels])
        }
      }
    }
  }
}
