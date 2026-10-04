import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../layouts/AuthLayout'

function ForgotPassword() {
    const navigate = useNavigate()

    const [email, setEmail] = useState('')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    const handleSubmit = async (event) => {
        event.preventDefault()

        setError('')

        const trimmedEmail = email.trim()

        // Email validation
        if (!trimmedEmail) {
            setError('Please enter your email address.')
            return
        }

        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

        if (!emailPattern.test(trimmedEmail)) {
            setError('Please enter a valid email address.')
            return
        }

        setLoading(true)

        try {
            const response = await fetch(
                'http://127.0.0.1:8000/auth/forgot-password',
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        email: trimmedEmail,
                    }),
                }
            )

            const data = await response.json()

            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    'Unable to process your request. Please try again.'
                )
            }

            // Store the email so the reset-password page
            // knows which account is being reset.
            localStorage.setItem(
                'password_reset_email',
                trimmedEmail.toLowerCase()
            )

            navigate('/reset-password')
        } catch (error) {
            setError(
                error.message ||
                'Something went wrong. Please try again.'
            )
        } finally {
            setLoading(false)
        }
    }

    return (
        <AuthLayout>
            <div className="auth-card">
                <div className="auth-card-header">
                    <h2>Forgot your password?</h2>

                    <p>
                        Enter your registered email address and we'll
                        send you a password reset OTP.
                    </p>
                </div>

                {error && (
                    <div className="auth-error">
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label htmlFor="forgotEmail">
                            Email
                        </label>

                        <input
                            id="forgotEmail"
                            type="email"
                            placeholder="you@example.com"
                            value={email}
                            onChange={(event) =>
                                setEmail(event.target.value)
                            }
                            autoComplete="email"
                            disabled={loading}
                        />
                    </div>

                    <button
                        type="submit"
                        className="auth-primary-button"
                        disabled={loading}
                    >
                        {loading
                            ? 'Sending OTP...'
                            : 'Send Reset OTP'}
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