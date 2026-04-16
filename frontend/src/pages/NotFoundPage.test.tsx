import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { NotFoundPage } from './NotFoundPage'

function renderNotFound() {
  return render(
    <MemoryRouter>
      <NotFoundPage />
    </MemoryRouter>,
  )
}

describe('NotFoundPage', () => {
  it('renders "Route not found" heading', () => {
    renderNotFound()
    expect(screen.getByText('Route not found')).toBeInTheDocument()
  })

  it('renders descriptive message', () => {
    renderNotFound()
    expect(
      screen.getByText('This view is not part of the Phase 6 frontend yet.'),
    ).toBeInTheDocument()
  })

  it('renders a link back to overview', () => {
    renderNotFound()
    const link = screen.getByRole('link', { name: 'Return to overview' })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/')
  })

  it('link has the button-link class', () => {
    renderNotFound()
    const link = screen.getByRole('link', { name: 'Return to overview' })
    expect(link).toHaveClass('button-link')
  })

  it('renders within a section.section-card', () => {
    const { container } = renderNotFound()
    expect(container.querySelector('section.section-card')).toBeInTheDocument()
  })
})