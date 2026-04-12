import React, { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import { apiService } from '@/services/api'

interface StrategicZoneLayerProps {
  map: L.Map
}

export const StrategicZoneLayer: React.FC<StrategicZoneLayerProps> = ({ map }) => {
  const layersRef = useRef<L.Polygon[]>([])
  const [zones, setZones] = useState<any[]>([])

  useEffect(() => {
    // Fetch strategic zones data
    const fetchZonesData = async () => {
      try {
        const data = await apiService.getStrategicZones()
        // Extract features from GeoJSON
        if (data && data.features) {
          setZones(data.features)
        } else {
          setZones([])
        }
      } catch (error) {
        console.error('Failed to fetch strategic zones data:', error)
        // Fallback to mock data
        import('@/data/strategicZones.json').then(module => {
          const mockData = module.default
          if (mockData && mockData.features) {
            setZones(mockData.features)
          } else {
            setZones([])
          }
        })
      }
    }

    fetchZonesData()
  }, [])

  useEffect(() => {
    if (!map) return

    // Clear existing layers
    layersRef.current.forEach(layer => layer.remove())
    layersRef.current = []

    // Add strategic zones
    zones.forEach((zone: any) => {
      const { properties, geometry } = zone
      const { name, importance } = properties
      const coordinates = geometry.coordinates[0] // Get first ring of polygon

      // Determine style based on importance
      let fillColor = 'rgba(0, 212, 255, 0.1)'
      let strokeColor = '#00d4ff'
      
      if (importance === 'Kritik') {
        fillColor = 'rgba(255, 0, 64, 0.2)'
        strokeColor = '#ff0040'
      } else if (importance === 'Yüksek') {
        fillColor = 'rgba(255, 107, 53, 0.15)'
        strokeColor = '#ff6b35'
      } else if (importance === 'Orta') {
        fillColor = 'rgba(255, 170, 0, 0.1)'
        strokeColor = '#ffaa00'
      }

      // Convert coordinates to Leaflet format [lat, lng]
      const latLngs = coordinates.map((coord: [number, number]) => [coord[1], coord[0]])

      // Create polygon
      const polygon = L.polygon(latLngs, {
        fillColor: fillColor,
        color: strokeColor,
        weight: 2,
        opacity: 0.8,
        fillOpacity: 0.3,
        className: 'strategic-zone'
      })

      // Create popup
      const popupContent = `
        <div style="
          background: rgba(20, 20, 30, 0.9);
          backdrop-filter: blur(10px);
          border: 1px solid ${strokeColor};
          border-radius: 8px;
          padding: 12px;
          min-width: 200px;
          color: white;
          font-family: 'Rajdhani', sans-serif;
        ">
          <h3 style="color: ${strokeColor}; font-weight: bold; margin: 0 0 8px 0;">${name}</h3>
          <div style="font-size: 12px; line-height: 1.4;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
              <span style="color: #999;">Önem Seviyesi:</span>
              <span style="color: ${strokeColor}; font-weight: bold;">${importance}</span>
            </div>
            <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.1);">
              <p style="margin: 0; font-size: 11px; color: #999;">
                Stratejik bölge - askeri öneme sahip alan
              </p>
            </div>
          </div>
        </div>
      `

      polygon.bindPopup(popupContent)

      // Add hover effect
      polygon.on('mouseover', function(this: L.Polygon) {
        this.setStyle({ fillOpacity: 0.5, weight: 3 })
      })

      polygon.on('mouseout', function(this: L.Polygon) {
        this.setStyle({ fillOpacity: 0.3, weight: 2 })
      })

      polygon.addTo(map)
      layersRef.current.push(polygon)
    })

    // Cleanup
    return () => {
      layersRef.current.forEach(layer => layer.remove())
      layersRef.current = []
    }
  }, [map, zones])

  return null
}
