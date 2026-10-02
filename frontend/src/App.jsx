import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom'

import Login from './pages/auth/Login'
import Register from './pages/auth/Register'
import OTP from './pages/auth/OTP'
import ForgotPassword from './pages/auth/ForgotPassword'
import ResetPassword from './pages/auth/ResetPassword'
import PasswordResetSuccess from './pages/auth/PasswordResetSuccess'

import DashboardPage from './pages/DashboardPage'
import Documents from './pages/Documents'
import AskAI from './pages/AskAI'
import Search from './pages/Search'
import Profile from './pages/Profile'
import About from './pages/About'
import AppLayout from './layouts/AppLayout'

function App() {
  return (
    <BrowserRouter>

      <Routes>

        {/* =========================
            AUTHENTICATION
        ========================== */}

        <Route
          path="/"
          element={
            <Navigate
              to="/login"
              replace
            />
          }
        />

        <Route
          path="/login"
          element={<Login />}
        />

        <Route
          path="/register"
          element={<Register />}
        />

        <Route
          path="/otp"
          element={<OTP />}
        />

        <Route
          path="/forgot-password"
          element={<ForgotPassword />}
        />

        <Route
          path="/reset-password"
          element={<ResetPassword />}
        />

        <Route
          path="/password-reset-success"
          element={<PasswordResetSuccess />}
        />


        {/* =========================
            APPLICATION
        ========================== */}

        <Route
          path="/dashboard"
          element={<DashboardPage />}
        />

        <Route
          path="/documents"
          element={
            <AppLayout>
              <Documents />
            </AppLayout>
          }
        />

        <Route
          path="/ask-ai"
          element={
            <AppLayout>
              <AskAI />
            </AppLayout>
          }
        />

        <Route
          path="/search"
          element={
            <AppLayout>
              <Search />
            </AppLayout>
          }
        />

        <Route
          path="/profile"
          element={
            <AppLayout>
              <Profile />
            </AppLayout>
          }
        />

        <Route
          path="/about"
          element={
            <AppLayout>
              <About />
            </AppLayout>
          }
        />

      </Routes>

    </BrowserRouter>
  )
}

export default App