import type { ReactNode } from 'react'

interface EmptyStateProps {
  title: string
  body: string
  action?: ReactNode
}

/**
 * Render an empty-state UI block with a title, descriptive body text, and an optional action node.
 *
 * @param title - Heading text displayed at the top of the empty state
 * @param body - Descriptive text shown beneath the title
 * @param action - Optional React node rendered inside an action container when provided
 * @returns A React element representing the empty state UI
 */
export function EmptyState({ title, body, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      <p>{body}</p>
      {action ? <div className="empty-action">{action}</div> : null}
    </div>
  )
}