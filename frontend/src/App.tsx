import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import { tokenService } from './services/tokenService'
import { isAdminUser, isMasterUser } from './utils/roles'
import { canReviewDeletionRequests, hasPermission } from './utils/permissions'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import MailManagement from './pages/MailManagement'
import Appointments from './pages/Appointments'
import ReceptionDashboard from './pages/ReceptionDashboard'
import UserAdministration from './pages/UserAdministration'
import PublicBooking from './pages/PublicBooking'
import PublicHome from './pages/PublicHome'
import Settings from './pages/Settings'
import DeletionRequests from './pages/DeletionRequests'
import AdminAuditLogs from './pages/AdminAuditLogs'
import AdminSystemNotifications from './pages/AdminSystemNotifications'
import AdminPublicPosts from './pages/AdminPublicPosts'
import ForgotPassword from './pages/ForgotPassword'
import PasswordResetRequestsAdmin from './pages/PasswordResetRequestsAdmin'
import PrivacyPolicy from './pages/PrivacyPolicy'
import TermsOfUse from './pages/TermsOfUse'
import Layout from './components/Layout'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth()
  const hasTokens = tokenService.hasTokens()
  
  // Show loading state while checking auth
  if (loading) {
    return null // or a loading spinner
  }
  
  // Check both state and token for authentication
  if (isAuthenticated || hasTokens) {
    return <>{children}</>
  }
  
  return <Navigate to="/login" />
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return null
  }
  if (!isAdminUser(user?.role)) {
    return <Navigate to="/app" replace />
  }
  return <>{children}</>
}

function MasterRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return null
  }
  if (!isMasterUser(user?.role)) {
    return <Navigate to="/app" replace />
  }
  return <>{children}</>
}

function PermissionRoute({
  permission,
  children,
}: {
  permission: string
  children: React.ReactNode
}) {
  const { user, loading } = useAuth()
  if (loading) {
    return null
  }
  if (!hasPermission(user, permission)) {
    return <Navigate to="/app" replace />
  }
  return <>{children}</>
}

function DeletionRequestsRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return null
  }
  if (!canReviewDeletionRequests(user)) {
    return <Navigate to="/app" replace />
  }
  return <>{children}</>
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<PublicHome />} />
      <Route path="/login" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/privacy" element={<PrivacyPolicy />} />
      <Route path="/terms" element={<TermsOfUse />} />
      <Route path="/public/booking" element={<PublicBooking />} />
      <Route path="/book" element={<Navigate to="/public/booking" replace />} />
      <Route
        path="/app"
        element={
          <PrivateRoute>
            <Layout />
          </PrivateRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="mail" element={<MailManagement />} />
        <Route path="appointments" element={<Appointments />} />
        <Route path="reception" element={<ReceptionDashboard />} />
        <Route
          path="deletion-requests"
          element={
            <DeletionRequestsRoute>
              <DeletionRequests />
            </DeletionRequestsRoute>
          }
        />
        <Route
          path="users"
          element={
            <AdminRoute>
              <UserAdministration />
            </AdminRoute>
          }
        />
        <Route
          path="admin/password-reset-requests"
          element={
            <MasterRoute>
              <PasswordResetRequestsAdmin />
            </MasterRoute>
          }
        />
        <Route
          path="admin/audit"
          element={
            <PermissionRoute permission="admin.audit">
              <AdminAuditLogs />
            </PermissionRoute>
          }
        />
        <Route
          path="admin/notifications"
          element={
            <PermissionRoute permission="admin.notifications">
              <AdminSystemNotifications />
            </PermissionRoute>
          }
        />
        <Route
          path="admin/public-posts"
          element={
            <PermissionRoute permission="content.public_posts">
              <AdminPublicPosts />
            </PermissionRoute>
          }
        />
        <Route path="settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}

export default App

