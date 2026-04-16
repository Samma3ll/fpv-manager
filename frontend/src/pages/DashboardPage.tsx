import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { StatCard } from '../components/StatCard'
import { client } from '../lib/api'
import { formatShortDate } from '../lib/format'
import type { BlackboxLog, Drone } from '../types'

/**
 * Dashboard page that loads and displays tracked drones and recent logs.
 *
 * Fetches drones and up to 100 logs when mounted, manages loading and error state, and renders stats (tracked drones, ready/queued/failed logs), navigation actions, and a recent-activity list showing up to 6 recent logs.
 *
 * @returns The dashboard page's JSX element containing stats, actions, and recent activity
 */
export function DashboardPage() {
  const [drones, setDrones] = useState<Drone[]>([])
  const [logs, setLogs] = useState<BlackboxLog[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    async function load() {
      setLoading(true)
      setError(null)

      try {
        const [dronesResponse, logsResponse] = await Promise.all([
          client.listDrones(),
          client.listLogs({ limit: 100 }),
        ])

        if (!active) {
          return
        }

        setDrones(dronesResponse.items)
        setLogs(logsResponse.items)
      } catch (loadError) {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : 'Unable to load dashboard.')
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }

    void load()

    return () => {
      active = false
    }
  }, [])

  const readyLogs = logs.filter((log) => log.status === 'ready').length
  const queuedLogs = logs.filter((log) => log.status === 'pending' || log.status === 'processing').length
  const errorLogs = logs.filter((log) => log.status === 'error').length
  const recentLogs = [...logs].slice(0, 6)

  return (
    <section className="page-grid">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Phase 6</p>
          <h3>Frontend operations are online</h3>
          <p>
            The UI now covers route navigation, drone management, log uploads, status polling, and analysis inspection against the existing FastAPI endpoints.
          </p>
        </div>
        <div className="hero-actions">
          <Link className="button-link" to="/drones">
            Open drones
          </Link>
          <Link className="ghost-button button-link" to="/compare">
            Compare logs
          </Link>
        </div>
      </section>

      <section className="stats-grid">
        <StatCard label="Tracked drones" value={loading ? '...' : drones.length.toString()} tone="accent" />
        <StatCard label="Ready logs" value={loading ? '...' : readyLogs.toString()} />
        <StatCard label="Queued logs" value={loading ? '...' : queuedLogs.toString()} />
        <StatCard label="Failed logs" value={loading ? '...' : errorLogs.toString()} />
      </section>

      <section className="section-card">
        <div className="section-head">
          <div>
            <p className="eyebrow">Recent Activity</p>
            <h3>Latest uploaded logs</h3>
          </div>
        </div>

        {error ? <p className="inline-error">{error}</p> : null}

        {!loading && recentLogs.length === 0 ? (
          <EmptyState
            title="No logs yet"
            body="Create a drone first, then upload a .bbl file to start analysis."
            action={<Link className="button-link" to="/drones">Go to drones</Link>}
          />
        ) : (
          <div className="activity-list">
            {recentLogs.map((log) => (
              <Link className="activity-item" key={log.id} to={`/logs/${log.id}`}>
                <div>
                  <strong>{log.file_name}</strong>
                  <span>{formatShortDate(log.flight_date ?? log.created_at)}</span>
                </div>
                <small>{log.status}</small>
              </Link>
            ))}
          </div>
        )}
      </section>
    </section>
  )
}