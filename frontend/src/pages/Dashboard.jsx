import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Sparkles,
  Search,
  FileText,
  UploadCloud,
  FileCheck,
  Layers,
  X,
  Copy,
  Check,
  MessageSquare,
  Zap,
} from 'lucide-react'
import { apiRequest } from '../services/api'
import '../App.css'

function Dashboard() {
  const navigate = useNavigate()

  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [showAll, setShowAll] = useState(false)

  const [selectedDocument, setSelectedDocument] = useState(null)
  const [documentLoading, setDocumentLoading] = useState(false)
  const [copiedDocText, setCopiedDocText] = useState(false)

  const [summary, setSummary] = useState('')
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [copiedSummaryText, setCopiedSummaryText] = useState(false)

  const [activityCounts, setActivityCounts] = useState({
    ai_questions: 0,
    searches: 0,
  })
  const [summaryCount, setSummaryCount] = useState(0)

  const [showAskModal, setShowAskModal] = useState(false)
  const [question, setQuestion] = useState('')
  const [questionAnswer, setQuestionAnswer] = useState('')
  const [questionLoading, setQuestionLoading] = useState(false)

  const [showSearchModal, setShowSearchModal] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [searchLoading, setSearchLoading] = useState(false)

  const user = (() => {
    try {
      const stored = localStorage.getItem('user')
      return stored ? JSON.parse(stored) : null
    } catch {
      return null
    }
  })()

  const greetingTime = (() => {
    const hour = new Date().getHours()
    if (hour < 12) return 'Good morning'
    if (hour < 18) return 'Good afternoon'
    return 'Good evening'
  })()

  useEffect(() => {
    let ignore = false
    const loadInitialDashboardData = async () => {
      try {
        const [docsData, activityData] = await Promise.allSettled([
          apiRequest('/documents/'),
          apiRequest('/auth/activity'),
        ])
        if (ignore) return

        if (docsData.status === 'fulfilled') {
          const documentList = Array.isArray(docsData.value)
            ? docsData.value
            : docsData.value?.documents || []
          setDocuments(documentList)
        } else {
          setError(docsData.reason?.message || 'Unable to connect to the backend.')
        }

        if (activityData.status === 'fulfilled' && activityData.value) {
          setActivityCounts({
            ai_questions: activityData.value.ai_questions ?? 0,
            searches: activityData.value.searches ?? 0,
          })
          setSummaryCount(activityData.value.summaries ?? 0)
        }
      } finally {
        if (!ignore) setLoading(false)
      }
    }

    loadInitialDashboardData()
    return () => {
      ignore = true
    }
  }, [])

  const handleOpenDocument = async (documentId) => {
    try {
      setDocumentLoading(true)
      setError('')
      setCopiedDocText(false)

      const data = await apiRequest(`/documents/${documentId}`)
      setSelectedDocument(data)
    } catch (error) {
      console.error('Open document error:', error)
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
      setCopiedSummaryText(false)

      const data = await apiRequest(`/documents/${documentId}/summary`)

      setSummary(
        data.summary ||
        'No summary available.'
      )

      // Refresh activity count safely
      try {
        const activityData = await apiRequest('/auth/activity')
        if (activityData) {
          setSummaryCount(activityData.summaries ?? 0)
          setActivityCounts({
            ai_questions: activityData.ai_questions ?? 0,
            searches: activityData.searches ?? 0,
          })
        }
      } catch (refreshErr) {
        console.warn('Unable to refresh activity counts after summary:', refreshErr)
      }
    } catch (error) {
      console.error('Summary error:', error)
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

      const data = await apiRequest(
        '/documents/ask',
        {
          method: 'POST',
          body: JSON.stringify({
            query: question,
            document_id: null,
            top_k: 5,
          }),
        }
      )

      const answer =
        data.answer ||
        data.response ||
        data.result ||
        'No answer returned.'

      setQuestionAnswer(answer)
    } catch (error) {
      console.error('Ask AI error:', error)
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

      const data = await apiRequest(
        `/documents/search?query=${encodeURIComponent(
          searchQuery
        )}&top_k=5`
      )

      setSearchResults(data.results || [])
    } catch (error) {
      console.error('Search error:', error)
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

  const closeDocument = () => {
    setSelectedDocument(null)
    setCopiedDocText(false)
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
          <div className="welcome-content">
            <p className="eyebrow">
              COGNIDOCS WORKSPACE
            </p>

            <h2>
              {greetingTime}, {user?.full_name ? user.full_name.split(' ')[0] : 'there'}.
            </h2>

            <p className="welcome-text">
              Transform your documents into answers. Ask questions, generate synthesized
              summaries, and explore your knowledge base with grounded local AI.
            </p>
          </div>

          <div className="welcome-actions">
            <button
              className="welcome-action-primary"
              onClick={() => setShowAskModal(true)}
            >
              <Sparkles size={16} />
              <span>Ask AI</span>
            </button>

            <button
              className="welcome-action-secondary"
              onClick={() => setShowSearchModal(true)}
            >
              <Search size={16} />
              <span>Search Documents</span>
            </button>

            <button
              className="welcome-action-secondary"
              onClick={() => navigate('/documents')}
            >
              <UploadCloud size={16} />
              <span>Upload Document</span>
            </button>
          </div>
        </section>

        {/* =========================
            STATISTICS CARDS
        ========================== */}
        <section className="stats">
          <div className="stat-card">
            <div className="stat-card-header">
              <span className="stat-label">Documents</span>
              <div className="stat-icon-wrap" style={{ color: '#38bdf8' }}>
                <FileText size={18} />
              </div>
            </div>

            <strong className="stat-value">
              {loading ? '...' : documents.length}
            </strong>

            <span className="stat-description">
              Indexed in vector repository
            </span>
          </div>

          <div className="stat-card">
            <div className="stat-card-header">
              <span className="stat-label">AI Questions</span>
              <div className="stat-icon-wrap" style={{ color: '#c084fc' }}>
                <MessageSquare size={18} />
              </div>
            </div>

            <strong className="stat-value">
              {loading ? '...' : activityCounts.ai_questions}
            </strong>

            <span className="stat-description">
              Grounded answers generated
            </span>
          </div>

          <div className="stat-card">
            <div className="stat-card-header">
              <span className="stat-label">AI Summaries</span>
              <div className="stat-icon-wrap" style={{ color: '#2dd4bf' }}>
                <Layers size={18} />
              </div>
            </div>

            <strong className="stat-value">
              {loading ? '...' : summaryCount}
            </strong>

            <span className="stat-description">
              Document syntheses produced
            </span>
          </div>

          <div className="stat-card">
            <div className="stat-card-header">
              <span className="stat-label">Supported Formats</span>
              <div className="stat-icon-wrap" style={{ color: '#f59e0b' }}>
                <FileCheck size={18} />
              </div>
            </div>

            <strong className="stat-value format-value">
              PDF · DOCX · TXT
            </strong>

            <span className="stat-description">
              Multi-format parsing active
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
                <h3>Recent Documents</h3>
                <p>Your latest uploaded files and indexed records</p>
              </div>

              {documents.length > 5 && (
                <button
                  className="view-all"
                  onClick={() => setShowAll(!showAll)}
                >
                  {showAll ? 'Show recent' : 'View all'}
                </button>
              )}
            </div>

            {error && (
              <div className="error-message">
                {error}
              </div>
            )}

            {loading && (
              <div className="empty-state">
                <div className="loading-pulse-ring" aria-hidden="true"></div>
                <h4>Loading documents...</h4>
                <p>Fetching repository indices</p>
              </div>
            )}

            {!loading && !error && documents.length === 0 && (
              <div className="empty-state">
                <div className="empty-icon">
                  <UploadCloud size={40} />
                </div>

                <h4>No documents yet</h4>

                <p>
                  Upload your first PDF, Word, or text file to start questioning
                  and exploring your knowledge base.
                </p>

                <button
                  className="upload-secondary"
                  onClick={() => navigate('/documents')}
                >
                  <UploadCloud size={16} />
                  <span>Go to Documents</span>
                </button>
              </div>
            )}

            {!loading && documents.length > 0 && (
              <div className="document-list">
                {displayedDocuments.map((doc) => {
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
                    <div className="document-item" key={doc.id}>
                      <div className={`doc-item-badge ${badgeClass}`}>
                        {ext}
                      </div>

                      <div className="document-info">
                        <h4 title={doc.filename}>{doc.filename}</h4>
                        <p>
                          <span>{doc.document_type || ext.toLowerCase()}</span>
                          <span> · </span>
                          <span>
                            {typeof doc.text_length === 'number'
                              ? `${doc.text_length.toLocaleString()} chars`
                              : `${doc.text_length || 0} chars`}
                          </span>
                        </p>
                      </div>

                      <div className="document-actions">
                        <button
                          className="document-action"
                          onClick={() => handleOpenDocument(doc.id)}
                        >
                          Open Text
                        </button>

                        <button
                          className="document-action summary-action"
                          onClick={() => handleSummary(doc.id)}
                        >
                          Summarize
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* AI ACTIVITY */}
          <div className="activity-card">
            <div className="section-header">
              <div>
                <h3>AI Activity</h3>
                <p>Workspace operations and metrics</p>
              </div>
            </div>

            <div className="activity-list">
              <div className="activity-item">
                <div className="activity-icon" style={{ background: 'rgba(192, 132, 252, 0.15)', color: '#c084fc' }}>
                  <MessageSquare size={18} />
                </div>

                <div className="activity-info">
                  <h4>Questions Asked</h4>
                  <p>Inquiries answered by local LLM</p>
                </div>

                <strong className="activity-count">
                  {loading ? '...' : activityCounts.ai_questions}
                </strong>
              </div>

              <div className="activity-item">
                <div className="activity-icon" style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8' }}>
                  <Search size={18} />
                </div>

                <div className="activity-info">
                  <h4>Semantic Searches</h4>
                  <p>Neural vector lookups executed</p>
                </div>

                <strong className="activity-count">
                  {loading ? '...' : activityCounts.searches}
                </strong>
              </div>

              <div className="activity-item">
                <div className="activity-icon" style={{ background: 'rgba(45, 212, 191, 0.15)', color: '#2dd4bf' }}>
                  <Layers size={18} />
                </div>

                <div className="activity-info">
                  <h4>Summaries</h4>
                  <p>Synthesized document briefs</p>
                </div>

                <strong className="activity-count">
                  {loading ? '...' : summaryCount}
                </strong>
              </div>

              <div className="activity-item">
                <div className="activity-icon" style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#f59e0b' }}>
                  <Zap size={18} />
                </div>

                <div className="activity-info">
                  <h4>AI Engine State</h4>
                  <p>Ollama Llama 3.2 · Local RAG</p>
                </div>

                <span className="engine-status-tag">Ready</span>
              </div>
            </div>
          </div>
        </section>

        {/* =========================
            HOW IT WORKS WORKFLOW
        ========================== */}
        <section className="how-it-works">
          <div className="how-it-works-header">
            <div>
              <p className="eyebrow">INTELLIGENCE PIPELINE</p>
              <h3>How Cognidocs processes your knowledge</h3>
              <p>
                From raw multi-format ingestion to context-verified AI answers.
              </p>
            </div>
          </div>

          <div className="workflow-steps">
            <div className="workflow-step">
              <div className="workflow-number">01</div>
              <div>
                <h4>Upload</h4>
                <p>
                  Add PDF, Word (.docx), or text (.txt) files into your secure workspace.
                </p>
              </div>
            </div>

            <div className="workflow-step">
              <div className="workflow-number">02</div>
              <div>
                <h4>Understand</h4>
                <p>
                  Content is parsed, partitioned into semantic chunks, and embedded into vectors.
                </p>
              </div>
            </div>

            <div className="workflow-step">
              <div className="workflow-number">03</div>
              <div>
                <h4>Ask</h4>
                <p>
                  Interrogate documents with local AI and receive answers anchored by citations.
                </p>
              </div>
            </div>

            <div className="workflow-step">
              <div className="workflow-number">04</div>
              <div>
                <h4>Discover</h4>
                <p>
                  Perform neural semantic searches across passages to uncover hidden facts.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* =========================
          DOCUMENT TEXT MODAL
      ========================== */}
      {selectedDocument && (
        <div className="modal-overlay" onClick={closeDocument}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>{selectedDocument.filename}</h2>
                <p>
                  {selectedDocument.document_type} ·{' '}
                  {typeof selectedDocument.text_length === 'number'
                    ? selectedDocument.text_length.toLocaleString()
                    : selectedDocument.text_length}{' '}
                  characters
                </p>
              </div>

              <button
                className="modal-close"
                onClick={closeDocument}
                aria-label="Close document dialog"
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              <div className="modal-content-toolbar">
                <h3>Extracted Text Content</h3>
                <button
                  type="button"
                  className="modal-copy-btn"
                  onClick={handleCopyDocText}
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

              <div className="document-text">
                {documentLoading
                  ? 'Loading document...'
                  : selectedDocument.extracted_text || 'No text extracted.'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* =========================
          SUMMARY MODAL
      ========================== */}
      {(summaryLoading || summary) && (
        <div className="modal-overlay" onClick={() => setSummary('')}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>AI Document Summary</h2>
                <p>Generated by local AI intelligence</p>
              </div>

              <button
                className="modal-close"
                onClick={() => setSummary('')}
                aria-label="Close summary dialog"
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              {summaryLoading ? (
                <div className="empty-state">
                  <div className="loading-pulse-ring" aria-hidden="true"></div>
                  <h4>Synthesizing summary...</h4>
                  <p>AI is analyzing and condensing key takeaways.</p>
                </div>
              ) : (
                <>
                  <div className="modal-content-toolbar">
                    <span className="summary-status-pill">Overview Ready</span>
                    <button
                      type="button"
                      className="modal-copy-btn"
                      onClick={handleCopySummary}
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
                  <div className="summary-text">{summary}</div>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* =========================
          ASK AI MODAL
      ========================== */}
      {showAskModal && (
        <div className="modal-overlay" onClick={closeAskModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Quick Ask AI</h2>
                <p>Query your document knowledge base</p>
              </div>

              <button
                className="modal-close"
                onClick={closeAskModal}
                aria-label="Close Ask AI dialog"
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              <textarea
                className="question-input"
                placeholder="Example: What are the main recommendations mentioned in the documents?"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                rows={4}
              />

              <div className="modal-action-row">
                <button
                  className="primary-action"
                  onClick={handleAskAI}
                  disabled={questionLoading || !question.trim()}
                >
                  <Sparkles size={16} />
                  <span>{questionLoading ? 'Thinking...' : 'Ask AI'}</span>
                </button>
                <button
                  type="button"
                  className="secondary-action"
                  onClick={() => {
                    closeAskModal()
                    navigate('/ask-ai')
                  }}
                >
                  Open Full Chat →
                </button>
              </div>

              {questionAnswer && (
                <div className="answer-box">
                  <div className="answer-box-header">
                    <Sparkles size={15} className="text-accent" />
                    <h3>Grounded Answer</h3>
                  </div>
                  <p>{questionAnswer}</p>
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
        <div className="modal-overlay" onClick={closeSearchModal}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2>Quick Semantic Search</h2>
                <p>Find relevant passages by meaning</p>
              </div>

              <button
                className="modal-close"
                onClick={closeSearchModal}
                aria-label="Close search dialog"
              >
                <X size={18} />
              </button>
            </div>

            <div className="modal-body">
              <div className="search-row">
                <input
                  className="search-input"
                  type="text"
                  placeholder="Enter a concept, query, or topic..."
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                      handleSearch()
                    }
                  }}
                  autoFocus
                />

                <button
                  className="primary-action"
                  onClick={handleSearch}
                  disabled={searchLoading || !searchQuery.trim()}
                >
                  <Search size={15} />
                  <span>{searchLoading ? 'Searching...' : 'Search'}</span>
                </button>
              </div>

              <div className="search-results">
                {searchResults.map((result, index) => (
                  <div className="search-result" key={index}>
                    {result.error ? (
                      <p>{result.error}</p>
                    ) : (
                      <>
                        <div className="search-result-top">
                          <span className="search-result-num">Result {index + 1}</span>
                          {result.score != null && (
                            <span className="search-result-score">
                              {Math.round(result.score * 100)}% match
                            </span>
                          )}
                        </div>
                        <p>
                          {result.content || result.text || JSON.stringify(result)}
                        </p>
                      </>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default Dashboard
