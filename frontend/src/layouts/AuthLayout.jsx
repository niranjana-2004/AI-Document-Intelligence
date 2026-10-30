import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'motion/react'
import { Sun, Moon, ShieldCheck } from 'lucide-react'
import CognidocsLogo from '../components/CognidocsLogo'
import ParticleNetwork from '../components/motion/ParticleNetwork'
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

            {/* Interactive floating particle field */}
            <ParticleNetwork particleCount={35} maxDistance={110} interactive={false} />

            <div className="auth-top-bar" style={{ position: 'relative', zIndex: 10 }}>
                <Link to="/" className="auth-brand" title="Back to Cognidocs Home">
                    <motion.div
                        className="auth-logo"
                        whileHover={{ rotate: 15, scale: 1.08 }}
                        transition={{ type: 'spring', stiffness: 300 }}
                    >
                        <CognidocsLogo />
                    </motion.div>

                    <div>
                        <h1>Cognidocs</h1>
                        <p>Knowledge, unlocked.</p>
                    </div>
                </Link>

                <motion.button
                    type="button"
                    className="auth-theme-toggle"
                    onClick={toggleTheme}
                    whileHover={{ scale: 1.08 }}
                    whileTap={{ scale: 0.94 }}
                    title={currentTheme === 'dark' ? 'Switch to Light mode' : 'Switch to Dark mode'}
                    aria-label="Toggle visual theme"
                >
                    {currentTheme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
                </motion.button>
            </div>

            <motion.div
                className="auth-content"
                initial={{ opacity: 0, scale: 0.97, y: 16 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
                style={{ position: 'relative', zIndex: 10 }}
            >
                {children}
            </motion.div>

            <p className="auth-footer" style={{ position: 'relative', zIndex: 10 }}>
                <ShieldCheck size={14} className="auth-footer-shield" />
                <span>
                    Private, verified, context-grounded retrieval. Powered by Cognidocs Intelligence Engine.
                </span>
            </p>
        </div>
    )
}

export default AuthLayout
