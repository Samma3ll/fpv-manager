import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EmptyState } from './EmptyState'

describe('EmptyState', () => {
  it('renders title and body text', () => {
    render(<EmptyState title="No logs yet" body="Create a drone first." />)
    expect(screen.getByText('No logs yet')).toBeInTheDocument()
    expect(screen.getByText('Create a drone first.')).toBeInTheDocument()
  })

  it('renders title in an h3 element', () => {
    render(<EmptyState title="My Title" body="Some body text." />)
    const heading = screen.getByRole('heading', { level: 3 })
    expect(heading).toHaveTextContent('My Title')
  })

  it('renders body in a paragraph element', () => {
    render(<EmptyState title="Title" body="Body content here." />)
    expect(screen.getByText('Body content here.')).toBeInTheDocument()
  })

  it('renders action when provided', () => {
    render(
      <EmptyState
        title="Title"
        body="Body"
        action={<button type="button">Click me</button>}
      />,
    )
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument()
  })

  it('does not render action container when action is not provided', () => {
    const { container } = render(<EmptyState title="Title" body="Body" />)
    const actionDiv = container.querySelector('.empty-action')
    expect(actionDiv).not.toBeInTheDocument()
  })

  it('renders action inside .empty-action div', () => {
    const { container } = render(
      <EmptyState
        title="Title"
        body="Body"
        action={<span>Action content</span>}
      />,
    )
    const actionDiv = container.querySelector('.empty-action')
    expect(actionDiv).toBeInTheDocument()
    expect(actionDiv).toHaveTextContent('Action content')
  })

  it('applies .empty-state class to root element', () => {
    const { container } = render(<EmptyState title="Title" body="Body" />)
    expect(container.firstChild).toHaveClass('empty-state')
  })

  it('handles empty string title and body without crashing', () => {
    render(<EmptyState title="" body="" />)
    expect(screen.getByRole('heading', { level: 3 })).toBeInTheDocument()
  })
})