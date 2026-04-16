import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ComparePage } from './ComparePage'
import type { Drone, BlackboxLog } from '../types'

vi.mock('../lib/api', () => ({
  client: {
    listDrones: vi.fn(),
    listLogs: vi.fn(),
    getAnalyses: vi.fn(),
  },
}))

vi.mock('plotly.js-dist-min', () => ({
  default: {
    react: vi.fn().mockResolvedValue(undefined),
    purge: vi.fn(),
  },
}))

import { client } from '../lib/api'

const mockDrone: Drone = {
  id: 1,
  name: 'Speed Quad',
  description: null,
  frame_size: '5-inch',
  motor_kv: 2300,
  prop_size: null,
  weight_g: null,
  notes: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-02T00:00:00Z',
}

const mockLog1: BlackboxLog = {
  id: 1,
  drone_id: 1,
  file_name: 'LOG001.bbl',
  file_path: null,
  flight_date: '2024-02-01T10:00:00Z',
  duration_s: 120,
  betaflight_version: '4.4.0',
  craft_name: null,
  pid_roll: null,
  pid_pitch: null,
  pid_yaw: null,
  notes: null,
  tags: [],
  status: 'ready',
  error_message: null,
  log_index: 0,
  created_at: '2024-02-01T10:00:00Z',
}

const mockLog2: BlackboxLog = {
  ...mockLog1,
  id: 2,
  file_name: 'LOG002.bbl',
  flight_date: '2024-02-10T10:00:00Z',
  created_at: '2024-02-10T10:00:00Z',
}

function renderCompare() {
  return render(
    <MemoryRouter>
      <ComparePage />
    </MemoryRouter>,
  )
}

describe('ComparePage', () => {
  beforeEach(() => {
    vi.mocked(client.listDrones).mockResolvedValue({
      items: [mockDrone],
      total: 1,
      skip: 0,
      limit: 10,
    })
    vi.mocked(client.listLogs).mockResolvedValue({
      items: [mockLog1, mockLog2],
      total: 2,
      skip: 0,
      limit: 10,
    })
    vi.mocked(client.getAnalyses).mockResolvedValue({})
  })

  it('renders "Compare logs from one drone" heading', async () => {
    renderCompare()
    expect(await screen.findByText('Compare logs from one drone')).toBeInTheDocument()
  })

  it('renders "Comparison" eyebrow', async () => {
    renderCompare()
    expect(await screen.findByText('Comparison')).toBeInTheDocument()
  })

  it('shows loading message initially', () => {
    renderCompare()
    expect(screen.getByText('Loading compare workspace...')).toBeInTheDocument()
  })

  it('renders drone selector after loading', async () => {
    renderCompare()
    const select = await screen.findByRole('combobox')
    expect(select).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Speed Quad' })).toBeInTheDocument()
  })

  it('renders log checkboxes for selection', async () => {
    renderCompare()
    await screen.findByText('Compare logs from one drone')
    await waitFor(() => {
      expect(screen.getByText('LOG001.bbl')).toBeInTheDocument()
      expect(screen.getByText('LOG002.bbl')).toBeInTheDocument()
    })
  })

  it('shows empty state for no drones', async () => {
    vi.mocked(client.listDrones).mockResolvedValue({ items: [], total: 0, skip: 0, limit: 10 })
    renderCompare()
    expect(await screen.findByText('No drones available')).toBeInTheDocument()
  })

  it('shows "Select logs to compare" empty state when no logs selected', async () => {
    renderCompare()
    await screen.findByText('Compare logs from one drone')
    expect(await screen.findByText('Select logs to compare')).toBeInTheDocument()
  })

  it('shows error when loading drones fails', async () => {
    vi.mocked(client.listDrones).mockRejectedValue(new Error('Network error'))
    renderCompare()
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })
  })

  it('selects a log when checkbox is clicked', async () => {
    renderCompare()
    await screen.findByText('Compare logs from one drone')
    await waitFor(() => expect(screen.getByText('LOG001.bbl')).toBeInTheDocument())

    const checkboxes = screen.getAllByRole('checkbox')
    await userEvent.click(checkboxes[0])
    expect(checkboxes[0]).toBeChecked()
  })

  it('shows comparison section after selecting logs', async () => {
    vi.mocked(client.getAnalyses).mockResolvedValue({
      tune_score: {
        module: 'tune_score',
        result: { overall_score: 75, roll_score: 70, pitch_score: 78, yaw_score: 77 },
        created_at: '2024-02-01T09:00:00Z',
      },
    })

    renderCompare()
    await screen.findByText('Compare logs from one drone')
    await waitFor(() => expect(screen.getByText('LOG001.bbl')).toBeInTheDocument())

    const checkboxes = screen.getAllByRole('checkbox')
    await userEvent.click(checkboxes[0])

    await waitFor(() => {
      expect(screen.getByText('Tune score snapshot')).toBeInTheDocument()
    })
  })

  it('deselects a log when checkbox is unchecked', async () => {
    renderCompare()
    await screen.findByText('Compare logs from one drone')
    await waitFor(() => expect(screen.getByText('LOG001.bbl')).toBeInTheDocument())

    const checkboxes = screen.getAllByRole('checkbox')
    await userEvent.click(checkboxes[0])
    expect(checkboxes[0]).toBeChecked()

    await userEvent.click(checkboxes[0])
    expect(checkboxes[0]).not.toBeChecked()
  })

  it('limits selection to 4 logs maximum', async () => {
    const manyLogs = Array.from({ length: 5 }, (_, i) => ({
      ...mockLog1,
      id: i + 1,
      file_name: `LOG${String(i + 1).padStart(3, '0')}.bbl`,
    }))
    vi.mocked(client.listLogs).mockResolvedValue({
      items: manyLogs,
      total: 5,
      skip: 0,
      limit: 10,
    })

    renderCompare()
    await screen.findByText('Compare logs from one drone')
    await waitFor(() => expect(screen.getByText('LOG001.bbl')).toBeInTheDocument())

    const checkboxes = screen.getAllByRole('checkbox')
    // Select 5 checkboxes
    for (const checkbox of checkboxes) {
      await userEvent.click(checkbox)
    }

    // Only 4 should be checked (last 4 selected due to .slice(-4))
    const checkedCount = checkboxes.filter((cb) => (cb as HTMLInputElement).checked).length
    expect(checkedCount).toBeLessThanOrEqual(4)
  })
})