import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { LogDetailPage } from './LogDetailPage'
import type { BlackboxLog, AnalysesResponse } from '../types'

vi.mock('../lib/api', () => ({
  client: {
    getLog: vi.fn(),
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

const mockLog: BlackboxLog = {
  id: 30,
  drone_id: 1,
  file_name: 'FLIGHT30.bbl',
  file_path: null,
  flight_date: '2024-03-01T08:00:00Z',
  duration_s: 300,
  betaflight_version: '4.4.2',
  craft_name: 'RacerV2',
  pid_roll: 44,
  pid_pitch: 46,
  pid_yaw: 60,
  notes: null,
  tags: ['fast', 'windy'],
  status: 'ready',
  error_message: null,
  log_index: 0,
  created_at: '2024-03-01T08:00:00Z',
}

const mockAnalyses: AnalysesResponse = {
  step_response: {
    module: 'step_response',
    result: {
      roll: {
        rise_time_ms: 25,
        overshoot_pct: 5,
        settling_time_ms: 80,
        ringing: 0.3,
        steps_analyzed: 100,
      },
      pitch: {
        rise_time_ms: 27,
        overshoot_pct: 6,
        settling_time_ms: 85,
        ringing: 0.35,
        steps_analyzed: 100,
      },
    },
    created_at: '2024-03-01T09:00:00Z',
  },
  tune_score: {
    module: 'tune_score',
    result: {
      overall_score: 87.5,
      roll_score: 88,
      pitch_score: 86,
      yaw_score: 89,
    },
    created_at: '2024-03-01T09:00:00Z',
  },
}

function renderLogDetail(logId = '30') {
  return render(
    <MemoryRouter initialEntries={[`/logs/${logId}`]}>
      <Routes>
        <Route path="/logs/:logId" element={<LogDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('LogDetailPage', () => {
  beforeEach(() => {
    vi.mocked(client.getLog).mockResolvedValue(mockLog)
    vi.mocked(client.getAnalyses).mockResolvedValue(mockAnalyses)
  })

  it('renders the log filename after loading', async () => {
    renderLogDetail()
    expect(await screen.findByText('FLIGHT30.bbl')).toBeInTheDocument()
  })

  it('renders "Log overview" eyebrow', async () => {
    renderLogDetail()
    expect(await screen.findByText('Log overview')).toBeInTheDocument()
  })

  it('renders status badge', async () => {
    renderLogDetail()
    await screen.findByText('FLIGHT30.bbl')
    expect(screen.getByText('Ready')).toBeInTheDocument()
  })

  it('renders log stat cards', async () => {
    renderLogDetail()
    await screen.findByText('FLIGHT30.bbl')
    expect(screen.getByText('Flight date')).toBeInTheDocument()
    expect(screen.getByText('Duration')).toBeInTheDocument()
    expect(screen.getByText('Craft name')).toBeInTheDocument()
    expect(screen.getByText('Betaflight')).toBeInTheDocument()
  })

  it('renders log tags', async () => {
    renderLogDetail()
    await screen.findByText('FLIGHT30.bbl')
    expect(screen.getByText('fast, windy')).toBeInTheDocument()
  })

  it('renders analysis tabs', async () => {
    renderLogDetail()
    await screen.findByText('FLIGHT30.bbl')
    expect(screen.getByRole('button', { name: 'Step Response' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'FFT Noise' })).toBeInTheDocument()
  })

  it('shows step response by default', async () => {
    renderLogDetail()
    await screen.findByText('FLIGHT30.bbl')
    // Step response shows axis metrics
    await waitFor(() => {
      expect(screen.getByText('ROLL')).toBeInTheDocument()
      expect(screen.getByText('PITCH')).toBeInTheDocument()
    })
  })

  it('switches to tune score tab when clicked', async () => {
    renderLogDetail()
    await screen.findByText('FLIGHT30.bbl')
    await userEvent.click(screen.getByRole('button', { name: 'Summary Score' }))
    expect(screen.getByText('Overall')).toBeInTheDocument()
    // Score value formatted with 1 decimal via formatNumber(87.5, 1) = '87.5'
    expect(screen.getByText('87.5')).toBeInTheDocument()
  })

  it('shows "Invalid log id." for non-numeric logId', () => {
    renderLogDetail('abc')
    expect(screen.getByText('Invalid log id.')).toBeInTheDocument()
  })

  it('shows error when loading fails', async () => {
    vi.mocked(client.getLog).mockRejectedValue(new Error('Log not found'))
    renderLogDetail()
    await waitFor(() => {
      expect(screen.getByText('Log not found')).toBeInTheDocument()
    })
  })

  it('shows step response empty state when no data', async () => {
    vi.mocked(client.getAnalyses).mockResolvedValue({})
    renderLogDetail()
    await screen.findByText('FLIGHT30.bbl')
    expect(await screen.findByText('Step response unavailable')).toBeInTheDocument()
  })

  it('renders craft name stat card value', async () => {
    renderLogDetail()
    await screen.findByText('FLIGHT30.bbl')
    expect(screen.getByText('RacerV2')).toBeInTheDocument()
  })

  it('renders betaflight version', async () => {
    renderLogDetail()
    await screen.findByText('FLIGHT30.bbl')
    expect(screen.getByText('4.4.2')).toBeInTheDocument()
  })

  it('renders PID values in header details', async () => {
    renderLogDetail()
    await screen.findByText('FLIGHT30.bbl')
    // The collapsible header-details section
    expect(screen.getByText('44.00')).toBeInTheDocument()
    expect(screen.getByText('46.00')).toBeInTheDocument()
    expect(screen.getByText('60.00')).toBeInTheDocument()
  })

  it('switches to FFT noise tab and shows empty state when no data', async () => {
    vi.mocked(client.getAnalyses).mockResolvedValue({})
    renderLogDetail()
    await screen.findByText('FLIGHT30.bbl')
    await userEvent.click(screen.getByRole('button', { name: 'FFT Noise' }))
    expect(await screen.findByText('FFT noise unavailable')).toBeInTheDocument()
  })
})