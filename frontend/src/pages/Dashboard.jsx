import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import '../App.css'

const API_URL = 'http://127.0.0.1:8000'

function Dashboard() {
  const navigate = useNavigate()

  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [showAll, setShowAll] = useState(false)

  const [selectedDocument, setSelectedDocument] = useState(null)
  const [documentLoading, setDocumentLoading] = useState(false)

  const [summary, setSummary] = useState('')
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [showSummaryDocuments, setShowSummaryDocuments] =
    useState(false)

  const [showAskModal, setShowAskModal] = useState(false)
  const [question, setQuestion] = useState('')
  const [questionAnswer, setQuestionAnswer] = useState('')
  const [questionLoading, setQuestionLoading] = useState(false)

  const [showSearchModal, setShowSearchModal] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)

  const [summaryCount, setSummaryCount] = useState(0)

  useEffect(() => {
    fetchDocuments()
  }, [])

  const fetchDocuments = async () => {
    try {
      setLoading(true)
      setError('')

      const response = await fetch(
        `${API_URL}/documents/`
      )

      if (!response.ok) {
        throw new Error('Failed to fetch documents')
      }

      const data = await response.json()

      const documentList = Array.isArray(data)
        ? data
        : data.documents || []

      setDocuments(documentList)

      const summaryResults = await Promise.all(
        documentList.map(async (document) => {
          try {
            const summaryResponse = await fetch(
              `${API_URL}/documents/${document.id}/summary`
            )

            if (!summaryResponse.ok) {
              return false
            }

            const summaryData =
              await summaryResponse.json()

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
      console.error(
        'Error fetching documents:',
        error
      )

      setError(
        'Unable to connect to the backend.'
      )

    } finally {
      setLoading(false)
    }
  }

  const handleOpenDocument = async (documentId) => {
    try {
      setDocumentLoading(true)
      setError('')

      const response = await fetch(
        `${API_URL}/documents/${documentId}`
      )

      if (!response.ok) {
        throw new Error(
          'Failed to open document'
        )
      }

      const data = await response.json()

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

  const handleSummary = async (documentId) => {
    try {
      setSummaryLoading(true)
      setSummary('')
      setError('')

      const response = await fetch(
        `${API_URL}/documents/${documentId}/summary`
      )

      if (!response.ok) {
        throw new Error(
          'Failed to generate summary'
        )
      }

      const data = await response.json()

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
          await response
            .json()
            .catch(() => null)

        throw new Error(
          errorData?.detail ||
          'Failed to get AI answer.'
        )
      }

      const data =
        await response.json()

      const answer =
        data.answer ||
        data.response ||
        data.result ||
        'No answer returned.'

      setQuestionAnswer(answer)

    } catch (error) {
      console.error(
        'Ask AI error:',
        error
      )

      setQuestionAnswer(
        error.message ||
        'Failed to get answer.'
      )

    } finally {
      setQuestionLoading(false)
    }
  }

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
          await response
            .json()
            .catch(() => null)

        throw new Error(
          errorData?.detail ||
          'Search failed.'
        )
      }

      const data =
        await response.json()

      setSearchResults(
        data.results || []
      )

    } catch (error) {
      console.error(
        'Search error:',
        error
      )

      setSearchResults([
        {
          error:
            error.message ||
            'Search failed.',
        },
      ])

    } finally {
      setSearchLoading(false)
    }
  }

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
    <>
      <main className="dashboard">

        {/* =========================
            WELCOME SECTION
        ========================== */}

        <section className="welcome">

          <div>

            <p className="eyebrow">
              AI DOCUMENT WORKSPACE
            </p>

            <h2>
              Turn your documents into answers.
            </h2>

            <p className="welcome-text">
              Ask questions, generate summaries,
              and search across your uploaded
              documents using AI.
            </p>

          </div>

          <div className="welcome-actions">

            <button
              className="welcome-action-primary"
              onClick={() =>
                setShowAskModal(true)
              }
            >
              Ask AI
            </button>

            <button
              className="welcome-action-secondary"
              onClick={() =>
                setShowSearchModal(true)
              }
            >
              Search Documents
            </button>

          </div>

        </section>


        {/* =========================
            STATISTICS
        ========================== */}

        <section className="stats">

          <div className="stat-card">

            <span className="stat-label">
              Documents
            </span>

            <strong>
              {loading
                ? '...'
                : documents.length}
            </strong>

            <span className="stat-description">
              Uploaded documents
            </span>

          </div>


          <div className="stat-card">

            <span className="stat-label">
              AI Summaries
            </span>

            <strong>
              {loading
                ? '...'
                : summaryCount}
            </strong>

            <span className="stat-description">
              Generated summaries
            </span>

          </div>


          <div className="stat-card">

            <span className="stat-label">
              Supported Formats
            </span>

            <strong className="format-value">
              PDF · DOCX · TXT
            </strong>

            <span className="stat-description">
              Accepted document types
            </span>

          </div>

        </section>


        {/* =========================
            RECENT DOCUMENTS + ACTIVITY
        ========================== */}

        <section className="content-grid">

          {/* RECENT DOCUMENTS */}

          <div className="documents-card">

            <div className="section-header">

              <div>

                <h3>
                  Recent Documents
                </h3>

                <p>
                  Your recently uploaded
                  documents
                </p>

              </div>

              <button
                className="view-all"
                onClick={() =>
                  setShowAll(!showAll)
                }
              >
                {showAll
                  ? 'Show recent'
                  : 'View all'}
              </button>

            </div>


            {error && (
              <div className="error-message">
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
                    Your uploaded documents
                    will appear here.
                    You can add documents
                    from the Documents page.
                  </p>

                  <button
                    className="upload-secondary"
                    onClick={() =>
                      navigate('/documents')
                    }
                  >
                    Go to Documents
                  </button>

                </div>
              )}


            {!loading &&
              documents.length > 0 && (

                <div className="document-list">

                  {displayedDocuments.map(
                    (document) => (

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

                      </div>

                    )
                  )}

                </div>
              )}

          </div>


          {/* AI ACTIVITY */}

          <div className="activity-card">

            <div className="section-header">

              <div>

                <h3>
                  AI Activity
                </h3>

                <p>
                  Your document workspace
                  activity
                </p>

              </div>

            </div>


            <div className="activity-list">

              <div className="activity-item">

                <div className="activity-icon">
                  ?
                </div>

                <div className="activity-info">

                  <h4>
                    Questions Asked
                  </h4>

                  <p>
                    Questions answered by AI
                  </p>

                </div>

                <strong>
                  —
                </strong>

              </div>


              <div className="activity-item">

                <div className="activity-icon">
                  ⌕
                </div>

                <div className="activity-info">

                  <h4>
                    Searches
                  </h4>

                  <p>
                    Semantic searches performed
                  </p>

                </div>

                <strong>
                  —
                </strong>

              </div>


              <div className="activity-item">

                <div className="activity-icon">
                  ≡
                </div>

                <div className="activity-info">

                  <h4>
                    Summaries
                  </h4>

                  <p>
                    AI-generated document
                    summaries
                  </p>

                </div>

                <strong>
                  {loading
                    ? '...'
                    : summaryCount}
                </strong>

              </div>

            </div>

          </div>

        </section>


        {/* =========================
            HOW IT WORKS
        ========================== */}

        <section className="how-it-works">

          <div className="how-it-works-header">

            <div>

              <p className="eyebrow">
                WORKFLOW
              </p>

              <h3>
                How Document Intelligence works
              </h3>

              <p>
                Turn your documents into searchable,
                useful knowledge in a few simple
                steps.
              </p>

            </div>

          </div>


          <div className="workflow-steps">

            <div className="workflow-step">

              <div className="workflow-number">
                01
              </div>

              <div>

                <h4>
                  Upload
                </h4>

                <p>
                  Add your PDF, DOCX, or TXT
                  documents from the Documents
                  page.
                </p>

              </div>

            </div>


            <div className="workflow-step">

              <div className="workflow-number">
                02
              </div>

              <div>

                <h4>
                  Understand
                </h4>

                <p>
                  Your documents are extracted,
                  processed, chunked, and
                  converted into embeddings.
                </p>

              </div>

            </div>


            <div className="workflow-step">

              <div className="workflow-number">
                03
              </div>

              <div>

                <h4>
                  Ask
                </h4>

                <p>
                  Ask questions and get answers
                  based on the information in
                  your documents.
                </p>

              </div>

            </div>


            <div className="workflow-step">

              <div className="workflow-number">
                04
              </div>

              <div>

                <h4>
                  Discover
                </h4>

                <p>
                  Search your document knowledge
                  base and find relevant
                  information using AI.
                </p>

              </div>

            </div>

          </div>

        </section>

      </main>


      {/* =========================
          DOCUMENT MODAL
      ========================== */}

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


      {/* =========================
          SUMMARY DOCUMENT SELECTION
      ========================== */}

      {showSummaryDocuments && (

        <div className="modal-overlay">

          <div className="modal summary-selection-modal">

            <div className="modal-header">

              <div>

                <h2>
                  Select a Document
                </h2>

                <p>
                  Choose which document you
                  want to summarize.
                </p>

              </div>

              <button
                className="modal-close"
                onClick={() =>
                  setShowSummaryDocuments(
                    false
                  )
                }
              >
                ×
              </button>

            </div>

            <div className="summary-document-list">

              {documents.map(
                (document) => (

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

                        setShowSummaryDocuments(
                          false
                        )

                        handleSummary(
                          document.id
                        )

                      }}
                    >
                      Summarize
                    </button>

                  </div>
                )
              )}

            </div>

          </div>

        </div>
      )}


      {/* =========================
          SUMMARY MODAL
      ========================== */}

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


      {/* =========================
          ASK AI MODAL
      ========================== */}

      {showAskModal && (

        <div className="modal-overlay">

          <div className="modal">

            <div className="modal-header">

              <div>

                <h2>
                  Ask AI
                </h2>

                <p>
                  Ask a question about your
                  documents
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
                  setQuestion(
                    event.target.value
                  )
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


      {/* =========================
          SEARCH MODAL
      ========================== */}

      {showSearchModal && (

        <div className="modal-overlay">

          <div className="modal">

            <div className="modal-header">

              <div>

                <h2>
                  Semantic Search
                </h2>

                <p>
                  Find relevant information
                  in your documents
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
                    setSearchQuery(
                      event.target.value
                    )
                  }
                  onKeyDown={(event) => {

                    if (
                      event.key === 'Enter'
                    ) {
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
                              JSON.stringify(
                                result
                              )}
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

    </>
  )
}

export default Dashboard