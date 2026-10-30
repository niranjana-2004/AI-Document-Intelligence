import { useState } from 'react'
import {
    Search as SearchIcon,
    Sparkles,
    FileText,
    X,
    ArrowRight,
    Compass,
    AlertCircle,
} from 'lucide-react'
import { apiRequest } from '../services/api'
import '../App.css'

const SUGGESTED_SEARCHES = [
    'Security compliance protocols and encryption standards',
    'Quarterly revenue growth and operational expenses',
    'System architecture and vector embedding pipeline',
    'Employee onboarding guidelines and company policy',
]

function Search() {
    const [query, setQuery] = useState('')
    const [results, setResults] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [hasSearched, setHasSearched] = useState(false)

    const executeSearch = async (searchQuery) => {
        const textToSearch = searchQuery !== undefined ? searchQuery : query
        if (!textToSearch.trim()) {
            return
        }

        try {
            setLoading(true)
            setError('')
            setResults([])
            setHasSearched(true)

            const data = await apiRequest(
                `/documents/search?query=${encodeURIComponent(textToSearch.trim())}&top_k=5`
            )

            setResults(data.results || [])
        } catch (err) {
            console.error('Search error:', err)
            setError(
                err.message ||
                'Unable to complete the semantic search.'
            )
        } finally {
            setLoading(false)
        }
    }

    const handleSearch = () => {
        executeSearch()
    }

    const handleKeyDown = (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            handleSearch()
        }
    }

    const handleClear = () => {
        setQuery('')
        setResults([])
        setError('')
        setHasSearched(false)
    }

    const handleSuggestedClick = (suggestedText) => {
        setQuery(suggestedText)
        executeSearch(suggestedText)
    }

    return (
        <main className="search-page">
            {/* =================================
                PAGE HEADER
            ================================= */}
            <section className="search-page-header">
                <div>
                    <p className="eyebrow">SEMANTIC RETRIEVAL ENGINE</p>
                    <h2>Semantic Vector Search</h2>
                    <p>
                        Discover passages, conceptual links, and facts by meaning across your indexed documents.
                    </p>
                </div>
            </section>

            {/* =================================
                SEARCH HERO CARD
            ================================= */}
            <section className="search-box-card">
                <div className="search-box-header">
                    <div>
                        <h3>Neural Vector Search</h3>
                        <p>Evaluates cosine distance between query embeddings and document chunks.</p>
                    </div>

                    {(query || hasSearched) && (
                        <button
                            type="button"
                            className="clear-search-button"
                            onClick={handleClear}
                        >
                            Reset Search
                        </button>
                    )}
                </div>

                <div className="search-input-row">
                    <div className="search-input-wrapper">
                        <SearchIcon size={18} className="search-icon-adornment" aria-hidden="true" />
                        <input
                            className="full-search-input"
                            type="text"
                            placeholder="Search by meaning: e.g., 'cloud security measures', 'budget forecasts'..."
                            value={query}
                            onChange={(event) => setQuery(event.target.value)}
                            onKeyDown={handleKeyDown}
                            aria-label="Semantic search query"
                            autoFocus
                        />
                        {query && (
                            <button
                                type="button"
                                className="search-inline-clear"
                                onClick={() => setQuery('')}
                                aria-label="Clear query text"
                            >
                                <X size={15} />
                            </button>
                        )}
                    </div>

                    <button
                        type="button"
                        className="search-submit-button"
                        onClick={handleSearch}
                        disabled={loading || !query.trim()}
                    >
                        {loading ? (
                            <>
                                <span className="spinner-inline" aria-hidden="true"></span>
                                <span>Searching...</span>
                            </>
                        ) : (
                            <>
                                <span>Search</span>
                                <ArrowRight size={16} />
                            </>
                        )}
                    </button>
                </div>

                <div className="search-shortcuts-bar">
                    <span className="search-hint">
                        Press <kbd>Enter ↵</kbd> to execute high-dimensional cosine similarity search
                    </span>
                </div>
            </section>

            {/* =================================
                ERROR BANNER
            ================================= */}
            {error && (
                <div className="search-error" role="alert">
                    <AlertCircle size={18} />
                    <span>{error}</span>
                </div>
            )}

            {/* =================================
                LOADING STATE
            ================================= */}
            {loading && (
                <section className="search-loading-card">
                    <div className="loading-pulse-ring" aria-hidden="true"></div>
                    <h3>Searching your knowledge vault...</h3>
                    <p>
                        Computing sentence embeddings and ranking document chunks by relevance.
                    </p>
                    <div className="search-loading-dots" aria-label="Loading search results">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </section>
            )}

            {/* =================================
                SEARCH RESULTS
            ================================= */}
            {!loading && hasSearched && !error && results.length > 0 && (
                <section className="search-results-section">
                    <div className="search-results-header">
                        <div>
                            <h3>Ranked Relevant Passages</h3>
                            <p>
                                Found {results.length}{' '}
                                {results.length === 1 ? 'matching chunk' : 'matching chunks'} ordered by cosine similarity
                            </p>
                        </div>
                    </div>

                    <div className="search-results-list">
                        {results.map((result, index) => {
                            const rawScore = result.score ?? result.similarity
                            const relevanceScore =
                                rawScore !== undefined && rawScore !== null
                                    ? Math.round(rawScore * 100)
                                    : null

                            return (
                                <article
                                    className="search-result-card"
                                    key={result.id || result.chunk_id || index}
                                >
                                    <div className="search-result-top">
                                        <div className="search-result-number">
                                            #{String(index + 1).padStart(2, '0')}
                                        </div>

                                        <div className="search-result-meta">
                                            {result.filename && (
                                                <span className="result-meta-file">
                                                    <FileText size={14} />
                                                    <span>{result.filename}</span>
                                                </span>
                                            )}
                                            {result.document_type && (
                                                <span className="result-meta-type">
                                                    {result.document_type}
                                                </span>
                                            )}
                                            {result.page_number != null && (
                                                <span className="result-meta-page">
                                                    Page {result.page_number}
                                                </span>
                                            )}
                                            {result.category && (
                                                <span className="result-meta-category">
                                                    {result.category}
                                                </span>
                                            )}
                                        </div>

                                        {relevanceScore !== null && (
                                            <div
                                                className="search-result-score-badge"
                                                title="Cosine similarity score"
                                            >
                                                <span className="score-label">Match</span>
                                                <span className="score-value">{relevanceScore}%</span>
                                            </div>
                                        )}
                                    </div>

                                    <div className="search-result-content">
                                        <p>
                                            {result.content || result.text || 'No text snippet available.'}
                                        </p>
                                    </div>

                                    {relevanceScore !== null && (
                                        <div className="search-result-footer">
                                            <div className="relevance-bar-track">
                                                <div
                                                    className="relevance-bar-fill"
                                                    style={{
                                                        width: `${Math.min(100, Math.max(0, relevanceScore))}%`,
                                                    }}
                                                ></div>
                                            </div>
                                            <span className="relevance-text-detail">
                                                {relevanceScore}% semantic relevance score
                                            </span>
                                        </div>
                                    )}
                                </article>
                            )
                        })}
                    </div>
                </section>
            )}

            {/* =================================
                NO RESULTS STATE
            ================================= */}
            {!loading && hasSearched && !error && results.length === 0 && (
                <section className="search-empty">
                    <div className="search-empty-icon" aria-hidden="true">
                        <SearchIcon size={40} />
                    </div>
                    <h3>No matching passages found</h3>
                    <p>
                        No document passages matched &ldquo;{query}&rdquo; within similarity thresholds.
                        Try phrasing your search query with different concepts or broader terms.
                    </p>
                    <button
                        type="button"
                        className="clear-button"
                        onClick={handleClear}
                    >
                        Try Another Query
                    </button>
                </section>
            )}

            {/* =================================
                INITIAL STATE WITH SUGGESTIONS
            ================================= */}
            {!loading && !hasSearched && !error && (
                <section className="search-initial-container">
                    <div className="search-initial-header">
                        <div className="search-initial-icon-wrap">
                            <Sparkles size={24} />
                        </div>
                        <h3>Explore Your Document Repository</h3>
                        <p>
                            Cognidocs semantic search doesn't just look for verbatim keywords—it evaluates
                            deep conceptual proximity using sentence embeddings.
                        </p>
                    </div>

                    <div className="search-suggestions-box">
                        <span className="suggestions-title">Example Semantic Inquiries</span>
                        <div className="suggestions-grid">
                            {SUGGESTED_SEARCHES.map((suggestion, idx) => (
                                <button
                                    key={idx}
                                    type="button"
                                    className="suggestion-card-btn"
                                    onClick={() => handleSuggestedClick(suggestion)}
                                >
                                    <Compass size={15} className="suggestion-icon" />
                                    <span>&ldquo;{suggestion}&rdquo;</span>
                                    <ArrowRight size={13} className="suggestion-arrow" />
                                </button>
                            ))}
                        </div>
                    </div>
                </section>
            )}
        </main>
    )
}

export default Search
