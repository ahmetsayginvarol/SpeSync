import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from '@/context/AuthContext'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { Layout } from '@/components/Layout'
import LoginPage from '@/pages/Login'
import RestaurantPage from '@/pages/restaurant/RestaurantPage'
import GalleyPage from '@/pages/galley/GalleyPage'
import AdminPage from '@/pages/admin/AdminPage'
import ReportsPage from '@/pages/reports/ReportsPage'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<Navigate to="/restaurant" replace />} />

              <Route
                path="/restaurant"
                element={<ProtectedRoute allowedRoles={['admin', 'restaurant']} />}
              >
                <Route index element={<RestaurantPage />} />
              </Route>

              <Route
                path="/galley"
                element={<ProtectedRoute allowedRoles={['admin', 'galley']} />}
              >
                <Route index element={<GalleyPage />} />
              </Route>

              <Route
                path="/admin/*"
                element={<ProtectedRoute allowedRoles={['admin']} />}
              >
                <Route index element={<AdminPage />} />
              </Route>

              <Route path="/reports" element={<ReportsPage />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
