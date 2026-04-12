import React from 'react'
import { Clock, TrendingUp, BarChart3, Activity } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export const BottomPanel: React.FC = () => {
  const timelineEvents = [
    {
      time: '14:22',
      type: 'hava',
      entity: 'THY4521',
      description: 'Yüksek riskli uçuş rota sapması tespit edildi',
      risk: 'Yüksek'
    },
    {
      time: '14:22',
      type: 'deniz',
      entity: 'MV MARMARA',
      description: 'AIS sinyal kesintisi gözlemlendi',
      risk: 'Yüksek'
    },
    {
      time: '14:28',
      type: 'sistem',
      entity: 'Sistem',
      description: 'Stratejik bölgede çok alanlı aktivite artışı',
      risk: 'Orta'
    },
    {
      time: '14:28',
      type: 'cok_alanli',
      entity: 'AFR666 + MV MARMARA',
      description: 'Kritik: Çakışan hava-deniz anomalisi tespit edildi',
      risk: 'Kritik'
    },
    {
      time: '14:32',
      type: 'hava',
      entity: 'UAE999',
      description: 'Ani yön değişimi ve hız artışı',
      risk: 'Yüksek'
    }
  ]

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'Kritik': return 'text-red border-red'
      case 'Yüksek': return 'text-orange border-orange'
      case 'Orta': return 'text-yellow border-yellow'
      default: return 'text-green border-green'
    }
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'hava': return '✈️'
      case 'deniz': return '🚢'
      case 'cok_alanli': return '⚠️'
      case 'sistem': return '🖥️'
      default: return '📍'
    }
  }

  return (
    <div className="h-64 bg-defense-darker border-t border-defense-border flex">
      {/* Olay Zaman Çizelgesi */}
      <div className="flex-1 border-r border-defense-border p-4">
        <Card className="glass-card h-full">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg text-glow-cyan flex items-center">
              <Clock className="w-5 h-5 mr-2" />
              Olay Zaman Çizelgesi
            </CardTitle>
          </CardHeader>
          <CardContent className="h-full overflow-y-auto">
            <div className="space-y-3">
              {timelineEvents.map((event, index) => (
                <div key={index} className="flex items-start space-x-3 text-sm">
                  <div className="flex-shrink-0 w-16 text-cyan font-mono">
                    {event.time}
                  </div>
                  <div className="flex-shrink-0 text-lg">
                    {getTypeIcon(event.type)}
                  </div>
                  <div className="flex-1">
                    <p className="text-muted-foreground">
                      <span className="font-semibold text-white">{event.entity}</span> - {event.description}
                    </p>
                  </div>
                  <div className="flex-shrink-0">
                    <span className={`text-xs font-semibold px-2 py-1 rounded border ${getRiskColor(event.risk)}`}>
                      {event.risk}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Grafikler */}
      <div className="flex-1 p-4">
        <div className="h-full grid grid-cols-2 gap-4">
          {/* Anomali Grafiği */}
          <Card className="glass-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-glow-cyan flex items-center">
                <TrendingUp className="w-4 h-4 mr-2" />
                Anomali Trendi
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-32 flex items-end justify-between space-x-1">
                {[30, 45, 60, 40, 75, 85, 60].map((height, index) => (
                  <div
                    key={index}
                    className="flex-1 bg-gradient-to-t from-cyan/20 to-cyan/80 rounded-t"
                    style={{ height: `${height}%` }}
                  ></div>
                ))}
              </div>
              <div className="flex justify-between text-xs text-muted-foreground mt-2">
                <span>08:00</span>
                <span>12:00</span>
                <span>16:00</span>
              </div>
            </CardContent>
          </Card>

          {/* Risk Dağılımı */}
          <Card className="glass-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-glow-cyan flex items-center">
                <BarChart3 className="w-4 h-4 mr-2" />
                Risk Dağılımı
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-green">Düşük</span>
                  <div className="flex-1 mx-2 bg-defense-accent/20 rounded-full h-2">
                    <div className="bg-green h-2 rounded-full" style={{ width: '20%' }}></div>
                  </div>
                  <span className="text-xs text-muted-foreground">2</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-yellow">Orta</span>
                  <div className="flex-1 mx-2 bg-defense-accent/20 rounded-full h-2">
                    <div className="bg-yellow h-2 rounded-full" style={{ width: '30%' }}></div>
                  </div>
                  <span className="text-xs text-muted-foreground">3</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-orange">Yüksek</span>
                  <div className="flex-1 mx-2 bg-defense-accent/20 rounded-full h-2">
                    <div className="bg-orange h-2 rounded-full" style={{ width: '35%' }}></div>
                  </div>
                  <span className="text-xs text-muted-foreground">4</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-red">Kritik</span>
                  <div className="flex-1 mx-2 bg-defense-accent/20 rounded-full h-2">
                    <div className="bg-red h-2 rounded-full" style={{ width: '15%' }}></div>
                  </div>
                  <span className="text-xs text-muted-foreground">2</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Aktivite Karşılaştırması */}
          <Card className="glass-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-glow-cyan flex items-center">
                <Activity className="w-4 h-4 mr-2" />
                Aktivite Karşılaştırması
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-green">Hava Trafiği</span>
                    <span className="text-green">5</span>
                  </div>
                  <div className="bg-defense-accent/20 rounded-full h-2">
                    <div className="bg-green h-2 rounded-full" style={{ width: '62%' }}></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-cyan">Deniz Trafiği</span>
                    <span className="text-cyan">5</span>
                  </div>
                  <div className="bg-defense-accent/20 rounded-full h-2">
                    <div className="bg-cyan h-2 rounded-full" style={{ width: '62%' }}></div>
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-red">Anomali</span>
                    <span className="text-red">6</span>
                  </div>
                  <div className="bg-defense-accent/20 rounded-full h-2">
                    <div className="bg-red h-2 rounded-full" style={{ width: '75%' }}></div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Bölgesel Yoğunluk */}
          <Card className="glass-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-glow-cyan flex items-center">
                <BarChart3 className="w-4 h-4 mr-2" />
                Bölgesel Uyarılar
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Ege Denizi</span>
                  <span className="text-orange">3</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">İstanbul Boğazı</span>
                  <span className="text-red">2</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Doğu Akdeniz</span>
                  <span className="text-yellow">1</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">Çanakkale</span>
                  <span className="text-green">0</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
