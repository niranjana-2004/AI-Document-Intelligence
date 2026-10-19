import { useNavigate } from 'react-router-dom'
import CognidocsLogo from '../components/CognidocsLogo'
import '../App.css'

function About() {
    const navigate = useNavigate()

    return (
        <main className="about-page">
            {/* =================================
                HERO SECTION
            ================================= */}
            <section className="about-hero">
                <div className="about-hero-content">
                    <p className="eyebrow">ABOUT COGNIDOCS</p>

                    <h2>
                        Knowledge, <span>unlocked.</span>
                    </h2>

                    <p className="about-hero-description">
                        Cognidocs transforms static documents into an interactive knowledge
                        vault. Upload PDFs, DOCX files, and text notes, then query, summarize,
                        and uncover context-grounded insights through local AI intelligence.
                    </p>

                    <div className="about-hero-actions">
                        <button
                            type="button"
                            className="about-primary-button"
                            onClick={() => navigate('/documents')}
                        >
                            Explore Documents →
                        </button>

                        <button
                            type="button"
                            className="about-secondary-button"
                            onClick={() => navigate('/ask-ai')}
                        >
                            Ask AI
                        </button>
                    </div>
                </div>

                <div className="about-hero-visual">
                    <div className="about-ai-card">
                        <div className="about-ai-icon" aria-hidden="true">
                            <CognidocsLogo />
                        </div>

                        <div>
                            <strong>Cognidocs Core</strong>
                            <span>Understand · Search · Synthesize</span>
                        </div>
                    </div>

                    <div className="about-floating-card about-floating-one">
                        <span aria-hidden="true">✓</span>
                        <div>
                            <strong>Semantic Retrieval</strong>
                            <small>Cosine vector similarity</small>
                        </div>
                    </div>

                    <div className="about-floating-card about-floating-two">
                        <span aria-hidden="true">✦</span>
                        <div>
                            <strong>Grounded Answers</strong>
                            <small>Context-verified reasoning</small>
                        </div>
                    </div>
                </div>
            </section>

            {/* =================================
                WHAT IT DOES
            ================================= */}
            <section className="about-section">
                <div className="about-section-heading">
                    <p className="eyebrow">WHAT IT DOES</p>
                    <h3>One Unified Workspace for Document Intelligence</h3>
                    <p>
                        Cognidocs brings document processing, vector search,
                        semantic retrieval, and AI-driven synthesis into a single high-performance workspace.
                    </p>
                </div>

                <div className="about-feature-grid">
                    <article className="about-feature-card">
                        <div className="about-feature-icon" aria-hidden="true">↑</div>
                        <h4>Document Ingestion</h4>
                        <p>
                            Upload PDF, DOCX, or TXT documents. The system automatically extracts text,
                            generates sentence embeddings, and partitions content into semantic chunks.
                        </p>
                    </article>

                    <article className="about-feature-card">
                        <div className="about-feature-icon" aria-hidden="true">⌕</div>
                        <h4>Semantic Search</h4>
                        <p>
                            Search by concept rather than keyword matching. Retrieve exact passages
                            ranked by mathematical vector proximity to your intent.
                        </p>
                    </article>

                    <article className="about-feature-card">
                        <div className="about-feature-icon" aria-hidden="true">✦</div>
                        <h4>Context-Grounded Q&A</h4>
                        <p>
                            Ask questions naturally. Cognidocs supplies relevant context chunks to the language model
                            to generate accurate, grounded responses.
                        </p>
                    </article>

                    <article className="about-feature-card">
                        <div className="about-feature-icon" aria-hidden="true">≡</div>
                        <h4>On-Demand Summaries</h4>
                        <p>
                            Generate condensed overviews in numbered, bulleted, or paragraph formats
                            to distill key document findings in seconds.
                        </p>
                    </article>
                </div>
            </section>

            {/* =================================
                HOW IT WORKS
            ================================= */}
            <section className="about-section about-workflow-section">
                <div className="about-section-heading">
                    <p className="eyebrow">HOW IT WORKS</p>
                    <h3>From Document to Grounded Answer</h3>
                    <p>
                        Cognidocs executes a multi-stage retrieval-augmented pipeline
                        to turn raw files into verified answers.
                    </p>
                </div>

                <div className="about-workflow">
                    <div className="about-workflow-step">
                        <div className="workflow-number">01</div>
                        <div>
                            <h4>Upload & Validate</h4>
                            <p>Documents are uploaded, verified for format integrity, and securely saved.</p>
                        </div>
                    </div>

                    <div className="workflow-line" aria-hidden="true"></div>

                    <div className="about-workflow-step">
                        <div className="workflow-number">02</div>
                        <div>
                            <h4>Extract & Chunk</h4>
                            <p>Text is extracted, cleaned, and split into overlapping chunks for coherent semantic context.</p>
                        </div>
                    </div>

                    <div className="workflow-line" aria-hidden="true"></div>

                    <div className="about-workflow-step">
                        <div className="workflow-number">03</div>
                        <div>
                            <h4>Embed & Retrieve</h4>
                            <p>Sentence transformers compute dense vector representations to locate high-affinity passages.</p>
                        </div>
                    </div>

                    <div className="workflow-line" aria-hidden="true"></div>

                    <div className="about-workflow-step">
                        <div className="workflow-number">04</div>
                        <div>
                            <h4>Synthesize</h4>
                            <p>Retrieved passages are passed to the language model to formulate context-grounded answers.</p>
                        </div>
                    </div>
                </div>
            </section>

            {/* =================================
                TECHNOLOGY
            ================================= */}
            <section className="about-section">
                <div className="about-section-heading">
                    <p className="eyebrow">ARCHITECTURE & STACK</p>
                    <h3>Engineered with Modern AI Technologies</h3>
                    <p>
                        Cognidocs couples an asynchronous Python backend with modern web standards,
                        local language models, and high-density vector embeddings.
                    </p>
                </div>

                <div className="about-tech-grid">
                    <div className="about-tech-item">
                        <strong>FastAPI</strong>
                        <span>High-performance asynchronous Python API</span>
                    </div>

                    <div className="about-tech-item">
                        <strong>React & Vite</strong>
                        <span>Reactive frontend with glassmorphic aesthetics</span>
                    </div>

                    <div className="about-tech-item">
                        <strong>SQLite & SQLAlchemy</strong>
                        <span>Document metadata & relational activity storage</span>
                    </div>

                    <div className="about-tech-item">
                        <strong>Sentence Transformers</strong>
                        <span>Dense multi-dimensional text embeddings</span>
                    </div>

                    <div className="about-tech-item">
                        <strong>Semantic Search</strong>
                        <span>Cosine vector similarity chunk ranking</span>
                    </div>

                    <div className="about-tech-item">
                        <strong>Ollama LLM</strong>
                        <span>Private, local language model inference</span>
                    </div>
                </div>
            </section>

            {/* =================================
                RAG PIPELINE
            ================================= */}
            <section className="about-rag-section">
                <div className="about-rag-content">
                    <p className="eyebrow">AI PIPELINE</p>
                    <h3>Retrieval-Augmented Generation (RAG)</h3>
                    <p>
                        Rather than querying a language model on generic web memory alone,
                        Cognidocs retrieves precise passages directly from your uploaded files.
                    </p>
                    <p>
                        By injecting these exact passages into the prompt context, the AI synthesizes
                        answers that reflect the specific facts, skills, and data in your private library.
                    </p>
                </div>

                <div className="about-rag-flow">
                    <div className="rag-box">
                        <strong>Your Documents</strong>
                        <span>Source text files</span>
                    </div>

                    <div className="rag-arrow" aria-hidden="true">→</div>

                    <div className="rag-box">
                        <strong>Semantic Retrieval</strong>
                        <span>Ranked chunk excerpts</span>
                    </div>

                    <div className="rag-arrow" aria-hidden="true">→</div>

                    <div className="rag-box">
                        <strong>AI Language Model</strong>
                        <span>Context + user prompt</span>
                    </div>

                    <div className="rag-arrow" aria-hidden="true">→</div>

                    <div className="rag-box rag-result">
                        <strong>Grounded Answer</strong>
                        <span>Context-backed synthesis</span>
                    </div>
                </div>
            </section>

            {/* =================================
                FINAL CTA
            ================================= */}
            <section className="about-final-card">
                <div>
                    <p className="eyebrow">READY TO UNLOCK KNOWLEDGE?</p>
                    <h3>Start Working with Your Documents</h3>
                    <p>
                        Upload files, perform semantic searches, or query the AI assistant.
                    </p>
                </div>

                <div className="about-final-actions">
                    <button
                        type="button"
                        className="about-primary-button"
                        onClick={() => navigate('/documents')}
                    >
                        View Documents
                    </button>

                    <button
                        type="button"
                        className="about-secondary-button"
                        onClick={() => navigate('/ask-ai')}
                    >
                        Ask AI
                    </button>
                </div>
            </section>
        </main>
    )
}

export default About