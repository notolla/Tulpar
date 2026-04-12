import React, { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import { apiService, Vessel } from '@/services/api'

interface VesselLayerProps {
  map: L.Map
  activeLayers?: Set<string>
}

export const VesselLayer: React.FC<VesselLayerProps> = ({ map, activeLayers }) => {
  const markersRef = useRef<L.Marker[]>([])
  const [vessels, setVessels] = useState<Vessel[]>([])

  useEffect(() => {
    // Fetch vessel data
    const fetchVesselData = async () => {
      try {
        const data = await apiService.getVessels()
        setVessels(data)
      } catch (error) {
        console.error('Failed to fetch vessel data:', error)
        // No fallback - no real marine data available
        setVessels([])
      }
    }

    fetchVesselData()

    // Refresh data every 30 seconds (AIS stream is near-realtime)
    const interval = setInterval(fetchVesselData, 30_000)
    
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (!map) return

    // Clear existing markers
    markersRef.current.forEach(marker => marker.remove())
    markersRef.current = []

    // Deniz alt-katman filtreleri
    const filtered = vessels.filter((vessel: any) => {
      if (!activeLayers) return true
      const mil = (vessel.flags ?? []).includes('MILITARY') || vessel.ship_type_code === 35
      const typeCode = vessel.ship_type_code ?? 0
      const isTankerCargo = (typeCode >= 70 && typeCode <= 89)
      const isPassenger   = (typeCode >= 60 && typeCode <= 69)

      if (activeLayers.has('deniz_askeri') && !activeLayers.has('deniz')) return mil
      if (activeLayers.has('deniz') && !activeLayers.has('deniz_askeri') && mil) return false
      if (activeLayers.has('deniz') && !activeLayers.has('deniz_kargo') && isTankerCargo) return false
      if (activeLayers.has('deniz') && !activeLayers.has('deniz_yolcu') && isPassenger) return false
      return true
    })

    // Add vessel markers
    filtered.forEach((vessel: any) => {
      // Handle Turkish field names
      const lat = vessel.lat
      const lon = vessel.lon
      const name = vessel.ad || vessel.name || 'Bilinmeyen Gemi'
      const risk_level = vessel.riskSeviyesi || vessel.risk_level || 'Düşük'
      const anomaly_score = vessel.anomaliSkoru || vessel.anomaly_score || 0
      const speed = vessel.hiz || vessel.speed || 0
      const heading = vessel.rota || vessel.heading || 0

      // Handle undefined values
      const safeSpeed = speed || 0
      const safeHeading = heading || 0
      const safeAnomalyScore = anomaly_score || 0

      // Determine color based on risk level
      let color = '#00ff88' // green - default
      
      if (risk_level === 'Kritik') {
        color = '#ff0040'
      } else if (risk_level === 'Yüksek') {
        color = '#ff6b35'
      } else if (risk_level === 'Orta') {
        color = '#ffaa00'
      }

      // Create custom vessel icon
      const vesselType   = vessel.vessel_type || vessel.tip || 'Gemi'
      const mmsi         = vessel.mmsi || vessel.id || ''
      const isLive       = vessel.source === 'aisstream' || (vessel.flags || []).includes('AIS_LIVE')
      const isMilitary   = (vessel.flags || []).includes('MILITARY')

      // Gemi gövdesi — küçük, sade siluet (18×18)
      // Askeri: eşkenar üçgen, diğer: gemi tekne şekli
      const shipPath = isMilitary
        ? `<polygon points="9,2 17,16 1,16" fill="${color}" fill-opacity=".9"/>`
        : `<path d="M9,4 L13,4 L15,8 L15,13 Q9,15 3,13 L3,8 Z" fill="${color}" fill-opacity=".9"/>
           <rect x="8" y="2" width="2" height="6" fill="${color}" fill-opacity=".7"/>`

      const vesselIcon = L.divIcon({
        html: `
          <div style="position:relative;width:18px;height:18px;filter:drop-shadow(0 0 4px ${color}90)">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              ${shipPath}
            </svg>
            ${risk_level === 'Kritik'
              ? `<span style="position:absolute;inset:-6px;border-radius:50%;border:1px solid ${color};animation:tulpar-pulse 1.2s ease-out infinite;opacity:.6"></span>`
              : ''}
          </div>`,
        className: 'vessel-marker',
        iconSize: [18, 18],
        iconAnchor: [9, 9],
      })

      // Create popup
      const popupContent = `
        <div style="
          background: rgba(20, 20, 30, 0.9);
          backdrop-filter: blur(10px);
          border: 1px solid rgba(0, 212, 255, 0.3);
          border-radius: 8px;
          padding: 12px;
          min-width: 200px;
          color: white;
          font-family: 'Rajdhani', sans-serif;
        ">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <h3 style="color: #00d4ff; font-weight: bold; margin: 0;">${name}</h3>
            <span style="
              font-size: 10px;
              font-weight: bold;
              padding: 2px 6px;
              border-radius: 4px;
              color: ${color};
              border: 1px solid ${color};
            ">
              ${risk_level}
            </span>
          </div>
          <div style="font-size: 11px; color: #666; margin-bottom: 6px;">
            ${vesselType}${mmsi ? ` · MMSI ${mmsi}` : ''}
            ${isLive ? '<span style="color:#00ff88;margin-left:4px;">● AIS CANLI</span>' : ''}
          </div>
          <div style="font-size: 12px; line-height: 1.6;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
              <span style="color: #999;">Hız:</span>
              <span>${safeSpeed.toFixed(1)} knot</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 2px;">
              <span style="color: #999;">Yön:</span>
              <span>${safeHeading}°</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
              <span style="color: #999;">Anomali Skoru:</span>
              <span style="font-weight: bold; color: ${safeAnomalyScore >= 45 ? color : 'white'};">${safeAnomalyScore}/100</span>
            </div>
          </div>
          <div style="
            margin-top: 6px;
            padding-top: 6px;
            border-top: 1px solid rgba(255,255,255,0.1);
            font-size: 11px;
            color: #999;
          ">
            ${vessel.anomaliNedeni || vessel.anomaly_reason || 'Anomali tespit edilmemiş.'}</div>
        </div>
      `

      const marker = L.marker([lat, lon], { icon: vesselIcon })
        .bindPopup(popupContent, { maxWidth: 240 })
        .addTo(map)

      // Add hover effect
      marker.on('mouseover', function(this: L.Marker) {
        this.openPopup()
      })

      markersRef.current.push(marker)
    })

    // Cleanup
    return () => {
      markersRef.current.forEach(marker => marker.remove())
      markersRef.current = []
    }
  }, [map, vessels])

  return null
}
