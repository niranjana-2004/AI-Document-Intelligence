import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import '../styles/auth.css'

function AuthLayout({ children }) {
    const [currentTheme, setCurrentTheme] = useState('ocean')

    useEffect(() => {
        const savedTheme = localStorage.getItem('app_theme') || 'ocean'
        setCurrentTheme(savedTheme)
    }, [])

    const toggleTheme = () => {
        const nextTheme = currentTheme === 'dark' ? 'ocean' : 'dark'
        setCurrentTheme(nextTheme)
        localStorage.setItem('app_theme', nextTheme)
        document.documentElement.dataset.theme = nextTheme
    }

    return (
        <div className="auth-page">
            <div className="auth-top-bar">
                <Link to="/" className="auth-brand" title="Back to Cognidocs Home">
                    <div className="auth-logo">CD</div>

                    <div>
                        <h1>Cognidocs</h1>
                        <p>Knowledge, unlocked.</p>
                    </div>
                </Link>

                <button
                    type="button"
                    className="auth-theme-toggle"
                    onClick={toggleTheme}
                    title={currentTheme === 'dark' ? 'Switch to Light mode' : 'Switch to Dark mode'}
                    aria-label="Toggle visual theme"
                >
                    {currentTheme === 'dark' ? '☀️' : '🌙'}
                </button>
            </div>

            <div className="auth-content">
                {children}
            </div>

            <p className="auth-footer">
                Cognidocs · Knowledge, unlocked. · Secure Local AI
            </p>
        </div>
    )
}

export default AuthLayout