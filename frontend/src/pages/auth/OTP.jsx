import { useState, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../layouts/AuthLayout'

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
    const [loading, setLoading] = useState(false)

    const inputRefs = useRef([])

    const handleChange = (index, value) => {
        // Allow only numbers
        if (!/^\d*$/.test(value)) {
            return
        }

        const newOtp = [...otp]
        newOtp[index] = value.slice(-1)

        setOtp(newOtp)
        setError('')

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

    const handleVerify = async (event) => {
        event.preventDefault()

        setError('')

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
        const registrationEmail =
            localStorage.getItem('registration_email')

        if (!registrationEmail) {
            setError(
                'Registration session not found. Please register again.'
            )
            return
        }

        setLoading(true)

        try {
            const response = await fetch(
                'http://127.0.0.1:8000/auth/verify-otp',
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        email: registrationEmail,
                        otp: enteredOtp,
                    }),
                }
            )

            const data = await response.json()

            if (!response.ok) {
                throw new Error(
                    data.detail ||
                    'OTP verification failed. Please try again.'
                )
            }

            // Verification successful.
            localStorage.removeItem('registration_email')

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

        const registrationEmail =
            localStorage.getItem('registration_email')

        if (!registrationEmail) {
            setError(
                'Registration session not found. Please register again.'
            )
            return
        }

        setLoading(true)

        try {
            const response = await fetch(
                'http://127.0.0.1:8000/auth/resend-otp',
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        email: registrationEmail,
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

            setOtp([
                '',
                '',
                '',
                '',
                '',
                '',
            ])

            setError('A new OTP has been sent. Please check your email.')
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
                        We've sent a 6-digit verification code to your
                        email address.
                    </p>
                </div>

                {error && (
                    <div className="auth-error">
                        {error}
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