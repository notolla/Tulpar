import { useCallback, useEffect, useRef, useState } from 'react'
import type { Aircraft, Vessel } from '@/services/api'

const API_BASE =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) ||
  'http://localhost:8000'

function wsUrl(): string {
  const u = new URL(API_BASE)
  u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:'
  u.pathname = '/ws/sitrep'
  u.search = ''
  return u.toString()
}

async function fetchJson<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`)
  if (!r.ok) throw new Error(String(r.status))
  return r.json() as Promise<T>
}

export function useSitrepData(pollMs = 8000) {
  const [aircraft, setAircraft] = useState<Aircraft[]>([])
  const [vessels, setVessels] = useState<Vessel[]>([])
  const [source, setSource] = useState<'ws' | 'http' | 'idle'>('idle')
  const wsRef = useRef<WebSocket | null>(null)

  const pullHttp = useCallback(async () => {
    try {
      const [a, v] = await Promise.all([
        fetchJson<Aircraft[]>('/api/aircraft'),
        fetchJson<Vessel[]>('/api/vessels'),
      ])
      setAircraft(Array.isArray(a) ? a : [])
      setVessels(Array.isArray(v) ? v : [])
      setSource('http')
    } catch {
      /* keep last */
    }
  }, [])

  useEffect(() => {
    let poll: ReturnType<typeof setInterval> | undefined
    let cancelled = false
    /** React Strict Mode: ilk unmount CONNECTING soketi kapatmasın diye gecikmeli kapatma */
    let closeTimer: ReturnType<typeof setTimeout> | undefined
    const socketIdRef = { id: 0 }

    const startWs = () => {
      socketIdRef.id += 1
      const mySocket = socketIdRef.id
      try {
        const ws = new WebSocket(wsUrl())
        wsRef.current = ws

        ws.onopen = () => {
          if (cancelled || socketIdRef.id !== mySocket) return
          setSource('ws')
        }

        ws.onmessage = (ev) => {
          if (cancelled || wsRef.current !== ws) return
          try {
            const msg = JSON.parse(ev.data as string)
            if (Array.isArray(msg.aircraft)) setAircraft(msg.aircraft)
            if (Array.isArray(msg.vessels)) setVessels(msg.vessels)
            setSource('ws')
          } catch {
            /* ignore */
          }
        }

        ws.onerror = () => {
          /* El sıkışma hatasında close() çağırma — "closed before established" gürültüsü */
        }

        ws.onclose = () => {
          if (wsRef.current === ws) wsRef.current = null
        }
      } catch {
        wsRef.current = null
      }
    }

    startWs()
    void pullHttp()
    poll = setInterval(() => {
      if (cancelled) return
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        void pullHttp()
      }
    }, pollMs)

    return () => {
      cancelled = true
      if (poll) clearInterval(poll)
      if (closeTimer) clearTimeout(closeTimer)

      const w = wsRef.current
      wsRef.current = null
      socketIdRef.id += 1

      closeTimer = setTimeout(() => {
        try {
          if (w && w.readyState === WebSocket.OPEN) {
            w.close()
          }
        } catch {
          /* ignore */
        }
      }, 120)
    }
  }, [pollMs, pullHttp])

  return { aircraft, vessels, source, apiBase: API_BASE, refresh: pullHttp }
}
