import { useState, useEffect } from 'react'
import { apiRequest } from '../services/api'
import '../App.css'

function AskAI() {
    const [question, setQuestion] = useState('')
    const [answer, setAnswer] = useState('')
    const [sources, setSources] = useState([])
    const [sourcesExpanded, setSourcesExpanded] = useState(false)
    const [highlightedCitation, setHighlightedCitation] = useState(null)
    const [expandedSourceExcerpts, setExpandedSourceExcerpts] = useState({})
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
            setHighlightedCitation(null)
            setExpandedSourceExcerpts({})
            setCopied(false)
            setError('')

            const data = await apiRequest(
                '/documents/ask',
                {
                    method: 'POST',
                    body: JSON.stringify({
                        query: question.trim(),
                        document_id: null,
                        top_k: 6,
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
        setHighlightedCitation(null)
        setExpandedSourceExcerpts({})
        setCopied(false)
        setError('')
    }

    const handleClear = () => {
        setQuestion('')
        setAnswer('')
        setSources([])
        setHighlightedCitation(null)
        setExpandedSourceExcerpts({})
        setCopied(false)
        setError('')
    }

    const handleCitationClick = (citationIndex) => {
        setHighlightedCitation(citationIndex)
        const targetId = `source-card-${citationIndex}`
        const element = document.getElementById(targetId)
        if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
            if (typeof element.focus === 'function') {
                element.focus({ preventScroll: true })
            }
        }
    }

    const toggleSourceExcerpt = (citationIndex) => {
        setExpandedSourceExcerpts((prev) => ({
            ...prev,
            [citationIndex]: !prev[citationIndex],
        }))
    }

    useEffect(() => {
        if (highlightedCitation != null) {
            const timer = setTimeout(() => {
                setHighlightedCitation(null)
            }, 2800)
            return () => clearTimeout(timer)
        }
    }, [highlightedCitation])

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

    const renderInlineCitations = (text, sourceList) => {
        if (!text) return null

        // Split on bracketed citations like [1], [2], or [1, 2]
        const parts = text.split(/(\[\s*\d+(?:\s*,\s*\d+)*\s*\])/g)

        return parts.map((part, index) => {
            const bracketMatch = part.match(/^\[\s*(\d+(?:\s*,\s*\d+)*)\s*\]$/)
            if (!bracketMatch) {
                return part
            }

            const rawNums = bracketMatch[1]
                .split(',')
                .map((s) => parseInt(s.trim(), 10))
                .filter((n) => !isNaN(n))

            if (rawNums.length === 0) {
                return part
            }

            return (
                <span key={`cite-group-${index}`} className="citation-group">
                    {rawNums.map((num, numIdx) => {
                        const matchingSource = sourceList?.find(
                            (s) => Number(s.citation_index) === num
                        )

                        if (!matchingSource) {
                            // Non-existent source reference: render as plain text without linking
                            return (
                                <span key={`plain-${num}-${numIdx}`} className="citation-plain">
                                    [{num}]
                                </span>
                            )
                        }

                        const filename = matchingSource.filename || `Document #${matchingSource.document_id || num}`
                        const pageLabel = matchingSource.page_number != null
                            ? `Page ${matchingSource.page_number}`
                            : 'Page unavailable'

                        return (
                            <button
                                key={`pill-${num}-${numIdx}`}
                                type="button"
                                className={`citation-pill ${highlightedCitation === num ? 'citation-pill-active' : ''}`}
                                onClick={() => handleCitationClick(num)}
                                title={`View Source ${num}: ${filename} (${pageLabel})`}
                                aria-label={`Source ${num}: ${filename}, ${pageLabel}`}
                            >
                                <span className="citation-pill-bracket">[</span>
                                <span className="citation-pill-num">{num}</span>
                                <span className="citation-pill-bracket">]</span>
                            </button>
                        )
                    })}
                </span>
            )
        })
    }

    const renderFormattedAnswer = (answerText, sourceList) => {
        if (!answerText) return null

        const blocks = answerText
            .split(/\n\n+/)
            .map((b) => b.trim())
            .filter((b) => b.length > 0)

        return blocks.map((block, blockIdx) => {
            const lines = block
                .split('\n')
                .map((l) => l.trim())
                .filter((l) => l.length > 0)

            const isNumberedList = lines.length > 0 && lines.every((l) => /^\d+\.\s+/.test(l))
            if (isNumberedList) {
                return (
                    <ol key={`ol-${blockIdx}`} className="answer-list">
                        {lines.map((line, lineIdx) => {
                            const cleanLine = line.replace(/^\d+\.\s+/, '')
                            return (
                                <li key={`li-${lineIdx}`} className="answer-list-item">
                                    {renderInlineCitations(cleanLine, sourceList)}
                                </li>
                            )
                        })}
                    </ol>
                )
            }

            const isBulletList = lines.length > 0 && lines.every((l) => /^[-*•]\s+/.test(l))
            if (isBulletList) {
                return (
                    <ul key={`ul-${blockIdx}`} className="answer-list">
                        {lines.map((line, lineIdx) => {
                            const cleanLine = line.replace(/^[-*•]\s+/, '')
                            return (
                                <li key={`li-${lineIdx}`} className="answer-list-item">
                                    {renderInlineCitations(cleanLine, sourceList)}
                                </li>
                            )
                        })}
                    </ul>
                )
            }

            return (
                <p key={`p-${blockIdx}`} className="answer-paragraph">
                    {lines.map((line, lineIdx) => (
                        <span key={`line-${lineIdx}`}>
                            {lineIdx > 0 && <br />}
                            {renderInlineCitations(line, sourceList)}
                        </span>
                    ))}
                </p>
            )
        })
    }

    const sortedSources = Array.isArray(sources)
        ? [...sources].sort(
              (a, b) => (Number(a.citation_index) || 0) - (Number(b.citation_index) || 0)
          )
        : []

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
                        {renderFormattedAnswer(answer, sources)}
                    </div>

                    {/* =================================
                        VERIFIED SOURCES SECTION
                    ================================= */}
                    {sortedSources.length > 0 && (
                        <section className="verified-sources-section" aria-labelledby="verified-sources-heading">
                            <div className="verified-sources-header">
                                <div className="verified-sources-title-wrap">
                                    <span className="sources-badge-icon" aria-hidden="true">🎯</span>
                                    <div>
                                        <h4 id="verified-sources-heading">
                                            Verified Sources ({sortedSources.length})
                                        </h4>
                                        <p>Document passages cited in the synthesized answer above</p>
                                    </div>
                                </div>
                            </div>

                            <div className="verified-sources-list">
                                {sortedSources.map((source) => {
                                    const citeNum = source.citation_index
                                    const isHighlighted = highlightedCitation === citeNum
                                    const isExpanded = !!expandedSourceExcerpts[citeNum]
                                    const filename = source.filename || `Document #${source.document_id || citeNum}`
                                    const pageLabel = source.page_number != null
                                        ? `Page ${source.page_number}`
                                        : 'Page unavailable'
                                    const contentText = source.content || source.text || 'No text excerpt available.'
                                    const needsTruncation = contentText.length > 220
                                    const displayText = !needsTruncation || isExpanded
                                        ? contentText
                                        : `${contentText.slice(0, 220)}...`

                                    return (
                                        <article
                                            key={source.chunk_id || source.id || citeNum}
                                            id={`source-card-${citeNum}`}
                                            className={`verified-source-card ${isHighlighted ? 'verified-source-card-highlighted' : ''}`}
                                            tabIndex={0}
                                            aria-label={`Source ${citeNum}: ${filename}, ${pageLabel}`}
                                        >
                                            <div className="verified-source-card-top">
                                                <div className="verified-source-meta">
                                                    <span className="source-citation-badge">
                                                        Source {citeNum}
                                                    </span>
                                                    <span className="verified-source-filename" title={filename}>
                                                        📄 {filename}
                                                    </span>
                                                    <span
                                                        className={`verified-source-page ${source.page_number != null ? 'page-verified' : 'page-na'}`}
                                                    >
                                                        {pageLabel}
                                                    </span>
                                                </div>

                                                {needsTruncation && (
                                                    <button
                                                        type="button"
                                                        className="source-excerpt-toggle"
                                                        onClick={() => toggleSourceExcerpt(citeNum)}
                                                        aria-expanded={isExpanded}
                                                    >
                                                        {isExpanded ? 'Show less ▲' : 'Expand excerpt ▼'}
                                                    </button>
                                                )}
                                            </div>

                                            <p className="verified-source-text">
                                                {displayText}
                                            </p>
                                        </article>
                                    )
                                })}
                            </div>
                        </section>
                    )}

                    {/* =================================
                        REFERENCED CONTEXT PANEL (EXPANDABLE)
                    ================================= */}
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
                                        {sources.length === 1 ? 'retrieved chunk' : 'retrieved chunks'})
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
                                            <article className="source-card" key={source.chunk_id || source.id || idx}>
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