import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiRequest } from '../services/api'
import '../App.css'

function Profile() {
    const navigate = useNavigate()

    const [user, setUser] = useState(null)
    const [activity, setActivity] = useState({
        documents: 0,
        ai_questions: 0,
        searches: 0,
        summaries: 0,
        account_created: null,
        last_login: null,
    })

    const [activityLoading, setActivityLoading] = useState(true)
    const [activityError, setActivityError] = useState('')

    // Edit Profile Modal State
    const [showEditModal, setShowEditModal] = useState(false)
    const [editName, setEditName] = useState('')
    const [editEmail, setEditEmail] = useState('')
    const [editPhone, setEditPhone] = useState('')
    const [phoneError, setPhoneError] = useState('')
    const [editLoading, setEditLoading] = useState(false)
    const [editError, setEditError] = useState('')

    // Password Modal State
    const [showPasswordModal, setShowPasswordModal] = useState(false)
    const [currentPassword, setCurrentPassword] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [confirmPassword, setConfirmPassword] = useState('')
    const [passwordError, setPasswordError] = useState('')
    const [passwordSuccess, setPasswordSuccess] = useState('')
    const [passwordLoading, setPasswordLoading] = useState(false)

    // Delete Account Modal State
    const [showDeleteModal, setShowDeleteModal] = useState(false)
    const [deleteLoading, setDeleteLoading] = useState(false)
    const [deleteError, setDeleteError] = useState('')

    // Theme Management State
    const [theme, setTheme] = useState(() => {
        if (typeof document !== 'undefined' && document.documentElement.dataset.theme) {
            return document.documentElement.dataset.theme
        }
        return localStorage.getItem('app_theme') || 'ocean'
    })

    // Notifications Preference State (explicit boolean persisted to localStorage)
    const [notificationsEnabled, setNotificationsEnabled] = useState(() => {
        return localStorage.getItem('notifications_enabled') !== 'false'
    })

    /* ========================================
       LOAD USER FROM STORAGE
    ======================================== */
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

    /* ========================================
       FETCH ACCOUNT ACTIVITY
    ======================================== */
    useEffect(() => {
        let isMounted = true

        const fetchActivity = async () => {
            try {
                setActivityLoading(true)
                setActivityError('')

                const data = await apiRequest('/auth/activity')

                if (isMounted) {
                    setActivity(data)
                }
            } catch (error) {
                if (isMounted) {
                    setActivityError(
                        error.message || 'Unable to load account activity.'
                    )
                }
            } finally {
                if (isMounted) {
                    setActivityLoading(false)
                }
            }
        }

        fetchActivity()

        return () => {
            isMounted = false
        }
    }, [])

    /* ========================================
       THEME SYNCHRONIZATION WITH DOM & STORAGE
    ======================================== */
    useEffect(() => {
        const syncTheme = () => {
            const activeTheme =
                document.documentElement.dataset.theme ||
                localStorage.getItem('app_theme') ||
                'ocean'
            setTheme(activeTheme)
        }

        syncTheme()

        // Observe external changes to data-theme (such as AppLayout header toggle)
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

        // Synchronize cross-tab storage changes
        const handleStorage = (event) => {
            if (event.key === 'app_theme') {
                syncTheme()
            }
            if (event.key === 'notifications_enabled') {
                setNotificationsEnabled(event.newValue !== 'false')
            }
        }

        window.addEventListener('storage', handleStorage)

        return () => {
            observer.disconnect()
            window.removeEventListener('storage', handleStorage)
        }
    }, [])

    const handleThemeChange = (newTheme) => {
        setTheme(newTheme)
        localStorage.setItem('app_theme', newTheme)
        document.documentElement.dataset.theme = newTheme
    }

    const handleNotificationsChange = (event) => {
        const checked = event.target.checked
        setNotificationsEnabled(checked)
        localStorage.setItem('notifications_enabled', String(checked))
    }

    /* ========================================
       LOGOUT ACTION
    ======================================== */
    const handleLogout = () => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')
        navigate('/login', { replace: true })
    }

    const formatActivityDate = (value) => {
        if (!value) {
            return 'Not available'
        }

        const date = new Date(value)
        if (Number.isNaN(date.getTime())) {
            return 'Not available'
        }

        return date.toLocaleString(undefined, {
            dateStyle: 'medium',
            timeStyle: 'short',
        })
    }

    return (
        <main className="profile-page">
            {/* =================================
                PROFILE HEADER
            ================================= */}
            <section className="profile-header">
                <div className="profile-header-content">
                    <div className="profile-large-avatar" aria-hidden="true">
                        {user?.full_name
                            ? user.full_name.charAt(0).toUpperCase()
                            : 'U'}
                    </div>

                    <div>
                        <p className="eyebrow">COGNIDOCS ACCOUNT</p>
                        <h2>{user?.full_name || 'Cognidocs User'}</h2>
                        <p>{user?.email || 'No email associated'}</p>
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
                        setPhoneError('')
                        setShowEditModal(true)
                    }}
                    aria-label="Edit Profile"
                >
                    Edit Profile
                </button>
            </section>

            {/* =================================
                PROFILE GRID
            ================================= */}
            <section className="profile-grid">
                {/* PERSONAL INFORMATION */}
                <div className="profile-card">
                    <div className="profile-card-header">
                        <div>
                            <h3>Personal Information</h3>
                            <p>Your verified account identity and details</p>
                        </div>
                    </div>

                    <div className="profile-fields">
                        <div className="profile-field">
                            <span>Full Name</span>
                            <strong>{user?.full_name || 'Not available'}</strong>
                        </div>

                        <div className="profile-field">
                            <span>Email</span>
                            <strong>{user?.email || 'Not available'}</strong>
                        </div>

                        <div className="profile-field">
                            <span>Phone Number</span>
                            <strong>{user?.phone || 'Not added'}</strong>
                        </div>

                        <div className="profile-field">
                            <span>Account Tier</span>
                            <strong className="profile-tier-badge">Standard Tier</strong>
                        </div>
                    </div>
                </div>

                {/* SECURITY */}
                <div className="profile-card">
                    <div className="profile-card-header">
                        <div>
                            <h3>Security & Authentication</h3>
                            <p>Manage passwords, verification, and credentials</p>
                        </div>
                    </div>

                    <div className="security-list">
                        <div className="security-item">
                            <div>
                                <h4>Password Protection</h4>
                                <p>Encrypted password stored with secure cryptographic hashing.</p>
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
                                Change Password
                            </button>
                        </div>

                        <div className="security-item">
                            <div>
                                <h4>Email Verification</h4>
                                <p>Verification status confirmed with OTP verification.</p>
                            </div>

                            <span
                                className={`verification-badge ${
                                    user?.is_verified
                                        ? 'verification-verified'
                                        : 'verification-not-verified'
                                }`}
                            >
                                {user?.is_verified ? '✓ Verified' : 'Not verified'}
                            </span>
                        </div>

                        <div className="security-item">
                            <div>
                                <h4>Two-Factor Authentication</h4>
                                <p>Additional verification layer for high-security sign-ins.</p>
                            </div>

                            <span className="security-status-badge">
                                Coming Soon
                            </span>
                        </div>
                    </div>
                </div>

                {/* PREFERENCES */}
                <div className="profile-card">
                    <div className="profile-card-header">
                        <div>
                            <h3>Workspace Preferences</h3>
                            <p>Customize your theme and visual workspace experience</p>
                        </div>
                    </div>

                    <div className="preference-list">
                        <div className="preference-item">
                            <div>
                                <h4>Theme & Accent Palette</h4>
                                <p>Switch between six curated Cognidocs visual themes.</p>
                            </div>

                            <div className="theme-selector-wrap">
                                <select
                                    className="profile-select"
                                    value={theme}
                                    onChange={(e) => handleThemeChange(e.target.value)}
                                    aria-label="Select application theme"
                                >
                                    <option value="ocean">🌊 Ocean Teal (Default)</option>
                                    <option value="dark">🌙 Dark Slate</option>
                                    <option value="forest">🌿 Forest Green</option>
                                    <option value="rose">🌸 Rose Pink</option>
                                    <option value="lavender">💜 Lavender Purple</option>
                                    <option value="sand">🌅 Warm Sand</option>
                                </select>
                            </div>
                        </div>

                        <div className="preference-item">
                            <div>
                                <h4>Workspace Notifications</h4>
                                <p>In-app alerts and processing status banners.</p>
                            </div>

                            <label className="toggle" aria-label="Toggle workspace notifications">
                                <input
                                    type="checkbox"
                                    checked={notificationsEnabled}
                                    onChange={handleNotificationsChange}
                                />
                                <span className="toggle-slider"></span>
                            </label>
                        </div>
                    </div>
                </div>

                {/* ACCOUNT ACTIVITY */}
                <div className="profile-card">
                    <div className="profile-card-header">
                        <div>
                            <h3>Account Activity</h3>
                            <p>Overview of your knowledge base engagement</p>
                        </div>
                    </div>

                    <div className="activity-stats">
                        <div className="profile-stat">
                            <strong>
                                {activityLoading ? '...' : activity.documents}
                            </strong>
                            <span>Documents</span>
                        </div>

                        <div className="profile-stat">
                            <strong>
                                {activityLoading ? '...' : activity.ai_questions}
                            </strong>
                            <span>AI Queries</span>
                        </div>

                        <div className="profile-stat">
                            <strong>
                                {activityLoading ? '...' : activity.searches}
                            </strong>
                            <span>Searches</span>
                        </div>

                        <div className="profile-stat">
                            <strong>
                                {activityLoading ? '...' : activity.summaries}
                            </strong>
                            <span>Summaries</span>
                        </div>
                    </div>

                    {activityError && (
                        <p className="profile-form-error" role="alert">
                            {activityError}
                        </p>
                    )}

                    <div className="account-details">
                        <div>
                            <span>Account Created</span>
                            <strong>
                                {activityLoading
                                    ? 'Loading...'
                                    : formatActivityDate(activity.account_created)}
                            </strong>
                        </div>

                        <div>
                            <span>Last Active Session</span>
                            <strong>
                                {activityLoading
                                    ? 'Loading...'
                                    : formatActivityDate(activity.last_login)}
                            </strong>
                        </div>
                    </div>
                </div>
            </section>

            {/* =================================
                ACCOUNT ACTIONS (DANGER ZONE)
            ================================= */}
            <section className="account-actions">
                <div>
                    <p className="eyebrow">SESSION & ACCOUNT DANGER ZONE</p>
                    <h3>Account Actions</h3>
                    <p>
                        Terminate your active session or permanently remove your account and stored knowledge vault.
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
                        onClick={() => {
                            setDeleteError('')
                            setShowDeleteModal(true)
                        }}
                    >
                        Delete Account
                    </button>
                </div>
            </section>

            {/* =================================
                EDIT PROFILE MODAL
            ================================= */}
            {showEditModal && (
                <div
                    className="modal-overlay profile-modal-overlay"
                    onClick={() => setShowEditModal(false)}
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="edit-profile-title"
                >
                    <div
                        className="modal profile-modal"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="modal-header profile-modal-header">
                            <div>
                                <h2 id="edit-profile-title">Edit Profile</h2>
                                <p>Update your personal account details</p>
                            </div>

                            <button
                                type="button"
                                className="modal-close"
                                onClick={() => setShowEditModal(false)}
                                aria-label="Close edit profile modal"
                            >
                                ✕
                            </button>
                        </div>

                        <div className="modal-body profile-modal-body">
                            {editError && (
                                <p className="profile-form-error" role="alert">
                                    {editError}
                                </p>
                            )}

                            <div className="profile-form-field">
                                <label htmlFor="edit-name">Full Name</label>
                                <input
                                    id="edit-name"
                                    type="text"
                                    value={editName}
                                    onChange={(event) => setEditName(event.target.value)}
                                    placeholder="Enter your full name"
                                />
                            </div>

                            <div className="profile-form-field">
                                <label htmlFor="edit-email">Email Address</label>
                                <input
                                    id="edit-email"
                                    type="email"
                                    value={editEmail}
                                    disabled
                                    readOnly
                                    placeholder="Enter your email address"
                                />
                                <small className="field-hint">
                                    Email is tied to your account identity and requires re-verification to modify.
                                </small>
                            </div>

                            <div className="profile-form-field">
                                <label htmlFor="edit-phone">Phone Number (10 Digits)</label>
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
                                    placeholder="Enter your 10-digit phone number"
                                />

                                {phoneError && (
                                    <p className="profile-form-error" role="alert">
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
                                disabled={editLoading}
                            >
                                Cancel
                            </button>

                            <button
                                type="button"
                                className="profile-primary-button"
                                disabled={editLoading}
                                onClick={async () => {
                                    if (!/^\d{10}$/.test(editPhone)) {
                                        setPhoneError('Phone number must contain exactly 10 digits.')
                                        return
                                    }

                                    try {
                                        setPhoneError('')
                                        setEditError('')
                                        setEditLoading(true)

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
                                        setEditError(error.message || 'Failed to update profile.')
                                    } finally {
                                        setEditLoading(false)
                                    }
                                }}
                            >
                                {editLoading ? 'Saving...' : 'Save Changes'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* =================================
                CHANGE PASSWORD MODAL
            ================================= */}
            {showPasswordModal && (
                <div
                    className="modal-overlay profile-modal-overlay"
                    onClick={() => setShowPasswordModal(false)}
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="change-password-title"
                >
                    <div
                        className="modal profile-modal"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="modal-header profile-modal-header">
                            <div>
                                <h2 id="change-password-title">Change Password</h2>
                                <p>Update your account password securely</p>
                            </div>

                            <button
                                type="button"
                                className="modal-close"
                                onClick={() => setShowPasswordModal(false)}
                                aria-label="Close change password modal"
                            >
                                ✕
                            </button>
                        </div>

                        <div className="modal-body profile-modal-body">
                            {passwordError && (
                                <p className="profile-form-error" role="alert">
                                    {passwordError}
                                </p>
                            )}

                            {passwordSuccess && (
                                <p className="profile-form-success" role="status">
                                    {passwordSuccess}
                                </p>
                            )}

                            <div className="profile-form-field">
                                <label htmlFor="current-password">Current Password</label>
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
                                <label htmlFor="new-password">New Password (8+ characters)</label>
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
                                <label htmlFor="confirm-password">Confirm New Password</label>
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
                        </div>

                        <div className="profile-modal-actions">
                            <button
                                type="button"
                                className="profile-secondary-button"
                                onClick={() => setShowPasswordModal(false)}
                                disabled={passwordLoading}
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
                                        setPasswordError('Please enter your current password.')
                                        return
                                    }

                                    if (!newPassword) {
                                        setPasswordError('Please enter a new password.')
                                        return
                                    }

                                    if (newPassword.length < 8) {
                                        setPasswordError(
                                            'New password must be at least 8 characters.'
                                        )
                                        return
                                    }

                                    if (newPassword !== confirmPassword) {
                                        setPasswordError('New passwords do not match.')
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

                                        setPasswordSuccess('Password changed successfully.')
                                        setCurrentPassword('')
                                        setNewPassword('')
                                        setConfirmPassword('')
                                    } catch (error) {
                                        setPasswordError(
                                            error.message || 'Failed to update password.'
                                        )
                                    } finally {
                                        setPasswordLoading(false)
                                    }
                                }}
                            >
                                {passwordLoading ? 'Updating...' : 'Update Password'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* =================================
                DELETE ACCOUNT MODAL
            ================================= */}
            {showDeleteModal && (
                <div
                    className="modal-overlay profile-modal-overlay"
                    onClick={() => setShowDeleteModal(false)}
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="delete-account-title"
                >
                    <div
                        className="modal profile-modal delete-account-modal"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="modal-header profile-modal-header">
                            <div>
                                <h2 id="delete-account-title">Delete Account</h2>
                                <p>Permanent account deletion and data removal</p>
                            </div>

                            <button
                                type="button"
                                className="modal-close"
                                onClick={() => setShowDeleteModal(false)}
                                aria-label="Close delete account modal"
                            >
                                ✕
                            </button>
                        </div>

                        <div className="modal-body profile-modal-body">
                            <div className="delete-account-warning">
                                <strong>⚠️ This action is permanent and irreversible.</strong>
                                <p>
                                    Your account, documents, embeddings, search logs, and activity records
                                    will be permanently erased from the system.
                                </p>
                            </div>

                            {deleteError && (
                                <p className="profile-form-error" role="alert">
                                    {deleteError}
                                </p>
                            )}
                        </div>

                        <div className="profile-modal-actions">
                            <button
                                type="button"
                                className="profile-secondary-button"
                                onClick={() => setShowDeleteModal(false)}
                                disabled={deleteLoading}
                            >
                                Cancel
                            </button>

                            <button
                                type="button"
                                className="delete-account-confirm-button"
                                disabled={deleteLoading}
                                onClick={async () => {
                                    setDeleteError('')
                                    setDeleteLoading(true)

                                    try {
                                        await apiRequest('/auth/account', {
                                            method: 'DELETE',
                                        })

                                        localStorage.removeItem('access_token')
                                        localStorage.removeItem('user')

                                        navigate('/login', { replace: true })
                                    } catch (error) {
                                        setDeleteError(
                                            error.message || 'Failed to delete account.'
                                        )
                                    } finally {
                                        setDeleteLoading(false)
                                    }
                                }}
                            >
                                {deleteLoading ? 'Deleting Account...' : 'Permanently Delete Account'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </main>
    )
}

export default Profile