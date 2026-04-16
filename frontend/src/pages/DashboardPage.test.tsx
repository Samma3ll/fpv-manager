import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { DashboardPage } from './DashboardPage'
import type { Drone, BlackboxLog } from '../types'

vi.mock('../lib/api', () => ({
  client: {
    listDrones: vi.fn(),
    listLogs: vi.fn(),
  },
}))

import { client } from '../lib/api'

const mockDrones: Drone[] = [
  {
    id: 1,
    name: 'Whoop 1',
    description: null,
    frame_size: '3-inch',
    motor_kv: 2500,
    prop_size: null,
    weight_g: 85,
    notes: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
]

const mockLogs: BlackboxLog[] = [
  {
    id: 10,
    drone_id: 1,
    file_name: 'LOG00001.bbl',
    file_path: null,
    flight_date: '2024-02-01T10:00:00Z',
    duration_s: 120,
    betaflight_version: '4.4.0',
    craft_name: 'Whoop',
    pid_roll: 45,
    pid_pitch: 47,
    pid_yaw: 60,
    notes: null,
    tags: ['test'],
    status: 'ready',
    error_message: null,
    log_index: 0,
    created_at: '2024-02-01T10:00:00Z',
  },
  {
    id: 11,
    drone_id: 1,
    file_name: 'LOG00002.bbl',
    file_path: null,
    flight_date: null,
    duration_s: null,
    betaflight_version: null,
    craft_name: null,
    pid_roll: null,
    pid_pitch: null,
    pid_yaw: null,
    notes: null,
    tags: [],
    status: 'pending',
    error_message: null,
    log_index: null,
    created_at: '2024-02-02T00:00:00Z',
  },
  {
    id: 12,
    drone_id: 1,
    file_name: 'LOG00003.bbl',
    file_path: null,
    flight_date: null,
    duration_s: null,
    betaflight_version: null,
    craft_name: null,
    pid_roll: null,
    pid_pitch: null,
    pid_yaw: null,
    notes: null,
    tags: [],
    status: 'error',
    error_message: 'Parse failed',
    log_index: null,
    created_at: '2024-02-03T00:00:00Z',
  },
]

function renderDashboard() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.mocked(client.listDrones).mockResolvedValue({
      items: mockDrones,
      total: 1,
      skip: 0,
      limit: 10,
    })
    vi.mocked(client.listLogs).mockResolvedValue({
      items: mockLogs,
      total: 3,
      skip: 0,
      limit: 100,
    })
  })

  it('shows loading indicators initially', () => {
    renderDashboard()
    const loadingTexts = screen.getAllByText('...')
    expect(loadingTexts.length).toBeGreaterThan(0)
  })

  it('renders stat cards after loading', async () => {
    renderDashboard()
    await waitFor(() => {
      expect(screen.queryByText('...')).not.toBeInTheDocument()
    })
    expect(screen.getByText('Tracked drones')).toBeInTheDocument()
    expect(screen.getByText('Ready logs')).toBeInTheDocument()
    expect(screen.getByText('Queued logs')).toBeInTheDocument()
    expect(screen.getByText('Failed logs')).toBeInTheDocument()
  })

  it('shows correct drone count after loading', async () => {
    renderDashboard()
    await waitFor(() => {
      expect(screen.queryByText('...')).not.toBeInTheDocument()
    })
    // 1 drone in mockDrones
    const cards = screen.getAllByText('1')
    expect(cards.length).toBeGreaterThan(0)
  })

  it('shows correct ready log count', async () => {
    renderDashboard()
    await waitFor(() => expect(screen.queryByText('...')).not.toBeInTheDocument())
    const readyCard = screen.getByText('Ready logs').closest('.stat-card')
    expect(readyCard).toHaveTextContent('1')
  })

  it('shows correct queued log count', async () => {
    renderDashboard()
    await waitFor(() => expect(screen.queryByText('...')).not.toBeInTheDocument())
    const queuedCard = screen.getByText('Queued logs').closest('.stat-card')
    expect(queuedCard).toHaveTextContent('1')
  })

  it('shows correct failed log count', async () => {
    renderDashboard()
    await waitFor(() => expect(screen.queryByText('...')).not.toBeInTheDocument())
    const failedCard = screen.getByText('Failed logs').closest('.stat-card')
    expect(failedCard).toHaveTextContent('1')
  })

  it('renders recent activity list with log filenames', async () => {
    renderDashboard()
    await waitFor(() => expect(screen.queryByText('...')).not.toBeInTheDocument())
    expect(screen.getByText('LOG00001.bbl')).toBeInTheDocument()
    expect(screen.getByText('LOG00002.bbl')).toBeInTheDocument()
  })

  it('renders log status in activity list', async () => {
    renderDashboard()
    await waitFor(() => expect(screen.queryByText('...')).not.toBeInTheDocument())
    expect(screen.getByText('ready')).toBeInTheDocument()
    expect(screen.getByText('pending')).toBeInTheDocument()
  })

  it('shows empty state when no logs are available', async () => {
    vi.mocked(client.listLogs).mockResolvedValue({ items: [], total: 0, skip: 0, limit: 100 })
    renderDashboard()
    await waitFor(() => expect(screen.queryByText('...')).not.toBeInTheDocument())
    expect(screen.getByText('No logs yet')).toBeInTheDocument()
  })

  it('shows error message when API fails', async () => {
    vi.mocked(client.listDrones).mockRejectedValue(new Error('Network error'))
    renderDashboard()
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })
  })

  it('renders links to log detail pages', async () => {
    renderDashboard()
    await waitFor(() => expect(screen.queryByText('...')).not.toBeInTheDocument())
    const logLink = screen.getByRole('link', { name: /LOG00001/ })
    expect(logLink).toHaveAttribute('href', '/logs/10')
  })

  it('renders hero panel with Phase 6 content', () => {
    renderDashboard()
    expect(screen.getByText('Phase 6')).toBeInTheDocument()
    expect(screen.getByText('Frontend operations are online')).toBeInTheDocument()
  })

  it('renders navigation links in hero panel', () => {
    renderDashboard()
    expect(screen.getByRole('link', { name: 'Open drones' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Compare logs' })).toBeInTheDocument()
  })
})