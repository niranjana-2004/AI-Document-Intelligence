import { Link, useNavigate } from 'react-router-dom'
import AuthLayout from '../../layouts/AuthLayout'

function ResetPassword() {
    const navigate = useNavigate()

    const handleReset = (event) => {
        event.preventDefault()

        // Temporary frontend navigation.
        // Real password reset will be connected to the backend later.
        navigate('/password-reset-success')
    }

    return (
        <AuthLayout>
            <div className="auth-card">
                <div className="auth-card-header">
                    <h2>Reset your password</h2>

                    <p>
                        Create a new password for your account.
                    </p>
                </div>

                <form onSubmit={handleReset}>
                    <div className="form-group">
                        <label htmlFor="newPassword">
                            New password
                        </label>

                        <input
                            id="newPassword"
                            type="password"
                            placeholder="Enter your new password"
                            required
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
                            required
                        />
                    </div>

                    <button
                        type="submit"
                        className="auth-primary-button"
                    >
                        Reset password
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