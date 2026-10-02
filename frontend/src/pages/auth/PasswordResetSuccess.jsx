import { Link } from 'react-router-dom'
import AuthLayout from '../../layouts/AuthLayout'

function PasswordResetSuccess() {
    return (
        <AuthLayout>
            <div className="auth-card success-card">
                <div className="success-icon">
                    ✓
                </div>

                <div className="auth-card-header success-header">
                    <h2>Password reset successful</h2>

                    <p>
                        Your password has been changed successfully.
                        You can now sign in with your new password.
                    </p>
                </div>

                <Link
                    to="/login"
                    className="auth-primary-button success-login-button"
                >
                    Go to Login
                </Link>
            </div>
        </AuthLayout>
    )
}

export default PasswordResetSuccess