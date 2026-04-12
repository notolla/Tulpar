/**
 * TULPAR — Askeri Aktivite Zonları
 *
 * track_store'dan gelen askeri uçak konumlarını haritada gösterir:
 *  - Kırmızı içi dolu nokta → son görülen konum
 *  - Sarı kesik çember       → hareket bölgesi yarıçapı
 *  - Kırmızı kesik çember    → exclusion zone (sivil girme)
 *  - Popup                   → callsign, son görülme, irtifa, hız
 */

import { useEffect, useRef } from 'react'
import L from 'leaflet'

interface MilitaryZone {
  callsign: string
  center_lat: number
  center_lon: number
  radius_km: number
  exclusion_radius_km: number
  point_count: number
  last_seen: number
  age_minutes: number
  max_altitude: number
  avg_speed: number
  peak_risk: number
  active: boolean
}

interface MilitaryZoneLayerProps {
  map: L.Map
}

function formatAge(minutes: number): string {
  if (minutes < 60)  return `${minutes} dk önce`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return `${h} sa ${m} dk önce`
}

export function MilitaryZoneLayer({ map }: MilitaryZoneLayerProps) {
  const layersRef = useRef<L.Layer[]>([])
  const timerRef  = useRef<ReturnType<typeof setInterval> | null>(null)

  const draw = async () => {
    try {
      const res = await fetch('/api/military/zones?hours=12')
      if (!res.ok) return
      const data = await res.json()
      const zones: MilitaryZone[] = data.zones ?? []

      // Önceki katmanları temizle
      layersRef.current.forEach(l => l.remove())
      layersRef.current = []

      for (const z of zones) {
        const center: [number, number] = [z.center_lat, z.center_lon]
        const activeColor = z.active ? '#ff1744' : '#ff6d00'
        const exColor     = z.active ? 'rgba(255,23,68,0.06)' : 'rgba(255,109,0,0.04)'

        // 1. Exclusion zone — büyük kesik kırmızı çember
        const exCircle = L.circle(center, {
          radius:      z.exclusion_radius_km * 1000,
          color:       activeColor,
          weight:      1.5,
          opacity:     z.active ? 0.7 : 0.4,
          dashArray:   '6 6',
          fillColor:   exColor,
          fillOpacity: 1,
        })

        // 2. Hareket bölgesi — sarı küçük çember
        const actCircle = L.circle(center, {
          radius:      z.radius_km * 1000,
          color:       '#ffd600',
          weight:      1,
          opacity:     0.5,
          dashArray:   '3 5',
          fillOpacity: 0,
        })

        // 3. Merkez nokta
        const dot = L.circleMarker(center, {
          radius:      z.active ? 6 : 4,
          color:       activeColor,
          weight:      2,
          fillColor:   activeColor,
          fillOpacity: z.active ? 0.9 : 0.5,
        })

        // 4. Callsign etiketi
        const label = L.marker(center, {
          icon: L.divIcon({
            className: '',
            iconSize:  [80, 16],
            iconAnchor:[40, -8],
            html: `<div style="
              color:${activeColor};
              font-family:monospace;
              font-size:10px;
              font-weight:bold;
              white-space:nowrap;
              text-shadow:0 0 4px #000, 0 0 8px #000;
              pointer-events:none;
            ">${z.callsign}${z.active ? ' ●' : ' ○'}</div>`,
          }),
        })

        // 5. Popup
        const popup = L.popup({ maxWidth: 240 }).setContent(`
          <div style="
            background:#050505;border:1px solid #333;
            padding:10px;color:#eee;font-family:monospace;font-size:11px;
          ">
            <div style="color:${activeColor};font-weight:bold;font-size:13px;margin-bottom:6px">
              ${z.callsign}
              <span style="font-size:9px;margin-left:4px;border:1px solid ${activeColor};padding:1px 4px">
                ${z.active ? 'AKTİF' : 'GEÇMİŞ'}
              </span>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-bottom:6px">
              <div><div style="color:#555;font-size:9px">Son görülme</div><div>${formatAge(z.age_minutes)}</div></div>
              <div><div style="color:#555;font-size:9px">Gözlem sayısı</div><div>${z.point_count}</div></div>
              <div><div style="color:#555;font-size:9px">Max irtifa</div><div>${(z.max_altitude ?? 0).toLocaleString('tr-TR')} ft</div></div>
              <div><div style="color:#555;font-size:9px">Ort. hız</div><div>${z.avg_speed} km/h</div></div>
            </div>
            <div style="border-top:1px solid #222;padding-top:6px;color:#777;font-size:9px">
              Exclusion zone: <span style="color:${activeColor}">${z.exclusion_radius_km} km</span>
              &nbsp;·&nbsp; Hareket bölgesi: ${z.radius_km} km
            </div>
            <div style="margin-top:4px;color:#444;font-size:9px">
              Bu bölgeye giren sivil/askeri uçuşlar otomatik anomali skoru alır.
            </div>
          </div>
        `)

        dot.bindPopup(popup)
        dot.on('mouseover', function(this: L.CircleMarker) { this.openPopup() })

        exCircle.addTo(map)
        actCircle.addTo(map)
        dot.addTo(map)
        label.addTo(map)

        layersRef.current.push(exCircle, actCircle, dot, label)
      }
    } catch (e) {
      console.warn('MilitaryZoneLayer fetch hatası:', e)
    }
  }

  useEffect(() => {
    if (!map) return
    draw()
    timerRef.current = setInterval(draw, 60_000)   // Her dakika güncelle
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      layersRef.current.forEach(l => l.remove())
      layersRef.current = []
    }
  }, [map])

  return null
}
