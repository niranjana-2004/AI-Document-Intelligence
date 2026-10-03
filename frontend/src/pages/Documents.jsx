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

    const [selectedDocument, setSelectedDocument] =
        useState(null)

    const [documentLoading, setDocumentLoading] =
        useState(false)

    const [summary, setSummary] = useState('')
    const [summaryLoading, setSummaryLoading] =
        useState(false)

    const [error, setError] = useState('')


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

        } catch (error) {
            console.error(
                'Error fetching documents:',
                error
            )

            setError(
                error.message ||
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

        } catch (error) {
            console.error(
                'Upload error:',
                error
            )

            setUploadMessage(
                error.message ||
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

            const data = await apiRequest(
                `/documents/${documentId}`
            )

            setSelectedDocument(data)

        } catch (error) {
            console.error(
                'Open document error:',
                error
            )

            setError(
                error.message ||
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

            const data = await apiRequest(
                `/documents/${documentId}/summary`
            )

            setSummary(
                data.summary ||
                'No summary available.'
            )

        } catch (error) {
            console.error(
                'Summary error:',
                error
            )

            setError(
                error.message ||
                'Failed to generate summary.'
            )

        } finally {
            setSummaryLoading(false)
        }
    }


    /* ========================================
       DELETE DOCUMENT
    ======================================== */

    const handleDelete = async (documentId) => {
        const confirmed = window.confirm(
            'Are you sure you want to delete this document?'
        )

        if (!confirmed) {
            return
        }

        try {
            setError('')

            await apiRequest(
                `/documents/${documentId}`,
                {
                    method: 'DELETE',
                }
            )

            setDocuments((currentDocuments) =>
                currentDocuments.filter(
                    (document) =>
                        document.id !== documentId
                )
            )

        } catch (error) {
            console.error(
                'Delete error:',
                error
            )

            setError(
                error.message ||
                'Failed to delete document.'
            )
        }
    }


    /* ========================================
       CLOSE MODALS
    ======================================== */

    const closeDocument = () => {
        setSelectedDocument(null)
    }

    const closeSummary = () => {
        setSummary('')
    }


    /* ========================================
       FILTER DOCUMENTS
    ======================================== */

    const filteredDocuments =
        documents.filter((document) =>
            document.filename
                ?.toLowerCase()
                .includes(
                    searchTerm.toLowerCase()
                )
        )


    return (
        <>
            <main className="documents-page">

                {/* =================================
                    PAGE HEADER
                ================================= */}

                <section className="documents-page-header">

                    <div>

                        <p className="eyebrow">
                            DOCUMENT LIBRARY
                        </p>

                        <h2>
                            Your Documents
                        </h2>

                        <p>
                            Upload, manage, and explore your
                            documents in one place.
                        </p>

                    </div>

                    <button
                        className="documents-upload-button"
                        onClick={handleUploadClick}
                        disabled={uploading}
                    >
                        {uploading
                            ? 'Uploading...'
                            : '+ Upload Document'}
                    </button>

                </section>


                {/* Hidden file input */}

                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.docx,.txt"
                    onChange={handleFileUpload}
                    style={{ display: 'none' }}
                />


                {/* =================================
                    UPLOAD MESSAGE
                ================================= */}

                {uploadMessage && (

                    <div className="upload-message">
                        {uploadMessage}
                    </div>

                )}


                {/* =================================
                    ERROR
                ================================= */}

                {error && (

                    <div className="error-message">
                        {error}
                    </div>

                )}


                {/* =================================
                    SEARCH + COUNT
                ================================= */}

                <section className="documents-toolbar">

                    <div>

                        <h3>
                            All Documents
                        </h3>

                        <p>
                            {documents.length}{' '}
                            {documents.length === 1
                                ? 'document'
                                : 'documents'}
                        </p>

                    </div>

                    <input
                        className="documents-search"
                        type="text"
                        placeholder="Search documents..."
                        value={searchTerm}
                        onChange={(event) =>
                            setSearchTerm(
                                event.target.value
                            )
                        }
                    />

                </section>


                {/* =================================
                    DOCUMENT LIST
                ================================= */}

                <section className="documents-library">

                    {loading && (

                        <div className="documents-empty">

                            <h3>
                                Loading documents...
                            </h3>

                        </div>

                    )}


                    {!loading &&
                        documents.length === 0 && (

                            <div className="documents-empty">

                                <div className="documents-empty-icon">
                                    📄
                                </div>

                                <h3>
                                    No documents yet
                                </h3>

                                <p>
                                    Upload your first PDF, DOCX,
                                    or TXT document to get started.
                                </p>

                                <button
                                    className="documents-upload-button"
                                    onClick={handleUploadClick}
                                >
                                    Upload Document
                                </button>

                            </div>

                        )}


                    {!loading &&
                        documents.length > 0 &&
                        filteredDocuments.length === 0 && (

                            <div className="documents-empty">

                                <h3>
                                    No matching documents
                                </h3>

                                <p>
                                    Try searching with a different
                                    document name.
                                </p>

                            </div>

                        )}


                    {!loading &&
                        filteredDocuments.length > 0 && (

                            <div className="documents-grid">

                                {filteredDocuments.map(
                                    (document) => (

                                        <article
                                            className="document-card"
                                            key={document.id}
                                        >

                                            <div className="document-card-top">

                                                <div className="document-card-icon">
                                                    📄
                                                </div>

                                                <button
                                                    className="document-delete"
                                                    onClick={() =>
                                                        handleDelete(
                                                            document.id
                                                        )
                                                    }
                                                    title="Delete document"
                                                >
                                                    ×
                                                </button>

                                            </div>


                                            <div className="document-card-body">

                                                <h3>
                                                    {document.filename}
                                                </h3>

                                                <p>
                                                    {document.document_type}
                                                </p>

                                                <span>
                                                    {document.text_length}
                                                    {' characters'}
                                                </span>

                                            </div>


                                            <div className="document-card-actions">

                                                <button
                                                    className="document-action"
                                                    onClick={() =>
                                                        handleOpenDocument(
                                                            document.id
                                                        )
                                                    }
                                                >
                                                    Open
                                                </button>

                                                <button
                                                    className="document-action"
                                                    onClick={() =>
                                                        handleSummary(
                                                            document.id
                                                        )
                                                    }
                                                >
                                                    Summarize
                                                </button>

                                            </div>

                                        </article>

                                    )
                                )}

                            </div>

                        )}

                </section>

            </main>


            {/* =================================
                DOCUMENT MODAL
            ================================= */}

            {selectedDocument && (

                <div className="modal-overlay">

                    <div className="modal">

                        <div className="modal-header">

                            <div>

                                <h2>
                                    {selectedDocument.filename}
                                </h2>

                                <p>
                                    {selectedDocument.document_type}
                                    {' · '}
                                    {selectedDocument.text_length}
                                    {' characters'}
                                </p>

                            </div>

                            <button
                                className="modal-close"
                                onClick={closeDocument}
                            >
                                ✕
                            </button>

                        </div>

                        <div className="modal-body">

                            <h3>
                                Extracted Text
                            </h3>

                            <div className="document-text">

                                {documentLoading
                                    ? 'Loading document...'
                                    : selectedDocument.extracted_text}

                            </div>

                        </div>

                    </div>

                </div>

            )}


            {/* =================================
                SUMMARY MODAL
            ================================= */}

            {(summaryLoading || summary) && (

                <div className="modal-overlay">

                    <div className="modal">

                        <div className="modal-header">

                            <div>

                                <h2>
                                    AI Summary
                                </h2>

                                <p>
                                    Generated from your document
                                </p>

                            </div>

                            <button
                                className="modal-close"
                                onClick={closeSummary}
                            >
                                ✕
                            </button>

                        </div>

                        <div className="modal-body">

                            {summaryLoading ? (

                                <div className="documents-empty">

                                    <h3>
                                        Generating summary...
                                    </h3>

                                    <p>
                                        AI is analyzing your document.
                                    </p>

                                </div>

                            ) : (

                                <div className="summary-text">
                                    {summary}
                                </div>

                            )}

                        </div>

                    </div>

                </div>

            )}

        </>
    )
}

export default Documents