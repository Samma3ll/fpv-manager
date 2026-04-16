import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it('renders "Pending" for pending status', () => {
    render(<StatusBadge status="pending" />)
    expect(screen.getByText('Pending')).toBeInTheDocument()
  })

  it('renders "Processing" for processing status', () => {
    render(<StatusBadge status="processing" />)
    expect(screen.getByText('Processing')).toBeInTheDocument()
  })

  it('renders "Ready" for ready status', () => {
    render(<StatusBadge status="ready" />)
    expect(screen.getByText('Ready')).toBeInTheDocument()
  })

  it('renders "Error" for error status', () => {
    render(<StatusBadge status="error" />)
    expect(screen.getByText('Error')).toBeInTheDocument()
  })

  it('applies status-badge class', () => {
    const { container } = render(<StatusBadge status="ready" />)
    expect(container.firstChild).toHaveClass('status-badge')
  })

  it('applies status-pending class for pending', () => {
    const { container } = render(<StatusBadge status="pending" />)
    expect(container.firstChild).toHaveClass('status-pending')
  })

  it('applies status-processing class for processing', () => {
    const { container } = render(<StatusBadge status="processing" />)
    expect(container.firstChild).toHaveClass('status-processing')
  })

  it('applies status-ready class for ready', () => {
    const { container } = render(<StatusBadge status="ready" />)
    expect(container.firstChild).toHaveClass('status-ready')
  })

  it('applies status-error class for error', () => {
    const { container } = render(<StatusBadge status="error" />)
    expect(container.firstChild).toHaveClass('status-error')
  })

  it('renders as a span element', () => {
    const { container } = render(<StatusBadge status="ready" />)
    expect(container.firstChild?.nodeName).toBe('SPAN')
  })
})