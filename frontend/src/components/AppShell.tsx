import { NavLink, Outlet, useLocation } from 'react-router-dom'

function Breadcrumbs() {
  const location = useLocation()
  const parts = location.pathname.split('/').filter(Boolean)

  const labels = parts.map((part, index) => {
    const href = `/${parts.slice(0, index + 1).join('/')}`
    const isNumeric = /^\d+$/.test(part)
    const label = isNumeric
      ? `${parts[index - 1] === 'logs' ? 'Log' : 'Drone'} ${part}`
      : part.replace(/-/g, ' ')

    return {
      href,
      label: label.charAt(0).toUpperCase() + label.slice(1),
    }
  })

  return (
    <nav className="breadcrumbs" aria-label="Breadcrumbs">
      <span>Control Room</span>
      {labels.map((item) => (
        <span key={item.href}>/ {item.label}</span>
      ))}
    </nav>
  )
}

const navigation = [
  { to: '/', label: 'Overview', end: true },
  { to: '/drones', label: 'Drones' },
  { to: '/compare', label: 'Compare' },
]

export function AppShell() {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand-block">
          <p className="eyebrow">FPV Manager</p>
          <h1>Blackbox control room</h1>
          <p className="brand-copy">
            Track airframes, queue logs, and inspect tune quality without leaving one workspace.
          </p>
        </div>

        <nav className="sidebar-nav" aria-label="Primary navigation">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
              to={item.to}
              end={item.end}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-note">
          <p>Future slots</p>
          <span>Settings and module management will land in Phase 7.</span>
        </div>
      </aside>

      <main className="content">
        <header className="topbar">
          <div>
            <Breadcrumbs />
            <h2>Flight analysis workspace</h2>
          </div>
        </header>
        <Outlet />
      </main>
    </div>
  )
}