import { useState } from 'react'
import { Link } from 'react-router-dom'
import AuthLayout from '../../layouts/AuthLayout'

function ForgotPassword() {
    const [email, setEmail] = useState('')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)
    const [showSuccessPopup, setShowSuccessPopup] = useState(false)
    const [linkSent, setLinkSent] = useState(false)

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
                    'Unable to send the reset link. Please try again.'
                )
            }

            // The reset link has been successfully requested.
            setLinkSent(true)
            setShowSuccessPopup(true)

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
                        send you a password reset link.
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
                            onChange={(event) => {
                                setEmail(event.target.value)
                                setError('')
                            }}
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
                            ? 'Sending reset link...'
                            : linkSent
                                ? 'Resend reset link'
                                : 'Send reset link'}
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

            {/* Success Popup */}
            {showSuccessPopup && (
                <div
                    className="reset-success-overlay"
                    onClick={() => setShowSuccessPopup(false)}
                >
                    <div
                        className="reset-success-popup"
                        onClick={(event) => event.stopPropagation()}
                    >
                        <div className="reset-success-icon">
                            ✓
                        </div>

                        <h3>Reset link sent!</h3>

                        <p>
                            We've sent a password reset link to
                            <strong> {email.trim()}</strong>.
                        </p>

                        <p>
                            Please check your inbox and click the
                            link to create a new password.
                        </p>

                        <button
                            type="button"
                            className="auth-primary-button"
                            onClick={() => setShowSuccessPopup(false)}
                        >
                            Got it
                        </button>
                    </div>
                </div>
            )}
        </AuthLayout>
    )
}

export default ForgotPassword