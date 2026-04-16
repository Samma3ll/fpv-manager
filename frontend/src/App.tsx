import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { ComparePage } from './pages/ComparePage'
import { DashboardPage } from './pages/DashboardPage'
import { DroneDetailPage } from './pages/DroneDetailPage'
import { DronesPage } from './pages/DronesPage'
import { LogDetailPage } from './pages/LogDetailPage'
import { NotFoundPage } from './pages/NotFoundPage'

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/drones" element={<DronesPage />} />
        <Route path="/drones/:droneId" element={<DroneDetailPage />} />
        <Route path="/logs/:logId" element={<LogDetailPage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="/home" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
