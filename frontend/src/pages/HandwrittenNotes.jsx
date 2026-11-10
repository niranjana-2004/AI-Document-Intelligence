import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'motion/react'
import {
    PenTool,
    Upload,
    FileText,
    CheckCircle2,
    Clock,
    AlertCircle,
    ArrowRight,
    Trash2,
    Eye,
    Layers,
    Sparkles,
    RefreshCw,
    X,
    AlertTriangle,
    GraduationCap
} from 'lucide-react'
import { apiRequest, API_BASE_URL } from '../services/api'
import PageTransition from '../components/motion/PageTransition'
import '../styles/handwritten.css'

export default function HandwrittenNotes() {
    const navigate = useNavigate()
    const fileInputRef = useRef(null)

    const [documents, setDocuments] = useState([])
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [dragActive, setDragActive] = useState(false)

    // Upload state
    const [uploading, setUploading] = useState(false)
    const [uploadProgress, setUploadProgress] = useState(0)
    const [uploadStage, setUploadStage] = useState('')

    // Delete Confirmation Modal & Toast states
    const [documentToDelete, setDocumentToDelete] = useState(null)
    const [deleteLoading, setDeleteLoading] = useState(false)
    const [deleteError, setDeleteError] = useState('')
    const [toastMessage, setToastMessage] = useState('')

    const fetchDocuments = async () => {
        try {
            setLoading(true)
            const data = await apiRequest('/handwritten/')
            setDocuments(data?.documents || [])
            setError(null)
        } catch (err) {
            setError(err.message || 'Failed to fetch handwritten documents.')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchDocuments()
    }, [])

    // Handle Escape key to close delete confirmation modal
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.key === 'Escape' && documentToDelete && !deleteLoading) {
                handleCancelDelete()
            }
        }
        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [documentToDelete, deleteLoading])

    // Auto-dismiss toast notification after 4 seconds
    useEffect(() => {
        if (!toastMessage) return
        const timer = setTimeout(() => {
            setToastMessage('')
        }, 4000)
        return () => clearTimeout(timer)
    }, [toastMessage])

    const handleDrag = (e) => {
        e.preventDefault()
        e.stopPropagation()
        if (e.type === 'dragenter' || e.type === 'dragover') {
            setDragActive(true)
        } else if (e.type === 'dragleave') {
            setDragActive(false)
        }
    }

    const handleDrop = (e) => {
        e.preventDefault()
        e.stopPropagation()
        setDragActive(false)
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleUploadFile(e.dataTransfer.files[0])
        }
    }

    const handleFileSelect = (e) => {
        if (e.target.files && e.target.files[0]) {
            handleUploadFile(e.target.files[0])
        }
    }

    const handleUploadFile = async (file) => {
        const allowedExtensions = ['.pdf', '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif']
        const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()

        if (!allowedExtensions.includes(ext)) {
            setError(`Unsupported file type '${ext}'. Please upload a PDF, PNG, JPG, or WEBP image.`)
            return
        }

        try {
            setUploading(true)
            setError(null)
            setUploadProgress(20)
            setUploadStage('Uploading document to server...')

            const formData = new FormData()
            formData.append('file', file)

            setUploadProgress(45)
            setUploadStage('Splitting pages & applying OpenCV contrast (CLAHE)...')

            const response = await apiRequest('/handwritten/upload', {
                method: 'POST',
                body: formData
            })

            setUploadProgress(85)
            setUploadStage('Correcting document skew & removing shadows...')

            setTimeout(() => {
                setUploadProgress(100)
                setUploadStage('Preprocessed successfully! Opening studio...')
                setTimeout(() => {
                    setUploading(false)
                    if (response?.document_id) {
                        navigate(`/handwritten/${response.document_id}`)
                    } else {
                        fetchDocuments()
                    }
                }, 600)
            }, 500)

        } catch (err) {
            setError(err.message || 'Upload and preprocessing failed.')
            setUploading(false)
        }
    }

    const handleRequestDelete = (doc, e) => {
        e.preventDefault()
        e.stopPropagation()
        setDocumentToDelete(doc)
        setDeleteError('')
    }

    const handleCancelDelete = () => {
        if (deleteLoading) return
        setDocumentToDelete(null)
        setDeleteError('')
    }

    const handleConfirmDelete = async () => {
        if (!documentToDelete || deleteLoading) return

        try {
            setDeleteLoading(true)
            setDeleteError('')

            await apiRequest(`/handwritten/${documentToDelete.id}`, {
                method: 'DELETE'
            })

            // Immediately remove deleted document from state
            setDocuments(prev => prev.filter(d => d.id !== documentToDelete.id))
            setDocumentToDelete(null)
            setToastMessage('Handwritten document deleted successfully.')
        } catch (err) {
            console.error('Delete handwritten document error:', err)
            setDeleteError(err.message || 'Failed to delete handwritten document. Please try again.')
        } finally {
            setDeleteLoading(false)
        }
    }

    return (
        <PageTransition>
            <div className="handwritten-page-container">
                {/* Header */}
                <header className="handwritten-header">
                    <div className="handwritten-badge-pill">
                        <PenTool size={14} />
                        <span>Handwritten Document Intelligence</span>
                    </div>
                    <h1 className="handwritten-title">
                        Handwritten Notes & Academic Intelligence
                    </h1>
                    <p className="handwritten-subtitle">
                        Upload multi-page handwritten PDFs, lecture notes, mathematical proofs, and whiteboards.
                        Automatically enhance contrast, deskew orientation, and prepare pages for AI transcription.
                    </p>
                </header>

                {/* Upload Card */}
                <div className="handwritten-upload-card">
                    <div
                        className={`handwritten-dropzone ${dragActive ? 'drag-active' : ''}`}
                        onDragEnter={handleDrag}
                        onDragLeave={handleDrag}
                        onDragOver={handleDrag}
                        onDrop={handleDrop}
                        onClick={() => fileInputRef.current?.click()}
                    >
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".pdf,.png,.jpg,.jpeg,.webp"
                            style={{ display: 'none' }}
                            onChange={handleFileSelect}
                        />

                        <div className="dropzone-icon-wrap">
                            <Upload size={28} />
                        </div>

                        <div className="dropzone-text">
                            <h3>Drag & drop handwritten notes or scanned PDFs</h3>
                            <p>or click to browse from your device</p>
                            <span className="dropzone-formats">
                                Supports: Multi-page Scanned PDF, PNG, JPG, WEBP
                            </span>
                        </div>
                    </div>

                    {/* Progress Bar when uploading */}
                    <AnimatePresence>
                        {uploading && (
                            <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                className="upload-progress-container"
                            >
                                <div className="progress-header">
                                    <span>{uploadStage}</span>
                                    <span>{uploadProgress}%</span>
                                </div>
                                <div className="progress-bar-track">
                                    <div
                                        className="progress-bar-fill"
                                        style={{ width: `${uploadProgress}%` }}
                                    />
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {error && (
                        <div style={{ marginTop: '16px', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--danger-ink)', fontSize: '13px' }}>
                            <AlertCircle size={16} />
                            <span>{error}</span>
                        </div>
                    )}
                </div>

                {/* Documents List Section */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
                    <h2 style={{ fontSize: '20px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                        Your Handwritten Library
                    </h2>
                    <button
                        onClick={fetchDocuments}
                        style={{
                            background: 'transparent',
                            border: '1px solid var(--border)',
                            color: 'var(--text-secondary)',
                            padding: '6px 12px',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            fontSize: '13px'
                        }}
                    >
                        <RefreshCw size={14} />
                        <span>Refresh</span>
                    </button>
                </div>

                {loading ? (
                    <div style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
                        <RefreshCw size={24} className="spin-icon" style={{ margin: '0 auto 12px' }} />
                        <p>Loading handwritten documents...</p>
                    </div>
                ) : documents.length === 0 ? (
                    <div className="handwritten-empty-state">
                        <div className="empty-state-icon">
                            <FileText size={32} />
                        </div>
                        <h3 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)', fontSize: '18px' }}>
                            No handwritten documents yet
                        </h3>
                        <p style={{ margin: '0 0 20px 0', fontSize: '14px', maxWidth: '440px', marginInline: 'auto' }}>
                            Drop your first lecture note, study sheet, or mathematical derivation above to begin AI enhancement.
                        </p>
                    </div>
                ) : (
                    <div className="handwritten-grid">
                        {documents.map((doc) => (
                            <motion.div
                                key={doc.id}
                                className="handwritten-card"
                                whileHover={{ scale: 1.01 }}
                                transition={{ duration: 0.2 }}
                            >
                                <div className="handwritten-card-top">
                                    <div className="handwritten-card-icon">
                                        <PenTool size={20} />
                                    </div>
                                    <div className="handwritten-card-info">
                                        <h3 className="handwritten-card-title" title={doc.filename}>
                                            {doc.filename}
                                        </h3>
                                        <div className="handwritten-meta-row" style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                            <span>{doc.page_count} {doc.page_count === 1 ? 'page' : 'pages'}</span>
                                            <span>•</span>
                                            <span className={`handwritten-status-pill ${doc.processing_status}`}>
                                                {doc.processing_status === 'ready' ? (
                                                    <>
                                                        <CheckCircle2 size={12} />
                                                        Ready
                                                    </>
                                                ) : (
                                                    <>
                                                        <Clock size={12} />
                                                        Processing
                                                    </>
                                                )}
                                            </span>
                                            {doc.subject && (
                                                <span className="handwritten-subject-pill" title={`Academic Discipline: ${doc.subject}`}>
                                                    <GraduationCap size={11} />
                                                    <span>{doc.subject}</span>
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                <div className="handwritten-card-footer">
                                    <Link
                                        to={`/handwritten/${doc.id}`}
                                        className="btn-open-studio"
                                    >
                                        <span>Open Studio</span>
                                        <ArrowRight size={14} />
                                    </Link>

                                    <button
                                        type="button"
                                        className="btn-delete-card"
                                        title={`Delete ${doc.filename}`}
                                        aria-label={`Delete ${doc.filename}`}
                                        onClick={(e) => handleRequestDelete(doc, e)}
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                )}

                {/* Custom Delete Confirmation Modal */}
                <AnimatePresence>
                    {documentToDelete && (
                        <motion.div
                            className="hw-delete-modal-overlay"
                            onClick={!deleteLoading ? handleCancelDelete : undefined}
                            role="dialog"
                            aria-modal="true"
                            aria-labelledby="delete-hw-modal-title"
                            aria-describedby="delete-hw-modal-desc"
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            transition={{ duration: 0.2 }}
                        >
                            <motion.div
                                className="hw-delete-modal-container"
                                onClick={(e) => e.stopPropagation()}
                                initial={{ opacity: 0, scale: 0.93, y: 16 }}
                                animate={{ opacity: 1, scale: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.93, y: 16 }}
                                transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}
                            >
                                {/* Top right Close 'X' Button */}
                                <button
                                    type="button"
                                    className="hw-delete-modal-close"
                                    onClick={handleCancelDelete}
                                    disabled={deleteLoading}
                                    aria-label="Close delete modal"
                                >
                                    <X size={18} />
                                </button>

                                <div className="hw-delete-modal-body">
                                    {/* Prominent Red Trash Icon Badge */}
                                    <div className="hw-delete-icon-badge" aria-hidden="true">
                                        <Trash2 size={26} />
                                    </div>

                                    {/* Heading */}
                                    <h3 id="delete-hw-modal-title" className="hw-delete-modal-title">
                                        Delete handwritten document?
                                    </h3>

                                    {/* Description */}
                                    <p id="delete-hw-modal-desc" className="hw-delete-modal-desc">
                                        Are you sure you want to delete this document? This action cannot be undone.
                                    </p>

                                    {/* Target document details */}
                                    <div className="hw-delete-target-preview">
                                        <div className="hw-delete-target-icon">
                                            <FileText size={16} />
                                        </div>
                                        <div className="hw-delete-target-meta">
                                            <span className="hw-delete-target-filename" title={documentToDelete.filename}>
                                                {documentToDelete.filename}
                                            </span>
                                            <span className="hw-delete-target-pages">
                                                {documentToDelete.page_count} {documentToDelete.page_count === 1 ? 'page' : 'pages'}
                                            </span>
                                        </div>
                                    </div>

                                    {/* Error Banner if deletion failed */}
                                    {deleteError && (
                                        <div className="hw-delete-error-banner" role="alert">
                                            <AlertCircle size={16} className="hw-error-alert-icon" />
                                            <span>{deleteError}</span>
                                        </div>
                                    )}

                                    {/* Actions */}
                                    <div className="hw-delete-modal-actions">
                                        <button
                                            type="button"
                                            className="hw-btn-cancel-delete"
                                            onClick={handleCancelDelete}
                                            disabled={deleteLoading}
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            type="button"
                                            className="hw-btn-confirm-delete"
                                            onClick={handleConfirmDelete}
                                            disabled={deleteLoading}
                                        >
                                            {deleteLoading ? (
                                                <>
                                                    <RefreshCw size={14} className="spin-icon" />
                                                    <span>Deleting...</span>
                                                </>
                                            ) : (
                                                <>
                                                    <Trash2 size={14} />
                                                    <span>Delete Document</span>
                                                </>
                                            )}
                                        </button>
                                    </div>
                                </div>
                            </motion.div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Custom Success Toast */}
                <AnimatePresence>
                    {toastMessage && (
                        <motion.div
                            className="hw-toast-container"
                            role="status"
                            aria-live="polite"
                            initial={{ opacity: 0, y: 20, scale: 0.95 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            exit={{ opacity: 0, y: 16, scale: 0.95 }}
                            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                        >
                            <div className="hw-toast-icon-wrap">
                                <CheckCircle2 size={18} />
                            </div>
                            <span className="hw-toast-message">{toastMessage}</span>
                            <button
                                type="button"
                                className="hw-toast-dismiss-btn"
                                onClick={() => setToastMessage('')}
                                aria-label="Dismiss notification"
                            >
                                <X size={14} />
                            </button>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </PageTransition>
    )
}

