import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Mail, CheckCircle2, AlertCircle } from 'lucide-react'
import AuthLayout from '../../layouts/AuthLayout'
import { apiRequest } from '../../services/api'

function ForgotPassword() {
    const [email, setEmail] = useState('')
    const [submittedEmail, setSubmittedEmail] = useState('')
    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)
    const [showSuccessPopup, setShowSuccessPopup] = useState(false)
    const [linkSent, setLinkSent] = useState(false)
    const [cooldownSeconds, setCooldownSeconds] = useState(0)

    useEffect(() => {
        if (cooldownSeconds <= 0) return

        const timer = setInterval(() => {
            setCooldownSeconds((prev) => (prev > 0 ? prev - 1 : 0))
        }, 1000)

        return () => clearInterval(timer)
    }, [cooldownSeconds])

    const handleSubmit = async (event) => {
        event.preventDefault()

        // Prevent concurrent or premature duplicate submissions
        if (loading || cooldownSeconds > 0) {
            return
        }

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

            // The reset link has been dispatched
            setSubmittedEmail(trimmedEmail)
            setLinkSent(true)
            setShowSuccessPopup(true)
            setCooldownSeconds(60)

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
                        Enter your registered email address and we'll send you a secure password reset link.
                    </p>
                </div>

                {error && (
                    <div className="auth-error" role="alert">
                        <AlertCircle size={16} />
                        <span>{error}</span>
                    </div>
                )}

                {linkSent && !error && !showSuccessPopup && (
                    <div className="auth-success-message" role="status" aria-live="polite">
                        <CheckCircle2 size={16} />
                        <span>
                            If an account exists for <strong>{submittedEmail || email.trim()}</strong>,
                            a password reset link has been dispatched.
                        </span>
                    </div>
                )}

                <form onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label htmlFor="forgotEmail">
                            Email Address
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
                            required
                        />
                    </div>

                    <button
                        type="submit"
                        className="auth-primary-button"
                        disabled={loading || cooldownSeconds > 0}
                        aria-busy={loading}
                        aria-disabled={loading || cooldownSeconds > 0}
                    >
                        {loading ? (
                            <>
                                <span className="spinner-inline" aria-hidden="true"></span>
                                <span>Sending reset link...</span>
                            </>
                        ) : cooldownSeconds > 0 ? (
                            `Resend reset link (${cooldownSeconds}s)`
                        ) : linkSent ? (
                            'Resend reset link'
                        ) : (
                            <>
                                <Mail size={16} />
                                <span>Send Reset Link</span>
                            </>
                        )}
                    </button>
                </form>

                <div className="auth-divider">
                    <span>OR</span>
                </div>

                <p className="auth-switch">
                    Remember your password?{' '}
                    <Link to="/login">
                        Sign In
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
                            <CheckCircle2 size={32} />
                        </div>

                        <h3 id="reset-modal-title">Check your email</h3>

                        <p>
                            If an account is registered with
                            <strong> {submittedEmail || email.trim()}</strong>,
                            a password reset link has been dispatched.
                        </p>

                        <p>
                            Delivery may take a short time. Please check your inbox and spam folder.
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
