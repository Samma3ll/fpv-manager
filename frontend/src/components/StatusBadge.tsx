import { statusLabel } from '../lib/format'
import type { LogStatus } from '../types'

interface StatusBadgeProps {
  status: LogStatus
}

/**
 * Render a styled status label as an inline `<span>`.
 *
 * @param status - The log status whose human-readable label is shown and whose value is appended to the `status-` CSS modifier class
 * @returns The JSX `<span>` element containing the status label with classes `status-badge` and `status-{status}`
 */
export function StatusBadge({ status }: StatusBadgeProps) {
  return <span className={`status-badge status-${status}`}>{statusLabel(status)}</span>
}