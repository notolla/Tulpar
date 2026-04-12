import React, { useEffect, useRef, useCallback } from 'react'
import L from 'leaflet'
import { Aircraft } from '@/services/api'

interface AircraftLayerProps {
  map: L.Map
  demoOverride?: Aircraft[]
  activeLayers?: Set<string>
}

interface MarkerState {
  marker: L.Marker
  trail: L.Polyline
  trailPoints: [number, number][]
  animFrame?: number
}

const TRAIL_LENGTH = 10
const ANIM_DURATION = 9000   // ms — OpenSky 10s polling ile senkron

function riskColor(risk: string): string {
  if (risk === 'Kritik') return '#ff1744'
  if (risk === 'Yüksek') return '#ff6d00'
  if (risk === 'Orta')   return '#ffd600'
  return '#00e676'
}

const MILITARY_PREFIXES = /^(TUAF|NATO|RFF|UKAF|USAF|ARMY|NAVY|RUS|UAF|ISR|BRTN|FRCE|DENA|GERM|ITAL)/i

function isMilitary(ac: Aircraft): boolean {
  if ((ac.flags ?? []).includes('MILITARY')) return true
  const cs = (ac.callsign ?? '').toUpperCase()
  return MILITARY_PREFIXES.test(cs)
}

function headingArrow(deg: number): string {
  const r = (deg * Math.PI) / 180
  const len = 10
  const cx = 12, cy = 12
  const tip = { x: cx + len * Math.sin(r), y: cy - len * Math.cos(r) }
  return `M${cx},${cy} L${tip.x.toFixed(1)},${tip.y.toFixed(1)}`
}

function buildIcon(ac: Aircraft): L.DivIcon {
  const color   = riskColor(ac.risk_level)
  const isPulse = ac.risk_level === 'Kritik'
  const score   = ac.anomaly_score ?? 0
  const mil     = isMilitary(ac)

  const pulse = isPulse
    ? `<span style="position:absolute;inset:-8px;border-radius:50%;border:1.5px solid ${color};animation:tulpar-pulse 1.2s ease-out infinite;opacity:.5"></span>`
    : ''

  // Uçak sembolü: askeri → kare, sivil → ✈
  const symbol = mil
    ? `<rect x="7" y="7" width="10" height="10" fill="${color}" fill-opacity=".9"/>`
    : `<text x="12" y="16" text-anchor="middle" font-size="13" fill="${color}">✈</text>`

  return L.divIcon({
    className: '',
    iconSize: [22, 22],
    iconAnchor: [11, 11],
    html: `
      <div style="position:relative;width:22px;height:22px">
        ${pulse}
        <svg width="22" height="22" viewBox="0 0 24 24" style="position:absolute;inset:0">
          ${symbol}
          <path d="${headingArrow(ac.heading ?? 0)}" stroke="${color}" stroke-width="1.5" stroke-linecap="round" opacity=".8"/>
        </svg>
        ${score >= 25 ? `<div style="position:absolute;top:-7px;right:-7px;background:${color};color:#000;font-size:8px;font-weight:bold;padding:0 2px;line-height:12px;font-family:monospace;min-width:12px;text-align:center">${score}</div>` : ''}
      </div>`,
  })
}

function buildPopup(ac: Aircraft): string {
  const color = riskColor(ac.risk_level)
  const score = ac.anomaly_score ?? 0
  const barW = Math.round(score)
  const flags = (ac.flags ?? []).join(' · ') || '—'

  return `
    <div style="background:#050505;border:1px solid #222;padding:12px;min-width:220px;color:#eee;font-family:'Courier New',monospace;font-size:11px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #222">
        <span style="color:#fff;font-size:13px;font-weight:bold">${ac.callsign}</span>
        <span style="background:${color};color:#000;font-size:9px;font-weight:bold;padding:2px 5px">${ac.risk_level.toUpperCase()}</span>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">
        <div><div style="color:#555;font-size:9px;text-transform:uppercase">İrtifa</div><div style="font-weight:bold">${(ac.altitude ?? 0).toLocaleString('tr-TR')} ft</div></div>
        <div><div style="color:#555;font-size:9px;text-transform:uppercase">Hız</div><div style="font-weight:bold">${Math.round(ac.speed ?? 0)} km/s</div></div>
        <div><div style="color:#555;font-size:9px;text-transform:uppercase">Yön</div><div style="font-weight:bold">${ac.heading ?? 0}°</div></div>
        <div><div style="color:#555;font-size:9px;text-transform:uppercase">Tip</div><div style="font-weight:bold">${ac.aircraft_type ?? 'CIV'}</div></div>
      </div>
      <div style="margin-bottom:6px">
        <div style="display:flex;justify-content:space-between;margin-bottom:2px">
          <span style="color:#555;font-size:9px;text-transform:uppercase">Anomali Skoru</span>
          <span style="color:${color};font-weight:bold;font-size:12px">${score}/100</span>
        </div>
        <div style="background:#1a1a1a;height:4px;border-radius:2px">
          <div style="background:${color};width:${barW}%;height:4px;border-radius:2px;transition:width .4s"></div>
        </div>
      </div>
      <div style="border-top:1px solid #222;padding-top:6px;color:#777;font-size:9px;line-height:1.4">${ac.anomaly_reason}</div>
      ${flags !== '—' ? `<div style="margin-top:4px;color:#444;font-size:9px">${flags}</div>` : ''}
    </div>`
}

