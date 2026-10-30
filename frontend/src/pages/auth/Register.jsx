import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'motion/react'
import { Eye, EyeOff, UserPlus, AlertCircle, CheckCircle2 } from 'lucide-react'
import AuthLayout from '../../layouts/AuthLayout'
import { apiRequest } from '../../services/api'

function Register() {
    const navigate = useNavigate()

    const [fullName, setFullName] = useState('')
    const [email, setEmail] = useState('')
    const [phone, setPhone] = useState('')
    const [password, setPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [showPassword, setShowPassword] = useState(false)
    const [showConfirmPassword, setShowConfirmPassword] = useState(false)

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

            // Store email temporarily for the OTP verification page
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

    // Dynamic password rules helper
    const hasMinLength = password.length >= 8
    const hasUpper = /[A-Z]/.test(password)
    const hasLower = /[a-z]/.test(password)
    const hasNumber = /[0-9]/.test(password)
    const hasSpecial = /[^A-Za-z0-9]/.test(password)

    return (
        <AuthLayout>
            <div className="auth-card register-card">
                <div className="auth-card-header">
                    <h2>Create your account</h2>
                    <p>
                        Get started with Cognidocs to manage, summarize, and query your documents.
                    </p>
                </div>

                {error && (
                    <div className="auth-error" role="alert">
                        <AlertCircle size={16} />
                        <span>{error}</span>
                    </div>
                )}

                <form onSubmit={handleRegister}>
                    <div className="form-group">
                        <label htmlFor="fullName">Full Name</label>
                        <input
                            id="fullName"
                            type="text"
                            placeholder="Alex Morgan"
                            value={fullName}
                            onChange={(event) => setFullName(event.target.value)}
                            autoComplete="name"
                            required
                        />
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label htmlFor="registerEmail">Email Address</label>
                            <input
                                id="registerEmail"
                                type="email"
                                placeholder="you@example.com"
                                value={email}
                                onChange={(event) => setEmail(event.target.value)}
                                autoComplete="email"
                                required
                            />
                        </div>

                        <div className="form-group">
                            <label htmlFor="phone">Phone (10 digits)</label>
                            <input
                                id="phone"
                                type="tel"
                                placeholder="9876543210"
                                value={phone}
                                onChange={(event) => setPhone(event.target.value)}
                                inputMode="numeric"
                                autoComplete="tel"
                                required
                            />
                        </div>
                    </div>

                    <div className="form-row">
                        <div className="form-group">
                            <label htmlFor="registerPassword">Password</label>
                            <div className="password-input-wrapper">
                                <input
                                    id="registerPassword"
                                    type={showPassword ? 'text' : 'password'}
                                    placeholder="Min 8 characters"
                                    value={password}
                                    onChange={(event) => setPassword(event.target.value)}
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
                            <label htmlFor="confirmPassword">Confirm Password</label>
                            <div className="password-input-wrapper">
                                <input
                                    id="confirmPassword"
                                    type={showConfirmPassword ? 'text' : 'password'}
                                    placeholder="Re-enter password"
                                    value={confirmPassword}
                                    onChange={(event) => setConfirmPassword(event.target.value)}
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
                    </div>

                    {/* Password criteria checklist if user started typing */}
                    {password && (
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

                    <motion.button
                        type="submit"
                        className="auth-primary-button"
                        disabled={loading}
                        whileHover={!loading ? { scale: 1.02, y: -1 } : {}}
                        whileTap={!loading ? { scale: 0.98 } : {}}
                    >
                        {loading ? (
                            <>
                                <span className="spinner-inline" aria-hidden="true"></span>
                                <span>Creating account...</span>
                            </>
                        ) : (
                            <>
                                <UserPlus size={16} />
                                <span>Create Account</span>
                            </>
                        )}
                    </motion.button>
                </form>

                <div className="auth-divider">
                    <span>OR</span>
                </div>

                <p className="auth-switch">
                    Already have an account?{' '}
                    <Link to="/login">
                        Sign In
                    </Link>
                </p>
            </div>
        </AuthLayout>
    )
}

export default Register
