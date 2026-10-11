import { useState, useEffect } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import '../styles/app-layout.css'

function AppLayout({ children }) {
    const navigate = useNavigate()

    const [currentTheme, setCurrentTheme] = useState(() => {
        if (typeof document !== 'undefined' && document.documentElement.dataset.theme) {
            return document.documentElement.dataset.theme
        }
        return localStorage.getItem('app_theme') || 'ocean'
    })

    useEffect(() => {
        const syncTheme = () => {
            const activeTheme =
                document.documentElement.dataset.theme ||
                localStorage.getItem('app_theme') ||
                'ocean'
            setCurrentTheme(activeTheme)
        }

        syncTheme()

        // Observe changes to document.documentElement.dataset.theme
        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                if (
                    mutation.type === 'attributes' &&
                    mutation.attributeName === 'data-theme'
                ) {
                    syncTheme()
                }
            }
        })

        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['data-theme'],
        })

        // Also synchronize cross-tab storage changes
        const handleStorage = (event) => {
            if (event.key === 'app_theme') {
                syncTheme()
            }
        }

        window.addEventListener('storage', handleStorage)

        return () => {
            observer.disconnect()
            window.removeEventListener('storage', handleStorage)
        }
    }, [])

    const toggleTheme = () => {
        const activeTheme =
            document.documentElement.dataset.theme ||
            localStorage.getItem('app_theme') ||
            currentTheme ||
            'ocean'

        // If current active theme is Ocean, switch to Dark; otherwise switch to Ocean.
        const nextTheme = activeTheme === 'ocean' ? 'dark' : 'ocean'
        setCurrentTheme(nextTheme)
        localStorage.setItem('app_theme', nextTheme)
        document.documentElement.dataset.theme = nextTheme
    }

    let user = null
    const storedUser = localStorage.getItem('user')

    if (storedUser) {
        try {
            user = JSON.parse(storedUser)
        } catch {
            user = null
        }
    }

    const handleLogout = () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')
        navigate('/login', { replace: true })
    }

    return (
        <div className="app-layout">

            {/* Sidebar */}
            <aside className="app-sidebar">

                {/* Brand */}
                <div className="app-brand">
                    <div className="app-logo">
                        CD
                    </div>

                    <div className="app-brand-text">
                        <h1>Cognidocs</h1>
                        <span>Knowledge, unlocked.</span>
                    </div>
                </div>

                {/* Navigation */}
                <nav className="app-navigation" aria-label="Workspace navigation">

                    <p className="nav-section-title">
                        Workspace
                    </p>

                    <NavLink
                        to="/dashboard"
                        className="nav-item"
                    >
                        <span className="nav-icon" aria-hidden="true">⌂</span>
                        <span>Dashboard</span>
                    </NavLink>

                    <NavLink
                        to="/documents"
                        className="nav-item"
                    >
                        <span className="nav-icon" aria-hidden="true">▤</span>
                        <span>Documents</span>
                    </NavLink>

                    <NavLink
                        to="/ask-ai"
                        className="nav-item"
                    >
                        <span className="nav-icon" aria-hidden="true">✦</span>
                        <span>Ask AI</span>
                    </NavLink>

                    <NavLink
                        to="/search"
                        className="nav-item"
                    >
                        <span className="nav-icon" aria-hidden="true">⌕</span>
                        <span>Search</span>
                    </NavLink>

                    <p className="nav-section-title nav-section-spaced">
                        Account
                    </p>

                    <NavLink
                        to="/profile"
                        className="nav-item"
                    >
                        <span className="nav-icon" aria-hidden="true">◯</span>
                        <span>Profile</span>
                    </NavLink>

                    <NavLink
                        to="/about"
                        className="nav-item"
                    >
                        <span className="nav-icon" aria-hidden="true">ⓘ</span>
                        <span>About</span>
                    </NavLink>

                </nav>

                {/* Sidebar Bottom */}
                <div className="sidebar-bottom">

                    <button
                        type="button"
                        className="logout-button"
                        onClick={handleLogout}
                    >
                        <span className="nav-icon" aria-hidden="true">↪</span>
                        <span>Logout</span>
                    </button>

                </div>

            </aside>

            {/* Main Area */}
            <div className="app-main">

                {/* Top Bar */}
                <header className="app-topbar">

                    <div className="topbar-left">
                        <div className="mobile-brand">
                            <div className="app-logo small-logo">
                                CD
                            </div>

                            <span>
                                Cognidocs
                            </span>
                        </div>
                    </div>

                    <div className="topbar-right">

                        <button
                            type="button"
                            className="theme-toggle-btn"
                            onClick={toggleTheme}
                            title={currentTheme === 'ocean' ? 'Switch to Dark appearance' : 'Switch to Ocean Teal appearance'}
                            aria-label={`Toggle appearance. Currently ${currentTheme}.`}
                        >
                            <span className="theme-toggle-icon" aria-hidden="true">
                                {currentTheme === 'dark' ? '☀️' : '🌙'}
                            </span>
                            <span className="theme-toggle-label">
                                {currentTheme === 'dark' ? 'Light' : 'Dark'}
                            </span>
                        </button>

                        <button
                            type="button"
                            className="topbar-icon-button"
                            title="Notifications"
                            aria-label="Notifications"
                        >
                            ♢
                        </button>

                        <button
                            type="button"
                            className="profile-button"
                            onClick={() => navigate('/profile')}
                            aria-label="View user profile"
                        >
                            <span className="profile-avatar">
                                {user?.full_name
                                    ? user.full_name.charAt(0).toUpperCase()
                                    : 'U'}
                            </span>

                            <span className="profile-name">
                                {user?.full_name || 'User'}
                            </span>
                        </button>

                    </div>

                </header>

                {/* Page Content */}
                <main className="app-content">
                    {children}
                </main>

            </div>

        </div>
    )
}

export default AppLayout