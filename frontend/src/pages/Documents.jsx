import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion, AnimatePresence } from 'motion/react'
import {
    UploadCloud,
    FileText,
    Search,
    X,
    Check,
    Copy,
    RotateCw,
    Trash2,
    Sparkles,
    AlertTriangle,
    Eye,
    ChevronLeft,
    ChevronRight,
    BookOpen,
} from 'lucide-react'
import { apiRequest } from '../services/api'
import { splitHighlightedText } from '../utils/citationUtils'
import '../App.css'

function Documents() {
    const fileInputRef = useRef(null)
    const highlightMarkRef = useRef(null)
    const [searchParams, setSearchParams] = useSearchParams()

    const [documents, setDocuments] = useState([])
    const [loading, setLoading] = useState(true)

    const [uploading, setUploading] = useState(false)
    const [uploadMessage, setUploadMessage] = useState('')
    const [isDragOver, setIsDragOver] = useState(false)

    const [searchTerm, setSearchTerm] = useState('')
    const [selectedTypeFilter, setSelectedTypeFilter] = useState('ALL') // 'ALL' | 'PDF' | 'DOCX' | 'TXT'

    const [selectedDocument, setSelectedDocument] = useState(null)
    const [documentLoading, setDocumentLoading] = useState(false)
    const [viewerPage, setViewerPage] = useState(1) // 1-based page number or 'all'
    const [viewerHighlight, setViewerHighlight] = useState('')

    const [summary, setSummary] = useState('')
    const [summaryLoading, setSummaryLoading] = useState(false)
    const [summaryFormat, setSummaryFormat] = useState('numbered')
    const [summaryLength, setSummaryLength] = useState('detailed')
    const [summaryDocId, setSummaryDocId] = useState(null)
    const [summaryDocFilename, setSummaryDocFilename] = useState('')
    const [regenerating, setRegenerating] = useState(false)
    const [summaryFeedback, setSummaryFeedback] = useState('')
    const [summaryError, setSummaryError] = useState('')

    const [error, setError] = useState('')
    const [copiedDocText, setCopiedDocText] = useState(false)
    const [copiedSummaryText, setCopiedSummaryText] = useState(false)

    const [documentToDelete, setDocumentToDelete] = useState(null)
    const [deleteLoading, setDeleteLoading] = useState(false)
    const [deleteError, setDeleteError] = useState('')

    /* ========================================
       FETCH DOCUMENTS
    ======================================== */

    const fetchDocuments = async () => {
        try {
            setLoading(true)
            setError('')

            const data = await apiRequest('/documents/')

            const documentList = Array.isArray(data)
                ? data
                : data.documents || []

            setDocuments(documentList)
        } catch (err) {
            console.error('Error fetching documents:', err)
            setError(
                err.message ||
                'Unable to connect to the backend.'
            )
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        let ignore = false
        const loadInitialDocuments = async () => {
            try {
                const data = await apiRequest('/documents/')
                if (!ignore) {
                    const documentList = Array.isArray(data)
                        ? data
                        : data.documents || []
                    setDocuments(documentList)
                }
            } catch (err) {
                if (!ignore) {
                    console.error('Error fetching documents:', err)
                    setError(
                        err.message ||
                        'Unable to connect to the backend.'
                    )
                }
            } finally {
                if (!ignore) {
                    setLoading(false)
                }
            }
        }

        loadInitialDocuments()
        return () => {
            ignore = true
        }
    }, [])

    /* ========================================
       UPLOAD
    ======================================== */

    const handleUploadClick = () => {
        fileInputRef.current?.click()
    }

    const processUploadFile = async (file) => {
        if (!file) return

        const allowedTypes = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain',
        ]

        // Check either MIME type or file extension
        const ext = file.name.split('.').pop().toLowerCase()
        const isValidExt = ['pdf', 'docx', 'txt'].includes(ext)

        if (!allowedTypes.includes(file.type) && !isValidExt) {
            setUploadMessage('Please select a PDF, DOCX, or TXT file.')
            return
        }

        try {
            setUploading(true)
            setUploadMessage('')
            setError('')

            const formData = new FormData()
            formData.append('file', file)

            await apiRequest('/documents/upload', {
                method: 'POST',
                body: formData,
            })

            setUploadMessage(`${file.name} uploaded and indexed successfully.`)
            await fetchDocuments()
        } catch (err) {
            console.error('Upload error:', err)
            setUploadMessage(err.message || 'Failed to upload document.')
        } finally {
            setUploading(false)
            if (fileInputRef.current) {
                fileInputRef.current.value = ''
            }
        }
    }

    const handleFileUpload = (event) => {
        const file = event.target.files[0]
        processUploadFile(file)
    }

    const handleDragOver = (e) => {
        e.preventDefault()
        setIsDragOver(true)
    }

    const handleDragLeave = (e) => {
        e.preventDefault()
        setIsDragOver(false)
    }

    const handleDrop = (e) => {
        e.preventDefault()
        setIsDragOver(false)
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            processUploadFile(e.dataTransfer.files[0])
        }
    }

    /* ========================================
       OPEN DOCUMENT
    ======================================== */

    const handleOpenDocument = async (documentId, options = {}) => {
        try {
            setDocumentLoading(true)
            setSelectedDocument(null)
            setError('')
            setCopiedDocText(false)

            const data = await apiRequest(`/documents/${documentId}`)
            const docPages = Array.isArray(data?.pages) ? data.pages : []
            const requestedPage = options?.page != null ? parseInt(options.page, 10) : null
            let initialPage = 'all'
            if (docPages.length > 0) {
                if (requestedPage && docPages.some((p) => p.page_number === requestedPage)) {
                    initialPage = requestedPage
                } else {
                    initialPage = docPages[0].page_number
                }
            }
            setViewerPage(initialPage)
            setViewerHighlight(options?.highlight || '')
            setSelectedDocument(data)
        } catch (err) {
            console.error('Open document error:', err)
            setError(err.message || 'Failed to open document.')
        } finally {
            setDocumentLoading(false)
        }
    }

    const deepLinkDoc = searchParams.get('doc')
    const deepLinkPage = searchParams.get('page')
    const deepLinkHighlight = searchParams.get('highlight') || ''

    useEffect(() => {
        if (!deepLinkDoc) return
        const docId = parseInt(deepLinkDoc, 10)
        if (isNaN(docId)) return

        let ignore = false
        const loadDeepLinkedDoc = async () => {
            setDocumentLoading(true)
            setSelectedDocument(null)
            try {
                const data = await apiRequest(`/documents/${docId}`)
                if (ignore) return
                const docPages = Array.isArray(data?.pages) ? data.pages : []
                const requestedPage = deepLinkPage != null ? parseInt(deepLinkPage, 10) : null
                let initialPage = 'all'
                if (docPages.length > 0) {
                    if (requestedPage && docPages.some((p) => p.page_number === requestedPage)) {
                        initialPage = requestedPage
                    } else {
                        initialPage = docPages[0].page_number
                    }
                }
                setViewerPage(initialPage)
                setViewerHighlight(deepLinkHighlight || '')
                setSelectedDocument(data)
            } catch (err) {
                if (!ignore) {
                    console.error('Open document error:', err)
                    setError(err.message || 'Failed to open document.')
                }
            } finally {
                if (!ignore) {
                    setDocumentLoading(false)
                }
            }
        }
        loadDeepLinkedDoc()

        return () => {
            ignore = true
        }
    }, [deepLinkDoc, deepLinkPage, deepLinkHighlight])

    useEffect(() => {
        if (selectedDocument && viewerHighlight && highlightMarkRef.current) {
            const timer = setTimeout(() => {
                highlightMarkRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
            }, 80)
            return () => clearTimeout(timer)
        }
    }, [selectedDocument, viewerPage, viewerHighlight])

    /* ========================================
       SUMMARY
    ======================================== */

    const handleSummary = async (doc) => {
        const docId = typeof doc === 'object' ? doc.id : doc
        const docFilename = typeof doc === 'object' ? doc.filename : ''
        try {
            setSummaryDocId(docId)
            setSummaryDocFilename(docFilename)
            setSummaryLoading(true)
            setSummary('')
            setError('')
            setSummaryError('')
            setSummaryFeedback('')
            setCopiedSummaryText(false)

            const data = await apiRequest(
                `/documents/${docId}/summary?format=${encodeURIComponent(summaryFormat)}&length=${encodeURIComponent(summaryLength)}`
            )

            setSummary(data.summary || 'No summary available.')
            if (data.filename && !docFilename) {
                setSummaryDocFilename(data.filename)
            }
        } catch (err) {
            console.error('Summary error:', err)
            setError(err.message || 'Failed to load summary.')
        } finally {
            setSummaryLoading(false)
        }
    }

    const handleRegenerateSummary = async () => {
        if (!summaryDocId || regenerating) return
        try {
            setRegenerating(true)
            setSummaryError('')
            setSummaryFeedback('')

            const data = await apiRequest(
                `/documents/${summaryDocId}/summary?format=${encodeURIComponent(summaryFormat)}&length=${encodeURIComponent(summaryLength)}&regenerate=true`
            )

            if (data.summary) {
                setSummary(data.summary)
                setSummaryFeedback('Summary regenerated successfully.')
                setTimeout(() => setSummaryFeedback(''), 4000)
            }
        } catch (err) {
            console.error('Regenerate error:', err)
            setSummaryError(err.message || 'Failed to regenerate summary.')
        } finally {
            setRegenerating(false)
        }
    }

    /* ========================================
       DELETE DOCUMENT
    ======================================== */

    const handleRequestDelete = (doc) => {
        setDocumentToDelete(doc)
        setDeleteError('')
    }

    const handleCancelDelete = () => {
        if (deleteLoading) return
        setDocumentToDelete(null)
        setDeleteError('')
    }

    const handleConfirmDelete = async () => {
        if (!documentToDelete || deleteLoading) {
            return
        }

        try {
            setDeleteLoading(true)
            setDeleteError('')
            setError('')

            await apiRequest(`/documents/${documentToDelete.id}`, {
                method: 'DELETE',
            })

            setDocuments((currentDocuments) =>
                currentDocuments.filter(
                    (document) => document.id !== documentToDelete.id
                )
            )

            if (selectedDocument?.id === documentToDelete.id) {
                closeDocument()
            }

            setDocumentToDelete(null)
        } catch (err) {
            console.error('Delete error:', err)
            const errMsg = err.message || 'Failed to delete document.'
            setDeleteError(errMsg)
            setError(errMsg)
        } finally {
            setDeleteLoading(false)
        }
    }

    /* ========================================
       CLOSE MODALS
    ======================================== */

    const closeDocument = () => {
        setSelectedDocument(null)
        setCopiedDocText(false)
        setViewerPage(1)
        setViewerHighlight('')
        if (searchParams.has('doc') || searchParams.has('page') || searchParams.has('highlight')) {
            setSearchParams({}, { replace: true })
        }
    }

    const closeSummary = () => {
        setSummary('')
        setSummaryDocId(null)
        setSummaryDocFilename('')
        setSummaryLoading(false)
        setRegenerating(false)
        setCopiedSummaryText(false)
        setSummaryFeedback('')
        setSummaryError('')
    }

    /* ========================================
       COPY HELPERS
    ======================================== */

    const handleCopyDocText = async () => {
        if (!selectedDocument?.extracted_text) return
        try {
            if (navigator?.clipboard?.writeText) {
                await navigator.clipboard.writeText(selectedDocument.extracted_text)
                setCopiedDocText(true)
                setTimeout(() => setCopiedDocText(false), 2000)
            }
        } catch (err) {
            console.error('Clipboard copy failed:', err)
        }
    }

    const handleCopySummary = async () => {
        if (!summary) return
        try {
            if (navigator?.clipboard?.writeText) {
                await navigator.clipboard.writeText(summary)
                setCopiedSummaryText(true)
                setTimeout(() => setCopiedSummaryText(false), 2000)
            }
        } catch (err) {
            console.error('Clipboard copy failed:', err)
        }
    }

    /* ========================================
       FILTER DOCUMENTS
    ======================================== */

    const filteredDocuments = documents.filter((document) => {
        const matchesSearch = document.filename
            ?.toLowerCase()
            .includes(searchTerm.toLowerCase())

        if (!matchesSearch) return false

        if (selectedTypeFilter === 'ALL') return true

        const ext = document.filename ? document.filename.split('.').pop().toUpperCase() : ''
        return ext === selectedTypeFilter
    })

    return (
        <>
            <main className="documents-page">
                {/* =================================
                    PAGE HEADER & DRAG DROP ZONE
                ================================= */}
                <section className="documents-page-header">
                    <div className="documents-header-text">
                        <p className="eyebrow">DOCUMENT VAULT</p>
                        <h2>Documents Library</h2>
                        <p>
                            Upload, organize, inspect, and synthesize multi-format files in your AI repository.
                        </p>
                    </div>

                    <button
                        type="button"
                        className="documents-upload-button"
                        onClick={handleUploadClick}
                        disabled={uploading}
                        aria-label="Upload document"
                    >
                        {uploading ? (
                            <>
                                <span className="spinner-inline" aria-hidden="true"></span>
                                <span>Uploading & Indexing...</span>
                            </>
                        ) : (
                            <>
                                <UploadCloud size={17} />
                                <span>Upload Document</span>
                            </>
                        )}
                    </button>
                </section>

                {/* Dropzone Card */}
                <motion.div
                    className={`documents-dropzone ${isDragOver ? 'drag-over' : ''}`}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={handleUploadClick}
                    whileHover={{ scale: 1.01, transition: { duration: 0.2 } }}
                    whileTap={{ scale: 0.99 }}
                    animate={isDragOver ? { scale: 1.02, borderColor: '#38bdf8' } : {}}
                >
                    <div className="dropzone-icon-wrap">
                        <UploadCloud size={28} />
                    </div>
                    <div className="dropzone-text">
                        <strong>Click or drag & drop files here to upload</strong>
                        <span>Supports Adobe PDF (.pdf), Microsoft Word (.docx), and Plain Text (.txt)</span>
                    </div>
                    <div className="dropzone-chips">
                        <span className="dropzone-chip badge-pdf">PDF</span>
                        <span className="dropzone-chip badge-docx">DOCX</span>
                        <span className="dropzone-chip badge-txt">TXT</span>
                    </div>
                </motion.div>

                {/* Hidden file input */}
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.docx,.txt"
                    onChange={handleFileUpload}
                    style={{ display: 'none' }}
                    aria-label="Choose file to upload"
                />

                {/* =================================
                    UPLOAD MESSAGE & ERROR
                ================================= */}
                {uploadMessage && (
                    <div className="upload-message" role="status">
                        <Check size={16} className="text-accent" />
                        <span>{uploadMessage}</span>
                    </div>
                )}

                {error && (
                    <div className="error-message" role="alert">
                        <AlertTriangle size={16} />
                        <span>{error}</span>
                    </div>
                )}

                {/* =================================
                    SEARCH + FORMAT FILTER TOOLBAR
                ================================= */}
                <section className="documents-toolbar">
                    <div className="documents-toolbar-left">
                        <div className="documents-search-wrapper">
                            <Search size={16} className="documents-search-icon" aria-hidden="true" />
                            <input
                                className="documents-search"
                                type="text"
                                placeholder="Filter documents by name..."
                                value={searchTerm}
                                onChange={(event) => setSearchTerm(event.target.value)}
                                aria-label="Search documents by name"
                            />
                            {searchTerm && (
                                <button
                                    type="button"
                                    className="documents-search-clear"
                                    onClick={() => setSearchTerm('')}
                                    aria-label="Clear search input"
                                >
                                    <X size={14} />
                                </button>
                            )}
                        </div>

                        {/* Format Filters */}
                        <div className="documents-filter-pills" role="radiogroup" aria-label="Filter by file type">
                            {['ALL', 'PDF', 'DOCX', 'TXT'].map((type) => (
                                <button
                                    key={type}
                                    type="button"
                                    className={`filter-pill ${selectedTypeFilter === type ? 'active' : ''}`}
                                    onClick={() => setSelectedTypeFilter(type)}
                                >
                                    {type}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="documents-toolbar-count">
                        <span>
                            {documents.length === 0
                                ? '0 documents'
                                : filteredDocuments.length === documents.length
                                ? `${documents.length} ${documents.length === 1 ? 'document' : 'documents'}`
                                : `Showing ${filteredDocuments.length} of ${documents.length}`}
                        </span>
                    </div>
                </section>

                {/* =================================
                    DOCUMENT LIBRARY GRID
                ================================= */}
                <section className="documents-library">
                    {loading && (
                        <div className="documents-empty">
                            <div className="loading-pulse-ring" aria-hidden="true"></div>
                            <h3>Loading document library...</h3>
                            <p>Connecting to vector vault.</p>
                        </div>
                    )}

                    {!loading && documents.length === 0 && (
                        <div className="documents-empty">
                            <div className="documents-empty-icon" aria-hidden="true">
                                <FileText size={44} />
                            </div>
                            <h3>No documents uploaded yet</h3>
                            <p>
                                Upload your first PDF, DOCX, or TXT file to start indexing and questioning your data.
                            </p>
                            <button
                                type="button"
                                className="documents-upload-button"
                                onClick={handleUploadClick}
                                disabled={uploading}
                            >
                                <UploadCloud size={16} />
                                <span>Upload Document</span>
                            </button>
                        </div>
                    )}

                    {!loading &&
                        documents.length > 0 &&
                        filteredDocuments.length === 0 && (
                            <div className="documents-empty">
                                <div className="documents-empty-icon" aria-hidden="true">
                                    <Search size={44} />
                                </div>
                                <h3>No matching documents</h3>
                                <p>
                                    No documents matched &ldquo;{searchTerm}&rdquo;{' '}
                                    {selectedTypeFilter !== 'ALL' ? `in format ${selectedTypeFilter}` : ''}.
                                </p>
                                <button
                                    type="button"
                                    className="clear-button"
                                    onClick={() => {
                                        setSearchTerm('')
                                        setSelectedTypeFilter('ALL')
                                    }}
                                >
                                    Reset Filters
                                </button>
                            </div>
                        )}

                    {!loading && filteredDocuments.length > 0 && (
                        <motion.div
                            className="documents-grid"
                            variants={{
                                hidden: { opacity: 0 },
                                visible: {
                                    opacity: 1,
                                    transition: { staggerChildren: 0.08 },
                                },
                            }}
                            initial="hidden"
                            animate="visible"
                        >
                            {filteredDocuments.map((doc) => {
                                const ext = doc.filename
                                    ? doc.filename.split('.').pop().toUpperCase()
                                    : 'DOC'
                                const badgeClass =
                                    ext === 'PDF'
                                        ? 'badge-pdf'
                                        : ext === 'DOCX'
                                        ? 'badge-docx'
                                        : 'badge-txt'

                                return (
                                    <motion.article
                                        className="document-card"
                                        key={doc.id}
                                        variants={{
                                            hidden: { opacity: 0, y: 20 },
                                            visible: { opacity: 1, y: 0, transition: { duration: 0.35 } },
                                        }}
                                        whileHover={{ y: -6, scale: 1.02 }}
                                    >
                                        <div className="document-card-top">
                                            <div className="document-card-badge-wrap">
                                                <span className={`document-card-badge ${badgeClass}`}>
                                                    {ext}
                                                </span>
                                            </div>

                                            <button
                                                type="button"
                                                className="document-delete"
                                                onClick={() => handleRequestDelete(doc)}
                                                title={`Delete ${doc.filename}`}
                                                aria-label={`Delete ${doc.filename}`}
                                            >
                                                <Trash2 size={15} />
                                            </button>
                                        </div>

                                        <div className="document-card-body">
                                            <h3 title={doc.filename}>{doc.filename}</h3>
                                            <div className="document-card-meta">
                                                <span className="doc-meta-type">
                                                    {doc.document_type || ext.toLowerCase()}
                                                </span>
                                                <span className="doc-meta-dot" aria-hidden="true">·</span>
                                                <span className="doc-meta-chars">
                                                    {typeof doc.text_length === 'number'
                                                        ? `${doc.text_length.toLocaleString()} chars`
                                                        : `${doc.text_length || 0} chars`}
                                                </span>
                                            </div>
                                        </div>

                                        <div className="document-card-actions">
                                            <button
                                                type="button"
                                                className="document-action"
                                                onClick={() => handleOpenDocument(doc.id)}
                                                disabled={documentLoading}
                                                aria-label={`Inspect extracted text of ${doc.filename}`}
                                            >
                                                <Eye size={14} />
                                                <span>Inspect Text</span>
                                            </button>

                                            <button
                                                type="button"
                                                className="document-action summary-action"
                                                onClick={() => handleSummary(doc)}
                                                disabled={summaryLoading && summaryDocId === doc.id}
                                                aria-label={`View summary of ${doc.filename}`}
                                            >
                                                <Sparkles size={14} />
                                                <span>{summaryLoading && summaryDocId === doc.id ? 'Loading...' : 'Summary'}</span>
                                            </button>
                                        </div>
                                    </motion.article>
                                )
                            })}
                        </motion.div>
                    )}
                </section>
            </main>

            {/* =================================
                ANIMATED MODALS WITH ANIMATEPRESENCE
            ================================= */}
            <AnimatePresence>
                {/* DOCUMENT EXTRACTED TEXT MODAL */}
                {selectedDocument && (
                    <motion.div
                        className="modal-overlay"
                        onClick={closeDocument}
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="doc-modal-title"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.22 }}
                    >
                        <motion.div
                            className="modal"
                            onClick={(e) => e.stopPropagation()}
                            initial={{ opacity: 0, scale: 0.94, y: 15 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.94, y: 15 }}
                            transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
                        >
                            <div className="modal-header">
                                <div>
                                    <h2 id="doc-modal-title">{selectedDocument.filename}</h2>
                                    <p>
                                        {selectedDocument.document_type} ·{' '}
                                        {typeof selectedDocument.text_length === 'number'
                                            ? selectedDocument.text_length.toLocaleString()
                                            : selectedDocument.text_length}{' '}
                                        characters extracted
                                    </p>
                                </div>

                                <button
                                    type="button"
                                    className="modal-close"
                                    onClick={closeDocument}
                                    aria-label="Close document modal"
                                >
                                    <X size={18} />
                                </button>
                            </div>

                            <div className="modal-body">
                                <div className="modal-content-toolbar">
                                    <h3>
                                        {Array.isArray(selectedDocument.pages) && selectedDocument.pages.length > 0 && viewerPage !== 'all'
                                            ? `Page ${viewerPage} of ${selectedDocument.pages.length}`
                                            : 'Extracted Text Content'}
                                    </h3>
                                    <button
                                        type="button"
                                        className="modal-copy-btn"
                                        onClick={handleCopyDocText}
                                        title="Copy extracted text to clipboard"
                                    >
                                        {copiedDocText ? (
                                            <>
                                                <Check size={14} />
                                                <span>Copied</span>
                                            </>
                                        ) : (
                                            <>
                                                <Copy size={14} />
                                                <span>Copy Text</span>
                                            </>
                                        )}
                                    </button>
                                </div>

                                {Array.isArray(selectedDocument.pages) && selectedDocument.pages.length > 0 && (
                                    <div className="viewer-page-nav" role="navigation" aria-label="Document Page Navigation">
                                        <div className="viewer-page-controls">
                                            <button
                                                type="button"
                                                className="viewer-page-btn"
                                                disabled={viewerPage === 'all' || viewerPage <= selectedDocument.pages[0].page_number}
                                                onClick={() => {
                                                    const idx = selectedDocument.pages.findIndex((p) => p.page_number === viewerPage)
                                                    if (idx > 0) setViewerPage(selectedDocument.pages[idx - 1].page_number)
                                                }}
                                            >
                                                <ChevronLeft size={14} />
                                                <span>Prev</span>
                                            </button>

                                            <label className="viewer-page-select-wrap">
                                                <span>Page</span>
                                                <select
                                                    className="viewer-page-select"
                                                    value={String(viewerPage)}
                                                    onChange={(e) => {
                                                        const val = e.target.value
                                                        setViewerPage(val === 'all' ? 'all' : parseInt(val, 10))
                                                    }}
                                                    aria-label="Select document page"
                                                >
                                                    {selectedDocument.pages.map((p) => (
                                                        <option key={p.page_number} value={String(p.page_number)}>
                                                            Page {p.page_number}
                                                        </option>
                                                    ))}
                                                    <option value="all">All Pages ({selectedDocument.pages.length})</option>
                                                </select>
                                            </label>

                                            <button
                                                type="button"
                                                className="viewer-page-btn"
                                                disabled={
                                                    viewerPage === 'all' ||
                                                    viewerPage >= selectedDocument.pages[selectedDocument.pages.length - 1].page_number
                                                }
                                                onClick={() => {
                                                    const idx = selectedDocument.pages.findIndex((p) => p.page_number === viewerPage)
                                                    if (idx >= 0 && idx < selectedDocument.pages.length - 1) {
                                                        setViewerPage(selectedDocument.pages[idx + 1].page_number)
                                                    }
                                                }}
                                            >
                                                <span>Next</span>
                                                <ChevronRight size={14} />
                                            </button>
                                        </div>

                                        <button
                                            type="button"
                                            className={`viewer-page-btn ${viewerPage === 'all' ? 'active' : ''}`}
                                            onClick={() =>
                                                setViewerPage(
                                                    viewerPage === 'all'
                                                        ? selectedDocument.pages[0].page_number
                                                        : 'all'
                                                )
                                            }
                                        >
                                            {viewerPage === 'all' ? 'Single Page View' : 'Show All Pages'}
                                        </button>
                                    </div>
                                )}

                                {viewerHighlight && (
                                    <div className="viewer-citation-banner" role="status">
                                        <span className="viewer-citation-label">
                                            <BookOpen size={14} />
                                            <span>
                                                Highlighting cited passage
                                                {viewerPage !== 'all' ? ` on Page ${viewerPage}` : ''}
                                            </span>
                                        </span>
                                        <button
                                            type="button"
                                            className="viewer-clear-highlight-btn"
                                            onClick={() => setViewerHighlight('')}
                                        >
                                            Clear
                                        </button>
                                    </div>
                                )}

                                <div className="document-text">
                                    {documentLoading ? (
                                        'Loading document...'
                                    ) : (() => {
                                        const hasPages = Array.isArray(selectedDocument.pages) && selectedDocument.pages.length > 0
                                        let activeText = selectedDocument.extracted_text || 'No text content available.'
                                        if (hasPages && viewerPage !== 'all') {
                                            const activePageObj = selectedDocument.pages.find((p) => p.page_number === viewerPage)
                                            if (activePageObj) {
                                                activeText = activePageObj.text || 'No readable text on this page.'
                                            }
                                        }
                                        const split = viewerHighlight ? splitHighlightedText(activeText, viewerHighlight) : null
                                        if (!split) return activeText
                                        return (
                                            <>
                                                {split.before}
                                                <mark ref={highlightMarkRef} className="viewer-highlight-mark">
                                                    {split.match}
                                                </mark>
                                                {split.after}
                                            </>
                                        )
                                    })()}
                                </div>
                            </div>
                        </motion.div>
                    </motion.div>
                )}

                {/* AI SUMMARY MODAL */}
                {(summaryLoading || summary || summaryDocId) && (
                    <motion.div
                        className="modal-overlay"
                        onClick={closeSummary}
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="summary-modal-title"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.22 }}
                    >
                        <motion.div
                            className="modal"
                            onClick={(e) => e.stopPropagation()}
                            initial={{ opacity: 0, scale: 0.94, y: 15 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.94, y: 15 }}
                            transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
                        >
                            <div className="modal-header">
                                <div>
                                    <h2 id="summary-modal-title">AI Document Summary</h2>
                                    <p>
                                        {summaryDocFilename
                                            ? `${summaryDocFilename} · Synthesized overview`
                                            : 'Synthesized knowledge overview'}
                                    </p>
                                </div>

                                <button
                                    type="button"
                                    className="modal-close"
                                    onClick={closeSummary}
                                    aria-label="Close summary modal"
                                >
                                    <X size={18} />
                                </button>
                            </div>

                            <div className="modal-body">
                                {summaryLoading ? (
                                    <div className="documents-empty modal-loading-empty">
                                        <div className="loading-pulse-ring" aria-hidden="true"></div>
                                        <h3>Generating AI summary...</h3>
                                        <p>Analyzing key concepts and synthesizing takeaways.</p>
                                    </div>
                                ) : (
                                    <>
                                        <div className="modal-content-toolbar">
                                            <div className="summary-meta-badges">
                                                <label className="summary-control-group">
                                                    <span>Format:</span>
                                                    <select
                                                        className="summary-select"
                                                        value={summaryFormat}
                                                        onChange={(e) => setSummaryFormat(e.target.value)}
                                                        disabled={regenerating}
                                                        aria-label="Select summary format"
                                                    >
                                                        <option value="numbered">Numbered</option>
                                                        <option value="paragraphs">Paragraphs</option>
                                                        <option value="bullets">Bullets</option>
                                                        <option value="headings">Headings</option>
                                                    </select>
                                                </label>

                                                <label className="summary-control-group">
                                                    <span>Length:</span>
                                                    <select
                                                        className="summary-select"
                                                        value={summaryLength}
                                                        onChange={(e) => setSummaryLength(e.target.value)}
                                                        disabled={regenerating}
                                                        aria-label="Select summary length"
                                                    >
                                                        <option value="detailed">Detailed</option>
                                                        <option value="brief">Brief</option>
                                                    </select>
                                                </label>
                                            </div>

                                            <div className="summary-actions-group">
                                                <button
                                                    type="button"
                                                    className="modal-copy-btn summary-regen-btn"
                                                    onClick={handleRegenerateSummary}
                                                    disabled={regenerating}
                                                    title="Regenerate summary with AI using selected options"
                                                    aria-label="Regenerate summary"
                                                >
                                                    <RotateCw size={13} className={regenerating ? 'spin-anim' : ''} />
                                                    <span>{regenerating ? 'Regenerating...' : 'Regenerate'}</span>
                                                </button>

                                                <button
                                                    type="button"
                                                    className="modal-copy-btn"
                                                    onClick={handleCopySummary}
                                                    disabled={regenerating}
                                                    title="Copy summary to clipboard"
                                                    aria-label="Copy summary to clipboard"
                                                >
                                                    {copiedSummaryText ? (
                                                        <>
                                                            <Check size={14} />
                                                            <span>Copied</span>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <Copy size={14} />
                                                            <span>Copy Summary</span>
                                                        </>
                                                    )}
                                                </button>
                                            </div>
                                        </div>

                                        {summaryFeedback && (
                                            <div className="summary-status-alert summary-status-success" role="status">
                                                <Check size={15} />
                                                <span>{summaryFeedback}</span>
                                            </div>
                                        )}

                                        {summaryError && (
                                            <div className="summary-status-alert summary-status-error" role="alert">
                                                <AlertTriangle size={15} />
                                                <span>{summaryError}</span>
                                            </div>
                                        )}

                                        <div
                                            className="summary-text"
                                            style={regenerating ? { opacity: 0.6 } : undefined}
                                        >
                                            {summary}
                                        </div>
                                    </>
                                )}
                            </div>
                        </motion.div>
                    </motion.div>
                )}

                {/* DELETE DOCUMENT CONFIRMATION MODAL */}
                {documentToDelete && (
                    <motion.div
                        className="modal-overlay"
                        onClick={!deleteLoading ? handleCancelDelete : undefined}
                        role="dialog"
                        aria-modal="true"
                        aria-labelledby="delete-doc-modal-title"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.22 }}
                    >
                        <motion.div
                            className="modal delete-doc-modal"
                            onClick={(e) => e.stopPropagation()}
                            initial={{ opacity: 0, scale: 0.94, y: 15 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.94, y: 15 }}
                            transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
                        >
                            <div className="modal-header">
                                <div>
                                    <h2 id="delete-doc-modal-title">Delete Document</h2>
                                    <p>Permanent document removal</p>
                                </div>

                                <button
                                    type="button"
                                    className="modal-close"
                                    onClick={handleCancelDelete}
                                    disabled={deleteLoading}
                                    aria-label="Close delete confirmation"
                                >
                                    <X size={18} />
                                </button>
                            </div>

                            <div className="modal-body delete-doc-modal-body">
                                <div className="delete-doc-warning">
                                    <div className="delete-doc-warning-icon-wrap" aria-hidden="true">
                                        <AlertTriangle size={24} />
                                    </div>
                                    <div className="delete-doc-warning-content">
                                        <p className="delete-doc-question">
                                            Are you sure you want to delete this document?
                                        </p>
                                        <p className="delete-doc-target" title={documentToDelete.filename}>
                                            <FileText size={15} />
                                            <span className="delete-doc-filename">{documentToDelete.filename}</span>
                                        </p>
                                        <p className="delete-doc-subtext">
                                            This action cannot be undone. All extracted text and vector embeddings will be permanently removed.
                                        </p>
                                    </div>
                                </div>

                                {deleteError && (
                                    <p className="delete-doc-error" role="alert">
                                        {deleteError}
                                    </p>
                                )}
                            </div>

                            <div className="delete-doc-actions">
                                <button
                                    type="button"
                                    className="delete-doc-cancel-btn"
                                    onClick={handleCancelDelete}
                                    disabled={deleteLoading}
                                >
                                    Cancel
                                </button>

                                <button
                                    type="button"
                                    className="delete-doc-confirm-btn"
                                    onClick={handleConfirmDelete}
                                    disabled={deleteLoading}
                                >
                                    {deleteLoading ? 'Deleting...' : 'Delete document'}
                                </button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    )
}

export default Documents
