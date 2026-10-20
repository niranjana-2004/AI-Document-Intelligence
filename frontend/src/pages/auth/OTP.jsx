import { useState, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../layouts/AuthLayout'
import { apiRequest } from '../../services/api'

function OTP() {
    const navigate = useNavigate()

    const [otp, setOtp] = useState([
        '',
        '',
        '',
        '',
        '',
        '',
    ])

    const [error, setError] = useState('')
    const [infoMessage, setInfoMessage] = useState('')
    const [loading, setLoading] = useState(false)

    const inputRefs = useRef([])
    const registrationEmail = localStorage.getItem('registration_email') || ''

    const handleChange = (index, value) => {
        // Allow only numbers
        if (!/^\d*$/.test(value)) {
            return
        }

        const newOtp = [...otp]
        newOtp[index] = value.slice(-1)

        setOtp(newOtp)
        setError('')
        setInfoMessage('')

        // Move to next box
        if (value && index < 5) {
            inputRefs.current[index + 1]?.focus()
        }
    }

    const handleKeyDown = (index, event) => {
        if (
            event.key === 'Backspace' &&
            !otp[index] &&
            index > 0
        ) {
            inputRefs.current[index - 1]?.focus()
        }
    }

    const handlePaste = (event) => {
        event.preventDefault()
        const pasted = event.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
        if (pasted.length > 0) {
            const newOtp = [...otp]
            for (let i = 0; i < 6; i++) {
                newOtp[i] = pasted[i] || ''
            }
            setOtp(newOtp)
            setError('')
            setInfoMessage('')
            const nextIdx = Math.min(pasted.length, 5)
            inputRefs.current[nextIdx]?.focus()
        }
    }

    const handleVerify = async (event) => {
        event.preventDefault()

        setError('')
        setInfoMessage('')

        const enteredOtp = otp.join('')

        // OTP validation
        if (enteredOtp.length !== 6) {
            setError('Please enter the complete 6-digit OTP.')
            return
        }

        if (!/^\d{6}$/.test(enteredOtp)) {
            setError('OTP must contain exactly 6 digits.')
            return
        }

        // Get the email saved during registration
        const savedEmail = registrationEmail || localStorage.getItem('registration_email')

        if (!savedEmail) {
            setError(
                'Registration session not found. Please register again.'
            )
            return
        }

        setLoading(true)

        try {
            await apiRequest('/auth/verify-otp', {
                method: 'POST',
                body: JSON.stringify({
                    email: savedEmail,
                    otp: enteredOtp,
                }),
            })

            // Verification successful.
            localStorage.removeItem('registration_email')

            const storedUser = localStorage.getItem('user')
            if (storedUser) {
                try {
                    const parsed = JSON.parse(storedUser)
                    if (parsed && parsed.email?.toLowerCase() === savedEmail.toLowerCase()) {
                        parsed.is_verified = true
                        localStorage.setItem('user', JSON.stringify(parsed))
                    }
                } catch {
                    // Ignore parsing error
                }
            }

            navigate('/login')
        } catch (error) {
            setError(
                error.message ||
                'Something went wrong. Please try again.'
            )
        } finally {
            setLoading(false)
        }
    }

    const handleResend = async () => {
        setError('')
        setInfoMessage('')

        const savedEmail = registrationEmail || localStorage.getItem('registration_email')

        if (!savedEmail) {
            setError(
                'Registration session not found. Please register again.'
            )
            return
        }

        setLoading(true)

        try {
            await apiRequest('/auth/resend-otp', {
                method: 'POST',
                body: JSON.stringify({
                    email: savedEmail,
                }),
            })

            setOtp([
                '',
                '',
                '',
                '',
                '',
                '',
            ])

            setInfoMessage('A new OTP has been sent. Please check your email inbox.')
            inputRefs.current[0]?.focus()
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
                    <h2>Verify your account</h2>

                    <p>
                        {registrationEmail ? (
                            <>
                                Enter the 6-digit code sent to{' '}
                                <strong style={{ color: 'var(--text-primary)' }}>{registrationEmail}</strong>.
                            </>
                        ) : (
                            "We've sent a 6-digit verification code to your email address."
                        )}
                    </p>
                </div>

                {error && (
                    <div className="auth-error">
                        {error}
                    </div>
                )}

                {infoMessage && (
                    <div className="auth-success-message">
                        {infoMessage}
                    </div>
                )}

                <form onSubmit={handleVerify}>
                    <div className="otp-input-container">
                        {otp.map((digit, index) => (
                            <input
                                key={index}
                                ref={(element) => {
                                    inputRefs.current[index] = element
                                }}
                                type="text"
                                inputMode="numeric"
                                maxLength="1"
                                value={digit}
                                onChange={(event) =>
                                    handleChange(
                                        index,
                                        event.target.value
                                    )
                                }
                                onKeyDown={(event) =>
                                    handleKeyDown(index, event)
                                }
                                onPaste={handlePaste}
                                className="otp-input"
                                aria-label={`OTP digit ${index + 1}`}
                                disabled={loading}
                            />
                        ))}
                    </div>

                    <button
                        type="submit"
                        className="auth-primary-button"
                        disabled={loading}
                    >
                        {loading
                            ? 'Verifying...'
                            : 'Verify OTP'}
                    </button>
                </form>

                <div className="otp-resend">
                    <p>
                        Didn't receive the code?
                    </p>

                    <button
                        type="button"
                        onClick={handleResend}
                        className="otp-resend-button"
                        disabled={loading}
                    >
                        Resend OTP
                    </button>
                </div>

                <div className="auth-divider">
                    <span>OR</span>
                </div>

                <p className="auth-switch">
                    <Link to="/register">
                        Back to Create Account
                    </Link>
                </p>
            </div>
        </AuthLayout>
    )
}

export default OTP