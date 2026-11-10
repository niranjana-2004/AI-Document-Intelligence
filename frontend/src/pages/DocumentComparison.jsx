import { useState, useEffect, useRef } from 'react'
import {
    FileText,
    PenTool,
    ArrowLeftRight,
    Sparkles,
    CheckCircle2,
    AlertTriangle,
    RotateCw,
    Search,
    ChevronDown,
    Layers,
    FileDiff,
    BookOpen,
    Info,
    Check,
} from 'lucide-react'
import { apiRequest } from '../services/api'
import '../styles/comparison.css'

export default function DocumentComparison() {
    const [documents, setDocuments] = useState([])
    const [loadingDocs, setLoadingDocs] = useState(true)
    const [docError, setDocError] = useState('')

    // Selection state
    const [docAId, setDocAId] = useState(null)
    const [docBId, setDocBId] = useState(null)
    const [forceRefresh, setForceRefresh] = useState(false)

    // Dropdown open states & search terms
    const [dropdownAOpen, setDropdownAOpen] = useState(false)
    const [dropdownBOpen, setDropdownBOpen] = useState(false)
    const [searchA, setSearchA] = useState('')
    const [searchB, setSearchB] = useState('')

    const dropdownARef = useRef(null)
    const dropdownBRef = useRef(null)

    // Comparison execution & result state
    const [isComparing, setIsComparing] = useState(false)
    const [compareStep, setCompareStep] = useState(1)
    const [comparisonResult, setComparisonResult] = useState(null)
    const [compareError, setCompareError] = useState('')

    // Results filters & search
    const [activeFilter, setActiveFilter] = useState('ALL') // 'ALL' | 'MODIFIED' | 'ADDED' | 'REMOVED' | 'SIMILAR'
    const [itemSearch, setItemSearch] = useState('')

    /* ========================================================
       LOAD USER DOCUMENTS
       ======================================================== */
    useEffect(() => {
        let isMounted = true

        async function loadDocuments() {
            try {
                setLoadingDocs(true)
                setDocError('')
                const data = await apiRequest('/documents/')
                if (isMounted) {
                    const docList = Array.isArray(data) ? data : (data.documents || [])
                    setDocuments(docList)
                    if (docList.length >= 2) {
                        setDocAId(docList[0].id)
                        setDocBId(docList[1].id)
                    } else if (docList.length === 1) {
                        setDocAId(docList[0].id)
                    }
                }
            } catch (err) {
                if (isMounted) {
                    setDocError(err.message || 'Failed to load documents.')
                }
            } finally {
                if (isMounted) setLoadingDocs(false)
            }
        }

        loadDocuments()
        return () => { isMounted = false }
    }, [])

    /* ========================================================
       OUTSIDE CLICK HANDLER FOR DROPDOWNS
       ======================================================== */
    useEffect(() => {
        function handleClickOutside(event) {
            if (dropdownARef.current && !dropdownARef.current.contains(event.target)) {
                setDropdownAOpen(false)
            }
            if (dropdownBRef.current && !dropdownBRef.current.contains(event.target)) {
                setDropdownBOpen(false)
            }
        }

        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    /* ========================================================
       STEP PROGRESS ANIMATION DURING COMPARISON
       ======================================================== */
    useEffect(() => {
        let interval = null
        if (isComparing) {
            interval = setInterval(() => {
                setCompareStep(prev => (prev < 4 ? prev + 1 : prev))
            }, 1800)
        }
        return () => {
            if (interval) clearInterval(interval)
        }
    }, [isComparing])

    /* ========================================================
       SWAP SELECTIONS
       ======================================================== */
    const handleSwap = () => {
        const temp = docAId
        setDocAId(docBId)
        setDocBId(temp)
    }

    /* ========================================================
       EXECUTE COMPARISON
       ======================================================== */
    const handleCompare = async () => {
        if (!docAId || !docBId) {
            setCompareError('Please select both Document A and Document B to compare.')
            return
        }
        if (docAId === docBId) {
            setCompareError('Cannot compare a document with itself. Please select two distinct documents.')
            return
        }

        try {
            setCompareStep(1)
            setIsComparing(true)
            setCompareError('')
            const result = await apiRequest('/documents/compare', {
                method: 'POST',
                body: JSON.stringify({
                    document_a_id: docAId,
                    document_b_id: docBId,
                    force_refresh: forceRefresh,
                }),
            })
            setComparisonResult(result)
            setActiveFilter('ALL')
        } catch (err) {
            setCompareError(err.message || 'Failed to compare documents.')
        } finally {
            setIsComparing(false)
        }
    }

    const docA = documents.find(d => d.id === docAId)
    const docB = documents.find(d => d.id === docBId)
    const isSameDoc = docAId && docBId && docAId === docBId

    const filteredDocsA = documents.filter(d =>
        (d.filename || '').toLowerCase().includes(searchA.toLowerCase())
    )
    const filteredDocsB = documents.filter(d =>
        (d.filename || '').toLowerCase().includes(searchB.toLowerCase())
    )

    /* ========================================================
       PREPARE FILTERED DIFFERENCE ITEMS
       ======================================================== */
    let displayedItems = []
    if (comparisonResult) {
        const term = itemSearch.trim().toLowerCase()

        const matchText = (text) => !term || (text || '').toLowerCase().includes(term)

        if (activeFilter === 'ALL' || activeFilter === 'MODIFIED') {
            (comparisonResult.modified || []).forEach(m => {
                if (matchText(m.title) || matchText(m.document_a_text) || matchText(m.document_b_text) || matchText(m.change_description)) {
                    displayedItems.push({ ...m, item_type: 'MODIFIED' })
                }
            })
        }
        if (activeFilter === 'ALL' || activeFilter === 'ADDED') {
            (comparisonResult.added || []).forEach(a => {
                if (matchText(a.title) || matchText(a.document_b_text) || matchText(a.category)) {
                    displayedItems.push({ ...a, item_type: 'ADDED' })
                }
            })
        }
        if (activeFilter === 'ALL' || activeFilter === 'REMOVED') {
            (comparisonResult.removed || []).forEach(r => {
                if (matchText(r.title) || matchText(r.document_a_text) || matchText(r.category)) {
                    displayedItems.push({ ...r, item_type: 'REMOVED' })
                }
            })
        }
        if (activeFilter === 'ALL' || activeFilter === 'SIMILAR') {
            (comparisonResult.similarities || []).forEach(s => {
                if (matchText(s.title) || matchText(s.excerpt) || matchText(s.category)) {
                    displayedItems.push({ ...s, item_type: 'SIMILAR' })
                }
            })
        }
    }

    const stats = comparisonResult?.statistics || { similar: 0, modified: 0, added: 0, removed: 0 }
    const totalChanges = (stats.modified || 0) + (stats.added || 0) + (stats.removed || 0)

    return (
        <div className="comparison-container">
            {/* --- Header --- */}
            <div className="comparison-header">
                <div className="comparison-header-content">
                    <h1>
                        <FileDiff size={28} style={{ color: 'var(--cyan-ink)' }} />
                        Document Comparison
                    </h1>
                    <p>
                        Perform deep semantic comparison between two documents. Detect added, removed, modified,
                        and identical sections with page citations and grounded local AI synthesis.
                    </p>
                </div>
                <div className="comparison-badges">
                    <span className="comparison-badge local-ai">
                        <Sparkles size={13} />
                        Llama 3.2 (Local AI)
                    </span>
                    <span className="comparison-badge">
                        <Layers size={13} />
                        MiniLM-L6-v2 Embeddings
                    </span>
                    <span className="comparison-badge">
                        <CheckCircle2 size={13} />
                        Zero Cloud Calls
                    </span>
                </div>
            </div>

            {/* --- Document Selector Card --- */}
            <div className="comparison-selector-card">
                {docError && (
                    <div className="error-notice" style={{ marginBottom: '16px' }}>
                        <AlertTriangle size={16} />
                        <span>{docError}</span>
                    </div>
                )}
                {loadingDocs ? (
                    <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                        <RotateCw size={18} className="animate-spin" style={{ display: 'inline', marginRight: '8px' }} />
                        Loading available documents from your library...
                    </div>
                ) : (
                <div className="selector-grid">
                    {/* Document A Selector */}
                    <div className="selector-pane" ref={dropdownARef}>
                        <div className="selector-label">
                            <span>Document A (Baseline / Reference)</span>
                            <span className="doc-tag">Left Document</span>
                        </div>

                        <div className="custom-doc-dropdown">
                            <button
                                type="button"
                                className={`dropdown-trigger ${dropdownAOpen ? 'open' : ''}`}
                                onClick={() => setDropdownAOpen(prev => !prev)}
                            >
                                {docA ? (
                                    <div className="selected-doc-display">
                                        <div className="doc-type-icon">
                                            {docA.is_handwritten ? <PenTool size={18} /> : <FileText size={18} />}
                                        </div>
                                        <div className="doc-details">
                                            <span className="doc-title">{docA.filename}</span>
                                            <span className="doc-subinfo">
                                                <span className={`doc-type-pill ${docA.is_handwritten ? 'ocr' : ''}`}>
                                                    {docA.is_handwritten ? 'Handwritten OCR' : (docA.document_type || 'DOC')}
                                                </span>
                                                {docA.page_count ? <span>{docA.page_count} pages</span> : null}
                                            </span>
                                        </div>
                                    </div>
                                ) : (
                                    <span className="placeholder-text">Select Document A...</span>
                                )}
                                <ChevronDown size={16} style={{ color: 'var(--text-muted)' }} />
                            </button>

                            {dropdownAOpen && (
                                <div className="dropdown-menu">
                                    <input
                                        type="text"
                                        className="dropdown-search"
                                        placeholder="Search documents..."
                                        value={searchA}
                                        onChange={e => setSearchA(e.target.value)}
                                        onClick={e => e.stopPropagation()}
                                        autoFocus
                                    />
                                    {filteredDocsA.map(doc => (
                                        <button
                                            key={doc.id}
                                            type="button"
                                            className={`dropdown-item ${doc.id === docAId ? 'selected' : ''}`}
                                            onClick={() => {
                                                setDocAId(doc.id)
                                                setDropdownAOpen(false)
                                            }}
                                        >
                                            <div className="selected-doc-display">
                                                <div className="doc-type-icon">
                                                    {doc.is_handwritten ? <PenTool size={16} /> : <FileText size={16} />}
                                                </div>
                                                <div className="doc-details">
                                                    <span className="doc-title">{doc.filename}</span>
                                                    <span className="doc-subinfo">
                                                        <span className={`doc-type-pill ${doc.is_handwritten ? 'ocr' : ''}`}>
                                                            {doc.is_handwritten ? 'Handwritten' : (doc.document_type || 'DOC')}
                                                        </span>
                                                        {doc.page_count ? <span>{doc.page_count}p</span> : null}
                                                    </span>
                                                </div>
                                            </div>
                                            {doc.id === docAId && <Check size={16} style={{ color: 'var(--accent)' }} />}
                                        </button>
                                    ))}
                                    {filteredDocsA.length === 0 && (
                                        <div style={{ padding: '12px', fontSize: '12px', color: 'var(--text-muted)', textAlign: 'center' }}>
                                            No matching documents found
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Swap Button */}
                    <div className="swap-button-wrapper">
                        <button
                            type="button"
                            className="swap-button"
                            onClick={handleSwap}
                            title="Swap Document A and Document B"
                            disabled={!docAId || !docBId || isComparing}
                        >
                            <ArrowLeftRight size={18} />
                        </button>
                    </div>

                    {/* Document B Selector */}
                    <div className="selector-pane" ref={dropdownBRef}>
                        <div className="selector-label">
                            <span>Document B (Comparison / Revised)</span>
                            <span className="doc-tag">Right Document</span>
                        </div>

                        <div className="custom-doc-dropdown">
                            <button
                                type="button"
                                className={`dropdown-trigger ${dropdownBOpen ? 'open' : ''}`}
                                onClick={() => setDropdownBOpen(prev => !prev)}
                            >
                                {docB ? (
                                    <div className="selected-doc-display">
                                        <div className="doc-type-icon">
                                            {docB.is_handwritten ? <PenTool size={18} /> : <FileText size={18} />}
                                        </div>
                                        <div className="doc-details">
                                            <span className="doc-title">{docB.filename}</span>
                                            <span className="doc-subinfo">
                                                <span className={`doc-type-pill ${docB.is_handwritten ? 'ocr' : ''}`}>
                                                    {docB.is_handwritten ? 'Handwritten OCR' : (docB.document_type || 'DOC')}
                                                </span>
                                                {docB.page_count ? <span>{docB.page_count} pages</span> : null}
                                            </span>
                                        </div>
                                    </div>
                                ) : (
                                    <span className="placeholder-text">Select Document B...</span>
                                )}
                                <ChevronDown size={16} style={{ color: 'var(--text-muted)' }} />
                            </button>

                            {dropdownBOpen && (
                                <div className="dropdown-menu">
                                    <input
                                        type="text"
                                        className="dropdown-search"
                                        placeholder="Search documents..."
                                        value={searchB}
                                        onChange={e => setSearchB(e.target.value)}
                                        onClick={e => e.stopPropagation()}
                                        autoFocus
                                    />
                                    {filteredDocsB.map(doc => (
                                        <button
                                            key={doc.id}
                                            type="button"
                                            className={`dropdown-item ${doc.id === docBId ? 'selected' : ''}`}
                                            onClick={() => {
                                                setDocBId(doc.id)
                                                setDropdownBOpen(false)
                                            }}
                                        >
                                            <div className="selected-doc-display">
                                                <div className="doc-type-icon">
                                                    {doc.is_handwritten ? <PenTool size={16} /> : <FileText size={16} />}
                                                </div>
                                                <div className="doc-details">
                                                    <span className="doc-title">{doc.filename}</span>
                                                    <span className="doc-subinfo">
                                                        <span className={`doc-type-pill ${doc.is_handwritten ? 'ocr' : ''}`}>
                                                            {doc.is_handwritten ? 'Handwritten' : (doc.document_type || 'DOC')}
                                                        </span>
                                                        {doc.page_count ? <span>{doc.page_count}p</span> : null}
                                                    </span>
                                                </div>
                                            </div>
                                            {doc.id === docBId && <Check size={16} style={{ color: 'var(--accent)' }} />}
                                        </button>
                                    ))}
                                    {filteredDocsB.length === 0 && (
                                        <div style={{ padding: '12px', fontSize: '12px', color: 'var(--text-muted)', textAlign: 'center' }}>
                                            No matching documents found
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
                )}

                {/* Validation Warnings */}
                {isSameDoc && (
                    <div className="validation-notice">
                        <AlertTriangle size={16} />
                        <span>Cannot compare a document with itself. Please select two distinct documents.</span>
                    </div>
                )}

                {compareError && (
                    <div className="error-notice">
                        <AlertTriangle size={16} />
                        <span>{compareError}</span>
                    </div>
                )}

                {/* Controls Bar */}
                <div className="selector-controls">
                    <div className="controls-left">
                        <label className="force-refresh-label">
                            <input
                                type="checkbox"
                                checked={forceRefresh}
                                onChange={e => setForceRefresh(e.target.checked)}
                            />
                            <span>Bypass cache (force fresh AI re-analysis)</span>
                        </label>
                    </div>

                    <button
                        type="button"
                        className="compare-action-btn"
                        onClick={handleCompare}
                        disabled={!docAId || !docBId || isSameDoc || isComparing}
                    >
                        {isComparing ? (
                            <>
                                <RotateCw size={16} className="animate-spin" />
                                <span>Comparing Documents...</span>
                            </>
                        ) : (
                            <>
                                <Sparkles size={16} />
                                <span>Compare Documents</span>
                            </>
                        )}
                    </button>
                </div>
            </div>

            {/* --- Stepper Progress Card (During Loading) --- */}
            {isComparing && (
                <div className="stepper-card">
                    <div className="stepper-header">
                        <h3>Running Semantic Document Comparison</h3>
                        <p>Processing text structures, calculating embedding vectors, and synthesizing changes locally.</p>
                    </div>

                    <div className="stepper-track">
                        <div className={`step-node ${compareStep === 1 ? 'active' : (compareStep > 1 ? 'done' : '')}`}>
                            <div className="step-icon-circle">
                                {compareStep > 1 ? <Check size={16} /> : 1}
                            </div>
                            <span className="step-label">Extracting Text</span>
                            <span className="step-desc">Loading paragraphs & pages</span>
                        </div>

                        <div className={`step-node ${compareStep === 2 ? 'active' : (compareStep > 2 ? 'done' : '')}`}>
                            <div className="step-icon-circle">
                                {compareStep > 2 ? <Check size={16} /> : 2}
                            </div>
                            <span className="step-label">Embedding Alignment</span>
                            <span className="step-desc">MiniLM bipartite cosine match</span>
                        </div>

                        <div className={`step-node ${compareStep === 3 ? 'active' : (compareStep > 3 ? 'done' : '')}`}>
                            <div className="step-icon-circle">
                                {compareStep > 3 ? <Check size={16} /> : 3}
                            </div>
                            <span className="step-label">Change Classification</span>
                            <span className="step-desc">Detecting additions & diffs</span>
                        </div>

                        <div className={`step-node ${compareStep === 4 ? 'active' : ''}`}>
                            <div className="step-icon-circle">
                                4
                            </div>
                            <span className="step-label">AI Synthesis</span>
                            <span className="step-desc">Grounded Ollama Llama 3.2</span>
                        </div>
                    </div>
                </div>
            )}

            {/* --- Comparison Results Section --- */}
            {comparisonResult && !isComparing && (
                <div className="comparison-results-view">
                    {/* Metrics Bar */}
                    <div className="overview-stats-grid">
                        <div className="stat-metric-card similar">
                            <div className="stat-icon-wrap">
                                <CheckCircle2 size={22} />
                            </div>
                            <div className="stat-info">
                                <span className="stat-number">{stats.similar || 0}</span>
                                <span className="stat-name">Similar / Unchanged</span>
                            </div>
                        </div>

                        <div className="stat-metric-card modified">
                            <div className="stat-icon-wrap">
                                <FileDiff size={22} />
                            </div>
                            <div className="stat-info">
                                <span className="stat-number">{stats.modified || 0}</span>
                                <span className="stat-name">Modified Sections</span>
                            </div>
                        </div>

                        <div className="stat-metric-card added">
                            <div className="stat-icon-wrap">
                                <Sparkles size={22} />
                            </div>
                            <div className="stat-info">
                                <span className="stat-number">{stats.added || 0}</span>
                                <span className="stat-name">Added to Doc B</span>
                            </div>
                        </div>

                        <div className="stat-metric-card removed">
                            <div className="stat-icon-wrap">
                                <AlertTriangle size={22} />
                            </div>
                            <div className="stat-info">
                                <span className="stat-number">{stats.removed || 0}</span>
                                <span className="stat-name">Removed from Doc A</span>
                            </div>
                        </div>
                    </div>

                    {/* AI Executive Summary Card */}
                    {(comparisonResult.summary || comparisonResult.ai_summary) && (
                        <div className="ai-summary-card">
                            <div className="ai-summary-header">
                                <div className="ai-summary-title">
                                    <Sparkles size={20} style={{ color: 'var(--violet-ink)' }} />
                                    <span>AI Comparison Synthesis & Analysis</span>
                                </div>
                                <span className="ai-badge">
                                    Local LLM (Llama 3.2)
                                </span>
                            </div>

                            <p className="ai-summary-prose">
                                {comparisonResult.summary || comparisonResult.ai_summary?.summary}
                            </p>

                            <div className="ai-insights-grid">
                                <div className="insight-block">
                                    <div className="insight-block-header">
                                        <FileDiff size={15} style={{ color: '#f59e0b' }} />
                                        <span>Key Changes</span>
                                    </div>
                                    <ul className="insight-list">
                                        {(comparisonResult.key_changes || comparisonResult.ai_summary?.key_changes || []).map((ch, idx) => (
                                            <li key={idx}>{ch}</li>
                                        ))}
                                        {(!(comparisonResult.key_changes || comparisonResult.ai_summary?.key_changes)?.length) && (
                                            <li style={{ color: 'var(--text-muted)' }}>No major rewrites detected.</li>
                                        )}
                                    </ul>
                                </div>

                                <div className="insight-block">
                                    <div className="insight-block-header">
                                        <Sparkles size={15} style={{ color: '#0ea5e9' }} />
                                        <span>Important Additions</span>
                                    </div>
                                    <ul className="insight-list">
                                        {(comparisonResult.important_additions || comparisonResult.ai_summary?.important_additions || []).map((ad, idx) => (
                                            <li key={idx}>{ad}</li>
                                        ))}
                                        {(!(comparisonResult.important_additions || comparisonResult.ai_summary?.important_additions)?.length) && (
                                            <li style={{ color: 'var(--text-muted)' }}>No new sections added.</li>
                                        )}
                                    </ul>
                                </div>

                                <div className="insight-block">
                                    <div className="insight-block-header">
                                        <BookOpen size={15} style={{ color: '#10b981' }} />
                                        <span>Implications & Takeaway</span>
                                    </div>
                                    <p style={{ margin: 0, fontSize: '12.5px', lineHeight: 1.5, color: 'var(--text-secondary)' }}>
                                        {comparisonResult.implications || comparisonResult.ai_summary?.implications || 'Content aligns consistently across both documents.'}
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Filter Pills & Search */}
                    <div className="comparison-filter-bar">
                        <div className="filter-pills">
                            <button
                                type="button"
                                className={`filter-pill ${activeFilter === 'ALL' ? 'active' : ''}`}
                                onClick={() => setActiveFilter('ALL')}
                            >
                                All Changes ({totalChanges})
                            </button>
                            <button
                                type="button"
                                className={`filter-pill ${activeFilter === 'MODIFIED' ? 'active' : ''}`}
                                onClick={() => setActiveFilter('MODIFIED')}
                            >
                                Modified ({stats.modified || 0})
                            </button>
                            <button
                                type="button"
                                className={`filter-pill ${activeFilter === 'ADDED' ? 'active' : ''}`}
                                onClick={() => setActiveFilter('ADDED')}
                            >
                                Added ({stats.added || 0})
                            </button>
                            <button
                                type="button"
                                className={`filter-pill ${activeFilter === 'REMOVED' ? 'active' : ''}`}
                                onClick={() => setActiveFilter('REMOVED')}
                            >
                                Removed ({stats.removed || 0})
                            </button>
                            <button
                                type="button"
                                className={`filter-pill ${activeFilter === 'SIMILAR' ? 'active' : ''}`}
                                onClick={() => setActiveFilter('SIMILAR')}
                            >
                                Similar / Unchanged ({stats.similar || 0})
                            </button>
                        </div>

                        <div className="search-input-wrapper">
                            <Search size={15} className="search-icon" />
                            <input
                                type="text"
                                placeholder="Filter differences by keyword..."
                                value={itemSearch}
                                onChange={e => setItemSearch(e.target.value)}
                            />
                        </div>
                    </div>

                    {/* Differences Content List */}
                    <div className="differences-list">
                        {displayedItems.map((item, idx) => {
                            if (item.item_type === 'MODIFIED') {
                                return (
                                    <div key={item.id || idx} className="difference-card">
                                        <div className="card-top-bar">
                                            <div className="card-title-group">
                                                <span className="card-topic-title">{item.title}</span>
                                                {item.category && <span className="card-category-pill">{item.category}</span>}
                                            </div>
                                            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                                                {item.similarity_score ? (
                                                    <span className="doc-type-pill">
                                                        {Math.round(item.similarity_score * 100)}% Match
                                                    </span>
                                                ) : null}
                                                <span className="type-status-badge modified">Modified</span>
                                            </div>
                                        </div>

                                        {item.change_description && (
                                            <div className="change-reason-banner">
                                                <Info size={14} />
                                                <span>{item.change_description}</span>
                                            </div>
                                        )}

                                        <div className="modified-side-by-side">
                                            <div className="diff-box doc-a">
                                                <div className="diff-box-header">
                                                    <span>{comparisonResult.document_a?.filename || 'Document A'}</span>
                                                    <span className="page-chip">Page {item.document_a_page || 1}</span>
                                                </div>
                                                <div className="diff-text">{item.document_a_text}</div>
                                            </div>

                                            <div className="diff-box doc-b">
                                                <div className="diff-box-header">
                                                    <span>{comparisonResult.document_b?.filename || 'Document B'}</span>
                                                    <span className="page-chip">Page {item.document_b_page || 1}</span>
                                                </div>
                                                <div className="diff-text">{item.document_b_text}</div>
                                            </div>
                                        </div>
                                    </div>
                                )
                            }

                            if (item.item_type === 'ADDED') {
                                return (
                                    <div key={item.id || idx} className="difference-card">
                                        <div className="card-top-bar">
                                            <div className="card-title-group">
                                                <span className="card-topic-title">{item.title}</span>
                                                {item.category && <span className="card-category-pill">{item.category}</span>}
                                            </div>
                                            <span className="type-status-badge added">Added in Doc B</span>
                                        </div>

                                        <div className="snippet-single-box added-border">
                                            <div className="diff-box-header">
                                                <span>Introduced in {comparisonResult.document_b?.filename || 'Document B'}</span>
                                                <span className="page-chip">Page {item.document_b_page || 1}</span>
                                            </div>
                                            <div className="diff-text">{item.document_b_text}</div>
                                        </div>
                                    </div>
                                )
                            }

                            if (item.item_type === 'REMOVED') {
                                return (
                                    <div key={item.id || idx} className="difference-card">
                                        <div className="card-top-bar">
                                            <div className="card-title-group">
                                                <span className="card-topic-title">{item.title}</span>
                                                {item.category && <span className="card-category-pill">{item.category}</span>}
                                            </div>
                                            <span className="type-status-badge removed">Removed from Doc A</span>
                                        </div>

                                        <div className="snippet-single-box removed-border">
                                            <div className="diff-box-header">
                                                <span>Present only in {comparisonResult.document_a?.filename || 'Document A'}</span>
                                                <span className="page-chip">Page {item.document_a_page || 1}</span>
                                            </div>
                                            <div className="diff-text">{item.document_a_text}</div>
                                        </div>
                                    </div>
                                )
                            }

                            if (item.item_type === 'SIMILAR') {
                                return (
                                    <div key={item.id || idx} className="difference-card">
                                        <div className="card-top-bar">
                                            <div className="card-title-group">
                                                <span className="card-topic-title">{item.title}</span>
                                                {item.category && <span className="card-category-pill">{item.category}</span>}
                                            </div>
                                            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                                                {item.similarity_score ? (
                                                    <span className="doc-type-pill">
                                                        {Math.round(item.similarity_score * 100)}% Equivalent
                                                    </span>
                                                ) : null}
                                                <span className="type-status-badge similar">Unchanged</span>
                                            </div>
                                        </div>

                                        <div className="snippet-single-box similar-border">
                                            <div className="diff-box-header">
                                                <span>Content identical or preserved across both documents</span>
                                                <div style={{ display: 'flex', gap: '6px' }}>
                                                    <span className="page-chip">Doc A: p.{item.document_a_page || 1}</span>
                                                    <span className="page-chip">Doc B: p.{item.document_b_page || 1}</span>
                                                </div>
                                            </div>
                                            <div className="diff-text">{item.excerpt}</div>
                                        </div>
                                    </div>
                                )
                            }

                            return null
                        })}

                        {displayedItems.length === 0 && (
                            <div className="no-items-state">
                                No comparison items match the selected filter.
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}
