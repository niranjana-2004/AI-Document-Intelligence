import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Sparkles,
  Search,
  UploadCloud,
  FileText,
  ShieldCheck,
  Cpu,
  ArrowRight,
  CheckCircle2,
  Sun,
  Moon,
  Zap,
  Layers,
  Database,
} from 'lucide-react'
import CognidocsLogo from '../components/CognidocsLogo'
import '../styles/landing.css'

function LandingPage() {
  const [isAuthenticated] = useState(() => {
    return typeof window !== 'undefined' ? Boolean(localStorage.getItem('access_token')) : false
  })
  const [currentTheme, setCurrentTheme] = useState(() => {
    return typeof window !== 'undefined' ? localStorage.getItem('app_theme') || 'ocean' : 'ocean'
  })
  const [activeDemoTab, setActiveDemoTab] = useState('qa')

  const toggleTheme = () => {
    const nextTheme = currentTheme === 'dark' ? 'ocean' : 'dark'
    setCurrentTheme(nextTheme)
    localStorage.setItem('app_theme', nextTheme)
    document.documentElement.dataset.theme = nextTheme
  }

  return (
    <div className="landing-container">
      {/* Background ambient light orbs */}
      <div
        className="ambient-orb ambient-orb-violet"
        style={{ width: 500, height: 500, top: '-100px', left: '10%' }}
      />
      <div
        className="ambient-orb ambient-orb-cyan"
        style={{ width: 600, height: 600, top: '200px', right: '-100px' }}
      />

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
          <a href="#demo" className="landing-nav-link">Interactive Demo</a>
          <a href="#workflow" className="landing-nav-link">Pipeline</a>
          <a href="#formats" className="landing-nav-link">Specs</a>
        </nav>

        <div className="landing-nav-actions">
          <button
            type="button"
            className="theme-toggle-btn"
            onClick={toggleTheme}
            title={currentTheme === 'dark' ? 'Switch to Light mode' : 'Switch to Dark mode'}
            aria-label="Toggle visual theme"
          >
            {currentTheme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
          </button>

          {isAuthenticated ? (
            <Link to="/dashboard" className="landing-register-btn">
              Go to Workspace <ArrowRight size={15} />
            </Link>
          ) : (
            <>
              <Link to="/login" className="landing-login-btn">
                Login
              </Link>
              <Link to="/register" className="landing-register-btn">
                Get Started <ArrowRight size={15} />
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
          <Sparkles size={14} className="hero-pill-sparkle" />
          <span>Next-Generation Document Intelligence</span>
        </div>

        <h1 className="hero-title">
          Your Documents.{' '}
          <span className="gradient-text">Your Intelligence.</span>
        </h1>

        <p className="hero-tagline">
          Cognidocs transforms your files into an interactive, privacy-first AI workspace.
          Upload PDF, DOCX, or text files to interrogate them with local LLMs, enjoy verified
          grounded citations, and execute deep semantic neural search with zero cloud lock-in.
        </p>

        <div className="hero-cta-group">
          {isAuthenticated ? (
            <Link to="/dashboard" className="hero-primary-cta">
              Open Your Workspace <ArrowRight size={16} />
            </Link>
          ) : (
            <>
              <Link to="/register" className="hero-primary-cta">
                Get Started <ArrowRight size={16} />
              </Link>
              <a href="#features" className="hero-secondary-cta">
                Explore Features
              </a>
            </>
          )}
        </div>

        <div className="hero-badges-row">
          <div className="hero-badge-item">
            <CheckCircle2 size={15} className="hero-badge-icon" />
            <span><strong>Context-Grounded</strong> — Verified citations</span>
          </div>
          <div className="hero-badge-item">
            <Zap size={15} className="hero-badge-icon" />
            <span><strong>Local LLM RAG</strong> — Private & instant</span>
          </div>
          <div className="hero-badge-item">
            <FileText size={15} className="hero-badge-icon" />
            <span><strong>Multi-Format</strong> — PDF · DOCX · TXT</span>
          </div>
        </div>
      </section>

      {/* ========================================
          INTERACTIVE DEMO PREVIEW SECTION
          ======================================== */}
      <section className="hero-preview-container" id="demo">
        <div className="demo-tabs-nav">
          <button
            type="button"
            className={`demo-tab-button ${activeDemoTab === 'qa' ? 'active' : ''}`}
            onClick={() => setActiveDemoTab('qa')}
          >
            <Sparkles size={15} />
            <span>1. Grounded Ask AI</span>
          </button>
          <button
            type="button"
            className={`demo-tab-button ${activeDemoTab === 'search' ? 'active' : ''}`}
            onClick={() => setActiveDemoTab('search')}
          >
            <Search size={15} />
            <span>2. Neural Search</span>
          </button>
          <button
            type="button"
            className={`demo-tab-button ${activeDemoTab === 'upload' ? 'active' : ''}`}
            onClick={() => setActiveDemoTab('upload')}
          >
            <UploadCloud size={15} />
            <span>3. Document Ingestion</span>
          </button>
        </div>

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
            {activeDemoTab === 'qa' && (
              <div className="preview-qa-layout">
                <div className="preview-user-bubble">
                  <div className="preview-bubble-label">User Query</div>
                  <p>
                    &ldquo;What were the primary security measures implemented in our cloud architecture report?&rdquo;
                  </p>
                </div>

                <div className="preview-ai-bubble">
                  <div className="preview-ai-header">
                    <div className="preview-ai-badge">
                      <Sparkles size={14} />
                      <span>Grounded Assistant</span>
                    </div>
                    <span className="preview-model-badge">Ollama Llama 3.2</span>
                  </div>
                  <p>
                    According to the architecture overview{' '}
                    <span className="demo-citation-pill">[1]</span>, the platform deployed
                    end-to-end AES-256 encryption across storage tiers, paired with zero-trust
                    IAM token verification{' '}
                    <span className="demo-citation-pill">[2]</span> and continuous automated
                    vulnerability auditing.
                  </p>

                  <div className="demo-sources-shelf">
                    <div className="demo-source-chip">
                      <span className="demo-source-num">[1]</span>
                      <span className="demo-source-name">Cloud_Security_Report_2026.pdf</span>
                      <span className="demo-source-page">Page 14 · 98% match</span>
                    </div>
                    <div className="demo-source-chip">
                      <span className="demo-source-num">[2]</span>
                      <span className="demo-source-name">IAM_Protocol_Spec.docx</span>
                      <span className="demo-source-page">Page 6 · 94% match</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeDemoTab === 'search' && (
              <div className="preview-search-layout">
                <div className="preview-search-bar">
                  <Search size={16} className="text-muted" />
                  <span className="preview-search-query">
                    &ldquo;vulnerability mitigation policy and zero-trust IAM&rdquo;
                  </span>
                  <span className="preview-search-badge">Cosine Retrieval</span>
                </div>

                <div className="preview-search-results">
                  <div className="preview-search-result-item">
                    <div className="result-item-top">
                      <span className="result-file-title">📄 Cloud_Security_Report_2026.pdf</span>
                      <span className="result-relevance">98% relevance</span>
                    </div>
                    <p className="result-snippet">
                      &ldquo;...enforcing strict zero-trust identity token verification with short-lived session grants and mandatory hardware security keys...&rdquo;
                    </p>
                  </div>

                  <div className="preview-search-result-item">
                    <div className="result-item-top">
                      <span className="result-file-title">📄 IAM_Protocol_Spec.docx</span>
                      <span className="result-relevance">93% relevance</span>
                    </div>
                    <p className="result-snippet">
                      &ldquo;...automated vulnerability mitigation scans run across all container orchestrators every four hours, logging zero-day disclosures...&rdquo;
                    </p>
                  </div>
                </div>
              </div>
            )}

            {activeDemoTab === 'upload' && (
              <div className="preview-upload-layout">
                <div className="preview-upload-box">
                  <div className="preview-file-icon">
                    <FileText size={36} />
                  </div>
                  <div className="preview-file-details">
                    <h4>Quarterly_Executive_Review_2026.pdf</h4>
                    <div className="preview-file-meta">
                      <span>Adobe PDF Document</span>
                      <span>·</span>
                      <span>28,450 characters extracted</span>
                      <span>·</span>
                      <span>32 vector chunks indexed</span>
                    </div>
                    <div className="preview-progress-track">
                      <div className="preview-progress-fill" style={{ width: '100%' }}></div>
                    </div>
                    <span className="preview-progress-status">✓ Extraction & Vectorization Complete</span>
                  </div>
                </div>

                <div className="preview-extraction-tags">
                  <div className="tag-item">
                    <Database size={13} />
                    <span>Indexed in SQLite Vector Vault</span>
                  </div>
                  <div className="tag-item">
                    <Layers size={13} />
                    <span>Recursive Sliding Chunking</span>
                  </div>
                  <div className="tag-item">
                    <Cpu size={13} />
                    <span>Sentence Transformer Embeddings</span>
                  </div>
                </div>
              </div>
            )}
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
            Cognidocs extracts text, builds vector embeddings, and couples local language models
            directly to your private document repository.
          </p>
        </div>

        <div className="features-grid">
          <article className="feature-card">
            <div className="feature-card-icon">
              <Sparkles size={22} />
            </div>
            <h3>Grounded Ask AI</h3>
            <p>
              Ask complex questions against your files. Cognidocs uses Retrieval-Augmented
              Generation (RAG) so every statement is backed by verifiable source citations.
            </p>
          </article>

          <article className="feature-card">
            <div className="feature-card-icon">
              <Layers size={22} />
            </div>
            <h3>Configurable Summaries</h3>
            <p>
              Generate summaries tailored to your workflow: choose numbered points, connected paragraphs,
              bullet points, or structured headings across brief and detailed depths.
            </p>
          </article>

          <article className="feature-card">
            <div className="feature-card-icon">
              <Search size={22} />
            </div>
            <h3>Semantic Vector Search</h3>
            <p>
              Search across your entire document library using conceptual meaning rather than brittle
              keywords. Find relevant passages instantly using high-dimensional neural vectors.
            </p>
          </article>

          <article className="feature-card">
            <div className="feature-card-icon">
              <ShieldCheck size={22} />
            </div>
            <h3>Private User Workspace</h3>
            <p>
              Multi-user authentication with encrypted tokens and OTP verification.
              Your documents, query history, and embeddings remain strictly confidential.
            </p>
          </article>

          <article className="feature-card">
            <div className="feature-card-icon">
              <Cpu size={22} />
            </div>
            <h3>Local LLM Intelligence</h3>
            <p>
              Powered by Ollama and Llama 3.2. Run your intelligence entirely on-premises
              with zero API costs, zero telemetry, and complete data privacy.
            </p>
          </article>

          <article className="feature-card">
            <div className="feature-card-icon">
              <Database size={22} />
            </div>
            <h3>Persistent Chat History</h3>
            <p>
              Organized chronological conversation threads. Rename discussions, resume
              inquiries anytime, or narrow reasoning to specific selected documents.
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
            From raw upload to actionable grounded answers in four seamless steps.
          </p>
        </div>

        <div className="workflow-grid">
          <div className="workflow-card">
            <div className="workflow-step-num">01</div>
            <h4>Upload Files</h4>
            <p>
              Add PDF, DOCX, or TXT documents into your workspace with real-time format validation.
            </p>
          </div>

          <div className="workflow-card">
            <div className="workflow-step-num">02</div>
            <h4>Extract & Chunk</h4>
            <p>
              Text is extracted, cleaned, and partitioned into overlapping semantic chunks with page tracking.
            </p>
          </div>

          <div className="workflow-card">
            <div className="workflow-step-num">03</div>
            <h4>Vector Embeddings</h4>
            <p>
              Neural embeddings are computed using sentence-transformers and indexed in SQLite.
            </p>
          </div>

          <div className="workflow-card">
            <div className="workflow-step-num">04</div>
            <h4>Grounded Synthesis</h4>
            <p>
              The local LLM receives context-ranked passages to formulate faithful answers with numbered citations.
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
            <div className="spec-icon">
              <FileText size={24} />
            </div>
            <div className="spec-content">
              <h4>Supported Formats</h4>
              <p>Adobe PDF (.pdf), Word (.docx), Plain Text (.txt)</p>
            </div>
          </div>

          <div className="spec-item">
            <div className="spec-icon">
              <Cpu size={24} />
            </div>
            <div className="spec-content">
              <h4>AI Processing</h4>
              <p>Ollama (Llama 3.2) & Sentence Transformers</p>
            </div>
          </div>

          <div className="spec-item">
            <div className="spec-icon">
              <Database size={24} />
            </div>
            <div className="spec-content">
              <h4>Data Architecture</h4>
              <p>FastAPI backend with SQLite relational and vector storage</p>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================
          BOTTOM CALL TO ACTION
          ======================================== */}
      <section className="landing-bottom-cta">
        <div className="cta-inner-card">
          <h2 className="cta-heading">
            Ready to unlock the intelligence in your files?
          </h2>
          <p className="cta-subheading">
            Join Cognidocs today. Upload your documents, ask questions,
            and extract verifiable insights in seconds.
          </p>

          <div className="cta-buttons">
            {isAuthenticated ? (
              <Link to="/dashboard" className="hero-primary-cta">
                Open Workspace <ArrowRight size={16} />
              </Link>
            ) : (
              <Link to="/register" className="hero-primary-cta">
                Create Free Account <ArrowRight size={16} />
              </Link>
            )}
          </div>
        </div>
      </section>

      {/* ========================================
          FOOTER
          ======================================== */}
      <footer className="landing-footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <div className="landing-logo-emblem" style={{ width: 32, height: 32 }}>
              <CognidocsLogo />
            </div>
            <div className="footer-brand-text">
              <strong>Cognidocs</strong>
              <span>Knowledge, unlocked.</span>
            </div>
          </div>

          <nav className="footer-nav">
            <Link to="/login">Login</Link>
            <Link to="/register">Sign Up</Link>
            {isAuthenticated && <Link to="/dashboard">Dashboard</Link>}
            <a href="#features">Features</a>
            <a href="#workflow">Pipeline</a>
          </nav>

          <div className="footer-status">
            <span className="status-live-dot"></span>
            <span>All Systems Operational</span>
          </div>
        </div>
        <div className="footer-copyright">
          &copy; {new Date().getFullYear()} Cognidocs. AI Document Intelligence & Retrieval.
        </div>
      </footer>
    </div>
  )
}

export default LandingPage
