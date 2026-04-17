import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { DroneFormDialog } from '../components/DroneFormDialog'
import { EmptyState } from '../components/EmptyState'
import { client } from '../lib/api'
import { formatShortDate } from '../lib/format'
import type { BlackboxLog, Drone, DroneFormValues } from '../types'

/**
 * Render the Drones management page that lists drones, shows per-drone log statistics, and provides create, edit, and delete actions.
 *
 * Fetches drones and recent blackbox logs on mount, computes per-drone log counts and most recent flight dates, and refreshes data after create/update/delete operations. Displays an inline error on load failure, an empty-state when no drones exist, a grid of drone cards with specs and actions, and a DroneFormDialog for creating or editing a drone.
 *
 * @returns The page's JSX element containing the fleet UI and DroneFormDialog.
 */
export function DronesPage() {
  const [drones, setDrones] = useState<Drone[]>([])
  const [logs, setLogs] = useState<BlackboxLog[]>([])
  const [loading, setLoading] = useState(true)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [selectedDrone, setSelectedDrone] = useState<Drone | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)

    try {
      const dronesResponse = await client.listDrones()

      // Fetch all logs by paginating through the entire dataset
      const allLogs: BlackboxLog[] = []
      let skip = 0
      const limit = 100

      while (true) {
        const logsResponse = await client.listLogs({ limit, skip })
        allLogs.push(...logsResponse.items)

        if (allLogs.length >= logsResponse.total || logsResponse.items.length < limit) {
          break
        }

        skip += limit
      }

      setDrones(dronesResponse.items)
      setLogs(allLogs)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load drones.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const statsByDrone = useMemo(() => {
    return logs.reduce<Record<number, { count: number; lastFlight: string | null }>>((accumulator, log) => {
      const current = accumulator[log.drone_id] ?? { count: 0, lastFlight: null }
      const candidateDate = log.flight_date ?? log.created_at

      accumulator[log.drone_id] = {
        count: current.count + 1,
        lastFlight:
          !current.lastFlight || new Date(candidateDate) > new Date(current.lastFlight)
            ? candidateDate
            : current.lastFlight,
      }

      return accumulator
    }, {})
  }, [logs])

  async function handleSubmit(values: DroneFormValues) {
    let droneId: number
    if (selectedDrone) {
      await client.updateDrone(selectedDrone.id, values)
      droneId = selectedDrone.id
    } else {
      const created = await client.createDrone(values)
      droneId = created.id
    }

    if (values.picture) {
      await client.uploadDronePicture(droneId, values.picture)
    }

    await load()
  }

  async function handleDelete(droneId: number) {
    const confirmed = window.confirm('Delete this drone and its related logs?')
    if (!confirmed) {
      return
    }

    try {
      await client.deleteDrone(droneId)
      await load()
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Failed to delete drone.')
    }
  }

  return (
    <section className="page-grid">
      <section className="section-card">
        <div className="section-head">
          <div>
            <p className="eyebrow">Fleet</p>
            <h3>Drones</h3>
          </div>
          <button
            type="button"
            onClick={() => {
              setSelectedDrone(null)
              setDialogOpen(true)
            }}
          >
            Create drone
          </button>
        </div>

        {error ? <p className="inline-error">{error}</p> : null}

        {!loading && drones.length === 0 ? (
          <EmptyState
            title="No drones configured"
            body="Create your first airframe profile to start uploading Betaflight logs."
            action={
              <button
                type="button"
                onClick={() => {
                  setSelectedDrone(null)
                  setDialogOpen(true)
                }}
              >
                Create drone
              </button>
            }
          />
        ) : (
          <div className="drone-grid">
            {drones.map((drone) => {
              const stats = statsByDrone[drone.id] ?? { count: 0, lastFlight: null }

              return (
                <article className="drone-card" key={drone.id}>
                  {drone.picture_url ? (
                    <img className="drone-card-thumb" src={drone.picture_url} alt={drone.name} />
                  ) : null}
                  <div className="drone-card-top">
                    <div>
                      <p className="eyebrow">{drone.frame_size ?? 'Unspecified frame'}</p>
                      <h4>{drone.name}</h4>
                    </div>
                    <span className="pill">{stats.count} logs</span>
                  </div>

                  <p className="drone-copy">{drone.description ?? drone.notes ?? 'No description yet.'}</p>

                  <dl className="spec-grid">
                    <div>
                      <dt>Prop</dt>
                      <dd>{drone.prop_size ?? 'N/A'}</dd>
                    </div>
                    <div>
                      <dt>KV</dt>
                      <dd>{drone.motor_kv ?? 'N/A'}</dd>
                    </div>
                    <div>
                      <dt>Weight</dt>
                      <dd>{drone.weight_g ? `${drone.weight_g}g` : 'N/A'}</dd>
                    </div>
                    <div>
                      <dt>Last flight</dt>
                      <dd>{formatShortDate(stats.lastFlight)}</dd>
                    </div>
                  </dl>

                  <div className="card-actions">
                    <Link className="button-link" to={`/drones/${drone.id}`}>
                      Open
                    </Link>
                    <button
                      className="ghost-button"
                      type="button"
                      onClick={() => {
                        setSelectedDrone(drone)
                        setDialogOpen(true)
                      }}
                    >
                      Edit
                    </button>
                    <button className="ghost-button danger" type="button" onClick={() => void handleDelete(drone.id)}>
                      Delete
                    </button>
                  </div>
                </article>
              )
            })}
          </div>
        )}
      </section>

      <DroneFormDialog
        open={dialogOpen}
        drone={selectedDrone}
        onClose={() => setDialogOpen(false)}
        onSubmit={handleSubmit}
      />
    </section>
  )
}