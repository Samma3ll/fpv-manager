import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { App } from './App'

// Mock API client to avoid actual network requests
vi.mock('./lib/api', () => ({
  client: {
    listDrones: vi.fn().mockResolvedValue({ items: [], total: 0, skip: 0, limit: 10 }),
    listLogs: vi.fn().mockResolvedValue({ items: [], total: 0, skip: 0, limit: 10 }),
    getDrone: vi.fn().mockResolvedValue(null),
    getLog: vi.fn().mockResolvedValue(null),
    getAnalyses: vi.fn().mockResolvedValue({}),
  },
}))

vi.mock('plotly.js-dist-min', () => ({
  default: {
    react: vi.fn().mockResolvedValue(undefined),
    purge: vi.fn(),
  },
}))

function renderApp(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <App />
    </MemoryRouter>,
  )
}

describe('App routing', () => {
  it('renders AppShell wrapper (sidebar) for all routes', () => {
    renderApp('/')
    expect(document.querySelector('.sidebar')).toBeInTheDocument()
  })

  it('renders DashboardPage at root path', () => {
    renderApp('/')
    expect(screen.getByText('Phase 6')).toBeInTheDocument()
  })

  it('renders NotFoundPage for unknown routes', () => {
    renderApp('/this-does-not-exist')
    expect(screen.getByText('Route not found')).toBeInTheDocument()
  })

  it('redirects /home to /', () => {
    renderApp('/home')
    // After redirect, DashboardPage content is shown
    expect(screen.getByText('Phase 6')).toBeInTheDocument()
  })

  it('renders DronesPage at /drones', async () => {
    renderApp('/drones')
    // DronesPage has the "Fleet" eyebrow label
    expect(await screen.findByText('Fleet')).toBeInTheDocument()
  })

  it('renders the navigation links in sidebar', () => {
    renderApp('/')
    expect(screen.getByRole('link', { name: 'Overview' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Drones' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Compare' })).toBeInTheDocument()
  })

  it('renders NotFoundPage content with link to return home', () => {
    renderApp('/nonexistent-route')
    expect(screen.getByRole('link', { name: 'Return to overview' })).toBeInTheDocument()
  })
})