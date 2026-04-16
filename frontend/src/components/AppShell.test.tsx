import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppShell } from './AppShell'

function renderWithRouter(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AppShell />
    </MemoryRouter>,
  )
}

describe('AppShell', () => {
  it('renders the sidebar', () => {
    renderWithRouter()
    expect(document.querySelector('.sidebar')).toBeInTheDocument()
  })

  it('renders the brand name "FPV Manager"', () => {
    renderWithRouter()
    expect(screen.getByText('FPV Manager')).toBeInTheDocument()
  })

  it('renders "Blackbox control room" heading', () => {
    renderWithRouter()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Blackbox control room')
  })

  it('renders all navigation links', () => {
    renderWithRouter()
    const nav = screen.getByRole('navigation', { name: 'Primary navigation' })
    expect(nav).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Overview' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Drones' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Compare' })).toBeInTheDocument()
  })

  it('links point to correct routes', () => {
    renderWithRouter()
    expect(screen.getByRole('link', { name: 'Overview' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: 'Drones' })).toHaveAttribute('href', '/drones')
    expect(screen.getByRole('link', { name: 'Compare' })).toHaveAttribute('href', '/compare')
  })

  it('renders topbar with flight analysis heading', () => {
    renderWithRouter()
    expect(screen.getByText('Flight analysis workspace')).toBeInTheDocument()
  })

  it('renders breadcrumbs navigation', () => {
    renderWithRouter()
    const breadcrumbs = screen.getByRole('navigation', { name: 'Breadcrumbs' })
    expect(breadcrumbs).toBeInTheDocument()
  })

  it('shows "Control Room" in breadcrumbs at root path', () => {
    renderWithRouter('/')
    expect(screen.getByText('Control Room')).toBeInTheDocument()
  })

  it('shows breadcrumb segments for nested paths', () => {
    renderWithRouter('/drones')
    const breadcrumbs = screen.getByRole('navigation', { name: 'Breadcrumbs' })
    expect(breadcrumbs).toHaveTextContent('Drones')
  })

  it('shows drone ID label for numeric segments in /drones path', () => {
    renderWithRouter('/drones/42')
    expect(screen.getByText(/Drone 42/)).toBeInTheDocument()
  })

  it('shows log ID label for numeric segments in /logs path', () => {
    renderWithRouter('/logs/99')
    expect(screen.getByText(/Log 99/)).toBeInTheDocument()
  })

  it('capitalizes breadcrumb segment labels', () => {
    renderWithRouter('/compare')
    const breadcrumbText = document.querySelector('.breadcrumbs')!.textContent
    expect(breadcrumbText).toContain('Compare')
  })

  it('renders the sidebar note about future slots', () => {
    renderWithRouter()
    expect(screen.getByText('Future slots')).toBeInTheDocument()
  })

  it('renders an Outlet (main content area)', () => {
    renderWithRouter()
    expect(document.querySelector('main.content')).toBeInTheDocument()
  })

  it('marks Overview nav link as active on root path', () => {
    renderWithRouter('/')
    const overviewLink = screen.getByRole('link', { name: 'Overview' })
    expect(overviewLink).toHaveClass('active')
  })

  it('marks Drones nav link as active on /drones path', () => {
    renderWithRouter('/drones')
    const dronesLink = screen.getByRole('link', { name: 'Drones' })
    expect(dronesLink).toHaveClass('active')
  })
})