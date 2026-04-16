import { useEffect, useMemo, useState } from 'react'
import { EmptyState } from '../components/EmptyState'
import { PlotlyChart } from '../components/PlotlyChart'
import { StatCard } from '../components/StatCard'
import { client } from '../lib/api'
import { formatDate, formatNumber } from '../lib/format'
import type { AnalysesResponse, BlackboxLog, Drone } from '../types'

interface ComparedLog {
  log: BlackboxLog
  analyses: AnalysesResponse
}

export function ComparePage() {
  const [drones, setDrones] = useState<Drone[]>([])
  const [logs, setLogs] = useState<BlackboxLog[]>([])
  const [selectedDroneId, setSelectedDroneId] = useState<number | null>(null)
  const [selectedLogIds, setSelectedLogIds] = useState<number[]>([])
  const [comparedLogs, setComparedLogs] = useState<ComparedLog[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function loadDrones() {
      try {
        const response = await client.listDrones()
        if (!active) {
          return
        }
        setDrones(response.items)
        setSelectedDroneId(response.items[0]?.id ?? null)
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : 'Unable to load drones.')
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void loadDrones()
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!selectedDroneId) {
      setLogs([])
      return
    }

    let active = true

    async function loadLogs() {
      try {
        const response = await client.listLogs({ droneId: selectedDroneId ?? undefined })
        if (!active) {
          return
        }
        setLogs(response.items)
        setSelectedLogIds((current) => current.filter((id) => response.items.some((log) => log.id === id)))
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : 'Unable to load logs.')
        }
      }
    }

    void loadLogs()
    return () => {
      active = false
    }
  }, [selectedDroneId])

  useEffect(() => {
    if (selectedLogIds.length === 0) {
      setComparedLogs([])
      return
    }

    let active = true

    async function loadAnalyses() {
      try {
        const next = await Promise.all(
          selectedLogIds.map(async (logId) => {
            const log = logs.find((entry) => entry.id === logId)
            if (!log) {
              return null
            }

            const analyses = await client.getAnalyses(logId)
            return { log, analyses }
          }),
        )

        if (active) {
          setComparedLogs(next.filter((item): item is ComparedLog => item !== null))
        }
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : 'Unable to compare logs.')
        }
      }
    }

    void loadAnalyses()
    return () => {
      active = false
    }
  }, [logs, selectedLogIds])

  const fftChartData = useMemo(() => {
    return comparedLogs.flatMap((entry) => {
      const fftResult = entry.analyses.fft_noise?.result as Record<string, unknown> | undefined
      const roll = fftResult?.roll as Record<string, unknown> | undefined
      if (!roll || !Array.isArray(roll.freqs) || !Array.isArray(roll.psd)) {
        return []
      }

      return [
        {
          x: roll.freqs,
          y: roll.psd,
          type: 'scatter',
          mode: 'lines',
          name: `${entry.log.file_name} roll`,
        },
      ]
    })
  }, [comparedLogs])

  return (
    <section className="page-grid">
      <section className="section-card">
        <div className="section-head">
          <div>
            <p className="eyebrow">Comparison</p>
            <h3>Compare logs from one drone</h3>
          </div>
        </div>

        {error ? <p className="inline-error">{error}</p> : null}

        {loading ? <p className="muted-copy">Loading compare workspace...</p> : null}

        {!loading && drones.length === 0 ? (
          <EmptyState title="No drones available" body="Create a drone and upload at least two logs to compare tune changes." />
        ) : (
          <div className="stack-gap">
            <label>
              <span className="field-label">Drone</span>
              <select
                value={selectedDroneId ?? ''}
                onChange={(event) => setSelectedDroneId(event.target.value ? Number(event.target.value) : null)}
              >
                {drones.map((drone) => (
                  <option key={drone.id} value={drone.id}>
                    {drone.name}
                  </option>
                ))}
              </select>
            </label>

            <div className="compare-picker">
              {logs.map((log) => (
                <label className="compare-option" key={log.id}>
                  <input
                    checked={selectedLogIds.includes(log.id)}
                    type="checkbox"
                    onChange={(event) => {
                      setSelectedLogIds((current) => {
                        if (event.target.checked) {
                          return [...current, log.id].slice(-4)
                        }
                        return current.filter((id) => id !== log.id)
                      })
                    }}
                  />
                  <div>
                    <strong>{log.file_name}</strong>
                    <span>{formatDate(log.flight_date ?? log.created_at)}</span>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}
      </section>

      {comparedLogs.length === 0 ? (
        <section className="section-card">
          <EmptyState title="Select logs to compare" body="Pick up to four logs from the same drone. The page overlays available FFT data and summarizes stored scores." />
        </section>
      ) : (
        <>
          <section className="section-card">
            <div className="section-head">
              <div>
                <p className="eyebrow">Summary</p>
                <h3>Tune score snapshot</h3>
              </div>
            </div>

            <div className="compare-summary-grid">
              {comparedLogs.map((entry) => {
                const score = entry.analyses.tune_score?.result as Record<string, number> | undefined
                return (
                  <article className="analysis-card" key={entry.log.id}>
                    <h4>{entry.log.file_name}</h4>
                    <p className="muted-copy">{formatDate(entry.log.flight_date ?? entry.log.created_at)}</p>
                    <div className="mini-stats">
                      <StatCard label="Overall" value={formatNumber(score?.overall_score)} tone="accent" />
                      <StatCard label="Roll" value={formatNumber(score?.roll_score)} />
                      <StatCard label="Pitch" value={formatNumber(score?.pitch_score)} />
                      <StatCard label="Yaw" value={formatNumber(score?.yaw_score)} />
                    </div>
                  </article>
                )
              })}
            </div>
          </section>

          <section className="section-card">
            <div className="section-head">
              <div>
                <p className="eyebrow">Overlay</p>
                <h3>FFT roll comparison</h3>
              </div>
            </div>

            {fftChartData.length === 0 ? (
              <EmptyState title="No FFT traces to overlay" body="The selected logs do not have stored FFT analysis yet." />
            ) : (
              <PlotlyChart
                data={fftChartData}
                layout={{
                  title: 'Roll PSD comparison',
                  xaxis: { title: 'Frequency (Hz)' },
                  yaxis: { title: 'Power' },
                }}
              />
            )}
          </section>
        </>
      )}
    </section>
  )
}