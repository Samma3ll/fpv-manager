import { useEffect, useRef, useState } from 'react'
import type { FormEvent, ChangeEvent } from 'react'
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
  picture: null,
}

/**
 * Convert a `Drone` (if provided) into `DroneFormValues` suitable for populating the form.
 *
 * @param drone - Optional `Drone` to convert; if omitted or `null`, returns the empty form values.
 * @returns `DroneFormValues` with each field mapped from `drone`; missing text fields become empty strings and numeric fields (`motor_kv`, `weight_g`) are converted to strings.
 */
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
    picture: null,
  }
}

/**
 * Render a modal form for creating or editing a drone profile.
 *
 * Renders form fields bound to internal state, handles input changes, and submits
 * normalized form values to the provided submit callback. The dialog can be
 * closed via the backdrop, Cancel/Close buttons, or after a successful submit.
 *
 * @param open - Whether the dialog is visible
 * @param drone - Optional drone to populate the form for editing; if omitted the form is empty for creation
 * @param onClose - Callback invoked to close the dialog
 * @param onSubmit - Callback invoked with the form values to persist; form submission will close the dialog on success and display an error message on failure
 * @returns The dialog element when `open` is true, otherwise `null`
 */
export function DroneFormDialog({ open, drone, onClose, onSubmit }: DroneFormDialogProps) {
  const [values, setValues] = useState<DroneFormValues>(emptyForm)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const firstFieldRef = useRef<HTMLInputElement>(null)
  const previousFocusRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (open) {
      setValues(toFormValues(drone))
      setError(null)
      previousFocusRef.current = document.activeElement as HTMLElement
      setTimeout(() => {
        firstFieldRef.current?.focus()
      }, 0)
    } else {
      previousFocusRef.current?.focus()
      previousFocusRef.current = null
    }
  }, [drone, open])

  useEffect(() => {
    if (!open) {
      return undefined
    }

    function handleKeydown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('keydown', handleKeydown)
    return () => {
      document.removeEventListener('keydown', handleKeydown)
    }
  }, [open, onClose])

  if (!open) {
    return null
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
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
    event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) {
    const { name, value } = event.target
    setValues((current) => ({ ...current, [name]: value }))
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null
    setValues((current) => ({ ...current, picture: file }))
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
            <input ref={firstFieldRef} name="name" value={values.name} onChange={handleChange} required />
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
          <label className="full-span">
            <span>Picture</span>
            <input type="file" accept="image/jpeg,image/png,image/gif,image/webp" onChange={handleFileChange} />
            {values.picture ? <span className="file-hint">{values.picture.name}</span> : null}
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