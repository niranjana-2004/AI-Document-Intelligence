import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiRequest } from '../services/api'
import '../App.css'

function Profile() {
    const navigate = useNavigate()
    const handleLogout = () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')

        navigate('/login', { replace: true })
    }

    const [user, setUser] = useState(null)
    const [showEditModal, setShowEditModal] = useState(false)
    const [editName, setEditName] = useState('')
    const [editEmail, setEditEmail] = useState('')
    const [editPhone, setEditPhone] = useState('')
    const [phoneError, setPhoneError] = useState('')
    const [editError, setEditError] = useState('')
    const [showPasswordModal, setShowPasswordModal] = useState(false)
    const [currentPassword, setCurrentPassword] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [passwordError, setPasswordError] = useState('')
    const [passwordSuccess, setPasswordSuccess] = useState('')
    const [passwordLoading, setPasswordLoading] = useState(false)
    const [theme, setTheme] = useState(
        () => localStorage.getItem('app_theme') || 'ocean'
    )

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
                    onClick={() => {
                        setEditName(user?.full_name || '')
                        setEditEmail(user?.email || '')
                        setEditPhone(user?.phone || '')
                        setEditError('')
                        setShowEditModal(true)
                    }}
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
                                {user?.phone || 'Not added'}
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
                                onClick={() => {
                                    setCurrentPassword('')
                                    setNewPassword('')
                                    setConfirmPassword('')
                                    setPasswordError('')
                                    setPasswordSuccess('')
                                    setShowPasswordModal(true)
                                }}
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

                            <span
                                className={`verification-badge ${user?.is_verified ? 'verification-verified' : 'verification-not-verified'
                                    }`}
                            >
                                {user?.is_verified ? 'Verified' : 'Not verified'}
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
                                value={theme}
                                onChange={(e) => {
                                    const newTheme = e.target.value

                                    setTheme(newTheme)
                                    localStorage.setItem('app_theme', newTheme)
                                    document.documentElement.dataset.theme = newTheme
                                }}
                            >
                                <option value="ocean">🌊 Ocean Teal</option>
                                <option value="dark">🌙 Dark</option>
                                <option value="forest">🌿 Forest</option>
                                <option value="rose">🌸 Rose</option>
                                <option value="lavender">💜 Lavender</option>
                                <option value="sand">🌅 Warm Sand</option>
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
            {showEditModal && (
                <div className="profile-modal-overlay">
                    <div className="profile-modal">

                        <div className="profile-modal-header">
                            <div>
                                <p className="eyebrow">
                                    ACCOUNT
                                </p>

                                <h3>Edit Profile</h3>
                            </div>

                            <button
                                type="button"
                                className="profile-modal-close"
                                onClick={() => setShowEditModal(false)}
                            >
                                ×
                            </button>
                        </div>

                        <div className="profile-modal-body">

                            <div className="profile-form-field">
                                <label htmlFor="edit-name">
                                    Full Name
                                </label>

                                <input
                                    id="edit-name"
                                    type="text"
                                    value={editName}
                                    onChange={(event) => setEditName(event.target.value)}
                                    placeholder="Enter your full name"
                                />
                            </div>


                            <div className="profile-form-field">
                                <label htmlFor="edit-email">
                                    Email
                                </label>

                                <input
                                    id="edit-email"
                                    type="email"
                                    value={editEmail}
                                    onChange={(event) => setEditEmail(event.target.value)}
                                    placeholder="Enter your email address"
                                />

                                <small>
                                    Changing your email may require verification.
                                </small>
                            </div>


                            <div className="profile-form-field">
                                <label htmlFor="edit-phone">
                                    Phone Number
                                </label>

                                <input
                                    id="edit-phone"
                                    type="tel"
                                    value={editPhone}
                                    onChange={(event) => {
                                        const value = event.target.value
                                        setEditPhone(value)

                                        if (!/^\d*$/.test(value)) {
                                            setPhoneError('Phone number can contain digits only.')
                                        } else if (value.length > 10) {
                                            setPhoneError('Phone number must contain exactly 10 digits.')
                                        } else {
                                            setPhoneError('')
                                        }
                                    }}
                                    placeholder="Enter your phone number"
                                />

                                {phoneError && (
                                    <p className="profile-form-error">
                                        {phoneError}
                                    </p>
                                )}
                            </div>

                        </div>

                        <div className="profile-modal-actions">

                            <button
                                type="button"
                                className="profile-secondary-button"
                                onClick={() => setShowEditModal(false)}
                            >
                                Cancel
                            </button>

                            <button
                                type="button"
                                className="profile-primary-button"
                                onClick={async () => {
                                    if (!/^\d{10}$/.test(editPhone)) {
                                        setPhoneError('Phone number must contain exactly 10 digits.')
                                        return
                                    }

                                    try {
                                        setPhoneError('')

                                        const data = await apiRequest('/auth/profile', {
                                            method: 'PUT',
                                            body: JSON.stringify({
                                                full_name: editName.trim(),
                                                phone: editPhone,
                                            }),
                                        })

                                        const updatedUser = data.user

                                        setUser(updatedUser)
                                        localStorage.setItem('user', JSON.stringify(updatedUser))

                                        setShowEditModal(false)
                                    } catch (error) {
                                        setPhoneError(error.message)
                                    }
                                }}
                            >
                                Save Changes
                            </button>

                        </div>

                    </div>
                </div>
            )}
            {showPasswordModal && (
                <div className="profile-modal-overlay">
                    <div className="profile-modal">

                        <div className="profile-modal-header">
                            <div>
                                <h3>Change Password</h3>
                                <p>Update your account password.</p>
                            </div>

                            <button
                                type="button"
                                className="profile-modal-close"
                                onClick={() => setShowPasswordModal(false)}
                            >
                                ×
                            </button>
                        </div>

                        {passwordError && (
                            <p className="profile-form-error">
                                {passwordError}
                            </p>
                        )}

                        {passwordSuccess && (
                            <p className="profile-form-success">
                                {passwordSuccess}
                            </p>
                        )}

                        <div className="profile-form-field">
                            <label htmlFor="current-password">
                                Current Password
                            </label>

                            <input
                                id="current-password"
                                type="password"
                                value={currentPassword}
                                onChange={(event) =>
                                    setCurrentPassword(event.target.value)
                                }
                                placeholder="Enter your current password"
                            />
                        </div>

                        <div className="profile-form-field">
                            <label htmlFor="new-password">
                                New Password
                            </label>

                            <input
                                id="new-password"
                                type="password"
                                value={newPassword}
                                onChange={(event) =>
                                    setNewPassword(event.target.value)
                                }
                                placeholder="Enter your new password"
                            />
                        </div>

                        <div className="profile-form-field">
                            <label htmlFor="confirm-password">
                                Confirm New Password
                            </label>

                            <input
                                id="confirm-password"
                                type="password"
                                value={confirmPassword}
                                onChange={(event) =>
                                    setConfirmPassword(event.target.value)
                                }
                                placeholder="Confirm your new password"
                            />
                        </div>

                        <div className="profile-modal-actions">

                            <button
                                type="button"
                                className="profile-secondary-button"
                                onClick={() => setShowPasswordModal(false)}
                            >
                                Cancel
                            </button>

                            <button
                                type="button"
                                className="profile-primary-button"
                                disabled={passwordLoading}
                                onClick={async () => {

                                    setPasswordError('')
                                    setPasswordSuccess('')

                                    if (!currentPassword) {
                                        setPasswordError(
                                            'Please enter your current password.'
                                        )
                                        return
                                    }

                                    if (!newPassword) {
                                        setPasswordError(
                                            'Please enter a new password.'
                                        )
                                        return
                                    }

                                    if (newPassword.length < 8) {
                                        setPasswordError(
                                            'New password must be at least 8 characters.'
                                        )
                                        return
                                    }

                                    if (newPassword !== confirmPassword) {
                                        setPasswordError(
                                            'New passwords do not match.'
                                        )
                                        return
                                    }

                                    setPasswordLoading(true)

                                    try {
                                        await apiRequest('/auth/change-password', {
                                            method: 'PUT',
                                            body: JSON.stringify({
                                                current_password: currentPassword,
                                                new_password: newPassword,
                                                confirm_password: confirmPassword,
                                            }),
                                        })

                                        setPasswordSuccess(
                                            'Password changed successfully.'
                                        )

                                        setCurrentPassword('')
                                        setNewPassword('')
                                        setConfirmPassword('')

                                    } catch (error) {
                                        setPasswordError(error.message)
                                    } finally {
                                        setPasswordLoading(false)
                                    }
                                }}
                            >
                                {passwordLoading
                                    ? 'Changing...'
                                    : 'Change Password'}
                            </button>

                        </div>

                    </div>
                </div>
            )}
        </main>
    )
}

export default Profile