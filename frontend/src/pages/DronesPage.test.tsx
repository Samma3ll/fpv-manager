import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { DronesPage } from './DronesPage'
import type { Drone, BlackboxLog } from '../types'

vi.mock('../lib/api', () => ({
  client: {
    listDrones: vi.fn(),
    listLogs: vi.fn(),
    createDrone: vi.fn(),
    updateDrone: vi.fn(),
    deleteDrone: vi.fn(),
  },
}))

import { client } from '../lib/api'

const originalConfirm = window.confirm

const mockDrone: Drone = {
  id: 1,
  name: 'Racer 5',
  description: 'A fast 5-inch quad',
  frame_size: '5-inch',
  motor_kv: 2400,
  prop_size: '5.1x3.6x3',
  weight_g: 280,
  notes: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-02T00:00:00Z',
}

const mockLog: BlackboxLog = {
  id: 1,
  drone_id: 1,
  file_name: 'LOG001.bbl',
  file_path: null,
  flight_date: '2024-01-10T00:00:00Z',
  duration_s: 180,
  betaflight_version: '4.4.0',
  craft_name: 'Racer',
  pid_roll: 45,
  pid_pitch: 47,
  pid_yaw: 60,
  notes: null,
  tags: [],
  status: 'ready',
  error_message: null,
  log_index: 0,
  created_at: '2024-01-10T00:00:00Z',
}

function renderDrones() {
  return render(
    <MemoryRouter>
      <DronesPage />
    </MemoryRouter>,
  )
}

describe('DronesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    window.confirm = originalConfirm
    vi.mocked(client.listDrones).mockResolvedValue({
      items: [mockDrone],
      total: 1,
      skip: 0,
      limit: 10,
    })
    vi.mocked(client.listLogs).mockResolvedValue({
      items: [mockLog],
      total: 1,
      skip: 0,
      limit: 100,
    })
  })

  it('renders "Fleet" section heading', async () => {
    renderDrones()
    expect(await screen.findByText('Fleet')).toBeInTheDocument()
  })

  it('renders the drones heading', async () => {
    renderDrones()
    expect(await screen.findByText('Drones')).toBeInTheDocument()
  })

  it('renders a drone card with name', async () => {
    renderDrones()
    expect(await screen.findByText('Racer 5')).toBeInTheDocument()
  })

  it('renders drone card with frame size', async () => {
    renderDrones()
    expect(await screen.findByText('5-inch')).toBeInTheDocument()
  })

  it('renders drone log count', async () => {
    renderDrones()
    expect(await screen.findByText('1 logs')).toBeInTheDocument()
  })

  it('renders drone specs', async () => {
    renderDrones()
    await screen.findByText('Racer 5')
    expect(screen.getByText('2400')).toBeInTheDocument()
    expect(screen.getByText('5.1x3.6x3')).toBeInTheDocument()
    expect(screen.getByText('280g')).toBeInTheDocument()
  })

  it('renders Create drone button', async () => {
    renderDrones()
    expect(await screen.findByText('Create drone')).toBeInTheDocument()
  })

  it('opens dialog when Create drone button is clicked', async () => {
    renderDrones()
    await screen.findByText('Fleet')
    await userEvent.click(screen.getAllByText('Create drone')[0])
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('opens edit dialog when Edit button is clicked', async () => {
    renderDrones()
    await screen.findByText('Racer 5')
    await userEvent.click(screen.getByRole('button', { name: 'Edit' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Edit drone')).toBeInTheDocument()
  })

  it('shows empty state when no drones exist', async () => {
    vi.mocked(client.listDrones).mockResolvedValue({ items: [], total: 0, skip: 0, limit: 10 })
    renderDrones()
    expect(await screen.findByText('No drones configured')).toBeInTheDocument()
  })

  it('shows error when API fails', async () => {
    vi.mocked(client.listDrones).mockRejectedValue(new Error('Failed to fetch'))
    renderDrones()
    await waitFor(() => {
      expect(screen.getByText('Failed to fetch')).toBeInTheDocument()
    })
  })

  it('renders Open link to drone detail page', async () => {
    renderDrones()
    await screen.findByText('Racer 5')
    const openLink = screen.getByRole('link', { name: 'Open' })
    expect(openLink).toHaveAttribute('href', '/drones/1')
  })

  it('calls deleteDrone after confirming deletion', async () => {
    vi.mocked(client.deleteDrone).mockResolvedValue(undefined)
    window.confirm = vi.fn().mockReturnValue(true)

    renderDrones()
    await screen.findByText('Racer 5')
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }))

    await waitFor(() => {
      expect(client.deleteDrone).toHaveBeenCalledWith(1)
    })
  })

  it('does not call deleteDrone when deletion is cancelled', async () => {
    window.confirm = vi.fn().mockReturnValue(false)

    renderDrones()
    await screen.findByText('Racer 5')
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }))

    expect(client.deleteDrone).not.toHaveBeenCalled()
  })

  it('shows log stats computed from logs', async () => {
    renderDrones()
    await screen.findByText('Racer 5')
    // Log count appears as "1 logs" pill
    expect(screen.getByText('1 logs')).toBeInTheDocument()
  })

  it('calls createDrone when form is submitted for new drone', async () => {
    vi.mocked(client.createDrone).mockResolvedValue({ ...mockDrone, id: 2, name: 'New Drone' })
    renderDrones()
    await screen.findByText('Fleet')

    // Click Create drone header button (first one in page header)
    await userEvent.click(screen.getAllByRole('button', { name: 'Create drone' })[0])

    // Fill in name field using the dialog form
    const { container } = { container: document.body }
    const nameInput = container.querySelector('.modal-panel input[name="name"]')!
    await userEvent.type(nameInput, 'New Drone')

    // Submit form - click the submit type button inside the modal
    const submitButton = container.querySelector('.modal-panel button[type="submit"]')!
    await userEvent.click(submitButton)

    await waitFor(() => {
      expect(client.createDrone).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'New Drone' }),
      )
    })
  })
})