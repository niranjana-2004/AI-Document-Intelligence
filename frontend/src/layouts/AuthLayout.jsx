import '../styles/auth.css'

function AuthLayout({ children }) {
    return (
        <div className="auth-page">
            <div className="auth-brand">
                <div className="auth-logo">AI</div>

                <div>
                    <h1>Document Intelligence</h1>
                    <p>Understand your documents with AI</p>
                </div>
            </div>

            <div className="auth-content">
                {children}
            </div>

            <p className="auth-footer">
                AI Document Intelligence · Secure document analysis
            </p>
        </div>
    )
}

export default AuthLayout