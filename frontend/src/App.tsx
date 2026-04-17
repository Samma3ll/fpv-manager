import { FormEvent, useEffect, useMemo, useState } from 'react'

type Drone = {
  id: number
  name: string
  description?: string | null
  frame_size?: string | null
  motor_kv?: number | null
  prop_size?: string | null
  weight_g?: number | null
  notes?: string | null
  picture_url?: string | null
}

type DroneListResponse = {
  items: Drone[]
  total: number
  skip: number
  limit: number
}

type DroneFormState = {
  name: string
  description: string
  frame_size: string
  motor_kv: string
  prop_size: string
  weight_g: string
  notes: string
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const initialForm: DroneFormState = {
  name: '',
  description: '',
  frame_size: '',
  motor_kv: '',
  prop_size: '',
  weight_g: '',
  notes: '',
}

export function App() {
  const [drones, setDrones] = useState<Drone[]>([])
  const [form, setForm] = useState<DroneFormState>(initialForm)
  const [pictureFile, setPictureFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sortedDrones = useMemo(
    () => [...drones].sort((a, b) => b.id - a.id),
    [drones],
  )

  const loadDrones = async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await fetch(`${API_BASE}/api/v1/drones?skip=0&limit=100`)
      if (!response.ok) {
        throw new Error(`Failed to fetch drones (${response.status})`)
      }
      const data: DroneListResponse = await response.json()
      setDrones(data.items)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch drones'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadDrones()
  }, [])

  const buildPictureSrc = (drone: Drone): string | null => {
    if (!drone.picture_url) {
      return null
    }
    if (drone.picture_url.startsWith('http://') || drone.picture_url.startsWith('https://')) {
      return drone.picture_url
    }
    return `${API_BASE}${drone.picture_url}`
  }

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      const payload: Record<string, string | number> = {
        name: form.name.trim(),
      }

      if (form.description.trim()) payload.description = form.description.trim()
      if (form.frame_size.trim()) payload.frame_size = form.frame_size.trim()
      if (form.prop_size.trim()) payload.prop_size = form.prop_size.trim()
      if (form.notes.trim()) payload.notes = form.notes.trim()

      if (form.motor_kv.trim()) {
        payload.motor_kv = Number(form.motor_kv)
      }
      if (form.weight_g.trim()) {
        payload.weight_g = Number(form.weight_g)
      }

      const createResponse = await fetch(`${API_BASE}/api/v1/drones`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      })

      if (!createResponse.ok) {
        throw new Error(`Failed to create drone (${createResponse.status})`)
      }

      const createdDrone: Drone = await createResponse.json()

      if (pictureFile) {
        try {
          const pictureData = new FormData()
          pictureData.append('file', pictureFile)

          const uploadResponse = await fetch(
            `${API_BASE}/api/v1/drones/${createdDrone.id}/picture`,
            {
              method: 'POST',
              body: pictureData,
            },
          )

          if (!uploadResponse.ok) {
            setError(`Drone created, but picture upload failed (${uploadResponse.status})`)
          }
        } catch (uploadErr) {
          const message = uploadErr instanceof Error ? uploadErr.message : 'Picture upload failed'
          setError(`Drone created, but ${message}`)
        }
      }

      setForm(initialForm)
      setPictureFile(null)
      await loadDrones()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create drone'
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="app">
      <h1>FPV Manager</h1>
      <p className="subtitle">Manage drones and their pictures</p>

      <section className="panel">
        <h2>Add Drone</h2>
        <form className="drone-form" onSubmit={onSubmit}>
          <label>
            Name *
            <input
              required
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              placeholder="My 5-inch quad"
            />
          </label>
          <label>
            Description
            <input
              value={form.description}
              onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
            />
          </label>
          <label>
            Frame size
            <input
              value={form.frame_size}
              onChange={(event) => setForm((prev) => ({ ...prev, frame_size: event.target.value }))}
            />
          </label>
          <label>
            Motor KV
            <input
              type="number"
              min={100}
              max={10000}
              value={form.motor_kv}
              onChange={(event) => setForm((prev) => ({ ...prev, motor_kv: event.target.value }))}
            />
          </label>
          <label>
            Prop size
            <input
              value={form.prop_size}
              onChange={(event) => setForm((prev) => ({ ...prev, prop_size: event.target.value }))}
            />
          </label>
          <label>
            Weight (g)
            <input
              type="number"
              min={0}
              step="0.1"
              value={form.weight_g}
              onChange={(event) => setForm((prev) => ({ ...prev, weight_g: event.target.value }))}
            />
          </label>
          <label>
            Notes
            <textarea
              value={form.notes}
              onChange={(event) => setForm((prev) => ({ ...prev, notes: event.target.value }))}
            />
          </label>
          <label>
            Picture
            <input
              type="file"
              accept="image/png,image/jpeg,image/gif,image/webp"
              onChange={(event) => {
                const selected = event.target.files?.[0] ?? null
                setPictureFile(selected)
              }}
            />
          </label>
          <button type="submit" disabled={submitting}>
            {submitting ? 'Saving...' : 'Add Drone'}
          </button>
        </form>
      </section>

      <section className="panel">
        <h2>Drones</h2>
        {loading && <p>Loading drones...</p>}
        {error && <p className="error">{error}</p>}
        {!loading && sortedDrones.length === 0 && <p>No drones yet.</p>}
        <div className="drone-grid">
          {sortedDrones.map((drone) => {
            const pictureSrc = buildPictureSrc(drone)
            return (
              <article className="drone-card" key={drone.id}>
                {pictureSrc ? (
                  <img className="drone-image" src={pictureSrc} alt={`${drone.name} picture`} />
                ) : (
                  <div className="drone-image placeholder">No picture</div>
                )}
                <h3>{drone.name}</h3>
                {drone.description && <p>{drone.description}</p>}
                <ul>
                  {drone.frame_size && <li>Frame: {drone.frame_size}</li>}
                  {drone.prop_size && <li>Props: {drone.prop_size}</li>}
                  {drone.motor_kv != null && <li>Motor KV: {drone.motor_kv}</li>}
                  {drone.weight_g != null && <li>Weight: {drone.weight_g}g</li>}
                </ul>
                {drone.notes && <p className="notes">{drone.notes}</p>}
              </article>
            )
          })}
        </div>
      </section>
    </div>
  )
}