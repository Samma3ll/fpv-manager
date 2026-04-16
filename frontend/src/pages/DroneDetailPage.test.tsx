import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { DroneDetailPage } from './DroneDetailPage'
import type { Drone, BlackboxLog } from '../types'

vi.mock('../lib/api', () => ({
  client: {
    getDrone: vi.fn(),
    listLogs: vi.fn(),
    updateLog: vi.fn(),
    deleteLog: vi.fn(),
    uploadLog: vi.fn(),
  },
}))

import { client } from '../lib/api'

const originalConfirm = window.confirm

const mockDrone: Drone = {
  id: 5,
  name: 'Test Quad',
  description: 'A quad for testing',
  frame_size: '5-inch',
  motor_kv: 2300,
  prop_size: '5.1x3',
  weight_g: 290,
  notes: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-15T00:00:00Z',
}

const mockLog: BlackboxLog = {
  id: 20,
  drone_id: 5,
  file_name: 'LOG00020.bbl',
  file_path: null,
  flight_date: '2024-02-10T09:00:00Z',
  duration_s: 210,
  betaflight_version: '4.4.1',
  craft_name: 'TestQuad',
  pid_roll: 44,
  pid_pitch: 46,
  pid_yaw: 58,
  notes: 'Pre-existing notes',
  tags: ['race', 'test'],
  status: 'ready',
  error_message: null,
  log_index: 0,
  created_at: '2024-02-10T09:00:00Z',
}

function renderDroneDetail(droneId = '5') {
  return render(
    <MemoryRouter initialEntries={[`/drones/${droneId}`]}>
      <Routes>
        <Route path="/drones/:droneId" element={<DroneDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('DroneDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.confirm = originalConfirm
    vi.mocked(client.getDrone).mockResolvedValue(mockDrone)
    vi.mocked(client.listLogs).mockResolvedValue({
      items: [mockLog],
      total: 1,
      skip: 0,
      limit: 10,
    })
  })

  it('renders drone name after loading', async () => {
    renderDroneDetail()
    expect(await screen.findByText('Test Quad')).toBeInTheDocument()
  })

  it('renders "Drone profile" eyebrow', async () => {
    renderDroneDetail()
    expect(await screen.findByText('Drone profile')).toBeInTheDocument()
  })

  it('renders stat cards for logs, ready, queued', async () => {
    renderDroneDetail()
    await screen.findByText('Test Quad')
    expect(screen.getAllByText('Logs').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Ready').length).toBeGreaterThan(0)
    expect(screen.getByText('Queued')).toBeInTheDocument()
  })

  it('renders drone specs', async () => {
    renderDroneDetail()
    await screen.findByText('Test Quad')
    expect(screen.getByText('5-inch')).toBeInTheDocument()
    expect(screen.getByText('2300')).toBeInTheDocument()
  })

  it('renders log table with file name', async () => {
    renderDroneDetail()
    await screen.findByText('Test Quad')
    expect(screen.getByText('LOG00020.bbl')).toBeInTheDocument()
  })

  it('renders log status badge', async () => {
    renderDroneDetail()
    await screen.findByText('Test Quad')
    // StatusBadge renders a span with class status-badge status-ready
    const badge = document.querySelector('.status-badge.status-ready')
    expect(badge).toBeInTheDocument()
    expect(badge).toHaveTextContent('Ready')
  })

  it('renders log tags', async () => {
    renderDroneDetail()
    await screen.findByText('Test Quad')
    expect(screen.getByText('race, test')).toBeInTheDocument()
  })

  it('shows empty state when no logs', async () => {
    vi.mocked(client.listLogs).mockResolvedValue({ items: [], total: 0, skip: 0, limit: 10 })
    renderDroneDetail()
    await screen.findByText('Test Quad')
    expect(screen.getByText('No logs uploaded')).toBeInTheDocument()
  })

  it('shows error when loading fails', async () => {
    vi.mocked(client.getDrone).mockRejectedValue(new Error('Drone not found'))
    renderDroneDetail()
    await waitFor(() => {
      expect(screen.getByText('Drone not found')).toBeInTheDocument()
    })
  })

  it('shows "Invalid drone id" for non-numeric droneId', () => {
    renderDroneDetail('abc')
    expect(screen.getByText('Invalid drone id.')).toBeInTheDocument()
  })

  it('renders upload section', async () => {
    renderDroneDetail()
    await screen.findByText('Test Quad')
    expect(screen.getByText('Queue new blackbox logs')).toBeInTheDocument()
  })

  it('renders link to log detail page', async () => {
    renderDroneDetail()
    await screen.findByText('Test Quad')
    const logLink = screen.getByRole('link', { name: 'LOG00020.bbl' })
    expect(logLink).toHaveAttribute('href', '/logs/20')
  })

  it('opens inline editor when Edit button is clicked', async () => {
    renderDroneDetail()
    await screen.findByText('Test Quad')
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    expect(screen.getByPlaceholderText('Notes')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('tag-one, tag-two')).toBeInTheDocument()
  })

  it('pre-fills inline editor with existing notes and tags', async () => {
    renderDroneDetail()
    await screen.findByText('Test Quad')
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    expect(screen.getByDisplayValue('Pre-existing notes')).toBeInTheDocument()
    expect(screen.getByDisplayValue('race, test')).toBeInTheDocument()
  })

  it('closes inline editor when Cancel is clicked', async () => {
    renderDroneDetail()
    await screen.findByText('Test Quad')
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByPlaceholderText('Notes')).not.toBeInTheDocument()
  })

  it('calls updateLog when inline Save is clicked', async () => {
    vi.mocked(client.updateLog).mockResolvedValue({ ...mockLog })
    renderDroneDetail()
    await screen.findByText('Test Quad')
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => {
      expect(client.updateLog).toHaveBeenCalledWith(20, expect.any(Object))
    })
  })

  it('calls deleteLog after confirm', async () => {
    vi.mocked(client.deleteLog).mockResolvedValue(undefined)
    window.confirm = vi.fn().mockReturnValue(true)
    renderDroneDetail()
    await screen.findByText('Test Quad')
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }))
    await waitFor(() => {
      expect(client.deleteLog).toHaveBeenCalledWith(20)
    })
  })

  it('does not call deleteLog when deletion cancelled', async () => {
    window.confirm = vi.fn().mockReturnValue(false)
    renderDroneDetail()
    await screen.findByText('Test Quad')
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }))
    expect(client.deleteLog).not.toHaveBeenCalled()
  })
})