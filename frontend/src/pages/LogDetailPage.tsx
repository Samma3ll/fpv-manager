import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { PlotlyChart } from '../components/PlotlyChart'
import { StatusBadge } from '../components/StatusBadge'
import { StatCard } from '../components/StatCard'
import { client } from '../lib/api'
import { formatDate, formatDuration, formatNumber } from '../lib/format'
import type { AnalysesResponse, AxisMetrics, BlackboxLog, Module } from '../types'

const FALLBACK_TABS = [
  { key: 'step_response', label: 'Step Response' },
  { key: 'fft_noise', label: 'FFT Noise' },
  { key: 'gyro_spectrogram', label: 'Gyro Spectrogram' },
  { key: 'pid_error', label: 'PID Error' },
  { key: 'motor_analysis', label: 'Motors' },
  { key: 'tune_score', label: 'Summary Score' },
]

/**
 * Determines whether a value can be treated as `AxisMetrics` by checking that it is a non-null object.
 *
 * @param value - The value to test
 * @returns `true` if `value` is a non-null object and can be considered `AxisMetrics`, `false` otherwise.
 */
function isAxisMetrics(value: unknown): value is AxisMetrics {
  return Boolean(value) && typeof value === 'object'
}

/**
 * Determines which of 'roll', 'pitch', and 'yaw' keys exist in the given result object.
 *
 * @param result - Object potentially containing per-axis analysis results
 * @returns The list of axis names present from ['roll', 'pitch', 'yaw'] in that order
 */
function axisNames(result: Record<string, unknown>) {
  return ['roll', 'pitch', 'yaw'].filter((axis) => axis in result)
}

/**
 * Displays a log's metadata and available analysis results in an overview and tabbed analysis panels.
 *
 * Polls the server while the log status is `pending` or `processing`.
 *
 * @returns The React element for the log detail page.
 */
