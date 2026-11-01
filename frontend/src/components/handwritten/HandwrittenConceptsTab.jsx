import { useState, useEffect, useMemo } from 'react'
import {
    BrainCircuit,
    Sparkles,
    Star,
    Search,
    Copy,
    Check,
    AlertTriangle,
    RefreshCw,
    Bookmark,
    Quote,
    Filter,
    ChevronDown,
    ChevronUp
} from 'lucide-react'
import { apiRequest } from '../../services/api'

export default function HandwrittenConceptsTab({ documentId, transcriptionUpdated }) {
    const [concepts, setConcepts] = useState([])
    const [isOutdated, setIsOutdated] = useState(false)
    const [loading, setLoading] = useState(false)
    const [extracting, setExtracting] = useState(false)
    const [error, setError] = useState(null)
    const [searchQuery, setSearchQuery] = useState('')
    const [filterBookmarked, setFilterBookmarked] = useState(false)
    const [expandedIds, setExpandedIds] = useState(new Set())
    const [copiedId, setCopiedId] = useState(null)

    // Load concepts
    const fetchConcepts = async () => {
        try {
            setLoading(true)
            setError(null)
            const res = await apiRequest(`/handwritten/${documentId}/concepts`)
            setConcepts(res?.concepts || [])
            setIsOutdated(Boolean(res?.is_outdated))
        } catch (err) {
            console.error('Fetch concepts error:', err)
            setError(err.message || 'Failed to load concepts.')
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        if (documentId) {
            fetchConcepts()
        }
    }, [documentId, transcriptionUpdated])

    // Extract concepts via Ollama
    const handleExtract = async () => {
        try {
            setExtracting(true)
            setError(null)
            const res = await apiRequest(`/handwritten/${documentId}/concepts/generate`, {
                method: 'POST'
            })
            setConcepts(res?.concepts || [])
            setIsOutdated(false)
        } catch (err) {
            console.error('Extract concepts error:', err)
            setError(err.message || 'Failed to extract concepts from notes.')
        } finally {
            setExtracting(false)
        }
    }

    // Toggle bookmark
    const handleToggleBookmark = async (conceptId) => {
        // Optimistic UI update
        setConcepts(prev => prev.map(c => c.id === conceptId ? { ...c, is_bookmarked: !c.is_bookmarked } : c))
        try {
            await apiRequest(`/handwritten/${documentId}/concepts/${conceptId}/bookmark`, {
                method: 'PATCH'
            })
        } catch (err) {
            console.error('Bookmark error:', err)
            // Revert on error
            fetchConcepts()
        }
    }

    const toggleExpand = (id) => {
        setExpandedIds(prev => {
            const next = new Set(prev)
            if (next.has(id)) next.delete(id)
            else next.add(id)
            return next
        })
    }

    const handleCopy = (text, id) => {
        navigator.clipboard.writeText(text)
        setCopiedId(id)
        setTimeout(() => setCopiedId(null), 1800)
    }

    // Filter concepts based on search and bookmark filter
    const filteredConcepts = useMemo(() => {
        return concepts.filter(c => {
            const matchesSearch = !searchQuery ||
                c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                c.definition.toLowerCase().includes(searchQuery.toLowerCase()) ||
                (c.related_concepts || []).some(r => r.toLowerCase().includes(searchQuery.toLowerCase()))

            const matchesBookmark = !filterBookmarked || c.is_bookmarked
            return matchesSearch && matchesBookmark
        })
    }, [concepts, searchQuery, filterBookmarked])

    const bookmarkedCount = useMemo(() => {
        return concepts.filter(c => c.is_bookmarked).length
    }, [concepts])

    return (
        <div className="intel-tab-container">
            {/* Toolbar */}
            <div className="intel-toolbar">
                <div className="intel-search-box">
                    <Search size={14} className="search-icon" />
                    <input
                        type="text"
                        placeholder="Search concepts or definitions..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="intel-search-input"
                    />
                    {searchQuery && (
                        <button
                            type="button"
                            className="clear-search-btn"
                            onClick={() => setSearchQuery('')}
                        >
                            ×
                        </button>
                    )}
                </div>

                <div className="intel-actions-group">
                    <button
                        type="button"
                        className={`intel-filter-btn ${filterBookmarked ? 'active' : ''}`}
                        onClick={() => setFilterBookmarked(!filterBookmarked)}
                        title="Filter bookmarked concepts"
                    >
                        <Star size={13} fill={filterBookmarked ? '#f59e0b' : 'none'} color={filterBookmarked ? '#f59e0b' : 'currentColor'} />
                        <span>Bookmarked ({bookmarkedCount})</span>
                    </button>

                    <button
                        type="button"
                        className="btn-studio-action btn-studio-primary"
                        onClick={handleExtract}
                        disabled={extracting}
                    >
                        <Sparkles size={13} className={extracting ? 'spin-icon' : ''} />
                        <span>{extracting ? 'Extracting...' : (concepts.length > 0 ? 'Regenerate' : 'Extract Concepts')}</span>
                    </button>
                </div>
            </div>

            {/* Outdated Notice */}
            {isOutdated && concepts.length > 0 && (
                <div className="intel-outdated-banner">
                    <div className="outdated-content">
                        <AlertTriangle size={18} className="outdated-icon" />
                        <div>
                            <strong>Transcription Modified</strong>
                            <p>Handwriting has been edited since these concepts were analyzed. Regenerate to capture newly added ideas.</p>
                        </div>
                    </div>
                    <button
                        type="button"
                        className="btn-outdated-regen"
                        onClick={handleExtract}
                        disabled={extracting}
                    >
                        <RefreshCw size={12} className={extracting ? 'spin-icon' : ''} />
                        <span>{extracting ? 'Updating...' : 'Regenerate Concepts'}</span>
                    </button>
                </div>
            )}

            {/* Error */}
            {error && (
                <div className="intel-error-banner">
                    <AlertTriangle size={16} />
                    <span>{error}</span>
                </div>
            )}

            {/* Generating Loader */}
            {extracting && (
                <div className="intel-generating-card">
                    <div className="intel-spinner-orb">
                        <BrainCircuit size={28} className="spin-icon" style={{ color: '#c084fc' }} />
                    </div>
                    <h4>Mining Key Concepts with Llama 3.2...</h4>
                    <p>Detecting central themes, definitions, supporting quotes, and interconnected terminology across your handwritten pages.</p>
                    <div className="intel-progress-bar-wrap">
                        <div className="intel-progress-bar-fill" />
                    </div>
                </div>
            )}

            {/* Empty State */}
            {!extracting && !loading && concepts.length === 0 && (
                <div className="intel-empty-card">
                    <div className="empty-icon-wrap" style={{ background: 'rgba(192, 132, 252, 0.15)', borderColor: 'rgba(192, 132, 252, 0.3)' }}>
                        <BrainCircuit size={40} style={{ color: '#c084fc' }} />
                    </div>
                    <h3>Build an Interactive Knowledge Glossary</h3>
                    <p>
                        Extract academic concepts, definitions, and supporting evidence directly from your handwritten notes.
                        Bookmark key concepts and review citations by page.
                    </p>
                    <button
                        type="button"
                        className="btn-intel-primary"
                        onClick={handleExtract}
                        style={{ background: 'linear-gradient(135deg, #a855f7, #6366f1)' }}
                    >
                        <Sparkles size={16} />
                        <span>Extract Key Concepts</span>
                    </button>
                </div>
            )}

            {/* Concepts Grid */}
            {!extracting && concepts.length > 0 && (
                <div className="concepts-grid">
                    {filteredConcepts.map(concept => {
                        const isExpanded = expandedIds.has(concept.id)
                        return (
                            <div
                                key={concept.id}
                                className={`concept-card ${concept.is_bookmarked ? 'bookmarked' : ''}`}
                            >
                                <div className="concept-card-top">
                                    <div className="concept-title-group">
                                        <h4 className="concept-name">{concept.name}</h4>
                                        <span className="page-citation-pill">Page {concept.page_number}</span>
                                    </div>
                                    <div className="concept-top-actions">
                                        <button
                                            type="button"
                                            className="btn-concept-action"
                                            onClick={() => handleCopy(concept.definition, concept.id)}
                                            title="Copy definition"
                                        >
                                            {copiedId === concept.id ? <Check size={13} style={{ color: '#34d399' }} /> : <Copy size={13} />}
                                        </button>
                                        <button
                                            type="button"
                                            className={`btn-concept-star ${concept.is_bookmarked ? 'starred' : ''}`}
                                            onClick={() => handleToggleBookmark(concept.id)}
                                            title={concept.is_bookmarked ? 'Remove bookmark' : 'Bookmark concept'}
                                        >
                                            <Star
                                                size={15}
                                                fill={concept.is_bookmarked ? '#f59e0b' : 'none'}
                                                color={concept.is_bookmarked ? '#f59e0b' : '#94a3b8'}
                                            />
                                        </button>
                                    </div>
                                </div>

                                <p className="concept-definition">{concept.definition}</p>

                                {/* Supporting Quote Excerpt */}
                                {concept.excerpt && (
                                    <div className="concept-excerpt-box">
                                        <Quote size={12} className="quote-icon" />
                                        <p className="excerpt-text">"{concept.excerpt}"</p>
                                    </div>
                                )}

                                {/* Related Concepts Tags */}
                                {concept.related_concepts && concept.related_concepts.length > 0 && (
                                    <div className="concept-related-row">
                                        <span className="related-label">Related:</span>
                                        <div className="related-tags-list">
                                            {concept.related_concepts.map((tag, tIdx) => (
                                                <span key={tIdx} className="related-tag-pill">
                                                    {tag}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )
                    })}
                </div>
            )}
        </div>
    )
}

