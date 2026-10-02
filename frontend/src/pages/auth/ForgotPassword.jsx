import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../layouts/AuthLayout'

function ForgotPassword() {
    const navigate = useNavigate()

    const handleSubmit = (event) => {
        event.preventDefault()

        navigate('/reset-password')
    }

    return (
        <AuthLayout>
            <div className="auth-card">
                <div className="auth-card-header">
                    <h2>Forgot your password?</h2>

                    <p>
                        Enter your registered email address and we'll
                        send you a password reset link.
                    </p>
                </div>

                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label htmlFor="forgotEmail">
                            Email
                        </label>

                        <input
                            id="forgotEmail"
                            type="email"
                            placeholder="you@example.com"
                            required
                        />
                    </div>

                    <button
                        type="submit"
                        className="auth-primary-button"
                    >
                        Send Reset Link
                    </button>
                </form>

                <div className="auth-divider">
                    <span>OR</span>
                </div>

                <p className="auth-switch">
                    Remember your password?{' '}
                    <Link to="/login">
                        Sign in
                    </Link>
                </p>
            </div>
        </AuthLayout>
    )
}

export default ForgotPassword