import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { ComparePage } from './pages/ComparePage'
import { DashboardPage } from './pages/DashboardPage'
import { DroneDetailPage } from './pages/DroneDetailPage'
import { DronesPage } from './pages/DronesPage'
import { LogDetailPage } from './pages/LogDetailPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { SettingsPage } from './pages/SettingsPage'

/**
 * Defines the application's client-side routing tree and layout.
 *
 * Renders a <Routes> tree wrapped by <AppShell> and registers the app's top-level routes:
 * "/" → DashboardPage, "/drones" → DronesPage, "/drones/:droneId" → DroneDetailPage,
 * "/logs/:logId" → LogDetailPage, "/compare" → ComparePage, "/home" → redirects to "/",
 * and a wildcard "*" → NotFoundPage.
 *
 * @returns The JSX element containing the <Routes> tree with <AppShell> and nested route definitions.
 */
export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/drones" element={<DronesPage />} />
        <Route path="/drones/:droneId" element={<DroneDetailPage />} />
        <Route path="/logs/:logId" element={<LogDetailPage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/home" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}