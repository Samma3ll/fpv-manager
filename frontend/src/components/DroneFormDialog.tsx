import { useEffect, useState } from 'react'
import type { Drone, DroneFormValues } from '../types'

interface DroneFormDialogProps {
  open: boolean
  drone?: Drone | null
  onClose: () => void
  onSubmit: (values: DroneFormValues) => Promise<void>
}

const emptyForm: DroneFormValues = {
  name: '',
  description: '',
  frame_size: '',
  motor_kv: '',
  prop_size: '',
  weight_g: '',
  notes: '',
}

function toFormValues(drone?: Drone | null): DroneFormValues {
  if (!drone) {
    return emptyForm
  }

  return {
    name: drone.name,
    description: drone.description ?? '',
    frame_size: drone.frame_size ?? '',
    motor_kv: drone.motor_kv?.toString() ?? '',
    prop_size: drone.prop_size ?? '',
    weight_g: drone.weight_g?.toString() ?? '',
    notes: drone.notes ?? '',
  }
}

export function DroneFormDialog({ open, drone, onClose, onSubmit }: DroneFormDialogProps) {
  const [values, setValues] = useState<DroneFormValues>(emptyForm)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setValues(toFormValues(drone))
      setError(null)
    }
  }, [drone, open])

  if (!open) {
    return null
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      await onSubmit(values)
      onClose()
    } catch (submitError) {
      const message = submitError instanceof Error ? submitError.message : 'Unable to save drone.'
      setError(message)
    } finally {
      setSubmitting(false)
    }
  }

  function handleChange(
    event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) {
    const { name, value } = event.target
    setValues((current) => ({ ...current, [name]: value }))
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div className="modal-panel" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}>
        <div className="section-head">
          <div>
            <p className="eyebrow">Drone Profile</p>
            <h3>{drone ? 'Edit drone' : 'Create drone'}</h3>
          </div>
          <button className="ghost-button" type="button" onClick={onClose}>
            Close
          </button>
        </div>

        <form className="form-grid" onSubmit={handleSubmit}>
          <label>
            <span>Name</span>
            <input name="name" value={values.name} onChange={handleChange} required />
          </label>
          <label>
            <span>Frame size</span>
            <input name="frame_size" value={values.frame_size} onChange={handleChange} placeholder="5-inch" />
          </label>
          <label>
            <span>Motor KV</span>
            <input name="motor_kv" value={values.motor_kv} onChange={handleChange} inputMode="numeric" />
          </label>
          <label>
            <span>Prop size</span>
            <input name="prop_size" value={values.prop_size} onChange={handleChange} placeholder="5.1x3.6x3" />
          </label>
          <label>
            <span>Weight (g)</span>
            <input name="weight_g" value={values.weight_g} onChange={handleChange} inputMode="decimal" />
          </label>
          <label className="full-span">
            <span>Description</span>
            <textarea name="description" value={values.description} onChange={handleChange} rows={3} />
          </label>
          <label className="full-span">
            <span>Notes</span>
            <textarea name="notes" value={values.notes} onChange={handleChange} rows={4} />
          </label>

          {error ? <p className="inline-error full-span">{error}</p> : null}

          <div className="form-actions full-span">
            <button className="ghost-button" type="button" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" disabled={submitting}>
              {submitting ? 'Saving...' : drone ? 'Save changes' : 'Create drone'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}