import { NavLink, useNavigate } from 'react-router-dom'
import '../styles/app-layout.css'

function AppLayout({ children }) {
    const navigate = useNavigate()

    const handleLogout = () => {
        navigate('/login')
    }

    return (
        <div className="app-layout">

            {/* Sidebar */}
            <aside className="app-sidebar">

                {/* Brand */}
                <div className="app-brand">
                    <div className="app-logo">
                        AI
                    </div>

                    <div className="app-brand-text">
                        <h1>Document Intelligence</h1>
                        <span>AI-powered workspace</span>
                    </div>
                </div>

                {/* Navigation */}
                <nav className="app-navigation">

                    <p className="nav-section-title">
                        Workspace
                    </p>

                    <NavLink
                        to="/dashboard"
                        className="nav-item"
                    >
                        <span className="nav-icon">⌂</span>
                        <span>Dashboard</span>
                    </NavLink>

                    <NavLink
                        to="/documents"
                        className="nav-item"
                    >
                        <span className="nav-icon">▤</span>
                        <span>Documents</span>
                    </NavLink>

                    <NavLink
                        to="/ask-ai"
                        className="nav-item"
                    >
                        <span className="nav-icon">✦</span>
                        <span>Ask AI</span>
                    </NavLink>

                    <NavLink
                        to="/search"
                        className="nav-item"
                    >
                        <span className="nav-icon">⌕</span>
                        <span>Search</span>
                    </NavLink>

                    <p className="nav-section-title nav-section-spaced">
                        Account
                    </p>

                    <NavLink
                        to="/profile"
                        className="nav-item"
                    >
                        <span className="nav-icon">◯</span>
                        <span>Profile</span>
                    </NavLink>

                    <NavLink
                        to="/about"
                        className="nav-item"
                    >
                        <span className="nav-icon">ⓘ</span>
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
                        <span className="nav-icon">↪</span>
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
                                AI
                            </div>

                            <span>
                                Document Intelligence
                            </span>
                        </div>
                    </div>

                    <div className="topbar-right">

                        <button
                            type="button"
                            className="topbar-icon-button"
                            title="Notifications"
                        >
                            ♢
                        </button>

                        <button
                            type="button"
                            className="profile-button"
                            onClick={() => navigate('/profile')}
                        >
                            <span className="profile-avatar">
                                N
                            </span>

                            <span className="profile-name">
                                User
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