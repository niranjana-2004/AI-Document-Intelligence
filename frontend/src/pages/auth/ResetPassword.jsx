import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import AuthLayout from '../../layouts/AuthLayout'

function ResetPassword() {
    const navigate = useNavigate()
    const [searchParams] = useSearchParams()

    const token = searchParams.get('token')

    const [newPassword, setNewPassword] = useState('')
    const [confirmNewPassword, setConfirmNewPassword] = useState('')

    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    const validateForm = () => {
        if (!token) {
            return 'Invalid or missing password reset link.'
        }

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

        if (!confirmNewPassword) {
            return 'Please confirm your new password.'
        }

        if (newPassword !== confirmNewPassword) {
            return 'Passwords do not match.'
        }

        return ''
    }

    const handleReset = async (event) => {
        event.preventDefault()

        setError('')

        const validationError = validateForm()

        if (validationError) {
            setError(validationError)
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
                        token,
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
                        Create a new password for your
                        AI Document Intelligence account.
                    </p>
                </div>

                {error && (
                    <div className="auth-error">
                        {error}
                    </div>
                )}

                <form onSubmit={handleReset}>
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