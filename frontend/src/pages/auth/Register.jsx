import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../layouts/AuthLayout'

function Register() {
    const navigate = useNavigate()

    const handleRegister = (event) => {
        event.preventDefault()

        // Temporary navigation.
        // OTP verification will be connected later.
        navigate('/otp')
    }

    return (
        <AuthLayout>
            <div className="auth-card">
                <div className="auth-card-header">
                    <h2>Create your account</h2>

                    <p>
                        Create an account to manage and analyze your documents.
                    </p>
                </div>

                <form onSubmit={handleRegister}>
                    <div className="form-group">
                        <label htmlFor="fullName">
                            Full name
                        </label>

                        <input
                            id="fullName"
                            type="text"
                            placeholder="Enter your full name"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="registerEmail">
                            Email
                        </label>

                        <input
                            id="registerEmail"
                            type="email"
                            placeholder="you@example.com"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="phone">
                            Phone number
                        </label>

                        <input
                            id="phone"
                            type="tel"
                            placeholder="Enter your phone number"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="registerPassword">
                            Password
                        </label>

                        <input
                            id="registerPassword"
                            type="password"
                            placeholder="Create a password"
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="confirmPassword">
                            Confirm password
                        </label>

                        <input
                            id="confirmPassword"
                            type="password"
                            placeholder="Confirm your password"
                            required
                        />
                    </div>

                    <button
                        type="submit"
                        className="auth-primary-button"
                    >
                        Create account
                    </button>
                </form>

                <div className="auth-divider">
                    <span>OR</span>
                </div>

                <p className="auth-switch">
                    Already have an account?{' '}
                    <Link to="/login">
                        Sign in
                    </Link>
                </p>
            </div>
        </AuthLayout>
    )
}

export default Register