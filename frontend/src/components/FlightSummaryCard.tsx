import { StatCard } from './StatCard'
import { formatNumber } from '../lib/format'

interface FlightSummaryData {
  battery: {
    min_voltage?: number
    max_voltage?: number
    sag_voltage?: number
    sag_pct?: number
    cell_count?: number
  }
  current: {
    mean_amps?: number
    max_amps?: number
    min_amps?: number
    total_charge_mah?: number
  }
  throttle_profile: {
    mean_throttle_pct?: number
    max_throttle_pct?: number
    min_throttle_pct?: number
    low_zone_pct?: number
    mid_zone_pct?: number
    high_zone_pct?: number
  }
  gps_profile: {
    has_gps?: boolean
    max_speed_kmh?: number
    mean_speed_kmh?: number
    max_altitude_m?: number
    min_altitude_m?: number
    altitude_range_m?: number
    max_climb_rate_ms?: number
    speed_vs_throttle_correlation?: number
    altitude_vs_throttle_correlation?: number
  }
  flight_duration: {
    duration_seconds?: number
    min_throttle_duration_pct?: number
  }
}

interface FlightSummarCardProps {
  data: FlightSummaryData | undefined
}

/**
 * Displays integrated flight summary analysis with battery, current, throttle, and GPS insights.
 *
 * @param data - Flight summary analysis result
 * @returns React element rendering operational insights
 */
export function FlightSummaryCard({ data }: FlightSummarCardProps) {
  if (!data) {
    return <p className="muted-copy">Flight summary data not available.</p>
  }

  const battery = data.battery || {}
  const current = data.current || {}
  const throttle = data.throttle_profile || {}
  const gps = data.gps_profile || {}
  const duration = data.flight_duration || {}

  return (
    <div className="stack-gap">
      {/* Battery & Power Section */}
      <article className="analysis-card">
        <h4>🔋 Battery & Power</h4>
        <div className="mini-stats">
          <StatCard label="Min Voltage" value={`${formatNumber(battery.min_voltage, 0)} mV`} />
          <StatCard label="Max Voltage" value={`${formatNumber(battery.max_voltage, 0)} mV`} />
          <StatCard label="Sag" value={`${formatNumber(battery.sag_pct, 1)}%`} />
          <StatCard label="Cell Count" value={`${battery.cell_count}S`} />
          <StatCard label="Avg Current" value={`${formatNumber(current.mean_amps, 1)} A`} />
          <StatCard label="Peak Current" value={`${formatNumber(current.max_amps, 1)} A`} />
          <StatCard label="Total Charge" value={`${formatNumber(current.total_charge_mah, 0)} mAh`} />
        </div>
      </article>

      {/* Flight Profile Section */}
      <article className="analysis-card">
        <h4>🎮 Flight Profile & Throttle</h4>
        <div className="mini-stats">
          <StatCard label="Flight Duration" value={`${formatNumber((duration.duration_seconds ?? 0) / 60, 1)} min`} />
          <StatCard label="Mean Throttle" value={`${formatNumber(throttle.mean_throttle_pct, 1)}%`} />
          <StatCard label="Throttle Range" value={`${formatNumber(throttle.min_throttle_pct, 0)}–${formatNumber(throttle.max_throttle_pct, 0)}%`} />
        </div>
        <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--color-border)' }}>
          <p style={{ fontSize: '0.9rem', marginBottom: '0.5rem', fontWeight: 500 }}>Time Distribution</p>
          <div className="mini-stats">
            <StatCard label="Low (0–33%)" value={`${formatNumber(throttle.low_zone_pct, 1)}%`} />
            <StatCard label="Mid (33–66%)" value={`${formatNumber(throttle.mid_zone_pct, 1)}%`} />
            <StatCard label="High (66–100%)" value={`${formatNumber(throttle.high_zone_pct, 1)}%`} />
            <StatCard label="Hover Time" value={`${formatNumber(duration.min_throttle_duration_pct, 1)}%`} />
          </div>
        </div>
      </article>

      {/* GPS & Movement Section */}
      {gps.has_gps ? (
        <article className="analysis-card">
          <h4>🛰️ GPS & Movement</h4>
          <div className="mini-stats">
            <StatCard label="Max Speed" value={`${formatNumber(gps.max_speed_kmh, 1)} km/h`} />
            <StatCard label="Avg Speed" value={`${formatNumber(gps.mean_speed_kmh, 1)} km/h`} />
            <StatCard label="Max Altitude" value={`${formatNumber(gps.max_altitude_m, 0)} m`} />
            <StatCard label="Min Altitude" value={`${formatNumber(gps.min_altitude_m, 0)} m`} />
            <StatCard label="Total Climb" value={`${formatNumber(gps.altitude_range_m, 0)} m`} />
            <StatCard label="Avg Climb Rate" value={`${formatNumber(gps.max_climb_rate_ms, 2)} m/s`} />
          </div>
          <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--color-border)' }}>
            <p style={{ fontSize: '0.9rem', marginBottom: '0.5rem', fontWeight: 500 }}>Throttle Response</p>
            <div className="mini-stats">
              <StatCard label="Speed ↔ Throttle" value={`r = ${formatNumber(gps.speed_vs_throttle_correlation, 3)}`} />
              <StatCard label="Altitude ↔ Throttle" value={`r = ${formatNumber(gps.altitude_vs_throttle_correlation, 3)}`} />
            </div>
            <p style={{ fontSize: '0.8rem', marginTop: '0.75rem', color: 'var(--color-text-muted)' }}>
              Correlations show how responsive the drone is to throttle inputs. Values close to 1 indicate strong positive
              relationship, close to -1 indicate strong negative.
            </p>
          </div>
        </article>
      ) : (
        <article className="analysis-card" style={{ opacity: 0.6 }}>
          <h4>🛰️ GPS & Movement</h4>
          <p className="muted-copy">No GPS data available in this log.</p>
        </article>
      )}
    </div>
  )
}
