import { Link } from 'react-router-dom'

/**
 * Render a "Route not found" page with a heading, explanatory note, and a link back to the overview.
 *
 * @returns A JSX element containing a section with the "Route not found" heading, a muted paragraph explaining the view is not present, and a link button that navigates to the root ("/").
 */
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