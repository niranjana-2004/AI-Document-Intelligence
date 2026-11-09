import { useState, useEffect } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import {
    LayoutDashboard,
    Files,
    PenTool,
    Sparkles,
    Search,
    ArrowLeftRight,
    Network,
    User,
    Info,
    LogOut,
    Sun,
    Moon,
    Bell,
    Menu,
    X,
} from 'lucide-react'
import CognidocsLogo from '../components/CognidocsLogo'
import PageTransition from '../components/motion/PageTransition'
import '../styles/app-layout.css'

const THEME_NAMES = {
    ocean: 'Ocean Teal',
    dark: 'Dark Slate',
    forest: 'Forest Green',
    rose: 'Rose Pink',
    lavender: 'Lavender Purple',
    sand: 'Warm Sand',
}

function AppLayout({ children }) {
    const navigate = useNavigate()
    const location = useLocation()
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

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

    // Close mobile menu whenever location changes
    const [prevPath, setPrevPath] = useState(location.pathname)
    if (prevPath !== location.pathname) {
        setPrevPath(location.pathname)
        setMobileMenuOpen(false)
    }

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
        <div className={`app-layout ${mobileMenuOpen ? 'mobile-menu-active' : ''}`}>
            {/* Mobile backdrop */}
            {mobileMenuOpen && (
                <div
                    className="app-mobile-backdrop"
                    onClick={() => setMobileMenuOpen(false)}
                    aria-hidden="true"
                />
            )}

            {/* Sidebar */}
            <aside className={`app-sidebar ${mobileMenuOpen ? 'mobile-drawer-open' : ''}`}>
                {/* Brand */}
                <div className="app-brand">
                    <div className="app-logo">
                        <CognidocsLogo />
                    </div>

                    <div className="app-brand-text">
                        <h1>Cognidocs</h1>
                        <span>Knowledge, unlocked.</span>
                    </div>

                    {/* Close button inside mobile drawer */}
                    <button
                        type="button"
                        className="mobile-sidebar-close"
                        onClick={() => setMobileMenuOpen(false)}
                        aria-label="Close navigation"
                    >
                        <X size={18} />
                    </button>
                </div>

                {/* Navigation */}
                <nav className="app-navigation" aria-label="Workspace navigation">
                    <p className="nav-section-title">
                        Workspace
                    </p>

                    <NavLink
                        to="/dashboard"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <span className="nav-icon" aria-hidden="true">
                            <LayoutDashboard size={18} />
                        </span>
                        <span>Dashboard</span>
                    </NavLink>

                    <NavLink
                        to="/documents"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <span className="nav-icon" aria-hidden="true">
                            <Files size={18} />
                        </span>
                        <span>Documents</span>
                    </NavLink>

                    <NavLink
                        to="/handwritten"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <span className="nav-icon" aria-hidden="true">
                            <PenTool size={18} />
                        </span>
                        <span className="nav-label-with-badge">
                            <span>Handwritten</span>
                            <span className="nav-badge-ai" style={{ background: 'linear-gradient(135deg, #8b5cf6, #38bdf8)' }}>OCR</span>
                        </span>
                    </NavLink>

                    <NavLink
                        to="/compare"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <span className="nav-icon" aria-hidden="true">
                            <ArrowLeftRight size={18} />
                        </span>
                        <span className="nav-label-with-badge">
                            <span>Compare</span>
                            <span className="nav-badge-ai" style={{ background: 'linear-gradient(135deg, #0ea5e9, #6366f1)' }}>AI</span>
                        </span>
                    </NavLink>

                    <NavLink
                        to="/mind-map"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <span className="nav-icon" aria-hidden="true">
                            <Network size={18} />
                        </span>
                        <span className="nav-label-with-badge">
                            <span>Mind Map</span>
                            <span className="nav-badge-ai" style={{ background: 'linear-gradient(135deg, #8b5cf6, #0ea5e9)' }}>AI</span>
                        </span>
                    </NavLink>

                    <NavLink
                        to="/ask-ai"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <span className="nav-icon" aria-hidden="true">
                            <Sparkles size={18} />
                        </span>
                        <span className="nav-label-with-badge">
                            <span>Ask AI</span>
                            <span className="nav-badge-ai">AI</span>
                        </span>
                    </NavLink>

                    <NavLink
                        to="/search"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <span className="nav-icon" aria-hidden="true">
                            <Search size={18} />
                        </span>
                        <span>Search</span>
                    </NavLink>

                    <p className="nav-section-title nav-section-spaced">
                        Account
                    </p>

                    <NavLink
                        to="/profile"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <span className="nav-icon" aria-hidden="true">
                            <User size={18} />
                        </span>
                        <span>Profile</span>
                    </NavLink>

                    <NavLink
                        to="/about"
                        className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                    >
                        <span className="nav-icon" aria-hidden="true">
                            <Info size={18} />
                        </span>
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
                        <span className="nav-icon" aria-hidden="true">
                            <LogOut size={18} />
                        </span>
                        <span>Logout</span>
                    </button>
                </div>
            </aside>

            {/* Main Area */}
            <div className="app-main">
                {/* Top Bar */}
                <header className="app-topbar">
                    <div className="topbar-left">
                        {/* Mobile hamburger menu toggle */}
                        <button
                            type="button"
                            className="mobile-menu-toggle"
                            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
                        >
                            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
                        </button>

                        <div className="mobile-brand">
                            <div className="app-logo small-logo">
                                <CognidocsLogo />
                            </div>

                            <span>Cognidocs</span>
                        </div>

                        <div className="topbar-status-pill">
                            <span className="topbar-status-dot"></span>
                            <span className="topbar-status-text">Intelligence Engine Active</span>
                        </div>
                    </div>

                    <div className="topbar-right">
                        <button
                            type="button"
                            className="theme-toggle-btn"
                            onClick={toggleTheme}
                            title={currentTheme === 'ocean' ? 'Switch to Dark appearance' : 'Switch to Ocean Teal appearance'}
                            aria-label={`Toggle appearance. Currently ${THEME_NAMES[currentTheme] || currentTheme}.`}
                        >
                            <span className="theme-toggle-icon" aria-hidden="true">
                                {currentTheme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
                            </span>
                            <span className="theme-toggle-label">
                                {THEME_NAMES[currentTheme] || (currentTheme === 'dark' ? 'Dark Slate' : 'Ocean Teal')}
                            </span>
                        </button>

                        <button
                            type="button"
                            className="topbar-icon-button"
                            title="Workspace Notifications"
                            aria-label="Notifications"
                        >
                            <Bell size={17} />
                            <span className="notification-indicator"></span>
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

                {/* Page Content with animated transition */}
                <main className="app-content">
                    <PageTransition key={location.pathname}>
                        {children}
                    </PageTransition>
                </main>
            </div>
        </div>
    )
}

export default AppLayout
