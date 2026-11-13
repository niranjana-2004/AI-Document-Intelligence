import { useState, useEffect, useCallback } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
    Compass,
    Search,
    Sparkles,
    CheckCircle,
    AlertCircle,
    GitBranch,
    Network,
    ArrowRight,
    ExternalLink,
    RefreshCw,
    Layers,
    ShieldCheck,
    Scale,
    Tag,
} from 'lucide-react'

import {
    apiRequest,
    queryKnowledgeIntelligence,
    clearKnowledgeIntelligenceCache,
} from '../services/api'
import '../styles/knowledge-explorer.css'

const QUICK_PROMPTS = [
    'What do my documents say about TCP?',
    'Explain everything Cognidocs knows about neural networks',
    'Compare TCP and UDP',
    'Which documents disagree about this topic?',
    'Show me all the evidence for this concept',
    'What are the key security concerns in cloud storage?',
]

export default function KnowledgeExplorer() {
    const navigate = useNavigate()
    const [searchParams, setSearchParams] = useSearchParams()

    const initialQ = searchParams.get('q') || ''
    const initialDocsStr = searchParams.get('docs') || ''

    // State
    const [documents, setDocuments] = useState([])
    const [loadingDocs, setLoadingDocs] = useState(true)
    const [selectedDocIds, setSelectedDocIds] = useState([])
    const [query, setQuery] = useState(initialQ)
    const [loading, setLoading] = useState(false)
    const [errorMsg, setErrorMsg] = useState('')
    const [response, setResponse] = useState(null)
    const [skipLlm, setSkipLlm] = useState(false)
    const [clearingCache, setClearingCache] = useState(false)

    // Load available user documents & run initial query if present
    useEffect(() => {
        let cancelled = false
        async function loadInitial() {
            setLoadingDocs(true)
            try {
                const res = await apiRequest('/documents')
                const list = Array.isArray(res) ? res : (res?.documents || [])
                if (cancelled) return
                setDocuments(list)

                const parsedDocs = initialDocsStr
                    ? initialDocsStr.split(',').map(Number).filter(Boolean)
                    : []
                let docsToUse = parsedDocs
                if (docsToUse.length === 0 && list.length > 0) {
                    docsToUse = list.slice(0, 8).map((d) => d.id)
                }
                setSelectedDocIds(docsToUse)

                if (initialQ && docsToUse.length > 0) {
                    setLoading(true)
                    try {
                        const kiRes = await queryKnowledgeIntelligence({
                            query: initialQ,
                            documentIds: docsToUse,
                            skipLlm,
                            maxEvidenceItems: 20,
                        })
                        if (!cancelled) setResponse(kiRes)
                    } catch (qErr) {
                        if (!cancelled) setErrorMsg(qErr.message || 'Failed to execute query')
                    } finally {
                        if (!cancelled) setLoading(false)
                    }
                }
            } catch (err) {
                if (!cancelled) {
                    setErrorMsg('Failed to load user documents: ' + (err.message || ''))
                }
            } finally {
                if (!cancelled) setLoadingDocs(false)
            }
        }
        loadInitial()
        return () => { cancelled = true }
    }, [initialDocsStr, initialQ, skipLlm])

    // Execute query
    const handleRunQuery = useCallback(async (customQuery = null, customFocus = null, forceRefresh = false) => {
        const queryText = (customQuery !== null ? customQuery : query).trim()
        if (!queryText) return

        if (selectedDocIds.length === 0) {
            setErrorMsg('Please select at least one document to explore.')
            return
        }

        setLoading(true)
        setErrorMsg('')

        try {
            const res = await queryKnowledgeIntelligence({
                query: queryText,
                documentIds: selectedDocIds,
                focusEntity: customFocus || null,
                forceRefresh,
                skipLlm,
                maxEvidenceItems: 20,
            })

            setResponse(res)
            setSearchParams({
                q: queryText,
                docs: selectedDocIds.join(','),
            }, { replace: true })
        } catch (err) {
            setErrorMsg(err.message || 'Failed to execute knowledge intelligence query.')
        } finally {
            setLoading(false)
        }
    }, [query, selectedDocIds, skipLlm, setSearchParams])

    const toggleDocSelection = (docId) => {
        setSelectedDocIds((prev) => {
            if (prev.includes(docId)) {
                return prev.filter((id) => id !== docId)
            }
            return [...prev, docId]
        })
    }

    const selectAllDocs = () => {
        if (selectedDocIds.length === documents.length) {
            setSelectedDocIds([])
        } else {
            setSelectedDocIds(documents.map((d) => d.id))
        }
    }

    const handleClearCache = async () => {
        setClearingCache(true)
        try {
            await clearKnowledgeIntelligenceCache()
            if (query) {
                await handleRunQuery(null, null, true)
            }
        } catch (err) {
            setErrorMsg('Failed to clear cache: ' + err.message)
        } finally {
            setClearingCache(false)
        }
    }

    // Deep navigation helpers
    const openDocViewer = (docId, pageNumber = 1) => {
        navigate(`/documents/${docId}?page=${pageNumber}`)
    }

    const openInKnowledgeGraph = (entityName = '') => {
        const docsParam = selectedDocIds.join(',')
        navigate(`/knowledge-graph?mode=cross&docs=${docsParam}${entityName ? `&search=${encodeURIComponent(entityName)}` : ''}`)
    }

    const openInMindMap = (docId = null) => {
        const targetId = docId || selectedDocIds[0] || ''
        navigate(`/mind-map?doc=${targetId}`)
    }

    const openInAskAI = (contextQuery = '') => {
        const finalQ = contextQuery || query || 'Explain this topic in detail'
        navigate(`/ask-ai?initial_query=${encodeURIComponent(finalQ)}&document_ids=${selectedDocIds.join(',')}`)
    }

    return (
        <div className="knowledge-explorer-container">
            {/* Header */}
            <div className="ke-header">
                <div className="ke-title-section">
                    <div className="ke-title-row">
                        <div className="ke-title-icon">
                            <Compass size={22} />
                        </div>
                        <h1>Knowledge Explorer</h1>
                        <span className="ke-badge-phase3">Phase 3</span>
                    </div>
                    <p className="ke-subtitle">
                        Unified, source-grounded cross-document intelligence layer powered by local AI.
                    </p>
                </div>

                <div className="ke-header-actions">
                    <label style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer', color: '#94a3b8' }}>
                        <input
                            type="checkbox"
                            checked={skipLlm}
                            onChange={(e) => setSkipLlm(e.target.checked)}
                        />
                        <span>Fast Deterministic Mode</span>
                    </label>

                    <button
                        type="button"
                        className="ke-btn-ghost"
                        onClick={handleClearCache}
                        disabled={clearingCache}
                        title="Clear cached queries and force recomputation"
                    >
                        <RefreshCw size={14} className={clearingCache ? 'ke-spinner' : ''} />
                        <span>{clearingCache ? 'Clearing...' : 'Clear Cache'}</span>
                    </button>
                </div>
            </div>

            {/* Document Selector Card */}
            <div className="ke-doc-selector-card">
                <div className="ke-doc-header">
                    <div className="ke-doc-title-row">
                        <span className="ke-doc-label">Knowledge Scope</span>
                        <span className="ke-doc-count-badge">
                            {selectedDocIds.length} of {documents.length} Selected
                        </span>
                    </div>
                    <button
                        type="button"
                        className="ke-doc-toggle-btn"
                        onClick={selectAllDocs}
                    >
                        {selectedDocIds.length === documents.length ? 'Deselect All' : 'Select All'}
                    </button>
                </div>

                {loadingDocs ? (
                    <div style={{ fontSize: 13, color: '#94a3b8' }}>Loading library documents...</div>
                ) : (
                    <div className="ke-doc-chips">
                        {documents.map((doc) => {
                            const isSelected = selectedDocIds.includes(doc.id)
                            const docType = doc.is_handwritten ? 'Handwritten' : (doc.document_type || 'PDF')
                            return (
                                <button
                                    key={doc.id}
                                    type="button"
                                    className={`ke-doc-chip ${isSelected ? 'selected' : ''}`}
                                    onClick={() => toggleDocSelection(doc.id)}
                                >
                                    <span className="ke-chip-type">{docType}</span>
                                    <span>{doc.filename || `Doc #${doc.id}`}</span>
                                </button>
                            )
                        })}
                    </div>
                )}
            </div>

            {/* Query Input Card */}
            <div className="ke-query-card">
                <form
                    onSubmit={(e) => {
                        e.preventDefault()
                        handleRunQuery()
                    }}
                >
                    <div className="ke-query-input-wrapper">
                        <Search size={18} className="ke-query-icon" />
                        <input
                            type="text"
                            className="ke-query-input"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="Ask anything about what Cognidocs knows across your documents..."
                            disabled={loading}
                        />
                        <button
                            type="submit"
                            className="ke-btn-primary"
                            disabled={loading || !query.trim()}
                        >
                            <Sparkles size={16} />
                            <span>{loading ? 'Synthesizing...' : 'Explore Intelligence'}</span>
                        </button>
                    </div>
                </form>

                {/* Quick Prompts */}
                <div className="ke-prompt-pills-row">
                    <span className="ke-prompt-label">Try:</span>
                    {QUICK_PROMPTS.map((promptText, idx) => (
                        <button
                            key={idx}
                            type="button"
                            className="ke-prompt-pill"
                            onClick={() => {
                                setQuery(promptText)
                                handleRunQuery(promptText)
                            }}
                        >
                            {promptText}
                        </button>
                    ))}
                </div>
            </div>

            {/* Error Banner */}
            {errorMsg && (
                <div className="ke-error-banner">
                    <AlertCircle size={18} />
                    <span>{errorMsg}</span>
                </div>
            )}

            {/* Loading Indicator */}
            {loading && (
                <div className="ke-loading-box">
                    <div className="ke-spinner" />
                    <span>Synthesizing grounded intelligence from selected documents...</span>
                </div>
            )}

            {/* Main Response Views */}
            {response && !loading && (
                <>
                    {/* Direct Grounded Answer Card */}
                    <div className="ke-answer-card">
                        <div className="ke-answer-header">
                            <div className="ke-answer-badge-row">
                                <span className={`ke-status-badge ${
                                    response.direct_answer.grounding_status === 'grounded' ? 'grounded' :
                                    response.direct_answer.grounding_status === 'partial' ? 'partial' : 'insufficient'
                                }`}>
                                    <ShieldCheck size={14} />
                                    <span>
                                        {response.direct_answer.grounding_status === 'grounded' ? 'Strictly Grounded' :
                                         response.direct_answer.grounding_status === 'partial' ? 'Partially Grounded' : 'Insufficient Evidence'}
                                    </span>
                                </span>

                                <span className="ke-method-badge">
                                    {response.direct_answer.synthesis_method === 'ollama' ? 'Local Ollama (llama3.2)' : 'Deterministic Verification'}
                                </span>

                                {response.cached && (
                                    <span className="ke-method-badge" style={{ color: '#86efac' }}>
                                        Cached Instant
                                    </span>
                                )}

                                <span className="ke-method-badge">
                                    Intent: {response.intent}
                                </span>
                            </div>

                            <div style={{ fontSize: 12, color: '#94a3b8' }}>
                                Latency: {response.diagnostics?.timings?.total_latency_ms || 0}ms
                            </div>
                        </div>

                        {/* Answer text */}
                        <div className="ke-answer-text">
                            {response.direct_answer.text}
                        </div>

                        {/* Supporting Sources */}
                        {response.direct_answer.supporting_sources?.length > 0 && (
                            <div className="ke-answer-sources">
                                <span className="ke-sources-label">Sources:</span>
                                {response.direct_answer.supporting_sources.map((src, i) => (
                                    <span key={i} className="ke-source-tag">
                                        <CheckCircle size={12} />
                                        <span>{src}</span>
                                    </span>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Multi-column Grid layout */}
                    <div className="ke-grid-layout">
                        {/* Left column (8 cols): Overview & Evidence */}
                        <div className="ke-col-8">
                            {/* Knowledge Overview Card */}
                            {response.knowledge_overview?.length > 0 && (
                                <div className="ke-card">
                                    <div className="ke-card-header">
                                        <h3 className="ke-card-title">
                                            <Layers size={16} />
                                            <span>Knowledge Overview</span>
                                        </h3>
                                        <span style={{ fontSize: 12, color: '#94a3b8' }}>
                                            {response.knowledge_overview.length} Concepts Identified
                                        </span>
                                    </div>

                                    <div className="ke-table-wrapper">
                                        <table className="ke-overview-table">
                                            <thead>
                                                <tr>
                                                    <th>Canonical Entity</th>
                                                    <th>Type</th>
                                                    <th>Documents</th>
                                                    <th>Mentions</th>
                                                    <th>Scope</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {response.knowledge_overview.map((item, idx) => (
                                                    <tr key={idx}>
                                                        <td>
                                                            <button
                                                                type="button"
                                                                className="ke-entity-btn"
                                                                onClick={() => {
                                                                    setQuery(`Explain everything Cognidocs knows about ${item.canonical_name}`)
                                                                    handleRunQuery(`Explain everything Cognidocs knows about ${item.canonical_name}`, item.canonical_name)
                                                                }}
                                                                title="Click to drill down on this concept"
                                                            >
                                                                {item.canonical_name}
                                                            </button>
                                                        </td>
                                                        <td>
                                                            <span style={{ color: '#94a3b8' }}>{item.entity_type}</span>
                                                        </td>
                                                        <td>
                                                            <span>{item.document_count} doc{item.document_count > 1 ? 's' : ''}</span>
                                                        </td>
                                                        <td>
                                                            <span>{item.mention_count}</span>
                                                        </td>
                                                        <td>
                                                            <span className={`ke-scope-pill ${item.is_shared ? 'shared' : 'specific'}`}>
                                                                {item.is_shared ? 'Shared' : 'Document-Specific'}
                                                            </span>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}

                            {/* Source Evidence Panel */}
                            {response.evidence?.length > 0 && (
                                <div className="ke-card">
                                    <div className="ke-card-header">
                                        <h3 className="ke-card-title">
                                            <ShieldCheck size={16} />
                                            <span>Source Evidence Excerpts</span>
                                        </h3>
                                        <span style={{ fontSize: 12, color: '#94a3b8' }}>
                                            {response.evidence.length} Verifiable Citations
                                        </span>
                                    </div>

                                    <div className="ke-evidence-list">
                                        {response.evidence.map((ev, idx) => (
                                            <div key={idx} className="ke-evidence-item">
                                                <div className="ke-evidence-top">
                                                    <div className="ke-evidence-source-info">
                                                        <span className={`ke-evidence-type-badge ${ev.source_type}`}>
                                                            {ev.source_type.replace('_', ' ')}
                                                        </span>
                                                        <span className="ke-evidence-doc-title">
                                                            {ev.document_title}
                                                        </span>
                                                        <span className="ke-evidence-page">
                                                            Page {ev.page_number}
                                                        </span>
                                                    </div>

                                                    <span style={{ fontSize: 11, color: '#64748b' }}>
                                                        Match: {Math.round(ev.confidence * 100)}%
                                                    </span>
                                                </div>

                                                <div className="ke-evidence-quote">
                                                    "{ev.excerpt}"
                                                </div>

                                                <div className="ke-evidence-actions">
                                                    <button
                                                        type="button"
                                                        className="ke-evidence-action-btn"
                                                        onClick={() => openDocViewer(ev.document_id, ev.page_number)}
                                                    >
                                                        <ExternalLink size={10} style={{ display: 'inline', marginRight: 4 }} />
                                                        Open Page
                                                    </button>
                                                    <button
                                                        type="button"
                                                        className="ke-evidence-action-btn"
                                                        onClick={() => openInAskAI(`Explain this excerpt from ${ev.document_title} page ${ev.page_number}: "${ev.excerpt}"`)}
                                                    >
                                                        <Sparkles size={10} style={{ display: 'inline', marginRight: 4 }} />
                                                        Ask AI About This
                                                    </button>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Right column (4 cols): Insights, Conflicts, Relationships, Related Topics */}
                        <div className="ke-col-4">
                            {/* Cross-Document Insights */}
                            {response.cross_document_insights?.length > 0 && (
                                <div className="ke-card">
                                    <div className="ke-card-header">
                                        <h3 className="ke-card-title">
                                            <Network size={16} />
                                            <span>Cross-Document Insights</span>
                                        </h3>
                                    </div>
                                    <div>
                                        {response.cross_document_insights.map((ins, idx) => (
                                            <div key={idx} className="ke-insight-card">
                                                <div style={{ fontSize: 12, fontWeight: 600, color: '#c7d2fe', marginBottom: 4 }}>
                                                    {ins.entity}
                                                </div>
                                                <div style={{ fontSize: 13, lineHeight: 1.5, color: '#94a3b8' }}>
                                                    {ins.description}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Differences / Conflicts */}
                            {response.conflicts?.length > 0 && (
                                <div className="ke-card">
                                    <div className="ke-card-header">
                                        <h3 className="ke-card-title">
                                            <Scale size={16} />
                                            <span>Source Differences & Consensus</span>
                                        </h3>
                                    </div>
                                    <div>
                                        {response.conflicts.map((conf, idx) => (
                                            <div key={idx} className="ke-insight-card">
                                                <span className={`ke-conflict-category ${conf.category}`}>
                                                    {conf.category.replace('_', ' ')}
                                                </span>
                                                <div style={{ fontSize: 13, lineHeight: 1.5, color: '#cbd5e1', marginBottom: 6 }}>
                                                    {conf.description}
                                                </div>
                                                {conf.claim_a?.statement && (
                                                    <div style={{ fontSize: 11, color: '#94a3b8', fontStyle: 'italic', marginBottom: 3 }}>
                                                        <strong>{conf.claim_a.document_name}</strong> (p.{conf.claim_a.page}): "{conf.claim_a.statement}..."
                                                    </div>
                                                )}
                                                {conf.claim_b?.statement && (
                                                    <div style={{ fontSize: 11, color: '#94a3b8', fontStyle: 'italic' }}>
                                                        <strong>{conf.claim_b.document_name}</strong> (p.{conf.claim_b.page}): "{conf.claim_b.statement}..."
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Relationships List */}
                            {response.relationships?.length > 0 && (
                                <div className="ke-card">
                                    <div className="ke-card-header">
                                        <h3 className="ke-card-title">
                                            <GitBranch size={16} />
                                            <span>Concept Relationships</span>
                                        </h3>
                                        <span style={{ fontSize: 12, color: '#94a3b8' }}>
                                            {response.relationships.length}
                                        </span>
                                    </div>
                                    <div className="ke-rel-list">
                                        {response.relationships.slice(0, 6).map((rel, idx) => (
                                            <div key={idx} className="ke-rel-item">
                                                <div className="ke-rel-flow">
                                                    <span className="ke-rel-src">{rel.source_entity}</span>
                                                    <span className="ke-rel-pred">{rel.predicate}</span>
                                                    <span className="ke-rel-tgt">{rel.target_entity}</span>
                                                </div>
                                                <div className="ke-rel-meta">
                                                    <span>{rel.supporting_documents?.join(', ') || '1 doc'}</span>
                                                    {rel.is_cross_document && (
                                                        <span style={{ color: '#d8b4fe' }}>• Cross-Doc</span>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Related Topics */}
                            {response.related_topics?.length > 0 && (
                                <div className="ke-card">
                                    <div className="ke-card-header">
                                        <h3 className="ke-card-title">
                                            <Tag size={16} />
                                            <span>Related Topics</span>
                                        </h3>
                                    </div>
                                    <div className="ke-related-topics-pills">
                                        {response.related_topics.map((topic, idx) => (
                                            <button
                                                key={idx}
                                                type="button"
                                                className="ke-topic-pill"
                                                onClick={() => {
                                                    setQuery(`What do my documents say about ${topic.name}?`)
                                                    handleRunQuery(`What do my documents say about ${topic.name}?`, topic.name)
                                                }}
                                                title={`Click to explore ${topic.name}`}
                                            >
                                                <span>{topic.name}</span>
                                                <ArrowRight size={12} />
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Explore Further Navigation Bar */}
                    <div className="ke-explore-bar">
                        <div style={{ fontSize: 13, color: '#94a3b8' }}>
                            Continue exploring this knowledge in other Cognidocs tools:
                        </div>
                        <div className="ke-explore-buttons">
                            <button
                                type="button"
                                className="ke-btn-nav"
                                onClick={() => openInKnowledgeGraph(response.focus_entities?.[0] || '')}
                            >
                                <GitBranch size={14} />
                                <span>Explore in Knowledge Graph</span>
                            </button>
                            <button
                                type="button"
                                className="ke-btn-nav"
                                onClick={() => openInMindMap()}
                            >
                                <Network size={14} />
                                <span>Explore in Mind Map</span>
                            </button>
                            <button
                                type="button"
                                className="ke-btn-nav"
                                onClick={() => openInAskAI()}
                            >
                                <Sparkles size={14} />
                                <span>Ask AI in Depth</span>
                            </button>
                        </div>
                    </div>
                </>
            )}
        </div>
    )
}
