import { useNavigate } from 'react-router-dom'
import '../App.css'

function About() {
    const navigate = useNavigate()

    return (
        <main className="about-page">

            {/* Header */}
            <section className="about-hero">
                <div className="about-hero-content">
                    <p className="eyebrow">ABOUT THE PLATFORM</p>

                    <h2>
                        Turn your documents into
                        <span> intelligent answers.</span>
                    </h2>

                    <p className="about-hero-description">
                        AI Document Intelligence helps you upload, search, summarize,
                        and ask questions about your documents using AI-powered
                        document understanding.
                    </p>

                    <div className="about-hero-actions">
                        <button
                            type="button"
                            className="about-primary-button"
                            onClick={() => navigate('/documents')}
                        >
                            Explore Documents
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
                        <div className="about-ai-icon">AI</div>

                        <div>
                            <strong>Document Intelligence</strong>
                            <span>Understand • Search • Ask</span>
                        </div>
                    </div>

                    <div className="about-floating-card about-floating-one">
                        <span>✓</span>
                        <div>
                            <strong>Smart Search</strong>
                            <small>Find relevant information</small>
                        </div>
                    </div>

                    <div className="about-floating-card about-floating-two">
                        <span>✦</span>
                        <div>
                            <strong>AI Answers</strong>
                            <small>Ask questions naturally</small>
                        </div>
                    </div>
                </div>
            </section>


            {/* What it does */}
            <section className="about-section">

                <div className="about-section-heading">
                    <p className="eyebrow">WHAT IT DOES</p>

                    <h3>
                        One workspace for your documents
                    </h3>

                    <p>
                        The platform combines document processing, semantic search,
                        retrieval, and AI-generated responses into one workspace.
                    </p>
                </div>

                <div className="about-feature-grid">

                    <article className="about-feature-card">
                        <div className="about-feature-icon">↑</div>

                        <h4>Upload Documents</h4>

                        <p>
                            Upload supported documents and let the system extract and
                            process their text automatically.
                        </p>
                    </article>

                    <article className="about-feature-card">
                        <div className="about-feature-icon">⌕</div>

                        <h4>Search Information</h4>

                        <p>
                            Search through document content and retrieve the sections
                            that are most relevant to your query.
                        </p>
                    </article>

                    <article className="about-feature-card">
                        <div className="about-feature-icon">✦</div>

                        <h4>Ask AI</h4>

                        <p>
                            Ask questions about your documents and receive answers
                            based on the retrieved document context.
                        </p>
                    </article>

                    <article className="about-feature-card">
                        <div className="about-feature-icon">≡</div>

                        <h4>Generate Summaries</h4>

                        <p>
                            Generate concise AI-powered summaries to understand
                            important document information quickly.
                        </p>
                    </article>

                </div>
            </section>


            {/* How it works */}
            <section className="about-section about-workflow-section">

                <div className="about-section-heading">
                    <p className="eyebrow">HOW IT WORKS</p>

                    <h3>
                        From document to answer
                    </h3>

                    <p>
                        The system follows a document intelligence pipeline to turn
                        raw document content into useful answers.
                    </p>
                </div>

                <div className="about-workflow">

                    <div className="about-workflow-step">
                        <div className="workflow-number">01</div>

                        <div>
                            <h4>Upload</h4>
                            <p>
                                A document is uploaded into the workspace.
                            </p>
                        </div>
                    </div>

                    <div className="workflow-line"></div>

                    <div className="about-workflow-step">
                        <div className="workflow-number">02</div>

                        <div>
                            <h4>Extract & Process</h4>
                            <p>
                                Text is extracted, cleaned, and divided into meaningful
                                chunks.
                            </p>
                        </div>
                    </div>

                    <div className="workflow-line"></div>

                    <div className="about-workflow-step">
                        <div className="workflow-number">03</div>

                        <div>
                            <h4>Retrieve</h4>
                            <p>
                                Relevant document sections are identified using semantic
                                and keyword-based retrieval.
                            </p>
                        </div>
                    </div>

                    <div className="workflow-line"></div>

                    <div className="about-workflow-step">
                        <div className="workflow-number">04</div>

                        <div>
                            <h4>Generate</h4>
                            <p>
                                The retrieved context is provided to the AI model to
                                generate a response.
                            </p>
                        </div>
                    </div>

                </div>
            </section>


            {/* Technology */}
            <section className="about-section">

                <div className="about-section-heading">
                    <p className="eyebrow">TECHNOLOGY</p>

                    <h3>
                        Built with modern AI technologies
                    </h3>

                    <p>
                        The application combines a Python backend, modern web
                        technologies, vector embeddings, and a local language model.
                    </p>
                </div>

                <div className="about-tech-grid">

                    <div className="about-tech-item">
                        <strong>FastAPI</strong>
                        <span>Backend API</span>
                    </div>

                    <div className="about-tech-item">
                        <strong>React</strong>
                        <span>Frontend interface</span>
                    </div>

                    <div className="about-tech-item">
                        <strong>SQLite</strong>
                        <span>Document metadata & storage</span>
                    </div>

                    <div className="about-tech-item">
                        <strong>Sentence Transformers</strong>
                        <span>Text embeddings</span>
                    </div>

                    <div className="about-tech-item">
                        <strong>Semantic Search</strong>
                        <span>Relevant information retrieval</span>
                    </div>

                    <div className="about-tech-item">
                        <strong>Ollama</strong>
                        <span>Local language model</span>
                    </div>

                </div>
            </section>


            {/* RAG explanation */}
            <section className="about-rag-section">

                <div className="about-rag-content">

                    <p className="eyebrow">AI PIPELINE</p>

                    <h3>
                        Retrieval-Augmented Generation
                    </h3>

                    <p>
                        Instead of asking the language model to answer from general
                        knowledge alone, the system first retrieves relevant
                        information from your documents.
                    </p>

                    <p>
                        That retrieved context is then passed to the language model,
                        allowing the generated response to be grounded in the
                        available document content.
                    </p>

                </div>

                <div className="about-rag-flow">

                    <div className="rag-box">
                        <strong>Your Document</strong>
                        <span>Source content</span>
                    </div>

                    <div className="rag-arrow">→</div>

                    <div className="rag-box">
                        <strong>Retrieval</strong>
                        <span>Relevant chunks</span>
                    </div>

                    <div className="rag-arrow">→</div>

                    <div className="rag-box">
                        <strong>AI Model</strong>
                        <span>Context + question</span>
                    </div>

                    <div className="rag-arrow">→</div>

                    <div className="rag-box rag-result">
                        <strong>Answer</strong>
                        <span>AI-generated response</span>
                    </div>

                </div>
            </section>


            {/* Bottom CTA */}
            <section className="about-final-card">

                <div>
                    <p className="eyebrow">READY TO EXPLORE?</p>

                    <h3>
                        Start working with your documents.
                    </h3>

                    <p>
                        Upload a document, search its content, or ask AI a question.
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