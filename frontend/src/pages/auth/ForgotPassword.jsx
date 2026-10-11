import { useState } from 'react'
import { Link } from 'react-router-dom'
import AuthLayout from '../../layouts/AuthLayout'
import { apiRequest } from '../../services/api'

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
            await apiRequest('/auth/forgot-password', {
                method: 'POST',
                body: JSON.stringify({
                    email: trimmedEmail,
                }),
            })

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
                        Login
                    </Link>
                </p>
            </div>

            {/* Success Popup */}
            {showSuccessPopup && (
                <div
                    className="reset-success-overlay"
                    onClick={() => setShowSuccessPopup(false)}
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="reset-modal-title"
                >
                    <div
                        className="reset-success-popup"
                        onClick={(event) => event.stopPropagation()}
                    >
                        <div className="reset-success-icon" aria-hidden="true">
                            ✓
                        </div>

                        <h3 id="reset-modal-title">Reset link sent!</h3>

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
                            autoFocus
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