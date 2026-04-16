import { statusLabel } from '../lib/format'
import type { LogStatus } from '../types'

interface StatusBadgeProps {
  status: LogStatus
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return <span className={`status-badge status-${status}`}>{statusLabel(status)}</span>
}