import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, Lock, AlertCircle, CheckCircle2 } from 'lucide-react'
import AuthLayout from '../../layouts/AuthLayout'
import { apiRequest } from '../../services/api'

function ResetPassword() {
    const navigate = useNavigate()
    const [searchParams] = useSearchParams()

    const token = searchParams.get('token')

    const [newPassword, setNewPassword] = useState('')
    const [confirmNewPassword, setConfirmNewPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [showConfirmPassword, setShowConfirmPassword] = useState(false)

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
            await apiRequest('/auth/reset-password', {
                method: 'POST',
                body: JSON.stringify({
                    token,
                    new_password: newPassword,
                }),
            })

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

    // Dynamic password rules helper
    const hasMinLength = newPassword.length >= 8
    const hasUpper = /[A-Z]/.test(newPassword)
    const hasLower = /[a-z]/.test(newPassword)
    const hasNumber = /[0-9]/.test(newPassword)
    const hasSpecial = /[^A-Za-z0-9]/.test(newPassword)

    return (
        <AuthLayout>
            <div className="auth-card">
                <div className="auth-card-header">
                    <h2>Reset your password</h2>
                    <p>Create a secure new password for your Cognidocs account.</p>
                </div>

                {error && (
                    <div className="auth-error" role="alert">
                        <AlertCircle size={16} />
                        <span>{error}</span>
                    </div>
                )}

                <form onSubmit={handleReset}>
                    <div className="form-group">
                        <label htmlFor="newPassword">New Password</label>
                        <div className="password-input-wrapper">
                            <input
                                id="newPassword"
                                type={showPassword ? 'text' : 'password'}
                                placeholder="Min 8 characters"
                                value={newPassword}
                                onChange={(event) => {
                                    setNewPassword(event.target.value)
                                    setError('')
                                }}
                                disabled={loading}
                                autoComplete="new-password"
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

                    <div className="form-group">
                        <label htmlFor="confirmNewPassword">Confirm New Password</label>
                        <div className="password-input-wrapper">
                            <input
                                id="confirmNewPassword"
                                type={showConfirmPassword ? 'text' : 'password'}
                                placeholder="Re-enter your new password"
                                value={confirmNewPassword}
                                onChange={(event) => {
                                    setConfirmNewPassword(event.target.value)
                                    setError('')
                                }}
                                disabled={loading}
                                autoComplete="new-password"
                                required
                            />
                            <button
                                type="button"
                                className="password-toggle-btn"
                                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                title={showConfirmPassword ? 'Hide password' : 'Show password'}
                                aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                            >
                                {showConfirmPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                        </div>
                    </div>

                    {newPassword && (
                        <div className="password-criteria-panel">
                            <span className={`criteria-item ${hasMinLength ? 'met' : ''}`}>
                                <CheckCircle2 size={12} /> 8+ chars
                            </span>
                            <span className={`criteria-item ${hasUpper ? 'met' : ''}`}>
                                <CheckCircle2 size={12} /> Uppercase
                            </span>
                            <span className={`criteria-item ${hasLower ? 'met' : ''}`}>
                                <CheckCircle2 size={12} /> Lowercase
                            </span>
                            <span className={`criteria-item ${hasNumber ? 'met' : ''}`}>
                                <CheckCircle2 size={12} /> Number
                            </span>
                            <span className={`criteria-item ${hasSpecial ? 'met' : ''}`}>
                                <CheckCircle2 size={12} /> Special char
                            </span>
                        </div>
                    )}

                    <button
                        type="submit"
                        className="auth-primary-button"
                        disabled={loading}
                    >
                        {loading ? (
                            <>
                                <span className="spinner-inline" aria-hidden="true"></span>
                                <span>Resetting password...</span>
                            </>
                        ) : (
                            <>
                                <Lock size={16} />
                                <span>Reset Password</span>
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
        </AuthLayout>
    )
}

export default ResetPassword
