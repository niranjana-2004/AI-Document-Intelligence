import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../layouts/AuthLayout'
import { apiRequest } from '../../services/api'

function Register() {
    const navigate = useNavigate()

    const [fullName, setFullName] = useState('')
    const [email, setEmail] = useState('')
    const [phone, setPhone] = useState('')
    const [password, setPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')

    const [error, setError] = useState('')
    const [loading, setLoading] = useState(false)

    const validateForm = () => {
        const trimmedName = fullName.trim()
        const trimmedEmail = email.trim()
        const trimmedPhone = phone.trim()

        // Full name validation
        if (!trimmedName) {
            return 'Please enter your full name.'
        }

        if (trimmedName.length < 2) {
            return 'Full name must contain at least 2 characters.'
        }

        if (!/^[A-Za-z]+(?:\s+[A-Za-z]+)*$/.test(trimmedName)) {
            return 'Full name can contain only letters and spaces.'
        }

        // Email validation
        if (!trimmedEmail) {
            return 'Please enter your email address.'
        }

        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

        if (!emailPattern.test(trimmedEmail)) {
            return 'Please enter a valid email address.'
        }

        // Phone validation
        if (!trimmedPhone) {
            return 'Please enter your phone number.'
        }

        if (!/^\d{10}$/.test(trimmedPhone)) {
            return 'Phone number must contain exactly 10 digits.'
        }

        // Password validation
        if (!password) {
            return 'Please enter a password.'
        }

        if (password.length < 8) {
            return 'Password must contain at least 8 characters.'
        }

        if (!/[A-Z]/.test(password)) {
            return 'Password must contain at least one uppercase letter.'
        }

        if (!/[a-z]/.test(password)) {
            return 'Password must contain at least one lowercase letter.'
        }

        if (!/[0-9]/.test(password)) {
            return 'Password must contain at least one number.'
        }

        if (!/[^A-Za-z0-9]/.test(password)) {
            return 'Password must contain at least one special character.'
        }

        // Confirm password
        if (!confirmPassword) {
            return 'Please confirm your password.'
        }

        if (password !== confirmPassword) {
            return 'Passwords do not match.'
        }

        return ''
    }

    const handleRegister = async (event) => {
        event.preventDefault()

        setError('')

        const validationError = validateForm()

        if (validationError) {
            setError(validationError)
            return
        }

        setLoading(true)

        try {
            await apiRequest('/auth/register', {
                method: 'POST',
                body: JSON.stringify({
                    full_name: fullName.trim(),
                    email: email.trim(),
                    password,
                }),
            })

            // Store email temporarily so the OTP page knows
            // which account is being verified.
            localStorage.setItem(
                'registration_email',
                email.trim().toLowerCase()
            )

            navigate('/otp')
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
                    <h2>Create your account</h2>

                    <p>
                        Create an account to manage and query your documents with Cognidocs.
                    </p>
                </div>

                {error && (
                    <div className="auth-error">
                        {error}
                    </div>
                )}

                <form onSubmit={handleRegister}>
                    <div className="form-group">
                        <label htmlFor="fullName">
                            Full name
                        </label>

                        <input
                            id="fullName"
                            type="text"
                            placeholder="Enter your full name"
                            value={fullName}
                            onChange={(event) =>
                                setFullName(event.target.value)
                            }
                            autoComplete="name"
                        />
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label htmlFor="registerEmail">
                                Email
                            </label>

                            <input
                                id="registerEmail"
                                type="email"
                                placeholder="you@example.com"
                                value={email}
                                onChange={(event) =>
                                    setEmail(event.target.value)
                                }
                                autoComplete="email"
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="phone">
                                Phone number
                            </label>

                            <input
                                id="phone"
                                type="tel"
                                placeholder="10-digit number"
                                value={phone}
                                onChange={(event) =>
                                    setPhone(event.target.value)
                                }
                                inputMode="numeric"
                                autoComplete="tel"
                            />
                        </div>
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label htmlFor="registerPassword">
                                Password
                            </label>

                            <input
                                id="registerPassword"
                                type="password"
                                placeholder="Min 8 characters"
                                value={password}
                                onChange={(event) =>
                                    setPassword(event.target.value)
                                }
                                autoComplete="new-password"
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="confirmPassword">
                                Confirm password
                            </label>

                            <input
                                id="confirmPassword"
                                type="password"
                                placeholder="Re-enter password"
                                value={confirmPassword}
                                onChange={(event) =>
                                    setConfirmPassword(event.target.value)
                                }
                                autoComplete="new-password"
                            />
                        </div>
                    </div>

                    <button
                        type="submit"
                        className="auth-primary-button"
                        disabled={loading}
                    >
                        {loading
                            ? 'Creating account...'
                            : 'Create Account'}
                    </button>
                </form>

                <div className="auth-divider">
                    <span>OR</span>
                </div>

                <p className="auth-switch">
                    Already have an account?{' '}
                    <Link to="/login">
                        Login
                    </Link>
                </p>
            </div>
        </AuthLayout>
    )
}

export default Register