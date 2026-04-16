import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatCard } from './StatCard'

describe('StatCard', () => {
  it('renders label and value', () => {
    render(<StatCard label="Total drones" value="42" />)
    expect(screen.getByText('Total drones')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders value in a strong element', () => {
    render(<StatCard label="Label" value="123" />)
    const strong = screen.getByText('123').closest('strong')
    expect(strong).toBeInTheDocument()
  })

  it('applies stat-card class to root element', () => {
    const { container } = render(<StatCard label="Label" value="Value" />)
    expect(container.firstChild).toHaveClass('stat-card')
  })

  it('does not apply accent class when tone is default', () => {
    const { container } = render(<StatCard label="Label" value="Value" tone="default" />)
    expect(container.firstChild).not.toHaveClass('accent')
  })

  it('applies accent class when tone is accent', () => {
    const { container } = render(<StatCard label="Label" value="Value" tone="accent" />)
    expect(container.firstChild).toHaveClass('accent')
  })

  it('defaults to default tone when tone prop is omitted', () => {
    const { container } = render(<StatCard label="Label" value="Value" />)
    expect(container.firstChild).not.toHaveClass('accent')
  })

  it('renders loading indicator string correctly', () => {
    render(<StatCard label="Loading drones" value="..." />)
    expect(screen.getByText('...')).toBeInTheDocument()
  })

  it('renders zero value string without breaking', () => {
    render(<StatCard label="Failed logs" value="0" />)
    expect(screen.getByText('0')).toBeInTheDocument()
  })
})