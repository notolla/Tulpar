// useRealtimeAircraft - Production-grade WebSocket client for aircraft tracking
// Handles diff-based updates, connection management, and state synchronization

import { useEffect, useRef, useState, useCallback } from 'react'

export interface Aircraft {
  id: string
  callsign: string
  lat: number
  lon: number
  heading: number
  speed: number
  altitude: number
  anomaly_score: number
  status: string
  last_update: string
  source: string
}

interface AircraftDiff {
  type: 'diff' | 'full' | 'heartbeat'
  timestamp: string
  added?: Aircraft[]
  updated?: Aircraft[]
  removed?: string[]
  aircraft?: Aircraft[]  // For full state messages
}

interface UseRealtimeAircraftOptions {
  wsUrl?: string
  httpUrl?: string
  onConnect?: () => void
  onDisconnect?: () => void
  onError?: (error: Error) => void
}

export function useRealtimeAircraft(options: UseRealtimeAircraftOptions = {}) {
  const {
    wsUrl = 'ws://localhost:8000/ws/sitrep',
    httpUrl = 'http://localhost:8000/api/aircraft',
    onConnect,
    onDisconnect,
    onError
  } = options

  const [aircraft, setAircraft] = useState<Map<string, Aircraft>>(new Map())
  const [isConnected, setIsConnected] = useState(false)
  const [connectionType, setConnectionType] = useState<'ws' | 'http' | 'none'>('none')
  const [stats, setStats] = useState({ updates: 0, lastUpdate: Date.now() })
  
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const httpIntervalRef = useRef<NodeJS.Timeout | null>(null)

  // Apply diff to aircraft map
  const applyDiff = useCallback((diff: AircraftDiff) => {
    setAircraft(prev => {
      const next = new Map(prev)
      
      // Remove aircraft
      diff.removed?.forEach(id => {
        next.delete(id)
      })
      
      // Add new aircraft
      diff.added?.forEach(ac => {
        next.set(ac.id, ac)
      })
      
      // Update existing aircraft
      diff.updated?.forEach(ac => {
        next.set(ac.id, ac)
      })
      
      return next
    })
    
    setStats(s => ({ 
      updates: s.updates + 1, 
      lastUpdate: Date.now() 
    }))
  }, [])

  // Apply full state reset
  const applyFullState = useCallback((aircraftList: Aircraft[]) => {
    setAircraft(() => {
      const next = new Map<string, Aircraft>()
      aircraftList.forEach(ac => next.set(ac.id, ac))
      return next
    })
    
    setStats(s => ({ 
      updates: s.updates + 1, 
      lastUpdate: Date.now() 
    }))
  }, [])

  // WebSocket connection
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    
    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('✅ WebSocket connected - Production Engine Active')
        setIsConnected(true)
        setConnectionType('ws')
        onConnect?.()
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as AircraftDiff
          
          switch (data.type) {
            case 'diff':
              applyDiff(data)
              break
            case 'full':
              if (Array.isArray(data.aircraft)) {
                applyFullState(data.aircraft)
              }
              break
            case 'heartbeat':
              // Connection is alive
              break
          }
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err)
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        onError?.(new Error('WebSocket connection failed'))
      }

      ws.onclose = () => {
        console.log('🔌 WebSocket closed, falling back to HTTP polling')
        setIsConnected(false)
        setConnectionType('none')
        onDisconnect?.()
        
        // Attempt reconnection after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          connectWebSocket()
        }, 3000)
      }
    } catch (err) {
      console.error('Failed to create WebSocket:', err)
      onError?.(err as Error)
    }
  }, [wsUrl, onConnect, onDisconnect, onError, applyDiff, applyFullState])

  // HTTP fallback polling
  const startHttpPolling = useCallback(() => {
    if (httpIntervalRef.current) return
    
    const fetchAircraft = async () => {
      try {
        const response = await fetch(httpUrl)
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        
        const data = await response.json()
        if (data.aircraft && Array.isArray(data.aircraft)) {
          applyFullState(data.aircraft)
          setConnectionType('http')
        }
      } catch (err) {
        console.error('HTTP fetch failed:', err)
      }
    }
    
    // Initial fetch
    fetchAircraft()
    
    // Poll every 5 seconds
    httpIntervalRef.current = setInterval(fetchAircraft, 5000)
  }, [httpUrl, applyFullState])

  // Initialize connection
  useEffect(() => {
    // Try WebSocket first
    connectWebSocket()
    
    // Fallback to HTTP after 5 seconds if WebSocket fails
    const fallbackTimeout = setTimeout(() => {
      if (!isConnected) {
        console.log('⚠️ WebSocket not connected, starting HTTP fallback')
        startHttpPolling()
      }
    }, 5000)

    return () => {
      clearTimeout(fallbackTimeout)
      
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      
      if (httpIntervalRef.current) {
        clearInterval(httpIntervalRef.current)
      }
      
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [connectWebSocket, startHttpPolling, isConnected])

  return {
    aircraft: Array.from(aircraft.values()),
    aircraftMap: aircraft,
    isConnected,
    connectionType,
    stats,
    count: aircraft.size
  }
}
