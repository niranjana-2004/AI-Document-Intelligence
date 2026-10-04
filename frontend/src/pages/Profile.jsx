import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import '../App.css'

function Profile() {
    const navigate = useNavigate()

    const handleLogout = () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')

        navigate('/login', { replace: true })
    }

    const [user, setUser] = useState(null)

    useEffect(() => {
        const storedUser = localStorage.getItem('user')

        if (storedUser) {
            try {
                setUser(JSON.parse(storedUser))
            } catch {
                setUser(null)
            }
        }
    }, [])

    return (
        <main className="profile-page">

            {/* =================================
          PROFILE HEADER
      ================================= */}

            <section className="profile-header">

                <div className="profile-header-content">

                    <div className="profile-large-avatar">
                        {user?.full_name
                            ? user.full_name.charAt(0).toUpperCase()
                            : 'U'}
                    </div>

                    <div>

                        <p className="eyebrow">
                            ACCOUNT
                        </p>

                        <h2>
                            {user?.full_name || 'User'}
                        </h2>

                        <p>
                            {user?.email || 'No email available'}
                        </p>

                    </div>

                </div>

                <button
                    className="profile-edit-button"
                    type="button"
                >
                    Edit Profile
                </button>

            </section>


            {/* =================================
          PROFILE GRID
      ================================= */}

            <section className="profile-grid">

                {/* ===============================
            PERSONAL INFORMATION
        ================================ */}

                <div className="profile-card">

                    <div className="profile-card-header">

                        <div>

                            <h3>
                                Personal Information
                            </h3>

                            <p>
                                Your basic account information
                            </p>

                        </div>

                    </div>


                    <div className="profile-fields">

                        <div className="profile-field">

                            <span>
                                Full Name
                            </span>

                            <strong>
                                {user?.full_name || 'Not available'}
                            </strong>

                        </div>


                        <div className="profile-field">

                            <span>
                                Email
                            </span>

                            <strong>
                                {user?.email || 'Not available'}
                            </strong>

                        </div>


                        <div className="profile-field">

                            <span>
                                Phone
                            </span>

                            <strong>
                                Not added
                            </strong>

                        </div>


                        <div className="profile-field">

                            <span>
                                Account Type
                            </span>

                            <strong>
                                Standard
                            </strong>

                        </div>

                    </div>

                </div>


                {/* ===============================
            SECURITY
        ================================ */}

                <div className="profile-card">

                    <div className="profile-card-header">

                        <div>

                            <h3>
                                Security
                            </h3>

                            <p>
                                Manage your account security
                            </p>

                        </div>

                    </div>


                    <div className="security-list">

                        <div className="security-item">

                            <div>

                                <h4>
                                    Password
                                </h4>

                                <p>
                                    Your password is protected
                                    and securely stored.
                                </p>

                            </div>

                            <button
                                className="profile-secondary-button"
                                type="button"
                            >
                                Change
                            </button>

                        </div>


                        <div className="security-item">

                            <div>

                                <h4>
                                    Email Verification
                                </h4>

                                <p>
                                    Email verification status
                                </p>

                            </div>

                            <span className="verification-badge">
                                Not verified
                            </span>

                        </div>


                        <div className="security-item">

                            <div>

                                <h4>
                                    Two-Factor Authentication
                                </h4>

                                <p>
                                    Add an additional layer of
                                    account protection.
                                </p>

                            </div>

                            <span className="security-status">
                                Coming soon
                            </span>

                        </div>

                    </div>

                </div>


                {/* ===============================
            PREFERENCES
        ================================ */}

                <div className="profile-card">

                    <div className="profile-card-header">

                        <div>

                            <h3>
                                Preferences
                            </h3>

                            <p>
                                Customize your workspace
                            </p>

                        </div>

                    </div>


                    <div className="preference-list">

                        <div className="preference-item">

                            <div>

                                <h4>
                                    Appearance
                                </h4>

                                <p>
                                    Choose how the application
                                    looks.
                                </p>

                            </div>

                            <select
                                className="profile-select"
                                defaultValue="light"
                            >
                                <option value="light">
                                    Light
                                </option>

                                <option value="dark">
                                    Dark
                                </option>

                                <option value="system">
                                    System
                                </option>
                            </select>

                        </div>


                        <div className="preference-item">

                            <div>

                                <h4>
                                    Notifications
                                </h4>

                                <p>
                                    Receive important application
                                    notifications.
                                </p>

                            </div>

                            <label className="toggle">

                                <input
                                    type="checkbox"
                                    defaultChecked
                                />

                                <span className="toggle-slider"></span>

                            </label>

                        </div>

                    </div>

                </div>


                {/* ===============================
            ACCOUNT ACTIVITY
        ================================ */}

                <div className="profile-card">

                    <div className="profile-card-header">

                        <div>

                            <h3>
                                Account Activity
                            </h3>

                            <p>
                                Overview of your workspace
                                activity
                            </p>

                        </div>

                    </div>


                    <div className="activity-stats">

                        <div className="profile-stat">

                            <strong>
                                —
                            </strong>

                            <span>
                                Documents
                            </span>

                        </div>


                        <div className="profile-stat">

                            <strong>
                                —
                            </strong>

                            <span>
                                AI Questions
                            </span>

                        </div>


                        <div className="profile-stat">

                            <strong>
                                —
                            </strong>

                            <span>
                                Searches
                            </span>

                        </div>


                        <div className="profile-stat">

                            <strong>
                                —
                            </strong>

                            <span>
                                Summaries
                            </span>

                        </div>

                    </div>


                    <div className="account-details">

                        <div>

                            <span>
                                Account Created
                            </span>

                            <strong>
                                —
                            </strong>

                        </div>

                        <div>

                            <span>
                                Last Login
                            </span>

                            <strong>
                                —
                            </strong>

                        </div>

                    </div>

                </div>

            </section>


            {/* =================================
          ACCOUNT ACTIONS
      ================================= */}

            <section className="account-actions">

                <div>

                    <p className="eyebrow">
                        ACCOUNT MANAGEMENT
                    </p>

                    <h3>
                        Account Actions
                    </h3>

                    <p>
                        Manage your current session or
                        permanently remove your account.
                    </p>

                </div>


                <div className="account-action-buttons">

                    <button
                        className="logout-profile-button"
                        type="button"
                        onClick={handleLogout}
                    >
                        Log out
                    </button>

                    <button
                        className="delete-account-button"
                        type="button"
                    >
                        Delete Account
                    </button>

                </div>

            </section>

        </main>
    )
}

export default Profile