import React, { useCallback, useEffect, useRef, useState } from 'react'
import * as Cesium from 'cesium'
import 'cesium/Build/Cesium/Widgets/widgets.css'
import { useSitrepData } from '@/hooks/useSitrepData'
import { pointInRing } from '@/lib/pointInPolygon'
import { MilitaryHud, type HudMode } from './MilitaryHud'
const ION = import.meta.env.VITE_CESIUM_ION_TOKEN
if (ION) {
  Cesium.Ion.defaultAccessToken = ION
}

function altMeters(alt: number | undefined): number {
  const a = Number(alt) || 0
  return a
}

type GeoFeature = {
  type?: string
  properties?: Record<string, unknown>
  geometry?: Record<string, unknown>
}
type GeoFeatureCollection = { type?: string; features?: GeoFeature[] }

function sceneFilterFor(mode: HudMode): string {
  if (mode === 'nvg') {
    return 'brightness(0.85) contrast(1.15) sepia(1) hue-rotate(70deg) saturate(2)'
  }
  if (mode === 'thermal') {
    return 'contrast(1.2) saturate(0) invert(0.06) hue-rotate(175deg)'
  }
  if (mode === 'radar') {
    return 'contrast(1.15) saturate(0)'
  }
  return 'none'
}

export const CommandGlobe: React.FC = () => {
  const hostRef = useRef<HTMLDivElement>(null)
  const viewerRef = useRef<Cesium.Viewer | null>(null)
  const entityById = useRef<Map<string, Cesium.Entity>>(new Map())
  const zoneDsRef = useRef<Cesium.GeoJsonDataSource | null>(null)
  const { aircraft, vessels, source } = useSitrepData(9000)
  const [zones, setZones] = useState<GeoFeatureCollection | null>(null)
  const [hudMode, setHudMode] = useState<HudMode>('normal')
  const [coords, setCoords] = useState('—')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [alerts, setAlerts] = useState<string[]>([])
  const alertedRef = useRef<Set<string>>(new Set())

  const apiBase =
    import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

  useEffect(() => {
    fetch(`${apiBase}/api/strategic-zones`)
      .then((r) => r.json())
      .then((j) => setZones(j))
      .catch(() => setZones(null))
  }, [apiBase])

  useEffect(() => {
    if (!zones?.features?.length) return
    for (const ac of aircraft) {
      if (ac.lat == null || ac.lon == null) continue
      for (const f of zones.features) {
        const imp = (f.properties as any)?.importance || (f.properties as any)?.onemSeviyesi
        if (imp !== 'Kritik') continue
        const ring = f.geometry && (f.geometry as any).coordinates?.[0]
        if (!ring) continue
        if (pointInRing(ac.lon, ac.lat, ring)) {
          const key = `${ac.id}|${(f.properties as any)?.id || 'Z'}`
          if (!alertedRef.current.has(key)) {
            alertedRef.current.add(key)
            const zname = (f.properties as any)?.name || (f.properties as any)?.ad || 'ZONE'
            setAlerts((p) => [
              ...p,
              `RESTRICTED BREACH: ${ac.callsign || ac.id} → ${zname}`,
            ])
          }
        }
      }
    }
  }, [aircraft, zones])

  useEffect(() => {
    if (!hostRef.current) return
    const v = new Cesium.Viewer(hostRef.current, {
      animation: false,
      timeline: false,
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: true,
      navigationHelpButton: false,
    })
    v.imageryLayers.removeAll()
    v.imageryLayers.addImageryProvider(
      new Cesium.UrlTemplateImageryProvider({
        url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      }),
    )
    void (async () => {
      try {
        if (ION) {
          v.terrainProvider = await Cesium.createWorldTerrainAsync({
            requestVertexNormals: true,
          })
        } else {
          v.terrainProvider = new Cesium.EllipsoidTerrainProvider()
        }
      } catch {
        v.terrainProvider = new Cesium.EllipsoidTerrainProvider()
      }
    })()
    v.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(29, 39, 2_400_000),
    })
    const onCam = () => {
      const c = v.camera.positionCartographic
      if (!c) return
      const lon = Cesium.Math.toDegrees(c.longitude).toFixed(4)
      const lat = Cesium.Math.toDegrees(c.latitude).toFixed(4)
      const h = c.height
      setCoords(`${lat}°N ${lon}°E  ${(h / 1000).toFixed(1)} km`)
    }
    v.camera.changed.addEventListener(onCam)
    const handler = new Cesium.ScreenSpaceEventHandler(v.scene.canvas)
    handler.setInputAction((click: { position: Cesium.Cartesian2 }) => {
      const picked = v.scene.pick(click.position)
      if (picked && picked.id instanceof Cesium.Entity) {
        setSelectedId(String(picked.id))
      } else {
        setSelectedId(null)
        v.trackedEntity = undefined as never
      }
    }, Cesium.ScreenSpaceEventType.LEFT_CLICK)
    viewerRef.current = v
    return () => {
      handler.destroy()
      v.camera.changed.removeEventListener(onCam)
      v.destroy()
      viewerRef.current = null
      entityById.current.clear()
    }
  }, [])

  useEffect(() => {
    const v = viewerRef.current
    if (!v || !zones?.features?.length) return
    let cancelled = false
    void (async () => {
      try {
        if (zoneDsRef.current) {
          await v.dataSources.remove(zoneDsRef.current, true)
          zoneDsRef.current = null
        }
        if (cancelled) return
        const ds = await Cesium.GeoJsonDataSource.load(zones, {
          stroke: Cesium.Color.CYAN.withAlpha(0.85),
          fill: Cesium.Color.CYAN.withAlpha(0.1),
          strokeWidth: 2,
        })
        if (cancelled) return
        zoneDsRef.current = ds
        await v.dataSources.add(ds)
      } catch {
        /* ignore */
      }
    })()
    return () => {
      cancelled = true
      const vv = viewerRef.current
      if (zoneDsRef.current && vv) {
        void vv.dataSources.remove(zoneDsRef.current, true)
        zoneDsRef.current = null
      }
    }
  }, [zones])

  useEffect(() => {
    const v = viewerRef.current
    if (!v) return
    const keep = new Set<string>()
    const addOrUpdate = (
      id: string,
      lon: number,
      lat: number,
      h: number,
      color: Cesium.Color,
      label: string,
    ) => {
      keep.add(id)
      const pos = Cesium.Cartesian3.fromDegrees(lon, lat, h)
      let e = entityById.current.get(id)
      if (!e) {
        e = v.entities.add({
          id,
          position: pos,
          point: {
            pixelSize: id.startsWith('v:') ? 11 : 9,
            color,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 1,
          },
          label: {
            text: label,
            font: '11px monospace',
            fillColor: Cesium.Color.WHITE,
            showBackground: true,
            backgroundColor: Cesium.Color.BLACK.withAlpha(0.55),
            pixelOffset: new Cesium.Cartesian2(0, -20),
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
        })
        entityById.current.set(id, e)
      } else {
        e.position = new Cesium.ConstantPositionProperty(pos)
      }
    }
    for (const a of aircraft) {
      if (a.lon == null || a.lat == null) continue
      addOrUpdate(
        `a:${a.id}`,
        a.lon,
        a.lat,
        altMeters(a.altitude),
        Cesium.Color.CYAN,
        (a.callsign || a.id).slice(0, 10),
      )
    }
    for (const s of vessels) {
      if (s.lon == null || s.lat == null) continue
      const vid = `v:${(s as any).id || s.mmsi}`
      addOrUpdate(
        vid,
        s.lon,
        s.lat,
        8,
        Cesium.Color.ORANGE,
        ((s as any).name || (s as any).ad || vid).slice(0, 12),
      )
    }
    for (const [id, ent] of entityById.current) {
      if (!keep.has(id)) {
        v.entities.remove(ent)
        entityById.current.delete(id)
      }
    }
  }, [aircraft, vessels])

  const follow = useCallback(() => {
    const v = viewerRef.current
    if (!v || !selectedId) return
    const e = entityById.current.get(selectedId)
    if (e) v.trackedEntity = e
  }, [selectedId])

  const dismiss = useCallback((idx: number) => {
    setAlerts((a) => a.filter((_, i) => i !== idx))
  }, [])

  let detail = ''
  if (selectedId?.startsWith('a:')) {
    const id = selectedId.slice(2)
    const a = aircraft.find((x) => String(x.id) === id)
    if (a)
      detail = `SPD ${(a.speed ?? 0).toFixed(0)}  HDG ${(a.heading ?? 0).toFixed(0)}°  ALT ${(a.altitude ?? 0).toFixed(0)} m  risk=${(a as any).risk_score ?? a.anomaly_score ?? 0}`
  } else if (selectedId?.startsWith('v:')) {
    const id = selectedId.slice(2)
    const s = vessels.find((x) => String((x as any).id || x.mmsi) === id)
    if (s)
      detail = `SPD ${(s.speed ?? 0).toFixed(1)} kn  HDG ${(s.heading ?? 0).toFixed(0)}°`
  }

  const selLabel =
    selectedId && (selectedId.startsWith('a:') || selectedId.startsWith('v:'))
      ? selectedId
      : '—'

  return (
    <div className="absolute inset-0 bg-black">
      <div
        className="absolute inset-0"
        style={{ filter: sceneFilterFor(hudMode) }}
      >
        <div ref={hostRef} className="absolute inset-0 h-full w-full" />
      </div>
      <MilitaryHud
        mode={hudMode}
        onMode={setHudMode}
        coords={coords}
        alerts={alerts}
        onDismissAlert={(i) => dismiss(i)}
        onFollow={follow}
        selectedLabel={selLabel}
        detail={detail || undefined}
        linkStatus={source}
      />
    </div>
  )
}
