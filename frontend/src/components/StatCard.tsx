interface StatCardProps {
  label: string
  value: string
  tone?: 'default' | 'accent'
}

/**
 * Renders a small statistic card showing a label and a prominent value.
 *
 * @param tone - Visual tone for the card; `'accent'` applies accent styling, `'default'` applies standard styling.
 * @returns A JSX element containing the stat card with the label in a <span> and the value in a <strong>.
 */
export function StatCard({ label, value, tone = 'default' }: StatCardProps) {
  return (
    <div className={`stat-card ${tone === 'accent' ? 'accent' : ''}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}