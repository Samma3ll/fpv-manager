import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <section className="section-card">
      <h3>Route not found</h3>
      <p className="muted-copy">This view is not part of the Phase 6 frontend yet.</p>
      <Link className="button-link" to="/">
        Return to overview
      </Link>
    </section>
  )
}