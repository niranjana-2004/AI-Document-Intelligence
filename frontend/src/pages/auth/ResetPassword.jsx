import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../layouts/AuthLayout'

function ResetPassword() {
    const navigate = useNavigate()

    const [otp, setOtp] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [confirmNewPassword, setConfirmNewPassword] = useState('')

    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    const [resending, setResending] = useState(false)
    const [resendMessage, setResendMessage] = useState('')

    const validateForm = () => {
        // OTP validation
        if (!otp.trim()) {
            return 'Please enter the OTP.'
        }

        if (!/^\d{6}$/.test(otp.trim())) {
            return 'OTP must contain exactly 6 digits.'
        }

        // Password validation
        if (!newPassword) {
            return 'Please enter your new password.'
        }

        if (newPassword.length < 8) {
            return 'Password must contain at least 8 characters.'
        }

        if (!/[A-Z]/.test(newPassword)) {
            return 'Password must contain at least one uppercase letter.'
        }

        if (!/[a-z]/.test(newPassword)) {
            return 'Password must contain at least one lowercase letter.'
        }

        if (!/[0-9]/.test(newPassword)) {
            return 'Password must contain at least one number.'
        }

        if (!/[^A-Za-z0-9]/.test(newPassword)) {
            return 'Password must contain at least one special character.'
        }

        // Confirm password
        if (!confirmNewPassword) {
            return 'Please confirm your new password.'
        }

        if (newPassword !== confirmNewPassword) {
            return 'Passwords do not match.'
        }

        return ''
    }

    const handleResendOTP = async () => {
        setError('')
        setResendMessage('')

        const resetEmail =
            localStorage.getItem('password_reset_email')

        if (!resetEmail) {
            setError(
                'Password reset session not found. Please request a new OTP.'
            )
            return
        }

        setResending(true)

        try {
            const response = await fetch(
                'http://127.0.0.1:8000/auth/resend-reset-otp',
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        email: resetEmail,
                    }),
                }
            )

            const data = await response.json()

            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    'Unable to resend OTP. Please try again.'
                )
            }

            setOtp('')

            setResendMessage(
                'A new OTP has been generated. Please check your email.'
            )
        } catch (error) {
            setError(
                error.message ||
                'Something went wrong. Please try again.'
            )
        } finally {
            setResending(false)
        }
    }

    const handleReset = async (event) => {
        event.preventDefault()

        setError('')

        const validationError = validateForm()

        if (validationError) {
            setError(validationError)
            return
        }

        const resetEmail =
            localStorage.getItem('password_reset_email')

        if (!resetEmail) {
            setError(
                'Password reset session not found. Please request a new OTP.'
            )
            return
        }

        setLoading(true)

        try {
            const response = await fetch(
                'http://127.0.0.1:8000/auth/reset-password',
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        email: resetEmail,
                        otp: otp.trim(),
                        new_password: newPassword,
                    }),
                }
            )

            const data = await response.json()

            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    'Password reset failed. Please try again.'
                )
            }

            // Remove the temporary password-reset email
            // after successful password reset.
            localStorage.removeItem('password_reset_email')

            navigate('/password-reset-success')
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
                    <h2>Reset your password</h2>

                    <p>
                        Enter the OTP sent to your email and create a
                        new password for your account.
                    </p>
                </div>

                {error && (
                    <div className="auth-error">
                        {error}
                    </div>
                )}

                <form onSubmit={handleReset}>
                    <div className="form-group">
                        <label htmlFor="resetOtp">
                            OTP
                        </label>

                        <input
                            id="resetOtp"
                            type="text"
                            inputMode="numeric"
                            maxLength="6"
                            placeholder="Enter 6-digit OTP"
                            value={otp}
                            onChange={(event) => {
                                const value = event.target.value

                                if (/^\d*$/.test(value)) {
                                    setOtp(value.slice(0, 6))
                                }

                                setError('')
                            }}
                            disabled={loading}
                            autoComplete="one-time-code"
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="newPassword">
                            New password
                        </label>

                        <input
                            id="newPassword"
                            type="password"
                            placeholder="Enter your new password"
                            value={newPassword}
                            onChange={(event) => {
                                setNewPassword(event.target.value)
                                setError('')
                            }}
                            disabled={loading}
                            autoComplete="new-password"
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="confirmNewPassword">
                            Confirm new password
                        </label>

                        <input
                            id="confirmNewPassword"
                            type="password"
                            placeholder="Confirm your new password"
                            value={confirmNewPassword}
                            onChange={(event) => {
                                setConfirmNewPassword(event.target.value)
                                setError('')
                            }}
                            disabled={loading}
                            autoComplete="new-password"
                        />
                    </div>

                    <button
                        type="submit"
                        className="auth-primary-button"
                        disabled={loading}
                    >
                        {loading
                            ? 'Resetting password...'
                            : 'Reset password'}
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

export default ResetPassword