function applyFilters(list: Aircraft[], layers: Set<string> | undefined): Aircraft[] {
  if (!layers) return list

  // Hızlı filtreler (sadece biri aktifse)
  if (layers.has('kritik'))       return list.filter(a => a.risk_level === 'Kritik')
  if (layers.has('yuksek_risk'))  return list.filter(a => a.risk_level === 'Yüksek' || a.risk_level === 'Kritik')
  if (layers.has('askeri'))       return list.filter(a => isMilitary(a))

  // Anomali filtresi: anomaliler açık, hava kapalı → sadece anomaliler
  if (layers.has('anomaliler') && !layers.has('hava')) {
    return list.filter(a => a.anomaly_flag || (a.anomaly_score ?? 0) >= 25)
  }

  // Alt katman: askeri alt-kategorisi kapalıysa askeri uçakları gizle
  if (layers.has('hava') && !layers.has('hava_askeri')) {
    list = list.filter(a => !isMilitary(a))
  }

  return list
}

export const AircraftLayer: React.FC<AircraftLayerProps> = ({ map, demoOverride, activeLayers }) => {
  const statesRef    = useRef<Map<string, MarkerState>>(new Map())
  const intervalRef  = useRef<ReturnType<typeof setInterval> | null>(null)
  const layersRef    = useRef(activeLayers)
  useEffect(() => { layersRef.current = activeLayers }, [activeLayers])

  const updateMarkers = useCallback((aircraftList: Aircraft[]) => {
    const currentIds = new Set(aircraftList.map(a => a.id))

    // Artık gelmeyenleri kaldır
    for (const [id, state] of statesRef.current) {
      if (!currentIds.has(id)) {
        cancelAnimationFrame(state.animFrame ?? 0)
        state.marker.remove()
        state.trail.remove()
        statesRef.current.delete(id)
      }
    }

    for (const ac of aircraftList) {
      if (!ac.lat || !ac.lon) continue
      const newPos: [number, number] = [ac.lat, ac.lon]

      if (statesRef.current.has(ac.id)) {
        // Var olan marker → smooth animasyon + trail güncelle
        const state = statesRef.current.get(ac.id)!
        const oldPos = state.marker.getLatLng()
        const startLat = oldPos.lat, startLon = oldPos.lng

        // Trail güncelle
        state.trailPoints.push(newPos)
        if (state.trailPoints.length > TRAIL_LENGTH) state.trailPoints.shift()
        state.trail.setLatLngs(state.trailPoints)

        // Marker ikonu güncelle (risk değişmiş olabilir)
        state.marker.setIcon(buildIcon(ac))
        state.marker.setPopupContent(buildPopup(ac))

        // Smooth hareket
        cancelAnimationFrame(state.animFrame ?? 0)
        const startTime = performance.now()
        const animate = (now: number) => {
          const t = Math.min((now - startTime) / ANIM_DURATION, 1)
          const ease = 1 - Math.pow(1 - t, 3)
          state.marker.setLatLng([
            startLat + (newPos[0] - startLat) * ease,
            startLon + (newPos[1] - startLon) * ease,
          ])
          if (t < 1) state.animFrame = requestAnimationFrame(animate)
        }
        state.animFrame = requestAnimationFrame(animate)

      } else {
        // Yeni marker
        const color = riskColor(ac.risk_level)
        const marker = L.marker(newPos, { icon: buildIcon(ac) })
          .bindPopup(buildPopup(ac), { maxWidth: 260, className: 'tulpar-popup' })
          .addTo(map)

        marker.on('mouseover', function (this: L.Marker) { this.openPopup() })

        const trail = L.polyline([[...newPos]], {
          color,
          weight: 1.5,
          opacity: 0.5,
          dashArray: '3 3',
        }).addTo(map)

        statesRef.current.set(ac.id, {
          marker,
          trail,
          trailPoints: [newPos],
        })
      }
    }
  }, [map])

  const fetchAndUpdate = useCallback(async () => {
    if (demoOverride) {
      updateMarkers(applyFilters(demoOverride, layersRef.current))
      return
    }
    try {
      const res = await fetch('/api/aircraft')
      if (!res.ok) return
      const data = await res.json()
      let list: Aircraft[] = Array.isArray(data) ? data : data?.data ?? []
      list = applyFilters(list, layersRef.current)
      if (list.length > 0) updateMarkers(list)
    } catch (e) {
      console.warn('AircraftLayer fetch hatası:', e)
    }
  }, [demoOverride, updateMarkers])

  useEffect(() => {
    if (!map) return
    fetchAndUpdate()
    intervalRef.current = setInterval(fetchAndUpdate, 10_000)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      for (const state of statesRef.current.values()) {
        cancelAnimationFrame(state.animFrame ?? 0)
        state.marker.remove()
        state.trail.remove()
      }
      statesRef.current.clear()
    }
  }, [map, fetchAndUpdate])

  // Demo override değişince hemen güncelle
  useEffect(() => {
    if (demoOverride) updateMarkers(applyFilters(demoOverride, layersRef.current))
  }, [demoOverride, updateMarkers])

  // Filtre değişince yeniden fetch et
  useEffect(() => {
    fetchAndUpdate()
  }, [activeLayers, fetchAndUpdate])

  return null
}
