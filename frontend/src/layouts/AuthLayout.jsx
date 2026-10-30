import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Sun, Moon, ShieldCheck } from 'lucide-react'
import CognidocsLogo from '../components/CognidocsLogo'
import '../styles/auth.css'

function AuthLayout({ children }) {
    const [currentTheme, setCurrentTheme] = useState(() => {
        return typeof window !== 'undefined'
            ? localStorage.getItem('app_theme') || 'ocean'
            : 'ocean'
    })

    const toggleTheme = () => {
        const nextTheme = currentTheme === 'dark' ? 'ocean' : 'dark'
        setCurrentTheme(nextTheme)
        localStorage.setItem('app_theme', nextTheme)
        document.documentElement.dataset.theme = nextTheme
    }

    return (
        <div className="auth-page">
            {/* Ambient lighting effects */}
            <div
                className="ambient-orb ambient-orb-violet"
                style={{ width: 450, height: 450, top: '-50px', left: '15%' }}
            />
            <div
                className="ambient-orb ambient-orb-cyan"
                style={{ width: 450, height: 450, bottom: '0px', right: '15%' }}
            />

            <div className="auth-top-bar">
                <Link to="/" className="auth-brand" title="Back to Cognidocs Home">
                    <div className="auth-logo">
                        <CognidocsLogo />
                    </div>

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
                    {currentTheme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
                </button>
            </div>

            <div className="auth-content">
                {children}
            </div>

            <p className="auth-footer">
                <ShieldCheck size={14} className="auth-footer-shield" />
                <span>Cognidocs · Privacy-First Local AI Document Intelligence</span>
            </p>
        </div>
    )
}

export default AuthLayout
