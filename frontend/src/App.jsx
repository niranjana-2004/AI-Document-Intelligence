import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_URL = 'http://127.0.0.1:8000'

function App() {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadMessage, setUploadMessage] = useState('')

  const fileInputRef = useRef(null)

  useEffect(() => {
    fetchDocuments()
  }, [])

  const fetchDocuments = async () => {
    try {
      setLoading(true)
      setError('')

      const response = await fetch(`${API_URL}/documents/`)

      if (!response.ok) {
        throw new Error('Failed to fetch documents')
      }

      const data = await response.json()

      setDocuments(
        Array.isArray(data)
          ? data
          : data.documents || []
      )
    } catch (error) {
      console.error('Error fetching documents:', error)
      setError('Unable to connect to the backend.')
    } finally {
      setLoading(false)
    }
  }
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
      setUploadMessage('Please select a PDF, DOCX, or TXT file.')
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
        const errorData = await response.json().catch(() => null)

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

  return (
    <div className="app">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.txt"
        onChange={handleFileUpload}
        style={{ display: 'none' }}
      />
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">AI</div>

          <div>
            <h1>Document Intelligence</h1>
            <p>AI-powered document analysis</p>
          </div>
        </div>

        <div className="status">
          <span className="status-dot"></span>
          AI System Ready
        </div>
      </header>

      <main className="dashboard">
        <section className="welcome">
          <div>
            <p className="eyebrow">DOCUMENT INTELLIGENCE</p>

            <h2>
              Turn your documents into insights.
            </h2>

            <p className="welcome-text">
              Upload a document and use AI to summarize, search,
              and ask questions about its content.
            </p>
          </div>

          <button
            className="upload-button"
            onClick={handleUploadClick}
            disabled={uploading}
          >
            {uploading ? 'Uploading...' : '+ Upload Document'}
          </button>
        </section>

        <section className="stats">
          <div className="stat-card">
            <span className="stat-label">Documents</span>

            <strong>
              {loading ? '...' : documents.length}
            </strong>

            <span className="stat-description">
              Uploaded documents
            </span>
          </div>

          <div className="stat-card">
            <span className="stat-label">AI Questions</span>

            <strong>0</strong>

            <span className="stat-description">
              Questions answered
            </span>
          </div>

          <div className="stat-card">
            <span className="stat-label">AI Summaries</span>

            <strong>
              {loading ? '...' : documents.filter(
                (document) => document.summary
              ).length}
            </strong>

            <span className="stat-description">
              Generated summaries
            </span>

          </div>
        </section>

        <section className="content-grid">
          <div className="documents-card">
            <div className="section-header">
              <div>
                <h3>Recent Documents</h3>

                <p>
                  Your recently uploaded documents
                </p>
              </div>

              <button className="view-all">
                View all
              </button>
            </div>

            {uploadMessage && (
              <div className="upload-message">
                {uploadMessage}
              </div>
            )}

            {loading && (
              <div className="empty-state">
                <h4>Loading documents...</h4>
              </div>
            )}

            {!loading && !error && documents.length === 0 && (
              <div className="empty-state">
                <div className="empty-icon">📄</div>

                <h4>No documents yet</h4>

                <p>
                  Upload your first document to start using
                  AI Document Intelligence.
                </p>

                <button
                  className="upload-secondary"
                  onClick={handleUploadClick}
                  disabled={uploading}
                >
                  {uploading ? 'Uploading...' : 'Upload Document'}
                </button>
              </div>
            )}

            {!loading && !error && documents.length > 0 && (
              <div className="document-list">
                {documents.slice(0, 5).map((document) => (
                  <div
                    className="document-item"
                    key={document.id}
                  >
                    <div className="document-icon">
                      📄
                    </div>

                    <div className="document-info">
                      <h4>{document.filename}</h4>

                      <p>
                        {document.document_type} ·{' '}
                        {document.text_length} characters
                      </p>
                    </div>

                    <button className="document-action">
                      Open
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="features-card">
            <h3>AI Capabilities</h3>

            <p className="features-subtitle">
              Explore what you can do with your documents.
            </p>

            <div className="feature">
              <div className="feature-icon">✦</div>

              <div>
                <h4>Ask AI</h4>

                <p>
                  Ask questions and get answers grounded in
                  your documents.
                </p>
              </div>
            </div>

            <div className="feature">
              <div className="feature-icon">≡</div>

              <div>
                <h4>Summarize</h4>

                <p>
                  Generate concise summaries from your
                  uploaded documents.
                </p>
              </div>
            </div>

            <div className="feature">
              <div className="feature-icon">⌕</div>

              <div>
                <h4>Semantic Search</h4>

                <p>
                  Find relevant information using meaning,
                  not just keywords.
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

export default App