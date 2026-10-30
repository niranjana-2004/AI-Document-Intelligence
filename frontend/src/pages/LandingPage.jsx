import { useState } from 'react'
import { Link } from 'react-router-dom'
import { motion, AnimatePresence } from 'motion/react'
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
import ParticleNetwork from '../components/motion/ParticleNetwork'
import WorkflowIllustration from '../components/motion/WorkflowIllustration'
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

  // Motion container variants
  const staggerContainer = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.12,
        delayChildren: 0.1,
      },
    },
  }

  const fadeInUp = {
    hidden: { opacity: 0, y: 28 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.55, ease: [0.16, 1, 0.3, 1] },
    },
  }

  const cardEntrance = {
    hidden: { opacity: 0, y: 35 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.5, ease: [0.16, 1, 0.3, 1] },
    },
  }

  return (
    <div className="landing-container">
      {/* Background ambient light orbs */}
      <div
        className="ambient-orb ambient-orb-violet"
        style={{ width: 550, height: 550, top: '-100px', left: '10%' }}
      />
      <div
        className="ambient-orb ambient-orb-cyan"
        style={{ width: 650, height: 650, top: '220px', right: '-120px' }}
      />

      {/* Interactive Particle & Neural Connection Field */}
      <ParticleNetwork particleCount={55} maxDistance={130} interactive={true} />

      {/* ========================================
          TOP NAVIGATION BAR
          ======================================== */}
      <header className="landing-nav" style={{ position: 'relative', zIndex: 10 }}>
        <Link to="/" className="landing-brand">
          <motion.div
            className="landing-logo-emblem"
            whileHover={{ rotate: 15, scale: 1.05 }}
            transition={{ type: 'spring', stiffness: 300 }}
          >
            <CognidocsLogo />
          </motion.div>
          <div>
            <div className="landing-brand-title">Cognidocs</div>
            <div className="landing-brand-tagline">Knowledge, unlocked.</div>
          </div>
        </Link>

        <nav className="landing-nav-links">
          <a href="#features" className="landing-nav-link">Capabilities</a>
          <a href="#workflow-stage" className="landing-nav-link">Architecture</a>
          <a href="#demo" className="landing-nav-link">Interactive Demo</a>
          <a href="#workflow" className="landing-nav-link">Pipeline</a>
          <a href="#formats" className="landing-nav-link">Specs</a>
        </nav>

        <div className="landing-nav-actions">
          <motion.button
            type="button"
            className="theme-toggle-btn"
            onClick={toggleTheme}
            whileHover={{ scale: 1.08 }}
            whileTap={{ scale: 0.94 }}
            title={currentTheme === 'dark' ? 'Switch to Light mode' : 'Switch to Dark mode'}
            aria-label="Toggle visual theme"
          >
            {currentTheme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
          </motion.button>

          {isAuthenticated ? (
            <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
              <Link to="/dashboard" className="landing-register-btn">
                Go to Workspace <ArrowRight size={15} />
              </Link>
            </motion.div>
          ) : (
            <>
              <Link to="/login" className="landing-login-btn">
                Login
              </Link>
              <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
                <Link to="/register" className="landing-register-btn">
                  Get Started <ArrowRight size={15} />
                </Link>
              </motion.div>
            </>
          )}
        </div>
      </header>

      {/* ========================================
          HERO SECTION
          ======================================== */}
      <section className="landing-hero" style={{ position: 'relative', zIndex: 5 }}>
        <motion.div
          className="hero-pill"
          initial={{ opacity: 0, y: -15, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        >
          <Sparkles size={14} className="hero-pill-sparkle spin-slow" />
          <span>Next-Generation Document Intelligence</span>
        </motion.div>

        {/* Word-by-word reveal headline */}
        <motion.h1
          className="hero-title"
          initial="hidden"
          animate="visible"
          variants={{
            hidden: { opacity: 0 },
            visible: {
              opacity: 1,
              transition: { staggerChildren: 0.14 },
            },
          }}
        >
          <motion.span variants={fadeInUp} style={{ display: 'inline-block' }}>
            Your Documents.{' '}
          </motion.span>
          <motion.span
            variants={fadeInUp}
            className="gradient-text"
            style={{ display: 'inline-block' }}
          >
            Your Intelligence.
          </motion.span>
        </motion.h1>

        <motion.p
          className="hero-tagline"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.35, ease: [0.16, 1, 0.3, 1] }}
        >
          Cognidocs transforms your files into an interactive, privacy-first AI workspace.
          Upload PDF, DOCX, or text files to interrogate them with local LLMs, enjoy verified
          grounded citations, and execute deep semantic neural search with zero cloud lock-in.
        </motion.p>

        <motion.div
          className="hero-cta-group"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
        >
          {isAuthenticated ? (
            <motion.div whileHover={{ scale: 1.05, y: -2 }} whileTap={{ scale: 0.97 }}>
              <Link to="/dashboard" className="hero-primary-cta">
                Open Your Workspace <ArrowRight size={16} />
              </Link>
            </motion.div>
          ) : (
            <>
              <motion.div whileHover={{ scale: 1.05, y: -2 }} whileTap={{ scale: 0.97 }}>
                <Link to="/register" className="hero-primary-cta">
                  Get Started <ArrowRight size={16} />
                </Link>
              </motion.div>
              <motion.a
                href="#features"
                className="hero-secondary-cta"
                whileHover={{ scale: 1.04, y: -2 }}
                whileTap={{ scale: 0.97 }}
              >
                Explore Features
              </motion.a>
            </>
          )}
        </motion.div>

        <motion.div
          className="hero-badges-row"
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.65 }}
        >
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
        </motion.div>
      </section>

      {/* ========================================
          HERO SHOWCASE: FLOATING AI WORKFLOW VISUALIZATION
          ======================================== */}
      <section className="landing-section" id="workflow-stage" style={{ paddingTop: 0, position: 'relative', zIndex: 5 }}>
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        >
          <WorkflowIllustration />
        </motion.div>
      </section>

      {/* ========================================
          INTERACTIVE DEMO PREVIEW SECTION
          ======================================== */}
      <section className="hero-preview-container" id="demo" style={{ position: 'relative', zIndex: 5 }}>
        <motion.div
          className="demo-tabs-nav"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
        >
          <motion.button
            type="button"
            className={`demo-tab-button ${activeDemoTab === 'qa' ? 'active' : ''}`}
            onClick={() => setActiveDemoTab('qa')}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
          >
            <Sparkles size={15} />
            <span>1. Grounded Ask AI</span>
          </motion.button>
          <motion.button
            type="button"
            className={`demo-tab-button ${activeDemoTab === 'search' ? 'active' : ''}`}
            onClick={() => setActiveDemoTab('search')}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
          >
            <Search size={15} />
            <span>2. Neural Search</span>
          </motion.button>
          <motion.button
            type="button"
            className={`demo-tab-button ${activeDemoTab === 'upload' ? 'active' : ''}`}
            onClick={() => setActiveDemoTab('upload')}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
          >
            <UploadCloud size={15} />
            <span>3. Document Ingestion</span>
          </motion.button>
        </motion.div>

        <motion.div
          className="hero-preview-card"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
        >
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
            <AnimatePresence mode="wait">
              {activeDemoTab === 'qa' && (
                <motion.div
                  key="demo-qa"
                  className="preview-qa-layout"
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -15 }}
                  transition={{ duration: 0.3 }}
                >
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
                      <motion.div
                        className="demo-source-chip"
                        whileHover={{ scale: 1.02, x: 3 }}
                      >
                        <span className="demo-source-num">[1]</span>
                        <span className="demo-source-name">Cloud_Security_Report_2026.pdf</span>
                        <span className="demo-source-page">Page 14 · 98% match</span>
                      </motion.div>
                      <motion.div
                        className="demo-source-chip"
                        whileHover={{ scale: 1.02, x: 3 }}
                      >
                        <span className="demo-source-num">[2]</span>
                        <span className="demo-source-name">IAM_Protocol_Spec.docx</span>
                        <span className="demo-source-page">Page 6 · 94% match</span>
                      </motion.div>
                    </div>
                  </div>
                </motion.div>
              )}

              {activeDemoTab === 'search' && (
                <motion.div
                  key="demo-search"
                  className="preview-search-layout"
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -15 }}
                  transition={{ duration: 0.3 }}
                >
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
                </motion.div>
              )}

              {activeDemoTab === 'upload' && (
                <motion.div
                  key="demo-upload"
                  className="preview-upload-layout"
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -15 }}
                  transition={{ duration: 0.3 }}
                >
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
                        <motion.div
                          className="preview-progress-fill"
                          initial={{ width: '0%' }}
                          animate={{ width: '100%' }}
                          transition={{ duration: 1.2, ease: 'easeInOut' }}
                        />
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
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      </section>

      {/* ========================================
          CORE CAPABILITIES SECTION
          ======================================== */}
      <section className="landing-section" id="features" style={{ position: 'relative', zIndex: 5 }}>
        <motion.div
          className="section-header"
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 0.6 }}
        >
          <p className="section-eyebrow">CORE CAPABILITIES</p>
          <h2 className="section-heading">Everything you need to master your files</h2>
          <p className="section-subheading">
            Cognidocs extracts text, builds vector embeddings, and couples local language models
            directly to your private document repository.
          </p>
        </motion.div>

        <motion.div
          className="features-grid"
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-60px' }}
        >
          <motion.article
            className="feature-card"
            variants={cardEntrance}
            whileHover={{ y: -8, scale: 1.02 }}
            transition={{ duration: 0.2 }}
          >
            <div className="feature-card-icon">
              <Sparkles size={22} />
            </div>
            <h3>Grounded Ask AI</h3>
            <p>
              Ask complex questions against your files. Cognidocs uses Retrieval-Augmented
              Generation (RAG) so every statement is backed by verifiable source citations.
            </p>
          </motion.article>

          <motion.article
            className="feature-card"
            variants={cardEntrance}
            whileHover={{ y: -8, scale: 1.02 }}
            transition={{ duration: 0.2 }}
          >
            <div className="feature-card-icon">
              <Layers size={22} />
            </div>
            <h3>Configurable Summaries</h3>
            <p>
              Generate summaries tailored to your workflow: choose numbered points, connected paragraphs,
              bullet points, or structured headings across brief and detailed depths.
            </p>
          </motion.article>

          <motion.article
            className="feature-card"
            variants={cardEntrance}
            whileHover={{ y: -8, scale: 1.02 }}
            transition={{ duration: 0.2 }}
          >
            <div className="feature-card-icon">
              <Search size={22} />
            </div>
            <h3>Semantic Vector Search</h3>
            <p>
              Search across your entire document library using conceptual meaning rather than brittle
              keywords. Find relevant passages instantly using high-dimensional neural vectors.
            </p>
          </motion.article>

          <motion.article
            className="feature-card"
            variants={cardEntrance}
            whileHover={{ y: -8, scale: 1.02 }}
            transition={{ duration: 0.2 }}
          >
            <div className="feature-card-icon">
              <ShieldCheck size={22} />
            </div>
            <h3>Private User Workspace</h3>
            <p>
              Multi-user authentication with encrypted tokens and OTP verification.
              Your documents, query history, and embeddings remain strictly confidential.
            </p>
          </motion.article>

          <motion.article
            className="feature-card"
            variants={cardEntrance}
            whileHover={{ y: -8, scale: 1.02 }}
            transition={{ duration: 0.2 }}
          >
            <div className="feature-card-icon">
              <Cpu size={22} />
            </div>
            <h3>Local LLM Intelligence</h3>
            <p>
              Powered by Ollama and Llama 3.2. Run your intelligence entirely on-premises
              with zero API costs, zero telemetry, and complete data privacy.
            </p>
          </motion.article>

          <motion.article
            className="feature-card"
            variants={cardEntrance}
            whileHover={{ y: -8, scale: 1.02 }}
            transition={{ duration: 0.2 }}
          >
            <div className="feature-card-icon">
              <Database size={22} />
            </div>
            <h3>Persistent Chat History</h3>
            <p>
              Organized chronological conversation threads. Rename discussions, resume
              inquiries anytime, or narrow reasoning to specific selected documents.
            </p>
          </motion.article>
        </motion.div>
      </section>

      {/* ========================================
          WORKFLOW PIPELINE SECTION
          ======================================== */}
      <section className="landing-section" id="workflow" style={{ position: 'relative', zIndex: 5 }}>
        <motion.div
          className="section-header"
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 0.6 }}
        >
          <p className="section-eyebrow">HOW IT WORKS</p>
          <h2 className="section-heading">The Document Intelligence Pipeline</h2>
          <p className="section-subheading">
            From raw upload to actionable grounded answers in four seamless steps.
          </p>
        </motion.div>

        <motion.div
          className="workflow-grid"
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-60px' }}
        >
          <motion.div
            className="workflow-card"
            variants={cardEntrance}
            whileHover={{ y: -6, scale: 1.02 }}
          >
            <div className="workflow-step-num">01</div>
            <h4>Upload Files</h4>
            <p>
              Add PDF, DOCX, or TXT documents into your workspace with real-time format validation.
            </p>
          </motion.div>

          <motion.div
            className="workflow-card"
            variants={cardEntrance}
            whileHover={{ y: -6, scale: 1.02 }}
          >
            <div className="workflow-step-num">02</div>
            <h4>Extract & Chunk</h4>
            <p>
              Text is extracted, cleaned, and partitioned into overlapping semantic chunks with page tracking.
            </p>
          </motion.div>

          <motion.div
            className="workflow-card"
            variants={cardEntrance}
            whileHover={{ y: -6, scale: 1.02 }}
          >
            <div className="workflow-step-num">03</div>
            <h4>Vector Embeddings</h4>
            <p>
              Neural embeddings are computed using sentence-transformers and indexed in SQLite.
            </p>
          </motion.div>

          <motion.div
            className="workflow-card"
            variants={cardEntrance}
            whileHover={{ y: -6, scale: 1.02 }}
          >
            <div className="workflow-step-num">04</div>
            <h4>Grounded Synthesis</h4>
            <p>
              The local LLM receives context-ranked passages to formulate faithful answers with numbered citations.
            </p>
          </motion.div>
        </motion.div>
      </section>

      {/* ========================================
          FORMATS & SPECS STRIP
          ======================================== */}
      <section className="landing-section" id="formats" style={{ position: 'relative', zIndex: 5 }}>
        <motion.div
          className="specs-strip"
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-50px' }}
          transition={{ duration: 0.6 }}
        >
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
        </motion.div>
      </section>

      {/* ========================================
          BOTTOM CALL TO ACTION
          ======================================== */}
      <motion.section
        className="landing-bottom-cta"
        initial={{ opacity: 0, scale: 0.96 }}
        whileInView={{ opacity: 1, scale: 1 }}
        viewport={{ once: true, margin: '-60px' }}
        transition={{ duration: 0.6 }}
        style={{ position: 'relative', zIndex: 5 }}
      >
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
              <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.97 }}>
                <Link to="/dashboard" className="hero-primary-cta">
                  Open Workspace <ArrowRight size={16} />
                </Link>
              </motion.div>
            ) : (
              <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.97 }}>
                <Link to="/register" className="hero-primary-cta">
                  Create Free Account <ArrowRight size={16} />
                </Link>
              </motion.div>
            )}
          </div>
        </div>
      </motion.section>

      {/* ========================================
          FOOTER
          ======================================== */}
      <footer className="landing-footer" style={{ position: 'relative', zIndex: 5 }}>
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
