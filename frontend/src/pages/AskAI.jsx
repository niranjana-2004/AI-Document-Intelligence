import { useState } from 'react'
import { apiRequest } from '../services/api'
import '../App.css'

function AskAI() {
    const [question, setQuestion] = useState('')
    const [answer, setAnswer] = useState('')
    const [sources, setSources] = useState([])
    const [sourcesExpanded, setSourcesExpanded] = useState(true)
    const [copied, setCopied] = useState(false)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')

    const suggestedQuestions = [
        'What are my skills?',
        'What projects have I done?',
        'What certifications do I have?',
        'What is my educational background?',
    ]

    const handleAskAI = async () => {
        if (!question.trim()) {
            return
        }

        try {
            setLoading(true)
            setAnswer('')
            setSources([])
            setCopied(false)
            setError('')

            const data = await apiRequest(
                '/documents/ask',
                {
                    method: 'POST',
                    body: JSON.stringify({
                        query: question.trim(),
                        document_id: null,
                        top_k: 12,
                    }),
                }
            )

            const aiAnswer =
                data.answer ||
                data.response ||
                data.result ||
                'No answer returned.'

            setAnswer(aiAnswer)

            if (Array.isArray(data.results) && data.results.length > 0) {
                setSources(data.results)
            } else {
                setSources([])
            }
        } catch (err) {
            console.error('Ask AI error:', err)
            setError(
                err.message ||
                'Failed to get an answer.'
            )
        } finally {
            setLoading(false)
        }
    }

    const handleSuggestedQuestion = (suggestion) => {
        setQuestion(suggestion)
        setAnswer('')
        setSources([])
        setCopied(false)
        setError('')
    }

    const handleClear = () => {
        setQuestion('')
        setAnswer('')
        setSources([])
        setCopied(false)
        setError('')
    }

    const handleCopyAnswer = async () => {
        if (!answer) return
        try {
            if (navigator?.clipboard?.writeText) {
                await navigator.clipboard.writeText(answer)
                setCopied(true)
                setTimeout(() => setCopied(false), 2000)
            }
        } catch (err) {
            console.error('Copy to clipboard failed:', err)
        }
    }

    return (
        <main className="ask-ai-page">
            {/* =================================
                PAGE HEADER
            ================================= */}
            <section className="ask-ai-header">
                <div>
                    <p className="eyebrow">COGNIDOCS INTELLIGENCE</p>
                    <h2>Ask AI</h2>
                    <p>
                        Context-grounded reasoning across your document knowledge base.
                    </p>
                </div>
            </section>

            {/* =================================
                SUGGESTED QUESTIONS
            ================================= */}
            <section className="suggestions-section">
                <div className="section-header">
                    <div>
                        <h3>Quick Inquiries</h3>
                        <p>Explore your document repository with one click</p>
                    </div>
                </div>

                <div className="suggestion-list">
                    {suggestedQuestions.map((suggestion) => (
                        <button
                            key={suggestion}
                            type="button"
                            className="suggestion-button"
                            onClick={() => handleSuggestedQuestion(suggestion)}
                        >
                            <span className="suggestion-sparkle" aria-hidden="true">✦</span>
                            <span>{suggestion}</span>
                        </button>
                    ))}
                </div>
            </section>

            {/* =================================
                QUESTION INPUT CARD
            ================================= */}
            <section className="ask-ai-card">
                <div className="ask-ai-card-header">
                    <div>
                        <h3>Your Inquiry</h3>
                        <p>Ask anything about your uploaded documents.</p>
                    </div>

                    {(question || answer) && (
                        <button
                            type="button"
                            className="clear-button"
                            onClick={handleClear}
                        >
                            Clear
                        </button>
                    )}
                </div>

                <textarea
                    className="ask-ai-input"
                    placeholder="Example: What are the key projects or skills highlighted in my documents?"
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    onKeyDown={(event) => {
                        if (event.key === 'Enter' && !event.shiftKey) {
                            event.preventDefault()
                            handleAskAI()
                        }
                    }}
                    aria-label="Ask a question about your documents"
                />

                <div className="ask-ai-input-footer">
                    <span className="ask-ai-hint">
                        Press <strong>Enter</strong> to ask · <strong>Shift + Enter</strong> for a new line
                    </span>

                    <button
                        type="button"
                        className="ask-ai-button"
                        onClick={handleAskAI}
                        disabled={loading || !question.trim()}
                    >
                        {loading ? 'Synthesizing...' : 'Ask Cognidocs AI →'}
                    </button>
                </div>
            </section>

            {/* =================================
                ERROR BANNER
            ================================= */}
            {error && (
                <div className="ask-ai-error" role="alert">
                    <span className="msg-icon" aria-hidden="true">⚠</span>
                    <span>{error}</span>
                </div>
            )}

            {/* =================================
                AI ANSWER / LOADING
            ================================= */}
            {loading && (
                <section className="answer-card answer-card-loading">
                    <div className="answer-header">
                        <div className="answer-icon" aria-hidden="true">AI</div>
                        <div>
                            <h3>Synthesizing Answer</h3>
                            <p>Scanning vector chunks and formulating grounded response...</p>
                        </div>
                    </div>

                    <div className="answer-loading" aria-label="Loading response">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </section>
            )}

            {!loading && answer && (
                <section className="answer-card">
                    <div className="answer-header">
                        <div className="answer-icon" aria-hidden="true">AI</div>
                        <div>
                            <h3>Context-Grounded Answer</h3>
                            <p>Synthesized directly from your document knowledge base</p>
                        </div>

                        <div className="answer-actions">
                            <button
                                type="button"
                                className="copy-answer-btn"
                                onClick={handleCopyAnswer}
                                title="Copy answer to clipboard"
                                aria-label="Copy answer to clipboard"
                            >
                                {copied ? '✓ Copied' : 'Copy Answer'}
                            </button>
                        </div>
                    </div>

                    <div className="answer-content">
                        {answer}
                    </div>

                    {/* REFERENCED CONTEXT SOURCES */}
                    {sources && sources.length > 0 && (
                        <div className="referenced-sources-section">
                            <button
                                type="button"
                                className="sources-toggle-btn"
                                onClick={() => setSourcesExpanded(!sourcesExpanded)}
                                aria-expanded={sourcesExpanded}
                            >
                                <span className="sources-toggle-title">
                                    <span className="sources-icon" aria-hidden="true">📑</span>
                                    <span>
                                        Referenced Context ({sources.length}{' '}
                                        {sources.length === 1 ? 'source' : 'sources'})
                                    </span>
                                </span>
                                <span className="sources-toggle-arrow" aria-hidden="true">
                                    {sourcesExpanded ? '▲' : '▼'}
                                </span>
                            </button>

                            {sourcesExpanded && (
                                <div className="sources-grid">
                                    {sources.map((source, idx) => {
                                        const similarityScore =
                                            typeof source.similarity === 'number' && !isNaN(source.similarity)
                                                ? Math.round(source.similarity * 100)
                                                : typeof source.score === 'number' && !isNaN(source.score)
                                                ? Math.round(source.score * 100)
                                                : null

                                        return (
                                            <article className="source-card" key={source.id || idx}>
                                                <div className="source-card-header">
                                                    <span className="source-filename">
                                                        📄 {source.filename || `Document #${source.document_id || idx + 1}`}
                                                    </span>
                                                    {similarityScore !== null && (
                                                        <span
                                                            className="source-relevance-chip"
                                                            title="Semantic retrieval relevance indicator"
                                                        >
                                                            {similarityScore}% relevance
                                                        </span>
                                                    )}
                                                </div>
                                                <p className="source-snippet">
                                                    {source.content || source.text || 'No text excerpt available.'}
                                                </p>
                                            </article>
                                        )
                                    })}
                                </div>
                            )}
                        </div>
                    )}
                </section>
            )}

            {/* =================================
                EMPTY STATE
            ================================= */}
            {!loading && !answer && !error && (
                <section className="ask-ai-empty">
                    <div className="ask-ai-empty-icon" aria-hidden="true">✦</div>
                    <h3>Document Intelligence Ready</h3>
                    <p>
                        Type a question above or select a quick inquiry to query your uploaded
                        documents. Cognidocs AI retrieves exact passages and generates context-grounded answers.
                    </p>
                </section>
            )}
        </main>
    )
}

export default AskAI