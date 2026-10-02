import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../layouts/AuthLayout'

function Login() {
    const navigate = useNavigate()

    const handleLogin = (event) => {
        event.preventDefault()

        // Temporary navigation.
        // Real authentication will be connected later.
        navigate('/dashboard')
    }

    return (
        <AuthLayout>
            <div className="auth-card">
                <div className="auth-card-header">
                    <h2>Welcome back</h2>

                    <p>
                        Sign in to continue to your document workspace.
                    </p>
                </div>

                <form onSubmit={handleLogin}>
                    <div className="form-group">
                        <label htmlFor="email">
                            Email
                        </label>

                        <input
                            id="email"
                            type="email"
                            placeholder="you@example.com"
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

                        <input
                            id="password"
                            type="password"
                            placeholder="Enter your password"
                            required
                        />
                    </div>

                    <button
                        type="submit"
                        className="auth-primary-button"
                    >
                        Sign in
                    </button>
                </form>

                <div className="auth-divider">
                    <span>OR</span>
                </div>

                <p className="auth-switch">
                    Don't have an account?{' '}
                    <Link to="/register">
                        Create account
                    </Link>
                </p>
            </div>
        </AuthLayout>
    )
}

export default Login