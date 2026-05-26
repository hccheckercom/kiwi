import { useEffect, useState } from 'react'
import axios from 'axios'
import type { RiskData } from '../types'
import './RiskHeatmap.css'

export default function RiskHeatmap() {
  const [data, setData] = useState<RiskData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadHeatmap()
  }, [])

  async function loadHeatmap() {
    try {
      setLoading(true)
      const response = await axios.post('http://localhost:8000/api/scan', {
        path: 'wezone-plugins',
        severity: 'ALL'
      })

      const riskData = calculateRiskScores(response.data.violations)
      setData(riskData)
      setLoading(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load heatmap')
      setLoading(false)
    }
  }

  function calculateRiskScores(violations: any[]): RiskData[] {
    const fileMap = new Map<string, RiskData>()

    violations.forEach((v: any) => {
      if (!fileMap.has(v.file)) {
        fileMap.set(v.file, {
          file: v.file,
          risk_score: 0,
          violations: 0,
          severity_breakdown: { CRITICAL: 0, HIGH: 0, SUGGEST: 0 }
        })
      }

      const data = fileMap.get(v.file)!
      data.violations++
      data.severity_breakdown[v.severity as keyof typeof data.severity_breakdown]++

      // Risk score: CRITICAL=10, HIGH=5, SUGGEST=1
      const severityWeight = v.severity === 'CRITICAL' ? 10 : v.severity === 'HIGH' ? 5 : 1
      data.risk_score += severityWeight
    })

    return Array.from(fileMap.values()).sort((a, b) => b.risk_score - a.risk_score)
  }

  function getRiskColor(score: number): string {
    if (score >= 50) return '#7f1d1d' // dark red
    if (score >= 30) return '#991b1b'
    if (score >= 20) return '#dc2626'
    if (score >= 10) return '#f59e0b' // orange
    if (score >= 5) return '#fbbf24'
    return '#3b82f6' // blue
  }

  if (loading) return <div className="loading">Loading risk heatmap...</div>
  if (error) return <div className="error">Error: {error}</div>

  return (
    <div className="risk-heatmap">
      <div className="heatmap-header">
        <h2>Risk Heatmap</h2>
        <button onClick={loadHeatmap}>Refresh</button>
      </div>

      <div className="heatmap-grid">
        {data.map((item) => (
          <div
            key={item.file}
            className="heatmap-cell"
            style={{ background: getRiskColor(item.risk_score) }}
            title={item.file}
          >
            <div className="cell-file">{item.file.split('/').pop()}</div>
            <div className="cell-score">{item.risk_score}</div>
            <div className="cell-violations">{item.violations} violations</div>
            <div className="cell-breakdown">
              {item.severity_breakdown.CRITICAL > 0 && (
                <div className="breakdown-item">
                  <span>🔴</span>
                  {item.severity_breakdown.CRITICAL}
                </div>
              )}
              {item.severity_breakdown.HIGH > 0 && (
                <div className="breakdown-item">
                  <span>🟡</span>
                  {item.severity_breakdown.HIGH}
                </div>
              )}
              {item.severity_breakdown.SUGGEST > 0 && (
                <div className="breakdown-item">
                  <span>🔵</span>
                  {item.severity_breakdown.SUGGEST}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="heatmap-legend">
        <div className="legend-item">
          <span className="legend-box" style={{ background: '#7f1d1d' }} />
          Critical (50+)
        </div>
        <div className="legend-item">
          <span className="legend-box" style={{ background: '#dc2626' }} />
          High (20-49)
        </div>
        <div className="legend-item">
          <span className="legend-box" style={{ background: '#f59e0b' }} />
          Medium (10-19)
        </div>
        <div className="legend-item">
          <span className="legend-box" style={{ background: '#3b82f6' }} />
          Low (0-9)
        </div>
      </div>
    </div>
  )
}