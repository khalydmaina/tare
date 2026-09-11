import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Landing } from './pages/Landing'
import { FlightRecorder } from './pages/FlightRecorder'

// GitHub Pages serves the site under /<repo>/; Vite's BASE_URL carries that prefix
const basename = import.meta.env.BASE_URL.replace(/\/$/, '')

export default function App() {
  return (
    <BrowserRouter basename={basename || undefined}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<FlightRecorder />} />
        <Route path="/flight-recorder" element={<Navigate to="/app" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
