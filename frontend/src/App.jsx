import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_URL = 'http://127.0.0.1:8000'

function App() {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')

  const [showAll, setShowAll] = useState(false)

  const [selectedDocument, setSelectedDocument] = useState(null)
  const [documentLoading, setDocumentLoading] = useState(false)

  const [summary, setSummary] = useState('')
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [summaryDocument, setSummaryDocument] = useState(null)
  const [showSummaryDocuments, setShowSummaryDocuments] = useState(false)

  const [showAskModal, setShowAskModal] = useState(false)
  const [question, setQuestion] = useState('')
  const [questionAnswer, setQuestionAnswer] = useState('')
  const [questionLoading, setQuestionLoading] = useState(false)

  const [showSearchModal, setShowSearchModal] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)

  const [summaryCount, setSummaryCount] = useState(0)

  const fileInputRef = useRef(null)

  useEffect(() => {
    fetchDocuments()
  }, [])

  // -----------------------------------------
  // FETCH DOCUMENTS
  // -----------------------------------------

  const fetchDocuments = async () => {
    try {
      setLoading(true)
      setError('')

      const response = await fetch(`${API_URL}/documents/`)

      if (!response.ok) {
        throw new Error('Failed to fetch documents')
      }

      const data = await response.json()

      const documentList = Array.isArray(data)
        ? data
        : data.documents || []

      setDocuments(documentList)

      // Check which documents have summaries
      const summaryResults = await Promise.all(
        documentList.map(async (document) => {
          try {
            const summaryResponse = await fetch(
              `${API_URL}/documents/${document.id}/summary`
            )

            if (!summaryResponse.ok) {
              return false
            }

            const summaryData = await summaryResponse.json()

            return Boolean(summaryData.summary)
          } catch {
            return false
          }
        })
      )

      setSummaryCount(
        summaryResults.filter(Boolean).length
      )

    } catch (error) {
      console.error('Error fetching documents:', error)
      setError('Unable to connect to the backend.')
    } finally {
      setLoading(false)
    }
  }

  // -----------------------------------------
  // UPLOAD
  // -----------------------------------------

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

      const response = await fetch(
        `${API_URL}/documents/upload`,
        {
          method: 'POST',
          body: formData,
        }
      )

      if (!response.ok) {
        const errorData =
          await response.json().catch(() => null)

        throw new Error(
          errorData?.detail || 'Upload failed.'
        )
      }

      await response.json()

      setUploadMessage(
        `${file.name} uploaded successfully!`
      )

      await fetchDocuments()

    } catch (error) {
      console.error('Upload error:', error)

      setUploadMessage(
        error.message || 'Failed to upload document.'
      )

    } finally {
      setUploading(false)

      // Allow selecting the same file again
      event.target.value = ''
    }
  }


  // -----------------------------------------
  // OPEN DOCUMENT
  // -----------------------------------------

  const handleOpenDocument = async (documentId) => {
    console.log("OPEN BUTTON CLICKED, ID:", documentId)
    try {
      setDocumentLoading(true)
      setError('')

      const response = await fetch(
        `${API_URL}/documents/${documentId}`
      )

      if (!response.ok) {
        throw new Error('Failed to open document')
      }

      const data = await response.json()

      setSelectedDocument(data)

    } catch (error) {
      console.error('Open document error:', error)

      setError(
        error.message || 'Failed to open document.'
      )

    } finally {
      setDocumentLoading(false)
    }
  }

  // -----------------------------------------
  // SUMMARY
  // -----------------------------------------

  const handleSummary = async (documentId) => {
    try {
      setSummaryLoading(true)
      setSummary('')
      setError('')

      const selectedDoc = documents.find(
        (document) => document.id === documentId
      )

      setSummaryDocument(selectedDoc || null)

      const response = await fetch(
        `${API_URL}/documents/${documentId}/summary`
      )

      if (!response.ok) {
        throw new Error('Failed to generate summary')
      }

      const data = await response.json()

      setSummary(data.summary || 'No summary available.')

    } catch (error) {
      console.error('Summary error:', error)

      setError(
        error.message || 'Failed to generate summary.'
      )

    } finally {
      setSummaryLoading(false)
    }
  }

  // -----------------------------------------
  // ASK AI
  // -----------------------------------------

  const handleAskAI = async () => {
    if (!question.trim()) {
      return
    }

    try {
      setQuestionLoading(true)
      setQuestionAnswer('')

      const response = await fetch(
        `${API_URL}/documents/ask`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            query: question,
            document_id: null,
            top_k: 5,
          }),
        }
      )

      if (!response.ok) {
        const errorData =
          await response.json().catch(() => null)

        throw new Error(
          errorData?.detail || 'Failed to get AI answer.'
        )
      }

      const data = await response.json()

      // Support common response field names
      const answer =
        data.answer ||
        data.response ||
        data.result ||
        'No answer returned.'

      setQuestionAnswer(answer)

    } catch (error) {
      console.error('Ask AI error:', error)

      setQuestionAnswer(
        error.message || 'Failed to get answer.'
      )

    } finally {
      setQuestionLoading(false)
    }
  }

  // -----------------------------------------
  // SEMANTIC SEARCH
  // -----------------------------------------

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      return
    }

    try {
      setSearchLoading(true)
      setSearchResults([])

      const response = await fetch(
        `${API_URL}/documents/search?query=${encodeURIComponent(
          searchQuery
        )}&top_k=5`
      )

      if (!response.ok) {
        const errorData =
          await response.json().catch(() => null)

        throw new Error(
          errorData?.detail || 'Search failed.'
        )
      }

      const data = await response.json()

      setSearchResults(data.results || [])

    } catch (error) {
      console.error('Search error:', error)

      setSearchResults([
        {
          error:
            error.message || 'Search failed.',
        },
      ])

    } finally {
      setSearchLoading(false)
    }
  }

  // -----------------------------------------
  // CLOSE MODALS
  // -----------------------------------------

  const closeDocument = () => {
    setSelectedDocument(null)
  }

  const closeAskModal = () => {
    setShowAskModal(false)
    setQuestion('')
    setQuestionAnswer('')
  }

  const closeSearchModal = () => {
    setShowSearchModal(false)
    setSearchQuery('')
    setSearchResults([])
  }

  const displayedDocuments = showAll
    ? documents
    : documents.slice(0, 5)

  return (
    <div className="app">

      {/* Hidden file input */}

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.txt"
        onChange={handleFileUpload}
        style={{ display: 'none' }}
      />

      {/* -------------------------------- */}
      {/* HEADER */}
      {/* -------------------------------- */}

      <header className="topbar">

        <div className="brand">

          <div className="brand-icon">
            AI
          </div>

          <div>
            <h1>Document Intelligence</h1>

            <p>
              AI-powered document analysis
            </p>
          </div>

        </div>

        <div className="status">
          <span className="status-dot"></span>
          AI System Ready
        </div>

      </header>

      <main className="dashboard">

        {/* -------------------------------- */}
        {/* WELCOME */}
        {/* -------------------------------- */}

        <section className="welcome">

          <div>

            <p className="eyebrow">
              DOCUMENT INTELLIGENCE
            </p>

            <h2>
              Turn your documents into insights.
            </h2>

            <p className="welcome-text">
              Upload a document and use AI to summarize,
              search, and ask questions about its content.
            </p>

          </div>

          <button
            className="upload-button"
            onClick={handleUploadClick}
            disabled={uploading}
          >
            {uploading
              ? 'Uploading...'
              : '+ Upload Document'}
          </button>

        </section>

        {/* -------------------------------- */}
        {/* STATS */}
        {/* -------------------------------- */}

        <section className="stats">

          <div className="stat-card">

            <span className="stat-label">
              Documents
            </span>

            <strong>
              {loading ? '...' : documents.length}
            </strong>

            <span className="stat-description">
              Uploaded documents
            </span>

          </div>

          <div className="stat-card">

            <span className="stat-label">
              AI Questions
            </span>

            <strong>
              —
            </strong>

            <span className="stat-description">
              Questions answered
            </span>

          </div>

          <div className="stat-card">

            <span className="stat-label">
              AI Summaries
            </span>

            <strong>
              {loading ? '...' : summaryCount}
            </strong>

            <span className="stat-description">
              Generated summaries
            </span>

          </div>

        </section>

        {/* -------------------------------- */}
        {/* MAIN CONTENT */}
        {/* -------------------------------- */}

        <section className="content-grid">

          {/* DOCUMENTS */}

          <div className="documents-card">

            <div className="section-header">

              <div>

                <h3>
                  Recent Documents
                </h3>

                <p>
                  Your recently uploaded documents
                </p>

              </div>

              <button
                className="view-all"
                onClick={() =>
                  setShowAll(!showAll)
                }
              >
                {showAll ? 'Show recent' : 'View all'}
              </button>

            </div>

            {uploadMessage && (
              <div className="upload-message">
                {uploadMessage}
              </div>
            )}

            {error && (
              <div className="upload-message">
                {error}
              </div>
            )}

            {loading && (
              <div className="empty-state">
                <h4>
                  Loading documents...
                </h4>
              </div>
            )}

            {!loading &&
              !error &&
              documents.length === 0 && (

                <div className="empty-state">

                  <div className="empty-icon">
                    📄
                  </div>

                  <h4>
                    No documents yet
                  </h4>

                  <p>
                    Upload your first document to start
                    using AI Document Intelligence.
                  </p>

                  <button
                    className="upload-secondary"
                    onClick={handleUploadClick}
                    disabled={uploading}
                  >
                    {uploading
                      ? 'Uploading...'
                      : 'Upload Document'}
                  </button>

                </div>
              )}

            {!loading &&
              documents.length > 0 && (

                <div className="document-list">

                  {displayedDocuments.map((document) => (

                    <div
                      className="document-item"
                      key={document.id}
                    >

                      <div className="document-icon">
                        📄
                      </div>

                      <div className="document-info">

                        <h4>
                          {document.filename}
                        </h4>

                        <p>
                          {document.document_type}
                          {' · '}
                          {document.text_length}
                          {' characters'}
                        </p>

                      </div>

                      <div className="document-actions">

                        <button
                          className="document-action"
                          onClick={() => handleOpenDocument(document.id)}
                        >
                          Open
                        </button>

                        <button
                          className="document-action summarize-action"
                          onClick={() => handleSummary(document.id)}
                        >
                          Summarize
                        </button>

                      </div>

                    </div>

                  ))}

                </div>
              )}
          </div>
          {/* -------------------------------- */}
          {/* AI CAPABILITIES */}
          {/* -------------------------------- */}

          <div className="features-card">

            <h3>
              AI Capabilities
            </h3>

            <p className="features-subtitle">
              Explore what you can do with your documents.
            </p>

            {/* ASK AI */}

            <button
              className="feature"
              onClick={() =>
                setShowAskModal(true)
              }
            >

              <div className="feature-icon">
                ✦
              </div>

              <div>

                <h4>
                  Ask AI
                </h4>

                <p>
                  Ask questions and get answers
                  grounded in your documents.
                </p>

              </div>

            </button>

            {/* SUMMARIZE */}

            <button
              className="feature"
              onClick={() => {
                if (documents.length > 0) {
                  setShowSummaryDocuments(true)
                } else {
                  setUploadMessage('Upload a document first.')
                }
              }}
            >

              <div className="feature-icon">
                ≡
              </div>

              <div>

                <h4>
                  Summarize
                </h4>

                <p>
                  Generate concise summaries from
                  your uploaded documents.
                </p>

              </div>

            </button>

            {/* SEARCH */}

            <button
              className="feature"
              onClick={() =>
                setShowSearchModal(true)
              }
            >

              <div className="feature-icon">
                ⌕
              </div>

              <div>

                <h4>
                  Semantic Search
                </h4>

                <p>
                  Find relevant information using
                  meaning, not just keywords.
                </p>

              </div>

            </button>

          </div>

        </section>

      </main>

      {/* ================================= */}
      {/* DOCUMENT MODAL */}
      {/* ================================= */}

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
                {selectedDocument.extracted_text}
              </div>

            </div>

          </div>

        </div>
      )}

      {/* SUMMARY DOCUMENT SELECTION MODAL */}

      {showSummaryDocuments && (
        <div className="modal-overlay">

          <div className="modal summary-selection-modal">

            <div className="modal-header">

              <div>
                <h2>Select a Document</h2>

                <p>
                  Choose which document you want to summarize.
                </p>
              </div>

              <button
                className="modal-close"
                onClick={() => setShowSummaryDocuments(false)}
              >
                ×
              </button>

            </div>

            <div className="summary-document-list">

              {documents.map((document) => (

                <div
                  className="summary-document-item"
                  key={document.id}
                >

                  <div className="document-icon">
                    📄
                  </div>

                  <div className="document-info">

                    <h4>
                      {document.filename}
                    </h4>

                    <p>
                      {document.document_type}
                      {' · '}
                      {document.text_length}
                      {' characters'}
                    </p>

                  </div>

                  <button
                    className="document-action"
                    onClick={() => {
                      setShowSummaryDocuments(false)
                      handleSummary(document.id)
                    }}
                  >
                    Summarize
                  </button>

                </div>

              ))}

            </div>

          </div>

        </div>
      )}
      {/* ================================= */}
      {/* SUMMARY MODAL */}
      {/* ================================= */}

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
                onClick={() =>
                  setSummary('')
                }
              >
                ✕
              </button>

            </div>

            <div className="modal-body">

              {summaryLoading ? (

                <div className="empty-state">
                  <h4>
                    Loading summary...
                  </h4>
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

      {/* ================================= */}
      {/* ASK AI MODAL */}
      {/* ================================= */}

      {showAskModal && (

        <div className="modal-overlay">

          <div className="modal">

            <div className="modal-header">

              <div>

                <h2>
                  Ask AI
                </h2>

                <p>
                  Ask a question about your documents
                </p>

              </div>

              <button
                className="modal-close"
                onClick={closeAskModal}
              >
                ✕
              </button>

            </div>

            <div className="modal-body">

              <textarea
                className="question-input"
                placeholder="Example: What are the main skills mentioned in the documents?"
                value={question}
                onChange={(event) =>
                  setQuestion(event.target.value)
                }
              />

              <button
                className="primary-action"
                onClick={handleAskAI}
                disabled={
                  questionLoading ||
                  !question.trim()
                }
              >
                {questionLoading
                  ? 'Thinking...'
                  : 'Ask AI'}
              </button>

              {questionAnswer && (

                <div className="answer-box">

                  <h3>
                    AI Answer
                  </h3>

                  <p>
                    {questionAnswer}
                  </p>

                </div>

              )}

            </div>

          </div>

        </div>
      )}

      {/* ================================= */}
      {/* SEARCH MODAL */}
      {/* ================================= */}

      {showSearchModal && (

        <div className="modal-overlay">

          <div className="modal">

            <div className="modal-header">

              <div>

                <h2>
                  Semantic Search
                </h2>

                <p>
                  Find relevant information in your documents
                </p>

              </div>

              <button
                className="modal-close"
                onClick={closeSearchModal}
              >
                ✕
              </button>

            </div>

            <div className="modal-body">

              <div className="search-row">

                <input
                  className="search-input"
                  type="text"
                  placeholder="Search your documents..."
                  value={searchQuery}
                  onChange={(event) =>
                    setSearchQuery(event.target.value)
                  }
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      handleSearch()
                    }
                  }}
                />

                <button
                  className="primary-action"
                  onClick={handleSearch}
                  disabled={
                    searchLoading ||
                    !searchQuery.trim()
                  }
                >
                  {searchLoading
                    ? 'Searching...'
                    : 'Search'}
                </button>

              </div>

              <div className="search-results">

                {searchResults.map(
                  (result, index) => (

                    <div
                      className="search-result"
                      key={index}
                    >

                      {result.error ? (

                        <p>
                          {result.error}
                        </p>

                      ) : (

                        <>
                          <h4>
                            Result {index + 1}
                          </h4>

                          <p>
                            {result.content ||
                              result.text ||
                              JSON.stringify(result)}
                          </p>
                        </>

                      )}

                    </div>
                  )
                )}

              </div>

            </div>

          </div>

        </div>
      )}

    </div>
  )
}

export default App