export function LogDetailPage() {
  const params = useParams()
  const logId = Number(params.logId)

  const [log, setLog] = useState<BlackboxLog | null>(null)
  const [analyses, setAnalyses] = useState<AnalysesResponse>({})
  const [modules, setModules] = useState<Module[]>([])
  const [activeTab, setActiveTab] = useState('step_response')
  const [fftAxis, setFftAxis] = useState<'roll' | 'pitch' | 'yaw'>('roll')
  const [spectroAxis, setSpectroAxis] = useState<'roll' | 'pitch' | 'yaw'>('roll')
  const [spectroFilter, setSpectroFilter] = useState<'unfiltered' | 'filtered'>('unfiltered')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Derive tabs from modules API (enabled analysis modules with a frontend_route)
  const moduleTabs = useMemo(() => {
    const dynamicTabs = modules
      .filter((m) => m.enabled && m.module_type === 'analysis' && m.frontend_route)
      .map((m) => ({ key: m.frontend_route!, label: m.display_name }))

    return dynamicTabs.length > 0 ? dynamicTabs : FALLBACK_TABS
  }, [modules])

  /**
   * Loads log metadata, associated analyses, and available modules into component state.
   *
   * @param initial - When true, toggles the component loading indicator while the request runs
   * @returns Nothing; results are applied to component state (`log`, `analyses`, `modules`, and `error`)
   */
  async function load(initial = true) {
    if (!Number.isFinite(logId)) {
      return
    }

    if (initial) {
      setLoading(true)
    }
    try {
      // Fetch log and analyses together
      const [logResponse, analysesResponse] = await Promise.all([
        client.getLog(logId),
        client.getAnalyses(logId),
      ])

      setLog(logResponse)
      setAnalyses(analysesResponse)
      setError(null)

      // Fetch modules separately with error handling to prevent blocking page render
      try {
        const modulesResponse = await client.listModules(true)
        setModules(modulesResponse.items)
      } catch (modulesError) {
        console.error('Failed to load modules:', modulesError)
        setModules([])
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load log.')
    } finally {
      if (initial) {
        setLoading(false)
      }
    }
  }

  useEffect(() => {
    void load()
  }, [logId])

  useEffect(() => {
    if (log?.status !== 'pending' && log?.status !== 'processing') {
      return undefined
    }

    const timer = window.setInterval(() => {
      void load(false)
    }, 5000)

    return () => window.clearInterval(timer)
  }, [log?.status])

  const tuneScore = analyses.tune_score?.result as Record<string, number> | undefined
  const fftResult = analyses.fft_noise?.result as Record<string, unknown> | undefined
  const activeFft = fftResult?.[fftAxis]

  const availableTabs = useMemo(() => {
    return moduleTabs.filter((tab) => analyses[tab.key] || tab.key === 'step_response' || tab.key === 'fft_noise')
  }, [analyses, moduleTabs])

  // Synchronize activeTab when availableTabs changes
  useEffect(() => {
    if (availableTabs.length > 0 && !availableTabs.some((tab) => tab.key === activeTab)) {
      setActiveTab(availableTabs[0].key)
    }
  }, [availableTabs, activeTab])

  if (!Number.isFinite(logId)) {
    return <section className="section-card"><p className="inline-error">Invalid log id.</p></section>
  }

  function renderStepResponse() {
    const result = analyses.step_response?.result
    if (!result || typeof result !== 'object') {
      return <EmptyState title="Step response unavailable" body="This log has not produced step response metrics yet." />
    }

    const axes = axisNames(result)
    return (
      <div className="analysis-grid three-up">
        {axes.map((axis) => {
          const metrics = result[axis]
          if (!isAxisMetrics(metrics)) {
            return null
          }

          return (
            <article className="analysis-card" key={axis}>
              <h4>{axis.toUpperCase()}</h4>
              {'error' in metrics || 'warning' in metrics ? (
                <p className="muted-copy">{metrics.error ?? metrics.warning}</p>
              ) : (
                <div className="mini-stats">
                  <StatCard label="Rise" value={`${formatNumber(metrics.rise_time_ms, 0)} ms`} />
                  <StatCard label="Overshoot" value={`${formatNumber(metrics.overshoot_pct, 1)} %`} />
                  <StatCard label="Settling" value={`${formatNumber(metrics.settling_time_ms, 0)} ms`} />
                  <StatCard label="Ringing" value={formatNumber(metrics.ringing, 1)} />
                </div>
              )}
            </article>
          )
        })}
      </div>
    )
  }

  function renderFftNoise() {
    if (!fftResult || typeof activeFft !== 'object' || activeFft == null) {
      return <EmptyState title="FFT noise unavailable" body="This log has not produced FFT data yet." />
    }

    const axisResult = activeFft as Record<string, unknown>
    const freqs = Array.isArray(axisResult.freqs) ? axisResult.freqs : []
    const psd = Array.isArray(axisResult.psd) ? axisResult.psd : []
    const peaks = Array.isArray(axisResult.peaks) ? axisResult.peaks : []

    return (
      <div className="stack-gap">
        <div className="axis-toggle">
          {(['roll', 'pitch', 'yaw'] as const).map((axis) => (
            <button
              className={fftAxis === axis ? 'axis-button active' : 'axis-button'}
              key={axis}
              type="button"
              onClick={() => setFftAxis(axis)}
            >
              {axis.toUpperCase()}
            </button>
          ))}
        </div>

        <div className="analysis-grid wide-chart">
          <PlotlyChart
            className="chart-surface"
            data={[
              {
                x: freqs,
                y: psd,
                type: 'scatter',
                mode: 'lines',
                line: { color: '#ffd166', width: 2 },
                name: `${fftAxis} psd`,
              },
            ]}
            layout={{
              title: `${fftAxis.toUpperCase()} PSD`,
              xaxis: { title: 'Frequency (Hz)' },
              yaxis: { title: 'Power' },
            }}
          />

          <div className="section-card inset-card">
            <div className="mini-stats">
              <StatCard label="Dominant freq" value={`${formatNumber(axisResult.dominant_frequency_hz as number, 1)} Hz`} />
              <StatCard label="Noise floor" value={formatNumber(axisResult.noise_floor as number, 4)} />
            </div>
            <div className="peak-list">
              {peaks.slice(0, 6).map((peak, index) => {
                const entry = peak as Record<string, unknown>
                return (
                  <div className="peak-item" key={index}>
                    <strong>{formatNumber(entry.frequency_hz as number, 1)} Hz</strong>
                    <span>{formatNumber(entry.power_db as number, 1)} dB</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    )
  }

  function renderGyroSpectrogram() {
    const result = analyses.gyro_spectrogram?.result as Record<string, unknown> | undefined
    if (!result || typeof result !== 'object') {
      return <EmptyState title="Gyro spectrogram unavailable" body="This log has not produced spectrogram data yet." />
    }

    const hasUnfiltered = result.has_unfiltered as boolean
    const hasFiltered = result.has_filtered as boolean
    const axisData = result[spectroAxis] as Record<string, unknown> | undefined
    if (!axisData || 'error' in axisData) {
      return <EmptyState title="Spectrogram unavailable" body={`No spectrogram data for ${spectroAxis} axis.`} />
    }

    const modeData = axisData[spectroFilter] as Record<string, unknown> | undefined
    if (!modeData || 'error' in modeData) {
      // Fall back to the other mode if this one is missing
      const alt = spectroFilter === 'unfiltered' ? 'filtered' : 'unfiltered'
      const altData = axisData[alt] as Record<string, unknown> | undefined
      if (!altData || 'error' in altData) {
        return <EmptyState title="Spectrogram unavailable" body={`No ${spectroFilter} data available.`} />
      }
      return <EmptyState title="Spectrogram unavailable" body={`No ${spectroFilter} data available. Try switching to ${alt}.`} />
    }

    const spec = modeData.spectrogram as Record<string, unknown> | undefined
    const fft = modeData.fft as Record<string, unknown> | undefined

    if (!spec || !fft) {
      return <EmptyState title="Spectrogram unavailable" body="Analysis data is incomplete (missing spectrogram or FFT)." />
    }

    const freqs = spec.freqs as number[]
    const throttlePct = (spec.throttle_pct ?? spec.time_pct) as number[]
    // Linear magnitude normalized 0-100 (like BBX Explorer)
    if (!spec.power_norm) {
      return <EmptyState title="Spectrogram unavailable" body="Normalized power data is missing from this analysis. Try re-uploading the log." />
    }
    const powerNorm = spec.power_norm as number[][]
    const zMin = (spec.zmin as number) ?? 0
    const zMax = (spec.zmax as number) ?? 100

    const fftFreqs = fft.freqs as number[]
    const fftPsd = fft.psd as number[]

    // Available filter modes for toggle
    const filterModes: ('unfiltered' | 'filtered')[] = []
    if (hasUnfiltered) filterModes.push('unfiltered')
    if (hasFiltered) filterModes.push('filtered')

    const gyroFieldLabel = spectroFilter === 'unfiltered' ? 'Unfiltered Gyro' : 'Gyro'

    return (
      <div className="stack-gap">
        {/* Controls row */}
        <div className="axis-toggle" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 0 }}>
            {(['roll', 'pitch', 'yaw'] as const).map((axis) => (
              <button
                className={spectroAxis === axis ? 'axis-button active' : 'axis-button'}
                key={axis}
                type="button"
                onClick={() => setSpectroAxis(axis)}
              >
                {axis.toUpperCase()}
              </button>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 0 }}>
            {filterModes.map((mode) => (
              <button
                className={spectroFilter === mode ? 'axis-button active' : 'axis-button'}
                key={mode}
                type="button"
                onClick={() => setSpectroFilter(mode)}
              >
                {mode === 'unfiltered' ? 'Unfiltered' : 'Filtered'}
              </button>
            ))}
          </div>
        </div>

        {/* FFT Frequency Spectrum (like Blackbox Explorer green "flame chart") */}
        <PlotlyChart
          className="chart-surface"
          data={[
            {
              x: fftFreqs,
              y: fftPsd,
              type: 'scatter',
              mode: 'lines',
              fill: 'tozeroy',
              fillcolor: 'rgba(76, 175, 80, 0.5)',
              line: { color: '#4caf50', width: 1 },
              name: `${gyroFieldLabel} [${spectroAxis}]`,
            },
          ]}
          layout={{
            title: `${gyroFieldLabel} [${spectroAxis}] — Frequency Spectrum`,
            xaxis: { title: 'Frequency (Hz)', range: [0, 500], gridcolor: '#333' },
            yaxis: { title: 'Power Spectral Density', type: 'log', gridcolor: '#333' },
            height: 350,
            showlegend: false,
            plot_bgcolor: '#1a1a1a',
            paper_bgcolor: 'transparent',
          }}
        />

        {/* Spectrogram Heatmap (BBX Explorer HSL(360,100%,L%) colorscale) */}
        <PlotlyChart
          className="chart-surface"
          data={[
            {
              z: powerNorm,
              x: freqs,
              y: throttlePct,
              type: 'heatmap',
              colorscale: [
                [0, 'hsl(0,100%,0%)'],
                [0.1, 'hsl(0,100%,10%)'],
                [0.2, 'hsl(0,100%,20%)'],
                [0.3, 'hsl(0,100%,30%)'],
                [0.4, 'hsl(0,100%,40%)'],
                [0.5, 'hsl(0,100%,50%)'],
                [0.6, 'hsl(0,100%,60%)'],
                [0.7, 'hsl(0,100%,70%)'],
                [0.8, 'hsl(0,100%,80%)'],
                [0.9, 'hsl(0,100%,90%)'],
                [1.0, 'hsl(0,100%,100%)'],
              ],
              zmin: zMin,
              zmax: zMax,
              zsmooth: 'best',
              colorbar: { title: '%' },
              hoverongaps: false,
            },
          ]}
          layout={{
            title: `${gyroFieldLabel} [${spectroAxis}] — Frequency vs Throttle`,
            xaxis: { title: 'Frequency (Hz)', range: [0, 500], gridcolor: '#333' },
            yaxis: { title: 'Throttle (%)', range: [0, 100], gridcolor: '#333' },
            height: 500,
            plot_bgcolor: '#1a1a1a',
            paper_bgcolor: 'transparent',
          }}
        />

        {/* Stats */}
        <div className="mini-stats">
          <StatCard label="Sample rate" value={`${formatNumber(result.sample_rate_hz as number, 0)} Hz`} />
          <StatCard label="Duration" value={`${formatNumber(result.duration_s as number, 1)} s`} />
        </div>
      </div>
    )
  }

  function renderPidError() {
    const result = analyses.pid_error?.result
    if (!result || typeof result !== 'object') {
      return <EmptyState title="PID error unavailable" body="This log has not produced PID error metrics yet." />
    }

    return (
      <div className="analysis-grid three-up">
        {axisNames(result).map((axis) => {
          const metrics = result[axis]
          if (!isAxisMetrics(metrics)) {
            return null
          }

          return (
            <article className="analysis-card" key={axis}>
              <h4>{axis.toUpperCase()}</h4>
              <div className="mini-stats">
                <StatCard label="RMS" value={formatNumber(metrics.rms_error, 2)} />
                <StatCard label="Max" value={formatNumber(metrics.max_error, 2)} />
                <StatCard label="MAE" value={formatNumber(metrics.mean_abs_error, 2)} />
              </div>
            </article>
          )
        })}
      </div>
    )
  }

  function renderMotors() {
    const result = analyses.motor_analysis?.result
    if (!result || typeof result !== 'object') {
      return <EmptyState title="Motor analysis unavailable" body="This log has not produced motor diagnostics yet." />
    }

    const motors = (result.motors as Record<string, Record<string, unknown>> | undefined) ?? {}
    const overall = (result.overall as Record<string, unknown> | undefined) ?? {}

    return (
      <div className="stack-gap">
        <div className="mini-stats">
          <StatCard label="Imbalance" value={`${formatNumber(overall.imbalance_pct as number, 1)} %`} />
          <StatCard label="Max deviation" value={formatNumber(overall.max_deviation as number, 2)} />
          <StatCard label="Correlation" value={formatNumber(overall.motor_correlation_mean as number, 3)} />
        </div>

        <div className="analysis-grid four-up">
          {Object.entries(motors).map(([name, metrics]) => (
            <article className="analysis-card" key={name}>
              <h4>{name.replace('_', ' ').toUpperCase()}</h4>
              <div className="mini-stats">
                <StatCard label="Average" value={formatNumber(metrics.avg_output as number, 1)} />
                <StatCard label="Range" value={formatNumber(metrics.output_range as number, 1)} />
                <StatCard label="RMS" value={formatNumber(metrics.rms_output as number, 1)} />
              </div>
            </article>
          ))}
        </div>
      </div>
    )
  }

  function renderTuneScore() {
    if (!tuneScore) {
      return <EmptyState title="Score unavailable" body="Overall tune scoring is not ready for this log yet." />
    }

    return (
      <div className="analysis-grid four-up">
        <StatCard label="Overall" value={formatNumber(tuneScore.overall_score, 1)} tone="accent" />
        <StatCard label="Roll" value={formatNumber(tuneScore.roll_score, 1)} />
        <StatCard label="Pitch" value={formatNumber(tuneScore.pitch_score, 1)} />
        <StatCard label="Yaw" value={formatNumber(tuneScore.yaw_score, 1)} />
      </div>
    )
  }

  function renderGenericPlugin() {
    const currentAnalysis = analyses[activeTab]
    if (!currentAnalysis?.result) {
      return <EmptyState title="Analysis unavailable" body={`The ${activeTab} analysis is not ready yet.`} />
    }
    return (
      <div className="section-card">
        <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {JSON.stringify(currentAnalysis.result, null, 2)}
        </pre>
      </div>
    )
  }

  return (
    <section className="page-grid">
      <section className="section-card">
        <div className="section-head">
          <div>
            <p className="eyebrow">Log overview</p>
            <h3>{loading ? 'Loading...' : log?.file_name ?? `Log ${logId}`}</h3>
          </div>
          {log ? <StatusBadge status={log.status} /> : null}
        </div>

        {error ? <p className="inline-error">{error}</p> : null}

        {log ? (
          <div className="stack-gap">
            <div className="stats-grid compact">
              <StatCard label="Flight date" value={formatDate(log.flight_date ?? log.created_at)} />
              <StatCard label="Duration" value={formatDuration(log.duration_s)} />
              <StatCard label="Craft name" value={log.craft_name ?? 'N/A'} />
              <StatCard label="Betaflight" value={log.betaflight_version ?? 'N/A'} />
            </div>
            <details className="collapsible-card" open>
              <summary>Header details</summary>
              <div className="spec-grid wide">
                <div>
                  <dt>PID Roll</dt>
                  <dd>{formatNumber(log.pid_roll)}</dd>
                </div>
                <div>
                  <dt>PID Pitch</dt>
                  <dd>{formatNumber(log.pid_pitch)}</dd>
                </div>
                <div>
                  <dt>PID Yaw</dt>
                  <dd>{formatNumber(log.pid_yaw)}</dd>
                </div>
                <div>
                  <dt>Tags</dt>
                  <dd>{log.tags.length ? log.tags.join(', ') : 'None'}</dd>
                </div>
              </div>
            </details>
          </div>
        ) : null}
      </section>

      <section className="section-card">
        <div className="tab-row">
          {availableTabs.map((tab) => (
            <button
              className={activeTab === tab.key ? 'tab-button active' : 'tab-button'}
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'step_response' ? renderStepResponse() : null}
        {activeTab === 'fft_noise' ? renderFftNoise() : null}
        {activeTab === 'gyro_spectrogram' ? renderGyroSpectrogram() : null}
        {activeTab === 'pid_error' ? renderPidError() : null}
        {activeTab === 'motor_analysis' ? renderMotors() : null}
        {activeTab === 'tune_score' ? renderTuneScore() : null}
        {activeTab !== 'step_response' &&
         activeTab !== 'fft_noise' &&
         activeTab !== 'gyro_spectrogram' &&
         activeTab !== 'pid_error' &&
         activeTab !== 'motor_analysis' &&
         activeTab !== 'tune_score'
          ? renderGenericPlugin()
          : null}
      </section>
    </section>
  )
}