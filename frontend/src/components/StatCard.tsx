interface StatCardProps {
  label: string
  value: string
  tone?: 'default' | 'accent'
}

export function StatCard({ label, value, tone = 'default' }: StatCardProps) {
  return (
    <div className={`stat-card ${tone === 'accent' ? 'accent' : ''}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}