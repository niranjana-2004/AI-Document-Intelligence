import { Link } from 'react-router-dom'
import { CheckCircle2, ArrowRight } from 'lucide-react'
import AuthLayout from '../../layouts/AuthLayout'

function PasswordResetSuccess() {
    return (
        <AuthLayout>
            <div className="auth-card success-card">
                <div className="success-icon" aria-hidden="true">
                    <CheckCircle2 size={42} />
                </div>

                <div className="auth-card-header success-header">
                    <h2>Password reset successful</h2>

                    <p>
                        Your password has been changed successfully.
                        You can now sign in to Cognidocs with your new credentials.
                    </p>
                </div>

                <Link
                    to="/login"
                    className="auth-primary-button success-login-button"
                >
                    <span>Go to Login</span>
                    <ArrowRight size={16} />
                </Link>
            </div>
        </AuthLayout>
    )
}

export default PasswordResetSuccess
