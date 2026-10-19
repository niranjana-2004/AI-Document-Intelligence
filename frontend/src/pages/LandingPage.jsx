import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import CognidocsLogo from '../components/CognidocsLogo'
import '../styles/landing.css'

function LandingPage() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [currentTheme, setCurrentTheme] = useState('ocean')

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    setIsAuthenticated(Boolean(token))

    const savedTheme = localStorage.getItem('app_theme') || 'ocean'
    setCurrentTheme(savedTheme)
  }, [])

  const toggleTheme = () => {
    const nextTheme = currentTheme === 'dark' ? 'ocean' : 'dark'
    setCurrentTheme(nextTheme)
    localStorage.setItem('app_theme', nextTheme)
    document.documentElement.dataset.theme = nextTheme
  }

  return (
    <div className="landing-container">
      {/* ========================================
          TOP NAVIGATION BAR
          ======================================== */}
      <header className="landing-nav">
        <Link to="/" className="landing-brand">
          <div className="landing-logo-emblem">
            <CognidocsLogo />
          </div>
          <div>
            <div className="landing-brand-title">Cognidocs</div>
            <div className="landing-brand-tagline">Knowledge, unlocked.</div>
          </div>
        </Link>

        <nav className="landing-nav-links">
          <a href="#features" className="landing-nav-link">Capabilities</a>
          <a href="#workflow" className="landing-nav-link">Pipeline</a>
          <a href="#formats" className="landing-nav-link">Formats</a>
        </nav>

        <div className="landing-nav-actions">
          <button
            type="button"
            className="theme-toggle-btn"
            onClick={toggleTheme}
            title={currentTheme === 'dark' ? 'Switch to Light mode' : 'Switch to Dark mode'}
            aria-label="Toggle visual theme"
          >
            {currentTheme === 'dark' ? '☀️' : '🌙'}
          </button>

          {isAuthenticated ? (
            <Link to="/dashboard" className="landing-register-btn">
              Go to Workspace →
            </Link>
          ) : (
            <>
              <Link to="/login" className="landing-login-btn">
                Login
              </Link>
              <Link to="/register" className="landing-register-btn">
                Sign Up
              </Link>
            </>
          )}
        </div>
      </header>

      {/* ========================================
          HERO SECTION
          ======================================== */}
      <section className="landing-hero">
        <div className="hero-pill">
          <span className="hero-pill-sparkle">✦</span>
          <span>Next-Generation Document Intelligence</span>
        </div>

        <h1 className="hero-title">
          Turn your documents into <br />
          <span className="gradient-text">intelligent answers.</span>
        </h1>

        <p className="hero-tagline">
          <strong>Cognidocs: Knowledge, unlocked.</strong> Upload PDF, DOCX, or text files
          and interrogate them with local AI. Enjoy grounded RAG answers, customizable summaries,
          and deep semantic search with zero cloud lock-in.
        </p>

        <div className="hero-cta-group">
          {isAuthenticated ? (
            <Link to="/dashboard" className="hero-primary-cta">
              Open Your Workspace →
            </Link>
          ) : (
            <>
              <Link to="/register" className="hero-primary-cta">
                Get Started Free →
              </Link>
              <Link to="/login" className="hero-secondary-cta">
                Login to Account
              </Link>
            </>
          )}
        </div>

        <div className="hero-badges-row">
          <div className="hero-badge-item">
            <span className="hero-badge-icon">✓</span>
            <span><strong>Context-Grounded</strong> — Answers anchored in your documents</span>
          </div>
          <div className="hero-badge-item">
            <span className="hero-badge-icon">⚡</span>
            <span><strong>Local LLM RAG</strong> — Private & instant</span>
          </div>
          <div className="hero-badge-item">
            <span className="hero-badge-icon">📁</span>
            <span><strong>Multi-Format</strong> — PDF · DOCX · TXT</span>
          </div>
        </div>
      </section>

      {/* ========================================
          INTERACTIVE PRODUCT PREVIEW CARD
          ======================================== */}
      <section className="hero-preview-container">
        <div className="hero-preview-card">
          <div className="preview-card-header">
            <div className="preview-window-dots">
              <span className="dot red"></span>
              <span className="dot yellow"></span>
              <span className="dot green"></span>
            </div>
            <div className="preview-status-pill">
              <span className="pulse-dot"></span>
              <span>Cognidocs Intelligence Engine Active</span>
            </div>
          </div>

          <div className="preview-card-body">
            <div className="preview-column">
              <div className="preview-box">
                <div className="preview-box-label">
                  <span>📄 Source Document</span>
                </div>
                <p className="preview-box-text">
                  <strong>Quarterly_Report_2026.pdf</strong> (14,820 characters extracted, 18 vector chunks indexed)
                </p>
              </div>

              <div className="preview-box">
                <div className="preview-box-label">
                  <span>💬 User Query</span>
                </div>
                <p className="preview-box-text">
                  &ldquo;What were the primary security measures implemented in the cloud infrastructure?&rdquo;
                </p>
              </div>
            </div>

            <div className="preview-column">
              <div className="preview-box ai-response">
                <div className="preview-box-label">
                  <span>✦ Grounded AI Response</span>
                </div>
                <p className="preview-box-text">
                  According to Section 4.2 of the report, the cloud architecture deployed end-to-end AES-256 encryption, zero-trust IAM token verification, and automated vulnerability scanning across all service endpoints.
                </p>
              </div>

              <div className="preview-box">
                <div className="preview-box-label">
                  <span>≡ Structured Summary Generated</span>
                </div>
                <p className="preview-box-text">
                  Bullet summary available in detailed and brief lengths with citation tracking.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================
          CORE CAPABILITIES SECTION
          ======================================== */}
      <section className="landing-section" id="features">
        <div className="section-header">
          <p className="section-eyebrow">CORE CAPABILITIES</p>
          <h2 className="section-heading">Everything you need to master your files</h2>
          <p className="section-subheading">
            Cognidocs extracts text, creates vector embeddings, and links a local language model
            to your personal document library.
          </p>
        </div>

        <div className="features-grid">
          <article className="feature-card">
            <div className="feature-card-icon">✦</div>
            <h3>Grounded Ask AI</h3>
            <p>
              Ask questions directly against your documents. Cognidocs uses Retrieval-Augmented
              Generation (RAG) so answers are strictly verified against your source text.
            </p>
          </article>

          <article className="feature-card">
            <div className="feature-card-icon">≡</div>
            <h3>Configurable Summaries</h3>
            <p>
              Generate summaries tailored to your workflow: choose numbered points, connected paragraphs,
              bullet points, or structured headings across brief and detailed modes.
            </p>
          </article>

          <article className="feature-card">
            <div className="feature-card-icon">⌕</div>
            <h3>Semantic Vector Search</h3>
            <p>
              Search across your entire document repository using semantic concepts rather than rigid keywords.
              Find relevant sections instantly using neural embeddings.
            </p>
          </article>

          <article className="feature-card">
            <div className="feature-card-icon">🔒</div>
            <h3>Private User Workspace</h3>
            <p>
              Secure multi-user authentication with encrypted tokens and OTP verification.
              Your files and search history stay private within your personal account.
            </p>
          </article>
        </div>
      </section>

      {/* ========================================
          WORKFLOW PIPELINE SECTION
          ======================================== */}
      <section className="landing-section" id="workflow">
        <div className="section-header">
          <p className="section-eyebrow">HOW IT WORKS</p>
          <h2 className="section-heading">The Document Intelligence Pipeline</h2>
          <p className="section-subheading">
            From raw upload to actionable answers in four seamless steps.
          </p>
        </div>

        <div className="workflow-grid">
          <div className="workflow-card">
            <div className="workflow-step-num">Step 01</div>
            <h4>Upload Files</h4>
            <p>
              Upload PDF, DOCX, or TXT documents into your workspace with real-time format validation.
            </p>
          </div>

          <div className="workflow-card">
            <div className="workflow-step-num">Step 02</div>
            <h4>Extract & Chunk</h4>
            <p>
              Text is extracted, cleaned, and split into overlapping chunks optimized for semantic retention.
            </p>
          </div>

          <div className="workflow-card">
            <div className="workflow-step-num">Step 03</div>
            <h4>Vector Embeddings</h4>
            <p>
              Chunks are transformed into high-dimensional vector embeddings and indexed in SQLite.
            </p>
          </div>

          <div className="workflow-card">
            <div className="workflow-step-num">Step 04</div>
            <h4>Grounded Synthesis</h4>
            <p>
              Ollama LLM receives the most relevant chunks to formulate faithful answers and summaries.
            </p>
          </div>
        </div>
      </section>

      {/* ========================================
          FORMATS & SPECS STRIP
          ======================================== */}
      <section className="landing-section" id="formats">
        <div className="specs-strip">
          <div className="spec-item">
            <div className="spec-icon">📄</div>
            <div className="spec-content">
              <h4>Supported Formats</h4>
              <p>Adobe PDF (.pdf), Word (.docx), Plain Text (.txt)</p>
            </div>
          </div>

          <div className="spec-item">
            <div className="spec-icon">🧠</div>
            <div className="spec-content">
              <h4>AI Processing</h4>
              <p>Ollama (Llama 3.2) & Sentence Transformers</p>
            </div>
          </div>

          <div className="spec-item">
            <div className="spec-icon">🛡️</div>
            <div className="spec-content">
              <h4>Data Architecture</h4>
              <p>FastAPI backend with SQLite relational storage</p>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================
          BOTTOM CALL TO ACTION
          ======================================== */}
      <section className="landing-bottom-cta">
        <h2 className="cta-heading">
          Ready to unlock the knowledge in your files?
        </h2>
        <p className="cta-subheading">
          Get started with Cognidocs today. Upload your documents, ask questions,
          and discover insights in seconds.
        </p>

        {isAuthenticated ? (
          <Link to="/dashboard" className="hero-primary-cta">
            Go to Your Dashboard →
          </Link>
        ) : (
          <Link to="/register" className="hero-primary-cta">
            Create Free Account →
          </Link>
        )}
      </section>

      {/* ========================================
          FOOTER
          ======================================== */}
      <footer className="landing-footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <div className="landing-logo-emblem" style={{ width: 28, height: 28 }}>
              <CognidocsLogo />
            </div>
            <span>Cognidocs — Knowledge, unlocked.</span>
          </div>

          <nav className="footer-nav">
            <Link to="/login">Login</Link>
            <Link to="/register">Sign Up</Link>
            {isAuthenticated && <Link to="/dashboard">Dashboard</Link>}
            <a href="#features">Features</a>
          </nav>

          <div>
            &copy; {new Date().getFullYear()} Cognidocs. AI Document Intelligence.
          </div>
        </div>
      </footer>
    </div>
  )
}

export default LandingPage
