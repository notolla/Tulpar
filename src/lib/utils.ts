import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatTime(date: Date | string): string {
  const d = new Date(date)
  return d.toLocaleTimeString('tr-TR', { 
    hour: '2-digit', 
    minute: '2-digit',
    hour12: false 
  })
}

export function formatDate(date: Date | string): string {
  const d = new Date(date)
  return d.toLocaleDateString('tr-TR', { 
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
  })
}

export function formatDateTime(date: Date | string): string {
  const d = new Date(date)
  return d.toLocaleString('tr-TR', { 
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  })
}

export function getRiskLevelColor(risk: string): string {
  switch (risk.toLowerCase()) {
    case 'düşük':
    case 'low':
      return 'text-green border-green glow-green'
    case 'orta':
    case 'medium':
      return 'text-yellow border-yellow glow-yellow'
    case 'yüksek':
    case 'high':
      return 'text-orange border-orange glow-orange'
    case 'kritik':
    case 'critical':
      return 'text-red border-red glow-red'
    default:
      return 'text-muted-foreground border-border'
  }
}

export function getRiskLevelBgColor(risk: string): string {
  switch (risk.toLowerCase()) {
    case 'düşük':
    case 'low':
      return 'bg-green/10'
    case 'orta':
    case 'medium':
      return 'bg-yellow/10'
    case 'yüksek':
    case 'high':
      return 'bg-orange/10'
    case 'kritik':
    case 'critical':
      return 'bg-red/10'
    default:
      return 'bg-muted/10'
  }
}

export function getAnomalyScoreColor(score: number): string {
  if (score >= 76) return 'text-red'
  if (score >= 51) return 'text-orange'
  if (score >= 26) return 'text-yellow'
  return 'text-green'
}

export function calculateDistance(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371 // Earth's radius in kilometers
  const dLat = (lat2 - lat1) * Math.PI / 180
  const dLon = (lon2 - lon1) * Math.PI / 180
  const a = 
    Math.sin(dLat/2) * Math.sin(dLat/2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * 
    Math.sin(dLon/2) * Math.sin(dLon/2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a))
  return R * c
}

export function generateMockId(): string {
  return Math.random().toString(36).substr(2, 9)
}
