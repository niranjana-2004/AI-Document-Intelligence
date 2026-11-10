import { useState, useEffect, useLayoutEffect, useRef, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
    Network,
    Sparkles,
    CheckCircle2,
    Layers,
    Search,
    Plus,
    Minus,
    Maximize2,
    RotateCcw,
    ChevronDown,
    Check,
    FileText,
    PenTool,
    RotateCw,
    X,
    ExternalLink,
    AlertTriangle,
} from 'lucide-react'
import { apiRequest } from '../services/api'
import {
    computeMindMapLayout,
    computeScrollLayout,
    computeFitScroll,
    computeResetScroll,
    MIN_ZOOM,
    MAX_ZOOM,
} from '../utils/mindMapLayout'
import '../styles/mind-map.css'

export default function MindMap() {
    const navigate = useNavigate()

    // Document selection
    const [documents, setDocuments] = useState([])
    const [loadingDocs, setLoadingDocs] = useState(true)
    const [docError, setDocError] = useState('')
    const [selectedDocId, setSelectedDocId] = useState(null)
    const [dropdownOpen, setDropdownOpen] = useState(false)
    const [docSearch, setDocSearch] = useState('')
    const [forceRefresh, setForceRefresh] = useState(false)

    // Generation state
    const [isGenerating, setIsGenerating] = useState(false)
    const [generationStep, setGenerationStep] = useState(1)
    const [mindMapData, setMindMapData] = useState(null)
    const [errorMsg, setErrorMsg] = useState('')

    // Zoom, collapse, and scroll viewport sizing state
    const [graphState, setGraphState] = useState(() => ({
        zoom: 1.0,
        collapsedIds: new Set(),
    }))
    const [viewportSize, setViewportSize] = useState({ width: 1000, height: 640 })
    const [isDragging, setIsDragging] = useState(false)
    const [dragStart, setDragStart] = useState({ clientX: 0, clientY: 0, scrollLeft: 0, scrollTop: 0 })

    // Node state
    const [selectedNode, setSelectedNode] = useState(null)
    const [searchTerm, setSearchTerm] = useState('')
    const [typeFilter, setTypeFilter] = useState('ALL') // 'ALL' | 'TOPIC' | 'CONCEPT' | 'PROCESS' | 'DEFINITION' | 'EXAMPLE'

    const dropdownRef = useRef(null)
    const viewportRef = useRef(null)
    const shouldAutoFitRef = useRef(false)
    const pendingScrollRef = useRef(null)

    /* ========================================================
       LAYOUT TREE COMPUTATION & DYNAMIC SCROLL CONTENT DIMENSIONS
       ======================================================== */
    const layout = useMemo(
        () => computeMindMapLayout(mindMapData, graphState.collapsedIds),
        [mindMapData, graphState.collapsedIds]
    )

    const scrollContent = useMemo(
        () => computeScrollLayout(layout.bounds, graphState.zoom, viewportSize.width, viewportSize.height),
        [layout.bounds, graphState.zoom, viewportSize.width, viewportSize.height]
    )

    const fitToScreen = useCallback(
        ({ enforceReadableMobileFloor = false } = {}) => {
            const el = viewportRef.current
            if (!el || !layout.bounds || layout.bounds.width <= 0) return
            const vw = el.clientWidth || viewportSize.width
            const vh = el.clientHeight || viewportSize.height
            const { zoom, scrollLeft, scrollTop } = computeFitScroll(layout, vw, vh, {
                enforceReadableMobileFloor,
            })
            pendingScrollRef.current = { left: scrollLeft, top: scrollTop }
            setGraphState(prev => ({ ...prev, zoom }))
        },
        [layout, viewportSize.width, viewportSize.height]
    )

    /* ========================================================
       SYNCHRONOUS SCROLL RESTORE AFTER SCROLL CONTENT RESIZES
       ======================================================== */
    useLayoutEffect(() => {
        const el = viewportRef.current
        const pending = pendingScrollRef.current
        if (!el || !pending) return
        pendingScrollRef.current = null
        el.scrollLeft = Math.max(0, Math.round(pending.left))
        el.scrollTop = Math.max(0, Math.round(pending.top))
    }, [scrollContent.width, scrollContent.height, graphState.zoom, mindMapData, layout.bounds])

    /* ========================================================
       LOAD USER DOCUMENTS
       ======================================================== */
    useEffect(() => {
        let isMounted = true

        async function fetchDocs() {
            try {
                setLoadingDocs(true)
                setDocError('')
                const data = await apiRequest('/documents/')
                if (isMounted) {
                    const list = Array.isArray(data) ? data : (data.documents || [])
                    setDocuments(list)
                    if (list.length > 0) {
                        setSelectedDocId(list[0].id)
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

        fetchDocs()
        return () => { isMounted = false }
    }, [])

    /* ========================================================
       OUTSIDE CLICK HANDLER FOR DROPDOWN
       ======================================================== */
    useEffect(() => {
        function handleClickOutside(e) {
            if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
                setDropdownOpen(false)
            }
        }
        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    /* ========================================================
       ANIMATED STEPPING DURING GENERATION
       ======================================================== */
    useEffect(() => {
        let interval = null
        if (isGenerating) {
            interval = setInterval(() => {
                setGenerationStep(prev => (prev < 5 ? prev + 1 : prev))
            }, 2000)
        }
        return () => {
            if (interval) clearInterval(interval)
        }
    }, [isGenerating])

    /* ========================================================
       VIEWPORT SIZE OBSERVER & AUTO-FIT ON INITIAL GENERATION
       ======================================================== */
    useEffect(() => {
        const el = viewportRef.current
        if (!el || !mindMapData || isGenerating || typeof ResizeObserver === 'undefined') return

        const updateSize = () => {
            const w = el.clientWidth
            const h = el.clientHeight
            if (w > 0 && h > 0) {
                setViewportSize(prev => (prev.width === w && prev.height === h ? prev : { width: w, height: h }))
            }
        }

        const rafId = requestAnimationFrame(updateSize)
        const observer = new ResizeObserver(updateSize)
        observer.observe(el)
        return () => {
            cancelAnimationFrame(rafId)
            observer.disconnect()
        }
    }, [mindMapData, isGenerating])

    useEffect(() => {
        if (!mindMapData || isGenerating || !shouldAutoFitRef.current) return
        const rafId = requestAnimationFrame(() => {
            const el = viewportRef.current
            if (shouldAutoFitRef.current && el) {
                shouldAutoFitRef.current = false
                const vw = el.clientWidth || 1000
                const vh = el.clientHeight || 640
                setViewportSize({ width: vw, height: vh })
                const { zoom, scrollLeft, scrollTop } = computeFitScroll(layout, vw, vh, {
                    enforceReadableMobileFloor: true,
                })
                pendingScrollRef.current = { left: scrollLeft, top: scrollTop }
                setGraphState(prev => ({ ...prev, zoom }))
            }
        })
        return () => cancelAnimationFrame(rafId)
    }, [mindMapData, isGenerating, layout])

    /* ========================================================
       POINTER-ANCHORED ZOOM (BUTTONS & CTRL/CMD+WHEEL PINCH)
       ======================================================== */
    const zoomAtViewportPoint = useCallback((delta, anchorX, anchorY) => {
        const el = viewportRef.current
        if (!el || !layout.bounds || layout.bounds.width <= 0) return

        const vw = el.clientWidth || viewportSize.width
        const vh = el.clientHeight || viewportSize.height
        const curScrollLeft = pendingScrollRef.current ? pendingScrollRef.current.left : el.scrollLeft
        const curScrollTop = pendingScrollRef.current ? pendingScrollRef.current.top : el.scrollTop

        setGraphState(prev => {
            const nextZoom = Math.min(
                Math.max(MIN_ZOOM, Number((prev.zoom + delta).toFixed(3))),
                MAX_ZOOM
            )
            if (nextZoom === prev.zoom) return prev

            const oldScroll = computeScrollLayout(layout.bounds, prev.zoom, vw, vh)
            const newScroll = computeScrollLayout(layout.bounds, nextZoom, vw, vh)

            const gx = (curScrollLeft + anchorX - oldScroll.offsetX) / prev.zoom
            const gy = (curScrollTop + anchorY - oldScroll.offsetY) / prev.zoom

            pendingScrollRef.current = {
                left: gx * nextZoom + newScroll.offsetX - anchorX,
                top: gy * nextZoom + newScroll.offsetY - anchorY,
            }
            return { ...prev, zoom: nextZoom }
        })
    }, [layout.bounds, viewportSize.width, viewportSize.height])

    useEffect(() => {
        const el = viewportRef.current
        if (!el || !mindMapData || isGenerating) return

        const onWheel = (e) => {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault()
                const rect = el.getBoundingClientRect()
                const anchorX = e.clientX - rect.left
                const anchorY = e.clientY - rect.top
                const zoomDelta = e.deltaY > 0 ? -0.1 : 0.1
                zoomAtViewportPoint(zoomDelta, anchorX, anchorY)
            }
        }

        el.addEventListener('wheel', onWheel, { passive: false })
        return () => el.removeEventListener('wheel', onWheel)
    }, [mindMapData, isGenerating, zoomAtViewportPoint])

    /* ========================================================
       GENERATE MIND MAP ACTION
       ======================================================== */
    const handleGenerate = async () => {
        if (!selectedDocId) {
            setErrorMsg('Please select a document to generate a mind map.')
            return
        }

        try {
            setGenerationStep(1)
            setIsGenerating(true)
            setErrorMsg('')
            setSelectedNode(null)
            setGraphState(prev => ({ ...prev, collapsedIds: new Set() }))

            const result = await apiRequest(`/documents/${selectedDocId}/mind-map`, {
                method: 'POST',
                body: JSON.stringify({ force_refresh: forceRefresh }),
            })

            shouldAutoFitRef.current = true
            setMindMapData(result)
        } catch (err) {
            setErrorMsg(err.message || 'Failed to generate mind map.')
        } finally {
            setIsGenerating(false)
        }
    }

    /* ========================================================
       COLLAPSE / EXPAND TOGGLE (RECALCULATES SCROLL BOUNDS & PINS NODE)
       ======================================================== */
    const toggleCollapse = (nodeId, e) => {
        e.stopPropagation()
        const el = viewportRef.current
        const vw = el?.clientWidth || viewportSize.width
        const vh = el?.clientHeight || viewportSize.height
        const curScrollLeft = el ? (pendingScrollRef.current ? pendingScrollRef.current.left : el.scrollLeft) : 0
        const curScrollTop = el ? (pendingScrollRef.current ? pendingScrollRef.current.top : el.scrollTop) : 0

        setGraphState(prev => {
            const oldLayout = computeMindMapLayout(mindMapData, prev.collapsedIds)
            const oldNode = oldLayout.nodes.find(n => n.id === nodeId)
            const oldScroll = computeScrollLayout(oldLayout.bounds, prev.zoom, vw, vh)

            const nextSet = new Set(prev.collapsedIds)
            if (nextSet.has(nodeId)) {
                nextSet.delete(nodeId)
            } else {
                nextSet.add(nodeId)
            }

            const nextLayout = computeMindMapLayout(mindMapData, nextSet)
            const newNode = nextLayout.nodes.find(n => n.id === nodeId)
            const newScroll = computeScrollLayout(nextLayout.bounds, prev.zoom, vw, vh)

            if (oldNode && newNode && el) {
                const screenX = oldNode.x * prev.zoom + oldScroll.offsetX - curScrollLeft
                const screenY = oldNode.y * prev.zoom + oldScroll.offsetY - curScrollTop
                const maxScrollX = Math.max(0, newScroll.width - vw)
                const maxScrollY = Math.max(0, newScroll.height - vh)
                pendingScrollRef.current = {
                    left: Math.min(maxScrollX, Math.max(0, Math.round(newNode.x * prev.zoom + newScroll.offsetX - screenX))),
                    top: Math.min(maxScrollY, Math.max(0, Math.round(newNode.y * prev.zoom + newScroll.offsetY - screenY))),
                }
            }

            return { ...prev, collapsedIds: nextSet }
        })
    }

    /* ========================================================
       DRAG-TO-PAN OVER NATIVE SCROLLBAR COEXISTENCE
       ======================================================== */
    const handleMouseDown = (e) => {
        if (e.button !== 0) return
        if (
            e.target.closest('.mindmap-node') ||
            e.target.closest('.node-collapse-toggle') ||
            e.target.closest('.node-details-drawer')
        ) {
            return
        }
        const el = viewportRef.current
        if (!el) return
        const rect = el.getBoundingClientRect()
        if (e.clientX - rect.left >= el.clientWidth || e.clientY - rect.top >= el.clientHeight) {
            return
        }
        setIsDragging(true)
        setDragStart({
            clientX: e.clientX,
            clientY: e.clientY,
            scrollLeft: el.scrollLeft,
            scrollTop: el.scrollTop,
        })
    }

    const handleMouseMove = useCallback((e) => {
        if (!isDragging) return
        const el = viewportRef.current
        if (!el) return
        el.scrollLeft = dragStart.scrollLeft - (e.clientX - dragStart.clientX)
        el.scrollTop = dragStart.scrollTop - (e.clientY - dragStart.clientY)
    }, [isDragging, dragStart])

    const handleMouseUp = () => {
        setIsDragging(false)
    }

    const zoomBy = useCallback((delta) => {
        const el = viewportRef.current
        const vw = el?.clientWidth || viewportSize.width
        const vh = el?.clientHeight || viewportSize.height
        zoomAtViewportPoint(delta, vw / 2, vh / 2)
    }, [zoomAtViewportPoint, viewportSize.width, viewportSize.height])

    const resetView = useCallback(() => {
        const el = viewportRef.current
        const vw = el?.clientWidth || viewportSize.width
        const vh = el?.clientHeight || viewportSize.height
        const { zoom, scrollLeft, scrollTop } = computeResetScroll(layout, vw, vh)
        pendingScrollRef.current = { left: scrollLeft, top: scrollTop }
        setGraphState(prev => ({ ...prev, zoom }))
    }, [layout, viewportSize.width, viewportSize.height])

    /* ========================================================
       NAVIGATE TO SOURCE DOCUMENT / PAGE
       ======================================================== */
    const handleOpenSource = (pageNumber) => {
        if (!selectedDoc) return
        if (selectedDoc.is_handwritten) {
            navigate(`/handwritten/${selectedDoc.id}?page=${pageNumber || 1}`)
        } else {
            navigate('/documents')
        }
    }

    const selectedDoc = documents.find(d => d.id === selectedDocId)
    const filteredDocs = documents.filter(d =>
        (d.filename || '').toLowerCase().includes(docSearch.toLowerCase())
    )

    // Search query & type filter matching
    const searchClean = searchTerm.trim().toLowerCase()
    const isNodeMatched = (node) => {
        if (!searchClean) return false
        return (
            (node.label || '').toLowerCase().includes(searchClean) ||
            (node.description || '').toLowerCase().includes(searchClean)
        )
    }

    const isNodeVisibleByType = (node) => {
        if (typeFilter === 'ALL' || node.type === 'root') return true
        return (node.type || '').toUpperCase() === typeFilter
    }

    return (
        <div className="mindmap-container">
            {/* --- Header --- */}
            <div className="mindmap-header">
                <div className="mindmap-header-content">
                    <h1>
                        <Network size={28} style={{ color: 'var(--violet-ink)' }} />
                        AI Mind Map Generator
                    </h1>
                    <p>
                        Transform any document into an interactive, source-grounded visual knowledge structure.
                        Explore hierarchies, semantic relationships, and trace every concept back to exact document pages.
                    </p>
                </div>
                <div className="mindmap-badges">
                    <span className="mindmap-badge local-ai">
                        <Sparkles size={13} />
                        Llama 3.2 (Local AI)
                    </span>
                    <span className="mindmap-badge">
                        <Layers size={13} />
                        Source-Grounded Citations
                    </span>
                    <span className="mindmap-badge">
                        <CheckCircle2 size={13} />
                        Zero Cloud Calls
                    </span>
                </div>
            </div>

            {/* --- Document Selector Card --- */}
            <div className="mindmap-selector-card">
                {docError && (
                    <div className="error-notice" style={{ margin: 0 }}>
                        <AlertTriangle size={16} />
                        <span>{docError}</span>
                    </div>
                )}

                <div className="selector-row">
                    <div className="selector-dropdown-wrap" ref={dropdownRef}>
                        <button
                            type="button"
                            className={`dropdown-trigger ${dropdownOpen ? 'open' : ''}`}
                            onClick={() => setDropdownOpen(prev => !prev)}
                        >
                            {selectedDoc ? (
                                <div className="selected-doc-display">
                                    <div className="doc-type-icon">
                                        {selectedDoc.is_handwritten ? <PenTool size={18} /> : <FileText size={18} />}
                                    </div>
                                    <div className="doc-details">
                                        <span className="doc-title">{selectedDoc.filename}</span>
                                        <span className="doc-subinfo">
                                            <span className={`doc-type-pill ${selectedDoc.is_handwritten ? 'ocr' : ''}`}>
                                                {selectedDoc.is_handwritten ? 'Handwritten OCR' : (selectedDoc.document_type || 'DOC')}
                                            </span>
                                            {selectedDoc.text_length ? (
                                                <span>{selectedDoc.text_length.toLocaleString()} chars</span>
                                            ) : null}
                                        </span>
                                    </div>
                                </div>
                            ) : (
                                <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                                    {loadingDocs ? 'Loading documents...' : 'Select a document...'}
                                </span>
                            )}
                            <ChevronDown size={16} style={{ color: 'var(--text-muted)' }} />
                        </button>

                        {dropdownOpen && (
                            <div className="dropdown-menu">
                                <input
                                    type="text"
                                    className="dropdown-search"
                                    placeholder="Search documents..."
                                    value={docSearch}
                                    onChange={e => setDocSearch(e.target.value)}
                                    onClick={e => e.stopPropagation()}
                                    autoFocus
                                />
                                {filteredDocs.map(doc => (
                                    <button
                                        key={doc.id}
                                        type="button"
                                        className={`dropdown-item ${doc.id === selectedDocId ? 'selected' : ''}`}
                                        onClick={() => {
                                            setSelectedDocId(doc.id)
                                            setDropdownOpen(false)
                                        }}
                                    >
                                        <div className="selected-doc-display">
                                            <div className="doc-type-icon">
                                                {doc.is_handwritten ? <PenTool size={15} /> : <FileText size={15} />}
                                            </div>
                                            <div className="doc-details">
                                                <span className="doc-title">{doc.filename}</span>
                                                <span className="doc-subinfo">
                                                    <span className={`doc-type-pill ${doc.is_handwritten ? 'ocr' : ''}`}>
                                                        {doc.is_handwritten ? 'Handwritten' : (doc.document_type || 'DOC')}
                                                    </span>
                                                </span>
                                            </div>
                                        </div>
                                        {doc.id === selectedDocId && <Check size={16} style={{ color: 'var(--accent)' }} />}
                                    </button>
                                ))}
                                {filteredDocs.length === 0 && (
                                    <div style={{ padding: '12px', fontSize: '12px', color: 'var(--text-muted)', textAlign: 'center' }}>
                                        No matching documents found
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    <button
                        type="button"
                        className="generate-mindmap-btn"
                        onClick={handleGenerate}
                        disabled={!selectedDocId || isGenerating}
                    >
                        {isGenerating ? (
                            <>
                                <RotateCw size={16} className="animate-spin" />
                                <span>Generating Knowledge Map...</span>
                            </>
                        ) : (
                            <>
                                <Sparkles size={16} />
                                <span>Generate Mind Map</span>
                            </>
                        )}
                    </button>
                </div>

                <div className="selector-subcontrols">
                    <label className="force-refresh-label">
                        <input
                            type="checkbox"
                            checked={forceRefresh}
                            onChange={e => setForceRefresh(e.target.checked)}
                        />
                        <span>Bypass cache (force fresh AI re-generation)</span>
                    </label>

                    {mindMapData && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>
                            <span>Total Nodes: <strong style={{ color: 'var(--text-primary)' }}>{mindMapData.node_count}</strong></span>
                            <span>•</span>
                            <span>Engine: <strong style={{ color: 'var(--violet-ink)' }}>{mindMapData.generation_method === 'ollama_llama3_2' ? 'Ollama Llama 3.2' : 'Deterministic Semantic Engine'}</strong></span>
                            {mindMapData.cached && (
                                <>
                                    <span>•</span>
                                    <span style={{ color: 'var(--success-ink)', fontWeight: 600 }}>(Cached)</span>
                                </>
                            )}
                        </div>
                    )}
                </div>

                {errorMsg && (
                    <div className="error-notice">
                        <AlertTriangle size={16} />
                        <span>{errorMsg}</span>
                    </div>
                )}
            </div>

            {/* --- Progress Stepper Card (During Generation) --- */}
            {isGenerating && (
                <div className="mindmap-stepper-card">
                    <div className="stepper-header">
                        <h3>Constructing Knowledge Graph</h3>
                        <p>Extracting key concepts, clustering topics, and mapping relationships locally.</p>
                    </div>

                    <div className="stepper-track-5">
                        <div className={`step-node ${generationStep === 1 ? 'active' : (generationStep > 1 ? 'done' : '')}`}>
                            <div className="step-icon-circle">
                                {generationStep > 1 ? <Check size={15} /> : 1}
                            </div>
                            <span className="step-label">Extract Concepts</span>
                            <span className="step-desc">Academic terms & quotes</span>
                        </div>

                        <div className={`step-node ${generationStep === 2 ? 'active' : (generationStep > 2 ? 'done' : '')}`}>
                            <div className="step-icon-circle">
                                {generationStep > 2 ? <Check size={15} /> : 2}
                            </div>
                            <span className="step-label">Topic Grouping</span>
                            <span className="step-desc">Domain clustering</span>
                        </div>

                        <div className={`step-node ${generationStep === 3 ? 'active' : (generationStep > 3 ? 'done' : '')}`}>
                            <div className="step-icon-circle">
                                {generationStep > 3 ? <Check size={15} /> : 3}
                            </div>
                            <span className="step-label">Build Hierarchy</span>
                            <span className="step-desc">Root & subtopic tree</span>
                        </div>

                        <div className={`step-node ${generationStep === 4 ? 'active' : (generationStep > 4 ? 'done' : '')}`}>
                            <div className="step-icon-circle">
                                {generationStep > 4 ? <Check size={15} /> : 4}
                            </div>
                            <span className="step-label">Link Citations</span>
                            <span className="step-desc">Page numbers & quotes</span>
                        </div>

                        <div className={`step-node ${generationStep === 5 ? 'active' : ''}`}>
                            <div className="step-icon-circle">
                                5
                            </div>
                            <span className="step-label">Render Map</span>
                            <span className="step-desc">Interactive canvas</span>
                        </div>
                    </div>
                </div>
            )}

            {/* --- Mind Map Workspace --- */}
            {mindMapData && !isGenerating && (
                <div className="mindmap-workspace">
                    {/* Toolbar */}
                    <div className="mindmap-toolbar">
                        <div className="toolbar-left">
                            <div className="mindmap-search-wrap">
                                <Search size={14} className="search-icon-pos" aria-hidden="true" />
                                <input
                                    type="text"
                                    placeholder="Search concepts..."
                                    aria-label="Search concepts in mind map"
                                    value={searchTerm}
                                    onChange={e => setSearchTerm(e.target.value)}
                                />
                                {searchTerm && (
                                    <button
                                        type="button"
                                        className="mindmap-search-clear"
                                        onClick={() => setSearchTerm('')}
                                        title="Clear concept search"
                                        aria-label="Clear concept search"
                                    >
                                        <X size={13} />
                                    </button>
                                )}
                            </div>

                            <div className="type-filter-group">
                                {['ALL', 'TOPIC', 'CONCEPT', 'PROCESS', 'DEFINITION'].map(type => (
                                    <button
                                        key={type}
                                        type="button"
                                        className={`type-filter-btn ${typeFilter === type ? 'active' : ''}`}
                                        onClick={() => setTypeFilter(type)}
                                    >
                                        {type.charAt(0) + type.slice(1).toLowerCase()}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="toolbar-right">
                            <button
                                type="button"
                                className="canvas-tool-btn"
                                onClick={() => zoomBy(0.15)}
                                title="Zoom In (Ctrl + Scroll)"
                                aria-label="Zoom In"
                            >
                                <Plus size={16} />
                            </button>
                            <span className="zoom-level-indicator">{Math.round(graphState.zoom * 100)}%</span>
                            <button
                                type="button"
                                className="canvas-tool-btn"
                                onClick={() => zoomBy(-0.15)}
                                title="Zoom Out (Ctrl + Scroll)"
                                aria-label="Zoom Out"
                            >
                                <Minus size={16} />
                            </button>
                            <button
                                type="button"
                                className="canvas-tool-btn fit-screen-btn"
                                onClick={() => fitToScreen({ enforceReadableMobileFloor: false })}
                                title="Fit complete mind map to screen"
                                aria-label="Fit to Screen"
                            >
                                <Maximize2 size={14} />
                                <span>Fit to Screen</span>
                            </button>
                            <button
                                type="button"
                                className="canvas-tool-btn"
                                onClick={resetView}
                                title="Reset View (100% centered on root)"
                                aria-label="Reset View"
                            >
                                <RotateCcw size={15} />
                            </button>
                        </div>
                    </div>

                    {/* Interactive Canvas Container & Scrollable Viewport */}
                    <div className="mindmap-canvas-area">
                        <div
                            className={`mindmap-scroll-viewport ${isDragging ? 'dragging' : ''}`}
                            ref={viewportRef}
                            onMouseDown={handleMouseDown}
                            onMouseMove={handleMouseMove}
                            onMouseUp={handleMouseUp}
                            onMouseLeave={handleMouseUp}
                        >
                            <div
                                className="mindmap-scroll-content"
                                style={{
                                    width: `${scrollContent.width}px`,
                                    height: `${scrollContent.height}px`,
                                }}
                            >
                                {/* SVG Edge Connectors Layer */}
                                <svg
                                    className="mindmap-svg-layer"
                                    width={scrollContent.width}
                                    height={scrollContent.height}
                                >
                                    <g transform={`translate(${scrollContent.offsetX}, ${scrollContent.offsetY}) scale(${graphState.zoom})`}>
                                        {layout.edges.map(edge => {
                                            const dx = Math.abs(edge.x2 - edge.x1) * 0.5
                                            const pathD = `M ${edge.x1} ${edge.y1} C ${edge.x1 + dx} ${edge.y1}, ${edge.x2 - dx} ${edge.y2}, ${edge.x2} ${edge.y2}`
                                            const midX = (edge.x1 + edge.x2) / 2
                                            const midY = (edge.y1 + edge.y2) / 2

                                            return (
                                                <g key={edge.id}>
                                                    <path d={pathD} className="connector-line" />
                                                    {edge.relationship && (
                                                        <text
                                                            x={midX}
                                                            y={midY - 5}
                                                            className="rel-text-label"
                                                        >
                                                            {edge.relationship}
                                                        </text>
                                                    )}
                                                </g>
                                            )
                                        })}
                                    </g>
                                </svg>

                                {/* HTML Nodes Overlay Layer */}
                                <div
                                    className="mindmap-nodes-layer"
                                    style={{
                                        width: `${Math.max(1200, Math.ceil((layout.bounds?.maxX || 0) + 300))}px`,
                                        height: `${Math.max(1200, Math.ceil((layout.bounds?.maxY || 0) + 300))}px`,
                                        transform: `translate(${scrollContent.offsetX}px, ${scrollContent.offsetY}px) scale(${graphState.zoom})`,
                                        transformOrigin: '0 0',
                                    }}
                                >
                                    {layout.nodes.map(node => {
                                        const matched = isNodeMatched(node)
                                        const isVisible = isNodeVisibleByType(node)
                                        const isSelected = selectedNode?.id === node.id

                                        return (
                                            <div
                                                key={node.id}
                                                className={`mindmap-node node-${node.type} ${isSelected ? 'selected' : ''} ${matched ? 'matched' : ''}`}
                                                style={{
                                                    left: `${node.x}px`,
                                                    top: `${node.y}px`,
                                                    opacity: isVisible ? 1 : 0.35,
                                                }}
                                                onClick={() => setSelectedNode(node)}
                                            >
                                                <div className="node-header">
                                                    <span className="node-type-tag">{node.type}</span>
                                                    {node.relationship && (
                                                        <span style={{ fontSize: '9px', color: 'var(--text-muted)' }}>
                                                            {node.relationship}
                                                        </span>
                                                    )}
                                                </div>

                                                <div className="node-title">{node.label}</div>

                                                {node.hasChildren && (
                                                    <button
                                                        type="button"
                                                        className="node-collapse-toggle"
                                                        onClick={(e) => toggleCollapse(node.id, e)}
                                                        title={node.isCollapsed ? 'Expand branch' : 'Collapse branch'}
                                                    >
                                                        {node.isCollapsed ? `+${node.childCount}` : '−'}
                                                    </button>
                                                )}
                                            </div>
                                        )
                                    })}
                                </div>
                            </div>
                        </div>

                        {/* Node Details Slide-Out Drawer */}
                        {selectedNode && (
                            <div className="node-details-drawer">
                                <div className="drawer-header">
                                    <div className="drawer-title-group">
                                        <span className="node-type-tag" style={{ marginBottom: '6px', display: 'inline-block' }}>
                                            {selectedNode.type}
                                        </span>
                                        <h3>{selectedNode.label}</h3>
                                    </div>
                                    <button
                                        type="button"
                                        className="drawer-close-btn"
                                        onClick={() => setSelectedNode(null)}
                                        aria-label="Close details"
                                    >
                                        <X size={18} />
                                    </button>
                                </div>

                                {selectedNode.relationship && (
                                    <div className="drawer-section">
                                        <span className="drawer-section-label">Relationship to Parent</span>
                                        <div className="drawer-rel-badge">
                                            <Network size={13} />
                                            <span>{selectedNode.relationship}</span>
                                        </div>
                                    </div>
                                )}

                                <div className="drawer-section">
                                    <span className="drawer-section-label">Description / Definition</span>
                                    <p className="drawer-description-text">
                                        {selectedNode.description || 'Core concept extracted from document structure.'}
                                    </p>
                                </div>

                                {selectedNode.sources && selectedNode.sources.length > 0 && (
                                    <div className="drawer-section">
                                        <span className="drawer-section-label">Source Evidence & Citation</span>
                                        {selectedNode.sources.map((src, idx) => (
                                            <div key={idx} className="drawer-source-box">
                                                <div className="source-box-top">
                                                    <span className="drawer-section-label" style={{ margin: 0 }}>Grounded Quote</span>
                                                    <span className="source-page-pill">Page {src.page || 1}</span>
                                                </div>
                                                <p className="source-quote">
                                                    &ldquo;{src.excerpt}&rdquo;
                                                </p>
                                                <button
                                                    type="button"
                                                    className="open-source-btn"
                                                    onClick={() => handleOpenSource(src.page)}
                                                >
                                                    <ExternalLink size={14} />
                                                    <span>Open Source Page {src.page || 1}</span>
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {(!selectedNode.sources || selectedNode.sources.length === 0) && (
                                    <div className="drawer-section">
                                        <span className="drawer-section-label">Source Evidence</span>
                                        <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0 }}>
                                            Synthesized from document overview.
                                        </p>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    )
}
