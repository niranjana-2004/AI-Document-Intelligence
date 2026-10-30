import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'motion/react'
import { Eye, EyeOff, LogIn, AlertCircle } from 'lucide-react'
import AuthLayout from '../../layouts/AuthLayout'
import { apiRequest } from '../../services/api'

function Login() {
    const navigate = useNavigate()

    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    const handleLogin = async (event) => {
        event.preventDefault()

        setError('')
        setLoading(true)

        try {
            const data = await apiRequest('/auth/login', {
                method: 'POST',
                body: JSON.stringify({
                    email,
                    password,
                }),
            })

            // Store authentication information
            localStorage.setItem('access_token', data.access_token)
            localStorage.setItem('user', JSON.stringify(data.user))

            navigate('/dashboard')
        } catch (error) {
            setError(error.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <AuthLayout>
            <div className="auth-card">
                <div className="auth-card-header">
                    <h2>Welcome back</h2>
                    <p>Sign in to continue to your Cognidocs workspace.</p>
                </div>

                <form onSubmit={handleLogin}>
                    <div className="form-group">
                        <label htmlFor="email">
                            Email Address
                        </label>

                        <input
                            id="email"
                            type="email"
                            placeholder="you@example.com"
                            value={email}
                            onChange={(event) => setEmail(event.target.value)}
                            autoComplete="email"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <div className="password-label">
                            <label htmlFor="password">
                                Password
                            </label>

                            <Link to="/forgot-password">
                                Forgot password?
                            </Link>
                        </div>

                        <div className="password-input-wrapper">
                            <input
                                id="password"
                                type={showPassword ? 'text' : 'password'}
                                placeholder="Enter your password"
                                value={password}
                                onChange={(event) => setPassword(event.target.value)}
                                autoComplete="current-password"
                                required
                            />
                            <button
                                type="button"
                                className="password-toggle-btn"
                                onClick={() => setShowPassword(!showPassword)}
                                title={showPassword ? 'Hide password' : 'Show password'}
                                aria-label={showPassword ? 'Hide password' : 'Show password'}
                            >
                                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                        </div>
                    </div>

                    {error && (
                        <div className="auth-error" role="alert">
                            <AlertCircle size={16} />
                            <span>{error}</span>
                        </div>
                    )}

                    <motion.button
                        type="submit"
                        className="auth-primary-button"
                        disabled={loading}
                        whileHover={!loading ? { scale: 1.02, y: -1 } : {}}
                        whileTap={!loading ? { scale: 0.98 } : {}}
                    >
                        {loading ? (
                            <>
                                <span className="spinner-inline" aria-hidden="true"></span>
                                <span>Signing in...</span>
                            </>
                        ) : (
                            <>
                                <LogIn size={16} />
                                <span>Login</span>
                            </>
                        )}
                    </motion.button>
                </form>

                <div className="auth-divider">
                    <span>OR</span>
                </div>

                <p className="auth-switch">
                    Don't have an account?{' '}
                    <Link to="/register">
                        Create Account
                    </Link>
                </p>
            </div>
        </AuthLayout>
    )
}

export default Login
