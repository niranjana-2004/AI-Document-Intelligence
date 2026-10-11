import { useEffect, useRef, useState } from 'react'
import { apiRequest } from '../services/api'
import '../App.css'

function Documents() {
    const fileInputRef = useRef(null)

    const [documents, setDocuments] = useState([])
    const [loading, setLoading] = useState(true)

    const [uploading, setUploading] = useState(false)
    const [uploadMessage, setUploadMessage] = useState('')

    const [searchTerm, setSearchTerm] = useState('')

    const [selectedDocument, setSelectedDocument] = useState(null)
    const [documentLoading, setDocumentLoading] = useState(false)

    const [summary, setSummary] = useState('')
    const [summaryLoading, setSummaryLoading] = useState(false)
    const [summaryFormat, setSummaryFormat] = useState('numbered')
    const [summaryLength, setSummaryLength] = useState('detailed')

    const [error, setError] = useState('')
    const [copiedDocText, setCopiedDocText] = useState(false)
    const [copiedSummaryText, setCopiedSummaryText] = useState(false)

    const [documentToDelete, setDocumentToDelete] = useState(null)
    const [deleteLoading, setDeleteLoading] = useState(false)
    const [deleteError, setDeleteError] = useState('')

    /* ========================================
       FETCH DOCUMENTS
    ======================================== */

    useEffect(() => {
        fetchDocuments()
    }, [])

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

    /* ========================================
       UPLOAD
    ======================================== */

    const handleUploadClick = () => {
        fileInputRef.current?.click()
    }

    const handleFileUpload = async (event) => {
        const file = event.target.files[0]

        if (!file) {
            return
        }

        const allowedTypes = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain',
        ]

        if (!allowedTypes.includes(file.type)) {
            setUploadMessage(
                'Please select a PDF, DOCX, or TXT file.'
            )
            event.target.value = ''
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

            setUploadMessage(
                `${file.name} uploaded successfully.`
            )

            await fetchDocuments()
        } catch (err) {
            console.error('Upload error:', err)
            setUploadMessage(
                err.message ||
                'Failed to upload document.'
            )
        } finally {
            setUploading(false)
            event.target.value = ''
        }
    }

    /* ========================================
       OPEN DOCUMENT
    ======================================== */

    const handleOpenDocument = async (documentId) => {
        try {
            setDocumentLoading(true)
            setSelectedDocument(null)
            setError('')
            setCopiedDocText(false)

            const data = await apiRequest(`/documents/${documentId}`)
            setSelectedDocument(data)
        } catch (err) {
            console.error('Open document error:', err)
            setError(
                err.message ||
                'Failed to open document.'
            )
        } finally {
            setDocumentLoading(false)
        }
    }

    /* ========================================
       SUMMARY
    ======================================== */

    const handleSummary = async (documentId) => {
        try {
            setSummaryLoading(true)
            setSummary('')
            setError('')
            setCopiedSummaryText(false)

            const data = await apiRequest(
                `/documents/${documentId}/summary?format=${encodeURIComponent(summaryFormat)}&length=${encodeURIComponent(summaryLength)}`
            )

            setSummary(
                data.summary ||
                'No summary available.'
            )
        } catch (err) {
            console.error('Summary error:', err)
            setError(
                err.message ||
                'Failed to generate summary.'
            )
        } finally {
            setSummaryLoading(false)
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

            await apiRequest(
                `/documents/${documentToDelete.id}`,
                {
                    method: 'DELETE',
                }
            )

            setDocuments((currentDocuments) =>
                currentDocuments.filter(
                    (document) =>
                        document.id !== documentToDelete.id
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
    }

    const closeSummary = () => {
        setSummary('')
        setCopiedSummaryText(false)
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

    const filteredDocuments = documents.filter((document) =>
        document.filename
            ?.toLowerCase()
            .includes(searchTerm.toLowerCase())
    )

    return (
        <>
            <main className="documents-page">
                {/* =================================
                    PAGE HEADER
                ================================= */}
                <section className="documents-page-header">
                    <div className="documents-header-text">
                        <p className="eyebrow">DOCUMENT REPOSITORY</p>
                        <h2>Documents</h2>
                        <p>
                            Upload, organize, and analyze your multi-format document library.
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
                                <span>Uploading...</span>
                            </>
                        ) : (
                            <>
                                <span className="upload-plus" aria-hidden="true">+</span>
                                <span>Upload Document</span>
                            </>
                        )}
                    </button>
                </section>

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
                        <span className="msg-icon" aria-hidden="true">ℹ</span>
                        <span>{uploadMessage}</span>
                    </div>
                )}

                {error && (
                    <div className="error-message" role="alert">
                        <span className="msg-icon" aria-hidden="true">⚠</span>
                        <span>{error}</span>
                    </div>
                )}

                {/* =================================
                    SEARCH + COUNT TOOLBAR
                ================================= */}
                <section className="documents-toolbar">
                    <div className="documents-toolbar-title">
                        <h3>All Documents</h3>
                        <p>
                            {documents.length === 0
                                ? '0 documents'
                                : filteredDocuments.length === documents.length
                                ? `${documents.length} ${documents.length === 1 ? 'document' : 'documents'}`
                                : `Showing ${filteredDocuments.length} of ${documents.length} documents`}
                        </p>
                    </div>

                    <div className="documents-search-wrapper">
                        <span className="documents-search-icon" aria-hidden="true">⌕</span>
                        <input
                            className="documents-search"
                            type="text"
                            placeholder="Search documents by name..."
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
                                ✕
                            </button>
                        )}
                    </div>
                </section>

                {/* =================================
                    DOCUMENT LIBRARY
                ================================= */}
                <section className="documents-library">
                    {loading && (
                        <div className="documents-empty">
                            <div className="loading-pulse-ring" aria-hidden="true"></div>
                            <h3>Loading document library...</h3>
                            <p>Connecting to knowledge vault.</p>
                        </div>
                    )}

                    {!loading && documents.length === 0 && (
                        <div className="documents-empty">
                            <div className="documents-empty-icon" aria-hidden="true">
                                📄
                            </div>
                            <h3>No documents yet</h3>
                            <p>
                                Upload your first PDF, DOCX, or TXT document to get started.
                            </p>
                            <button
                                type="button"
                                className="documents-upload-button"
                                onClick={handleUploadClick}
                                disabled={uploading}
                            >
                                Upload Document
                            </button>
                        </div>
                    )}

                    {!loading &&
                        documents.length > 0 &&
                        filteredDocuments.length === 0 && (
                            <div className="documents-empty">
                                <div className="documents-empty-icon" aria-hidden="true">
                                    🔍
                                </div>
                                <h3>No matching documents</h3>
                                <p>
                                    No documents matched &ldquo;{searchTerm}&rdquo;. Try another name.
                                </p>
                                <button
                                    type="button"
                                    className="clear-button"
                                    onClick={() => setSearchTerm('')}
                                >
                                    Clear Search
                                </button>
                            </div>
                        )}

                    {!loading && filteredDocuments.length > 0 && (
                        <div className="documents-grid">
                            {filteredDocuments.map((doc) => {
                                const ext = doc.filename
                                    ? doc.filename.split('.').pop().toUpperCase()
                                    : 'DOC'
                                const badgeLabel = ['PDF', 'DOCX', 'TXT'].includes(ext)
                                    ? ext
                                    : (doc.document_type || 'DOC').toUpperCase()

                                return (
                                    <article className="document-card" key={doc.id}>
                                        <div className="document-card-top">
                                            <div className="document-card-badge-wrap">
                                                <span className={`document-card-badge badge-${badgeLabel.toLowerCase()}`}>
                                                    {badgeLabel}
                                                </span>
                                            </div>

                                            <button
                                                type="button"
                                                className="document-delete"
                                                onClick={() => handleRequestDelete(doc)}
                                                title={`Delete ${doc.filename}`}
                                                aria-label={`Delete ${doc.filename}`}
                                            >
                                                ✕
                                            </button>
                                        </div>

                                        <div className="document-card-body">
                                            <h3 title={doc.filename}>{doc.filename}</h3>
                                            <div className="document-card-meta">
                                                <span className="doc-meta-type">
                                                    {doc.document_type || badgeLabel.toLowerCase()}
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
                                                Inspect Text
                                            </button>

                                            <button
                                                type="button"
                                                className="document-action summary-action"
                                                onClick={() => handleSummary(doc.id)}
                                                disabled={summaryLoading}
                                                aria-label={`Generate summary of ${doc.filename}`}
                                            >
                                                {summaryLoading ? 'Generating...' : 'Summarize'}
                                            </button>
                                        </div>
                                    </article>
                                )
                            })}
                        </div>
                    )}
                </section>
            </main>

            {/* =================================
                DOCUMENT EXTRACTED TEXT MODAL
            ================================= */}
            {selectedDocument && (
                <div
                    className="modal-overlay"
                    onClick={closeDocument}
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="doc-modal-title"
                >
                    <div className="modal" onClick={(e) => e.stopPropagation()}>
                        <div className="modal-header">
                            <div>
                                <h2 id="doc-modal-title">{selectedDocument.filename}</h2>
                                <p>
                                    {selectedDocument.document_type} ·{' '}
                                    {typeof selectedDocument.text_length === 'number'
                                        ? selectedDocument.text_length.toLocaleString()
                                        : selectedDocument.text_length}{' '}
                                    characters
                                </p>
                            </div>

                            <button
                                type="button"
                                className="modal-close"
                                onClick={closeDocument}
                                aria-label="Close document modal"
                            >
                                ✕
                            </button>
                        </div>

                        <div className="modal-body">
                            <div className="modal-content-toolbar">
                                <h3>Extracted Text Content</h3>
                                <button
                                    type="button"
                                    className="modal-copy-btn"
                                    onClick={handleCopyDocText}
                                    title="Copy extracted text to clipboard"
                                >
                                    {copiedDocText ? '✓ Copied' : 'Copy Text'}
                                </button>
                            </div>

                            <div className="document-text">
                                {documentLoading
                                    ? 'Loading document...'
                                    : selectedDocument.extracted_text || 'No text content available.'}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* =================================
                AI SUMMARY MODAL
            ================================= */}
            {(summaryLoading || summary) && (
                <div
                    className="modal-overlay"
                    onClick={closeSummary}
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="summary-modal-title"
                >
                    <div className="modal" onClick={(e) => e.stopPropagation()}>
                        <div className="modal-header">
                            <div>
                                <h2 id="summary-modal-title">AI Document Summary</h2>
                                <p>Synthesized knowledge overview</p>
                            </div>

                            <button
                                type="button"
                                className="modal-close"
                                onClick={closeSummary}
                                aria-label="Close summary modal"
                            >
                                ✕
                            </button>
                        </div>

                        <div className="modal-body">
                            {summaryLoading ? (
                                <div className="documents-empty modal-loading-empty">
                                    <div className="loading-pulse-ring" aria-hidden="true"></div>
                                    <h3>Generating summary...</h3>
                                    <p>AI is analyzing and condensing key takeaways.</p>
                                </div>
                            ) : (
                                <>
                                    <div className="modal-content-toolbar">
                                        <div className="summary-meta-badges">
                                            <span className="summary-badge">
                                                Format: {summaryFormat}
                                            </span>
                                            <span className="summary-badge">
                                                Length: {summaryLength}
                                            </span>
                                        </div>

                                        <button
                                            type="button"
                                            className="modal-copy-btn"
                                            onClick={handleCopySummary}
                                            title="Copy summary to clipboard"
                                        >
                                            {copiedSummaryText ? '✓ Copied' : 'Copy Summary'}
                                        </button>
                                    </div>

                                    <div className="summary-text">
                                        {summary}
                                    </div>
                                </>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* =================================
                DELETE DOCUMENT CONFIRMATION MODAL
            ================================= */}
            {documentToDelete && (
                <div
                    className="modal-overlay"
                    onClick={!deleteLoading ? handleCancelDelete : undefined}
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="delete-doc-modal-title"
                >
                    <div
                        className="modal delete-doc-modal"
                        onClick={(e) => e.stopPropagation()}
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
                                ✕
                            </button>
                        </div>

                        <div className="modal-body delete-doc-modal-body">
                            <div className="delete-doc-warning">
                                <span className="delete-doc-warning-icon" aria-hidden="true">⚠️</span>
                                <div className="delete-doc-warning-content">
                                    <p className="delete-doc-question">
                                        Are you sure you want to delete this document?
                                    </p>
                                    <p className="delete-doc-target" title={documentToDelete.filename}>
                                        📄 <span className="delete-doc-filename">{documentToDelete.filename}</span>
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
                    </div>
                </div>
            )}
        </>
    )
}

export default Documents