import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
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

    // Interactive canvas state
    const [zoom, setZoom] = useState(1.0)
    const [pan, setPan] = useState({ x: 60, y: 300 })
    const [isDragging, setIsDragging] = useState(false)
    const [dragStart, setDragStart] = useState({ x: 0, y: 0 })

    // Node state
    const [selectedNode, setSelectedNode] = useState(null)
    const [collapsedIds, setCollapsedIds] = useState(() => new Set())
    const [searchTerm, setSearchTerm] = useState('')
    const [typeFilter, setTypeFilter] = useState('ALL') // 'ALL' | 'TOPIC' | 'CONCEPT' | 'PROCESS' | 'DEFINITION' | 'EXAMPLE'

    const dropdownRef = useRef(null)
    const canvasRef = useRef(null)

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
            setCollapsedIds(new Set())

            const result = await apiRequest(`/documents/${selectedDocId}/mind-map`, {
                method: 'POST',
                body: JSON.stringify({ force_refresh: forceRefresh }),
            })

            setMindMapData(result)
            // Center the root node in canvas
            setPan({ x: 120, y: 320 })
            setZoom(1.0)
        } catch (err) {
            setErrorMsg(err.message || 'Failed to generate mind map.')
        } finally {
            setIsGenerating(false)
        }
    }

    /* ========================================================
       COLLAPSE / EXPAND TOGGLE
       ======================================================== */
    const toggleCollapse = (nodeId, e) => {
        e.stopPropagation()
        setCollapsedIds(prev => {
            const next = new Set(prev)
            if (next.has(nodeId)) {
                next.delete(nodeId)
            } else {
                next.add(nodeId)
            }
            return next
        })
    }

    /* ========================================================
       CANVAS PANNING & ZOOMING HANDLERS
       ======================================================== */
    const handleMouseDown = (e) => {
        if (e.target.closest('.mindmap-node') || e.target.closest('.node-collapse-toggle')) {
            return
        }
        setIsDragging(true)
        setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
    }

    const handleMouseMove = useCallback((e) => {
        if (!isDragging) return
        setPan({
            x: e.clientX - dragStart.x,
            y: e.clientY - dragStart.y,
        })
    }, [isDragging, dragStart])

    const handleMouseUp = () => {
        setIsDragging(false)
    }

    const handleWheel = (e) => {
        e.preventDefault()
        const zoomDelta = e.deltaY > 0 ? -0.08 : 0.08
        setZoom(prev => Math.min(Math.max(0.4, prev + zoomDelta), 1.8))
    }

    const resetView = () => {
        setZoom(1.0)
        setPan({ x: 120, y: 320 })
    }

    /* ========================================================
       LAYOUT TREE COMPUTATION (X, Y COORDINATES)
       ======================================================== */
    const layout = useMemo(() => {
        if (!mindMapData || !mindMapData.root) return { nodes: [], edges: [] }

        const nodes = []
        const edges = []
        const HORIZONTAL_GAP = 320
        const VERTICAL_GAP = 90

        // Helper: compute leaf count for vertical space allocation
        function getLeafCount(node) {
            if (!node.children || node.children.length === 0 || collapsedIds.has(node.id)) {
                return 1
            }
            return node.children.reduce((acc, child) => acc + getLeafCount(child), 0)
        }

        // Recursive tree layout
        function assignCoordinates(node, depth, topY) {
            const totalLeaves = getLeafCount(node)
            const height = totalLeaves * VERTICAL_GAP
            const nodeX = depth * HORIZONTAL_GAP
            const nodeY = topY + height / 2

            nodes.push({
                ...node,
                x: nodeX,
                y: nodeY,
                depth,
                isCollapsed: collapsedIds.has(node.id),
                hasChildren: Boolean(node.children && node.children.length > 0),
                childCount: node.children ? node.children.length : 0,
            })

            if (node.children && !collapsedIds.has(node.id)) {
                let currentY = topY
                for (const child of node.children) {
                    const childLeaves = getLeafCount(child)
                    const childHeight = childLeaves * VERTICAL_GAP
                    const childPos = assignCoordinates(child, depth + 1, currentY)

                    edges.push({
                        id: `${node.id}->${child.id}`,
                        x1: nodeX + 90,
                        y1: nodeY,
                        x2: childPos.x - 90,
                        y2: childPos.y,
                        relationship: child.relationship || 'contains',
                    })

                    currentY += childHeight
                }
            }

            return { x: nodeX, y: nodeY }
        }

        assignCoordinates(mindMapData.root, 0, 0)
        return { nodes, edges }
    }, [mindMapData, collapsedIds])

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
                        <Network size={28} style={{ color: '#8b5cf6' }} />
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
                            <span>Engine: <strong style={{ color: '#c084fc' }}>{mindMapData.generation_method === 'ollama_llama3_2' ? 'Ollama Llama 3.2' : 'Deterministic Semantic Engine'}</strong></span>
                            {mindMapData.cached && (
                                <>
                                    <span>•</span>
                                    <span style={{ color: '#10b981', fontWeight: 600 }}>(Cached)</span>
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
                                <Search size={14} className="search-icon-pos" />
                                <input
                                    type="text"
                                    placeholder="Search concepts..."
                                    value={searchTerm}
                                    onChange={e => setSearchTerm(e.target.value)}
                                />
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
                                onClick={() => setZoom(prev => Math.min(1.8, prev + 0.1))}
                                title="Zoom In"
                            >
                                <Plus size={16} />
                            </button>
                            <span className="zoom-level-indicator">{Math.round(zoom * 100)}%</span>
                            <button
                                type="button"
                                className="canvas-tool-btn"
                                onClick={() => setZoom(prev => Math.max(0.4, prev - 0.1))}
                                title="Zoom Out"
                            >
                                <Minus size={16} />
                            </button>
                            <button
                                type="button"
                                className="canvas-tool-btn"
                                onClick={resetView}
                                title="Reset View"
                            >
                                <Maximize2 size={15} />
                            </button>
                        </div>
                    </div>

                    {/* Interactive Canvas */}
                    <div
                        className={`mindmap-canvas-area ${isDragging ? 'dragging' : ''}`}
                        ref={canvasRef}
                        onMouseDown={handleMouseDown}
                        onMouseMove={handleMouseMove}
                        onMouseUp={handleMouseUp}
                        onMouseLeave={handleMouseUp}
                        onWheel={handleWheel}
                    >
                        {/* SVG Edge Connectors Layer */}
                        <svg className="mindmap-svg-layer">
                            <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
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
                                transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
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
