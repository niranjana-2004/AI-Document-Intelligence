import { useState } from 'react'
import { apiRequest } from '../services/api'
import '../App.css'

function Search() {
    const [query, setQuery] = useState('')
    const [results, setResults] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [hasSearched, setHasSearched] = useState(false)

    const handleSearch = async () => {
        if (!query.trim()) {
            return
        }

        try {
            setLoading(true)
            setError('')
            setResults([])
            setHasSearched(true)

            const data = await apiRequest(
                `/documents/search?query=${encodeURIComponent(query)}&top_k=5`
            )

            setResults(data.results || [])
        } catch (err) {
            console.error('Search error:', err)
            setError(
                err.message ||
                'Unable to complete the search.'
            )
        } finally {
            setLoading(false)
        }
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

    return (
        <main className="search-page">
            {/* =================================
                PAGE HEADER
            ================================= */}
            <section className="search-page-header">
                <div>
                    <p className="eyebrow">SEMANTIC EXPLORATION</p>
                    <h2>Semantic Search</h2>
                    <p>
                        Discover concepts, passages, and facts by meaning across your document library.
                    </p>
                </div>
            </section>

            {/* =================================
                SEARCH BOX CARD
            ================================= */}
            <section className="search-box-card">
                <div className="search-box-header">
                    <div>
                        <h3>Neural Vector Retrieval</h3>
                        <p>Search by meaning and context, not just exact keywords.</p>
                    </div>

                    {(query || hasSearched) && (
                        <button
                            type="button"
                            className="clear-search-button"
                            onClick={handleClear}
                        >
                            Clear
                        </button>
                    )}
                </div>

                <div className="search-input-row">
                    <div className="search-input-wrapper">
                        <span className="search-icon-adornment" aria-hidden="true">⌕</span>
                        <input
                            className="full-search-input"
                            type="text"
                            placeholder="What concepts or information are you looking for?"
                            value={query}
                            onChange={(event) => setQuery(event.target.value)}
                            onKeyDown={handleKeyDown}
                            aria-label="Semantic search query"
                        />
                        {query && (
                            <button
                                type="button"
                                className="search-inline-clear"
                                onClick={() => setQuery('')}
                                aria-label="Clear query text"
                            >
                                ✕
                            </button>
                        )}
                    </div>

                    <button
                        type="button"
                        className="search-submit-button"
                        onClick={handleSearch}
                        disabled={loading || !query.trim()}
                    >
                        {loading ? 'Searching...' : 'Search →'}
                    </button>
                </div>

                <p className="search-hint">
                    Press <strong>Enter</strong> to execute vector similarity search
                </p>
            </section>

            {/* =================================
                ERROR BANNER
            ================================= */}
            {error && (
                <div className="search-error" role="alert">
                    <span className="msg-icon" aria-hidden="true">⚠</span>
                    <span>{error}</span>
                </div>
            )}

            {/* =================================
                LOADING STATE
            ================================= */}
            {loading && (
                <section className="search-loading-card">
                    <div className="search-loading-icon" aria-hidden="true">⌕</div>
                    <h3>Searching your documents...</h3>
                    <p>
                        Calculating cosine embeddings and ranking the most relevant passages.
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
                            <h3>Search Results</h3>
                            <p>
                                Found {results.length}{' '}
                                {results.length === 1 ? 'relevant passage' : 'relevant passages'}
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
                                            {String(index + 1).padStart(2, '0')}
                                        </div>

                                        <div className="search-result-meta">
                                            {result.filename && (
                                                <span className="result-meta-file">
                                                    📄 {result.filename}
                                                </span>
                                            )}
                                            {result.document_type && (
                                                <span className="result-meta-type">
                                                    {result.document_type}
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
                                                title="Semantic vector similarity"
                                            >
                                                <span className="score-label">Relevance</span>
                                                <span className="score-value">{relevanceScore}%</span>
                                            </div>
                                        )}
                                    </div>

                                    <div className="search-result-content">
                                        <p>
                                            {result.content || result.text || 'No content available.'}
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
                                                {relevanceScore}% semantic match
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
                    <div className="search-empty-icon" aria-hidden="true">⌕</div>
                    <h3>No matching passages found</h3>
                    <p>
                        No document passages matched &ldquo;{query}&rdquo;.
                        Try phrasing your query using different concepts or broader terms.
                    </p>
                </section>
            )}

            {/* =================================
                INITIAL STATE
            ================================= */}
            {!loading && !hasSearched && !error && (
                <section className="search-initial">
                    <div className="search-initial-icon" aria-hidden="true">✦</div>
                    <h3>Explore Your Documents Semantically</h3>
                    <p>
                        Enter any concept, question, or keyword above. Cognidocs semantic search
                        evaluates sentence embeddings to surface contextually related passages.
                    </p>
                </section>
            )}
        </main>
    )
}

export default Search