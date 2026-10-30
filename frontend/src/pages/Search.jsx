import { useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
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
                'Unable to retrieve matching passages from vector storage.'
            )
            setResults([])
        } finally {
            setLoading(false)
        }
    }

    const handleSearch = () => {
        executeSearch()
    }

    const handleKeyDown = (event) => {
        if (event.key === 'Enter') {
            executeSearch()
        }
    }

    const handleClear = () => {
        setQuery('')
        setResults([])
        setError('')
        setHasSearched(false)
    }

    const handleSuggestedClick = (suggestion) => {
        setQuery(suggestion)
        executeSearch(suggestion)
    }

    const containerVariants = {
        hidden: { opacity: 0 },
        visible: {
            opacity: 1,
            transition: { staggerChildren: 0.1 },
        },
    }

    const cardVariants = {
        hidden: { opacity: 0, y: 22 },
        visible: {
            opacity: 1,
            y: 0,
            transition: { duration: 0.45, ease: [0.16, 1, 0.3, 1] },
        },
    }

    return (
        <main className="search-page">
            {/* =================================
                PAGE HEADER
            ================================= */}
            <motion.section
                className="search-header"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
            >
                <p className="eyebrow">NEURAL RETRIEVAL</p>
                <h2>Semantic Document Search</h2>
                <p>
                    Retrieve exact passages from your document vault based on conceptual similarity
                    rather than keyword matching.
                </p>
            </motion.section>

            {/* =================================
                SEARCH INPUT BOX
            ================================= */}
            <motion.section
                className="search-box-card"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.45, delay: 0.1 }}
            >
                <div className="search-box-header">
                    <div>
                        <h3>Neural Vector Search</h3>
                        <p>Evaluates cosine distance between query embeddings and document chunks.</p>
                    </div>

                    {(query || hasSearched) && (
                        <motion.button
                            type="button"
                            className="clear-search-button"
                            onClick={handleClear}
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                        >
                            Reset Search
                        </motion.button>
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

                    <motion.button
                        type="button"
                        className="search-submit-button"
                        onClick={handleSearch}
                        disabled={loading || !query.trim()}
                        whileHover={!loading && query.trim() ? { scale: 1.04, y: -1 } : {}}
                        whileTap={!loading && query.trim() ? { scale: 0.97 } : {}}
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
                    </motion.button>
                </div>

                <div className="search-shortcuts-bar">
                    <span className="search-hint">
                        Press <kbd>Enter ↵</kbd> to execute high-dimensional cosine similarity search
                    </span>
                </div>
            </motion.section>

            {/* =================================
                ERROR BANNER
            ================================= */}
            <AnimatePresence>
                {error && (
                    <motion.div
                        className="search-error"
                        role="alert"
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                    >
                        <AlertCircle size={18} />
                        <span>{error}</span>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* =================================
                LOADING STATE WITH RADAR PULSE
            ================================= */}
            {loading && (
                <motion.section
                    className="search-loading-card"
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0 }}
                >
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
                </motion.section>
            )}

            {/* =================================
                SEARCH RESULTS (ANIMATED)
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

                    <motion.div
                        className="search-results-list"
                        variants={containerVariants}
                        initial="hidden"
                        animate="visible"
                    >
                        {results.map((result, index) => {
                            const rawScore = result.score ?? result.similarity
                            const relevanceScore =
                                rawScore !== undefined && rawScore !== null
                                    ? Math.round(rawScore * 100)
                                    : null

                            return (
                                <motion.article
                                    className="search-result-card"
                                    key={result.id || result.chunk_id || index}
                                    variants={cardVariants}
                                    whileHover={{ y: -4, scale: 1.01 }}
                                    transition={{ duration: 0.2 }}
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
                                                <motion.div
                                                    className="relevance-bar-fill"
                                                    initial={{ width: '0%' }}
                                                    animate={{
                                                        width: `${Math.min(100, Math.max(0, relevanceScore))}%`,
                                                    }}
                                                    transition={{
                                                        duration: 0.85,
                                                        delay: 0.15 + index * 0.08,
                                                        ease: [0.16, 1, 0.3, 1],
                                                    }}
                                                />
                                            </div>
                                            <span className="relevance-text-detail">
                                                {relevanceScore}% semantic relevance score
                                            </span>
                                        </div>
                                    )}
                                </motion.article>
                            )
                        })}
                    </motion.div>
                </section>
            )}

            {/* =================================
                NO RESULTS STATE
            ================================= */}
            {!loading && hasSearched && !error && results.length === 0 && (
                <motion.section
                    className="search-empty"
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                >
                    <div className="search-empty-icon" aria-hidden="true">
                        <SearchIcon size={40} />
                    </div>
                    <h3>No matching passages found</h3>
                    <p>
                        No document passages matched &ldquo;{query}&rdquo; within similarity thresholds.
                        Try phrasing your search query with different concepts or broader terms.
                    </p>
                    <motion.button
                        type="button"
                        className="clear-button"
                        onClick={handleClear}
                        whileHover={{ scale: 1.05 }}
                        whileTap={{ scale: 0.96 }}
                    >
                        Try Another Query
                    </motion.button>
                </motion.section>
            )}

            {/* =================================
                INITIAL STATE WITH SUGGESTIONS
            ================================= */}
            {!loading && !hasSearched && !error && (
                <motion.section
                    className="search-initial-container"
                    initial={{ opacity: 0, y: 15 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                >
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
                                <motion.button
                                    key={idx}
                                    type="button"
                                    className="suggestion-card-btn"
                                    onClick={() => handleSuggestedClick(suggestion)}
                                    whileHover={{ scale: 1.03, x: 4 }}
                                    whileTap={{ scale: 0.97 }}
                                >
                                    <Compass size={15} className="suggestion-icon" />
                                    <span>&ldquo;{suggestion}&rdquo;</span>
                                    <ArrowRight size={13} className="suggestion-arrow" />
                                </motion.button>
                            ))}
                        </div>
                    </div>
                </motion.section>
            )}
        </main>
    )
}

export default Search
