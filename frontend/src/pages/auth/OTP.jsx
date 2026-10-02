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

    const inputRefs = useRef([])

    const handleChange = (index, value) => {
        // Allow only numbers
        if (!/^\d*$/.test(value)) {
            return
        }

        const newOtp = [...otp]
        newOtp[index] = value.slice(-1)

        setOtp(newOtp)

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

    const handleVerify = (event) => {
        event.preventDefault()

        const enteredOtp = otp.join('')

        if (enteredOtp.length !== 6) {
            return
        }

        // Temporary navigation.
        // Real OTP verification will be connected later.
        navigate('/login')
    }

    const handleResend = () => {
        // Temporary action.
        // Real OTP resend will be connected later.
        console.log('OTP resent')
    }

    return (
        <AuthLayout>
            <div className="auth-card">
                <div className="auth-card-header">
                    <h2>Verify your account</h2>

                    <p>
                        We've sent a 6-digit verification code to your
                        email or phone number.
                    </p>
                </div>

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
                                    handleChange(index, event.target.value)
                                }
                                onKeyDown={(event) =>
                                    handleKeyDown(index, event)
                                }
                                className="otp-input"
                                aria-label={`OTP digit ${index + 1}`}
                            />
                        ))}
                    </div>

                    <button
                        type="submit"
                        className="auth-primary-button"
                    >
                        Verify OTP
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