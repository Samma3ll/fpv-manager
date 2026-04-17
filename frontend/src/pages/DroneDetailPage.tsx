import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { StatusBadge } from '../components/StatusBadge'
import { StatCard } from '../components/StatCard'
import { client } from '../lib/api'
import { formatDate, formatDuration, formatNumber } from '../lib/format'
import type { BlackboxLog, Drone } from '../types'

interface UploadProgressItem {
  name: string
  percent: number
}

/**
 * Render the drone detail page including header, upload area, and per-flight logs.
 *
 * Loads drone metadata and associated blackbox logs (based on route `droneId`), displays
 * summary statistics, provides a dropzone and file selector for uploading `.bbl` files with
 * per-file progress, and renders a logs table that supports inline editing of notes/tags
 * and deletion of individual logs. When any log is in `pending` or `processing` status,
 * the page polls for updates every 5 seconds until those statuses clear.
 *
 * @returns The JSX element for the Drone detail page.
 */
export function DroneDetailPage() {
  const params = useParams()
  const navigate = useNavigate()
  const droneId = Number(params.droneId)

  const [drone, setDrone] = useState<Drone | null>(null)
  const [logs, setLogs] = useState<BlackboxLog[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [editLogId, setEditLogId] = useState<number | null>(null)
  const [noteDraft, setNoteDraft] = useState('')
  const [tagDraft, setTagDraft] = useState('')
  const [uploads, setUploads] = useState<UploadProgressItem[]>([])

  async function load() {
    if (!Number.isFinite(droneId)) {
      return
    }

    try {
      const [droneResponse, logsResponse] = await Promise.all([
        client.getDrone(droneId),
        client.listLogs({ droneId }),
      ])

      setDrone(droneResponse)
      setLogs(logsResponse.items)
      setError(null)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load drone details.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [droneId])

  useEffect(() => {
    const hasPending = logs.some((log) => log.status === 'pending' || log.status === 'processing')

    if (!hasPending) {
      return undefined
    }

    const timer = window.setInterval(() => {
      void load()
    }, 5000)

    return () => window.clearInterval(timer)
  }, [logs])

  const logStats = useMemo(() => {
    return {
      total: logs.length,
      ready: logs.filter((log) => log.status === 'ready').length,
      queued: logs.filter((log) => log.status === 'pending' || log.status === 'processing').length,
    }
  }, [logs])

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0 || !drone) {
      return
    }

    const selectedFiles = Array.from(files)
    setUploads(selectedFiles.map((file) => ({ name: file.name, percent: 0 })))

    try {
      for (const file of selectedFiles) {
        await client.uploadLog(drone.id, file, (percent: number) => {
          setUploads((current) =>
            current.map((item) => (item.name === file.name ? { ...item, percent } : item)),
          )
        })
      }
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Upload failed.')
    } finally {
      setUploads([])
      await load()
    }
  }

  async function handleSaveLog(logId: number) {
    try {
      await client.updateLog(logId, { notes: noteDraft, tags: tagDraft })
      setEditLogId(null)
      setNoteDraft('')
      setTagDraft('')
      await load()
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Failed to save log.')
    }
  }

  async function handleDeleteLog(logId: number) {
    const confirmed = window.confirm('Delete this log?')
    if (!confirmed) {
      return
    }

    try {
      await client.deleteLog(logId)
      await load()
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Failed to delete log.')
    }
  }

  if (!Number.isFinite(droneId)) {
    return <section className="section-card"><p className="inline-error">Invalid drone id.</p></section>
  }

  return (
    <section className="page-grid">
      <section className="section-card drone-header-card">
        <div className="section-head">
          <div>
            <p className="eyebrow">Drone profile</p>
            <h3>{loading ? 'Loading...' : drone?.name ?? `Drone ${droneId}`}</h3>
          </div>
          <button className="ghost-button" type="button" onClick={() => navigate('/drones')}>
            Back to fleet
          </button>
        </div>

        {drone ? (
          <>
            <div className="stats-grid compact">
              <StatCard label="Logs" value={logStats.total.toString()} />
              <StatCard label="Ready" value={logStats.ready.toString()} />
              <StatCard label="Queued" value={logStats.queued.toString()} />
              <StatCard label="Updated" value={formatDate(drone.updated_at)} />
            </div>

            <div className="spec-grid wide">
              <div>
                <dt>Frame</dt>
                <dd>{drone.frame_size ?? 'N/A'}</dd>
              </div>
              <div>
                <dt>KV</dt>
                <dd>{drone.motor_kv ?? 'N/A'}</dd>
              </div>
              <div>
                <dt>Prop</dt>
                <dd>{drone.prop_size ?? 'N/A'}</dd>
              </div>
              <div>
                <dt>Weight</dt>
                <dd>{drone.weight_g ? `${drone.weight_g}g` : 'N/A'}</dd>
              </div>
            </div>
            <p className="drone-copy">{drone.description ?? drone.notes ?? 'No notes yet.'}</p>
          </>
        ) : null}
      </section>

      <section className="section-card">
        <div className="section-head">
          <div>
            <p className="eyebrow">Upload</p>
            <h3>Queue new blackbox logs</h3>
          </div>
          <label className="button-link file-trigger">
            Add .bbl files
            <input
              hidden
              multiple
              accept=".bbl"
              type="file"
              onChange={(event) => {
                void handleFiles(event.target.files)
                event.currentTarget.value = ''
              }}
            />
          </label>
        </div>

        <label
          className="upload-dropzone"
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault()
            void handleFiles(event.dataTransfer.files)
          }}
        >
          <input
            hidden
            multiple
            accept=".bbl"
            type="file"
            onChange={(event) => {
              void handleFiles(event.target.files)
              event.currentTarget.value = ''
            }}
          />
          <strong>Drop BBL files here</strong>
          <span>Uploads stream directly to the backend storage endpoint and trigger worker parsing.</span>
        </label>

        {uploads.length > 0 ? (
          <div className="upload-list">
            {uploads.map((item) => (
              <div className="upload-item" key={item.name}>
                <div>
                  <strong>{item.name}</strong>
                  <span>{item.percent}%</span>
                </div>
                <div className="progress-track">
                  <div className="progress-fill" style={{ width: `${item.percent}%` }} />
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      <section className="section-card">
        <div className="section-head">
          <div>
            <p className="eyebrow">Logs</p>
            <h3>Per-flight records</h3>
          </div>
        </div>

        {error ? <p className="inline-error">{error}</p> : null}

        {!loading && logs.length === 0 ? (
          <EmptyState title="No logs uploaded" body="Upload a .bbl file to populate the drone timeline." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>File</th>
                  <th>Date</th>
                  <th>Duration</th>
                  <th>Status</th>
                  <th>PIDs</th>
                  <th>Tags</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td>
                      <Link className="text-link" to={`/logs/${log.id}`}>
                        {log.file_name}
                      </Link>
                    </td>
                    <td>{formatDate(log.flight_date ?? log.created_at)}</td>
                    <td>{formatDuration(log.duration_s)}</td>
                    <td><StatusBadge status={log.status} /></td>
                    <td>
                      R {formatNumber(log.pid_roll)} / P {formatNumber(log.pid_pitch)} / Y {formatNumber(log.pid_yaw)}
                    </td>
                    <td>{log.tags ? log.tags : 'None'}</td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="ghost-button"
                          type="button"
                          onClick={() => {
                            setEditLogId(log.id)
                            setNoteDraft(log.notes ?? '')
                            setTagDraft(log.tags ?? '')
                          }}
                        >
                          Edit
                        </button>
                        <button className="ghost-button danger" type="button" onClick={() => void handleDeleteLog(log.id)}>
                          Delete
                        </button>
                      </div>
                      {editLogId === log.id ? (
                        <div className="inline-editor">
                          <textarea value={noteDraft} onChange={(event) => setNoteDraft(event.target.value)} rows={3} placeholder="Notes" />
                          <input value={tagDraft} onChange={(event) => setTagDraft(event.target.value)} placeholder="tag-one, tag-two" />
                          <div className="row-actions">
                            <button type="button" onClick={() => void handleSaveLog(log.id)}>
                              Save
                            </button>
                            <button className="ghost-button" type="button" onClick={() => setEditLogId(null)}>
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  )
}