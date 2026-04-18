import { useEffect, useState } from 'react'
import { client } from '../lib/api'
import type { Module } from '../types'

export function SettingsPage() {
  const [modules, setModules] = useState<Module[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [toggling, setToggling] = useState<number | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const response = await client.listModules()
      setModules(response.items)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Unable to load modules.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  async function handleToggle(mod: Module) {
    setToggling(mod.id)
    try {
      await client.toggleModule(mod.id, !mod.enabled)
      setModules((prev) =>
        prev.map((m) => (m.id === mod.id ? { ...m, enabled: !m.enabled } : m)),
      )
    } catch (toggleError) {
      setError(toggleError instanceof Error ? toggleError.message : 'Failed to update module.')
    } finally {
      setToggling(null)
    }
  }

  const analysisModules = modules.filter((m) => m.module_type === 'analysis')
  const otherModules = modules.filter((m) => m.module_type !== 'analysis')

  if (loading) {
    return (
      <section className="page-grid">
        <section className="section-card">
          <p className="muted-copy">Loading modules…</p>
        </section>
      </section>
    )
  }

  return (
    <section className="page-grid">
      <section className="section-card">
        <div className="section-head">
          <div>
            <p className="eyebrow">Settings</p>
            <h3>Modules &amp; Plugins</h3>
          </div>
        </div>
        <p className="muted-copy">
          Enable or disable analysis modules and future plugins. Disabled analysis modules
          will be skipped when processing new logs.
        </p>
        {error ? <p className="inline-error">{error}</p> : null}
      </section>

      {analysisModules.length > 0 ? (
        <section className="section-card">
          <div className="section-head">
            <h3>Analysis modules</h3>
          </div>
          <div className="module-list">
            {analysisModules.map((mod) => (
              <div className="module-row" key={mod.id}>
                <div className="module-info">
                  <strong>{mod.display_name}</strong>
                  <span className="muted-copy">{mod.description}</span>
                </div>
                <button
                  className={mod.enabled ? 'toggle-button on' : 'toggle-button off'}
                  type="button"
                  disabled={toggling === mod.id}
                  onClick={() => handleToggle(mod)}
                  aria-label={`${mod.enabled ? 'Disable' : 'Enable'} ${mod.display_name}`}
                >
                  <span className="toggle-knob" />
                </button>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {otherModules.length > 0 ? (
        <section className="section-card">
          <div className="section-head">
            <h3>Plugins</h3>
          </div>
          <div className="module-list">
            {otherModules.map((mod) => (
              <div className="module-row" key={mod.id}>
                <div className="module-info">
                  <strong>{mod.display_name}</strong>
                  <span className="muted-copy">{mod.description}</span>
                  <span className="pill" style={{ justifySelf: 'start' }}>{mod.module_type}</span>
                </div>
                <button
                  className={mod.enabled ? 'toggle-button on' : 'toggle-button off'}
                  type="button"
                  disabled={toggling === mod.id}
                  onClick={() => handleToggle(mod)}
                  aria-label={`${mod.enabled ? 'Disable' : 'Enable'} ${mod.display_name}`}
                >
                  <span className="toggle-knob" />
                </button>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </section>
  )
}
