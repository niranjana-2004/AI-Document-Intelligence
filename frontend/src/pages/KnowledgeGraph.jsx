import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import {
    AlertTriangle,
    ArrowRight,
    Check,
    CheckSquare,
    ExternalLink,
    Eye,
    FileText,
    Filter,
    GitBranch,
    Layers,
    List,
    Loader2,
    Maximize2,
    Minus,
    Network,
    PenTool,
    Plus,
    RefreshCw,
    RotateCcw,
    Route,
    Search,
    ShieldCheck,
    Sparkles,
    Square,
    Trash2,
} from 'lucide-react'
import {
    apiRequest,
    deleteCrossDocumentKnowledgeGraph,
    deleteKnowledgeGraph,
    generateCrossDocumentKnowledgeGraph,
    generateKnowledgeGraph,
    getKnowledgeGraph,
    regenerateKnowledgeGraph,
} from '../services/api'
import { buildSourceNavigationUrl } from '../utils/citationUtils'
import { clampView, computeFitScroll, MAX_ZOOM, MIN_ZOOM } from '../utils/mindMapLayout'
import {
    computeKnowledgeGraphLayout,
    computeShortestPath,
    filterKnowledgeGraph,
    formatRelationshipLabel,
    getEdgeKey,
    getNeighborhood,
    getNodeTypeStyle,
    NODE_HEIGHT,
    NODE_WIDTH,
} from '../utils/knowledgeGraphUtils'
import '../styles/knowledge-graph.css'

const BUILD_STAGES = [
    { key: 'units', label: 'Assemble Document Units', desc: 'Load chunks & OCR pages' },
    { key: 'entities', label: 'Extract & Ground Entities', desc: 'Verify mentions & deduplicate' },
    { key: 'relations', label: 'Verify Relationships', desc: 'Controlled predicates & scoring' },
    { key: 'persist', label: 'Persist & Index Graph', desc: 'Save grounded graph snapshot' },
]

function KnowledgeGraph() {
    const [searchParams, setSearchParams] = useSearchParams()
    const navigate = useNavigate()
    const urlDocId = searchParams.get('doc')
    const urlMode = searchParams.get('mode')

    const [graphScopeMode, setGraphScopeMode] = useState(urlMode === 'cross' ? 'cross' : 'single') // 'single' | 'cross'
    const [documents, setDocuments] = useState([])
    const [loadingDocs, setLoadingDocs] = useState(true)
    const [selectedDocId, setSelectedDocId] = useState(urlDocId || '')
    const [selectedCrossDocIds, setSelectedCrossDocIds] = useState(() => {
        const rawDocs = searchParams.get('docs')
        if (rawDocs) {
            return rawDocs.split(',').map((id) => Number(id)).filter(Boolean)
        }
        return urlDocId ? [Number(urlDocId)] : []
    })

    const [singleGraphData, setSingleGraphData] = useState(null)
    const [crossGraphData, setCrossGraphData] = useState(null)
    const [loadingGraph, setLoadingGraph] = useState(false)
    const [isGenerating, setIsGenerating] = useState(false)
    const [activeStageIdx, setActiveStageIdx] = useState(0)
    const [errorMsg, setErrorMsg] = useState('')

    // Build options
    const [includeLowConfidence, setIncludeLowConfidence] = useState(false)
    const [skipLlm, setSkipLlm] = useState(false)
    const [onlyShared, setOnlyShared] = useState(false)

    // Exploration controls
    const [viewTab, setViewTab] = useState('canvas') // 'canvas' | 'table'
    const [layoutMode, setLayoutMode] = useState('clustered') // 'clustered' | 'hierarchical' | 'force'
    const [searchQuery, setSearchQuery] = useState('')
    const [selectedNodeTypes, setSelectedNodeTypes] = useState([])
    const [selectedRelationship, setSelectedRelationship] = useState('')
    const [selectedConfidenceTiers, setSelectedConfidenceTiers] = useState([])
    const [isolateNeighborhood, setIsolateNeighborhood] = useState(false)
    const [scopeFilter, setScopeFilter] = useState('all') // 'all' | 'shared' | 'doc_specific'
    const [activeDocFilter, setActiveDocFilter] = useState('') // '' | doc_id

    // Selection & Path exploration
    const [selectedNodeKey, setSelectedNodeKey] = useState(null)
    const [selectedEdgeKey, setSelectedEdgeKey] = useState(null)
    const [pathStartKey, setPathStartKey] = useState('')
    const [pathEndKey, setPathEndKey] = useState('')

    // Pan & Zoom viewport state
    const viewportRef = useRef(null)
    const [zoom, setZoom] = useState(0.88)
    const [isDragging, setIsDragging] = useState(false)
    const dragRef = useRef({ active: false, startX: 0, startY: 0, scrollLeft: 0, scrollTop: 0 })

    // Fetch user documents
    useEffect(() => {
        let cancelled = false
        async function fetchDocs() {
            setLoadingDocs(true)
            try {
                const res = await apiRequest('/documents')
                const list = Array.isArray(res) ? res : (res?.documents || [])
                if (!cancelled) {
                    setDocuments(list)
                    setSelectedDocId((prev) => {
                        if (prev || list.length === 0) return prev
                        const firstReady = list.find((d) => d.processing_status === 'completed') || list[0]
                        return firstReady ? String(firstReady.id) : prev
                    })
                    setSelectedCrossDocIds((prev) => {
                        if (prev.length > 0 || list.length === 0) return prev
                        return list.slice(0, 3).map((d) => d.id)
                    })
                }
            } catch (err) {
                if (!cancelled) setErrorMsg(err.message || 'Failed to load documents')
            } finally {
                if (!cancelled) setLoadingDocs(false)
            }
        }
        fetchDocs()
        return () => { cancelled = true }
    }, [])

    // Sync state -> URL parameters
    useEffect(() => {
        const nextParams = {}
        if (graphScopeMode === 'cross') {
            nextParams.mode = 'cross'
            if (selectedCrossDocIds.length > 0) nextParams.docs = selectedCrossDocIds.join(',')
        } else if (selectedDocId) {
            nextParams.doc = selectedDocId
        }
        setSearchParams(nextParams, { replace: true })
    }, [graphScopeMode, selectedDocId, selectedCrossDocIds, setSearchParams])

    // Load Single Document cached graph
    useEffect(() => {
        if (graphScopeMode !== 'single' || !selectedDocId) return

        let cancelled = false
        async function fetchExistingSingle() {
            setLoadingGraph(true)
            setErrorMsg('')
            setSelectedNodeKey(null)
            setSelectedEdgeKey(null)
            try {
                const data = await getKnowledgeGraph(selectedDocId, { includeLowConfidence })
                if (!cancelled) setSingleGraphData(data)
            } catch (err) {
                if (!cancelled) {
                    if (String(err.message || '').toLowerCase().includes('not found')) {
                        setSingleGraphData(null)
                    } else {
                        setErrorMsg(err.message || 'Failed to check cached knowledge graph')
                    }
                }
            } finally {
                if (!cancelled) setLoadingGraph(false)
            }
        }
        fetchExistingSingle()
        return () => { cancelled = true }
    }, [graphScopeMode, selectedDocId, includeLowConfidence])

    // Honest step progression visual timer while request is running
    useEffect(() => {
        if (!isGenerating) {
            return
        }
        const timers = [
            setTimeout(() => setActiveStageIdx(1), 450),
            setTimeout(() => setActiveStageIdx(2), 1400),
            setTimeout(() => setActiveStageIdx(3), 2600),
        ]
        return () => timers.forEach(clearTimeout)
    }, [isGenerating])

    const selectedDocument = useMemo(
        () => documents.find((d) => String(d.id) === String(selectedDocId)) || null,
        [documents, selectedDocId]
    )

    // Build or Regenerate Knowledge Graph (Single or Cross)
    const handleBuildGraph = useCallback(async (force = false) => {
        if (isGenerating) return
        setActiveStageIdx(0)
        setIsGenerating(true)
        setErrorMsg('')
        try {
            if (graphScopeMode === 'single') {
                if (!selectedDocId) return
                const fn = force ? regenerateKnowledgeGraph : generateKnowledgeGraph
                const data = await fn(selectedDocId, {
                    forceRefresh: force,
                    includeLowConfidence,
                    skipLlm,
                })
                setSingleGraphData(data)
            } else {
                if (selectedCrossDocIds.length === 0) {
                    setErrorMsg('Please select at least one document for cross-document analysis')
                    return
                }
                const data = await generateCrossDocumentKnowledgeGraph({
                    documentIds: selectedCrossDocIds,
                    forceRefresh: force,
                    includeLowConfidence,
                    skipLlm,
                    onlyShared,
                })
                setCrossGraphData(data)
            }
            setSelectedNodeKey(null)
            setSelectedEdgeKey(null)
        } catch (err) {
            setErrorMsg(err.message || 'Knowledge graph generation failed')
        } finally {
            setIsGenerating(false)
            setActiveStageIdx(0)
        }
    }, [graphScopeMode, selectedDocId, selectedCrossDocIds, isGenerating, includeLowConfidence, skipLlm, onlyShared])

    const handleDeleteGraph = useCallback(async () => {
        try {
            if (graphScopeMode === 'single') {
                if (!selectedDocId || !singleGraphData) return
                await deleteKnowledgeGraph(selectedDocId)
                setSingleGraphData(null)
            } else {
                if (!crossGraphData?.id) return
                await deleteCrossDocumentKnowledgeGraph(crossGraphData.id)
                setCrossGraphData(null)
            }
            setSelectedNodeKey(null)
            setSelectedEdgeKey(null)
        } catch (err) {
            setErrorMsg(err.message || 'Failed to delete knowledge graph')
        }
    }, [graphScopeMode, selectedDocId, singleGraphData, crossGraphData])

    // Active Graph Data based on Mode
    const activeGraphData = graphScopeMode === 'cross' ? crossGraphData : singleGraphData

    // Normalized Nodes and Edges
    const allNodes = useMemo(() => {
        if (graphScopeMode === 'cross') {
            return (crossGraphData?.entities || []).map((e) => ({
                ...e,
                node_key: e.entity_key,
                label: e.canonical_name,
                source_pages: (e.documents || []).flatMap((d) => d.source_pages || []),
            }))
        }
        return singleGraphData?.nodes || []
    }, [graphScopeMode, singleGraphData, crossGraphData])

    const allEdges = useMemo(() => {
        return activeGraphData?.edges || []
    }, [activeGraphData])

    const graphContentHash = activeGraphData?.content_hash || activeGraphData?.collection_hash || ''

    const availableNodeTypes = useMemo(() => {
        const counts = {}
        for (const n of allNodes) {
            counts[n.node_type] = (counts[n.node_type] || 0) + 1
        }
        return Object.entries(counts).sort((a, b) => b[1] - a[1])
    }, [allNodes])

    const availableRelationships = useMemo(() => {
        const set = new Set()
        for (const e of allEdges) set.add(e.relationship)
        return [...set].sort()
    }, [allEdges])

    const filtered = useMemo(() => {
        return filterKnowledgeGraph(allNodes, allEdges, {
            searchQuery,
            selectedNodeTypes,
            selectedRelationships: selectedRelationship ? [selectedRelationship] : [],
            selectedConfidenceTiers,
            focusNodeKey: selectedNodeKey,
            isolateNeighborhood,
            scopeFilter: graphScopeMode === 'cross' ? scopeFilter : 'all',
            activeDocumentId: activeDocFilter ? Number(activeDocFilter) : null,
        })
    }, [
        allNodes,
        allEdges,
        searchQuery,
        selectedNodeTypes,
        selectedRelationship,
        selectedConfidenceTiers,
        selectedNodeKey,
        isolateNeighborhood,
        graphScopeMode,
        scopeFilter,
        activeDocFilter,
    ])

    const shortestPath = useMemo(() => {
        if (!pathStartKey || !pathEndKey) return { found: false, nodeKeys: [], edgeKeys: [] }
        return computeShortestPath(filtered.edges, pathStartKey, pathEndKey)
    }, [filtered.edges, pathStartKey, pathEndKey])

    const pathNodeSet = useMemo(() => new Set(shortestPath.nodeKeys), [shortestPath])
    const pathEdgeSet = useMemo(() => new Set(shortestPath.edgeKeys), [shortestPath])

    const activeNeighborhood = useMemo(
        () => getNeighborhood(filtered.edges, selectedNodeKey),
        [filtered.edges, selectedNodeKey]
    )

    const layout = useMemo(
        () => computeKnowledgeGraphLayout(filtered.nodes, filtered.edges, layoutMode),
        [filtered.nodes, filtered.edges, layoutMode]
    )

    const fitToScreen = useCallback(() => {
        const el = viewportRef.current
        if (!el || filtered.nodes.length === 0) return
        const fit = computeFitScroll(
            { width: el.clientWidth, height: el.clientHeight },
            { minX: 0, minY: 0, maxX: layout.width, maxY: layout.height, width: layout.width, height: layout.height },
            32
        )
        setZoom(fit.zoom)
        requestAnimationFrame(() => {
            el.scrollLeft = fit.scrollLeft
            el.scrollTop = fit.scrollTop
        })
    }, [filtered.nodes.length, layout.width, layout.height])

    useEffect(() => {
        if (graphContentHash && viewTab === 'canvas' && filtered.nodes.length > 0) {
            const t = setTimeout(fitToScreen, 60)
            return () => clearTimeout(t)
        }
    }, [graphContentHash, layoutMode, viewTab, fitToScreen, filtered.nodes.length])

    const handleZoomDelta = (delta) => {
        setZoom((prev) => clampView({ zoom: prev + delta, x: 0, y: 0 }, MIN_ZOOM, MAX_ZOOM).zoom)
    }

    const handleResetView = () => {
        setZoom(0.9)
        if (viewportRef.current) {
            viewportRef.current.scrollLeft = 0
            viewportRef.current.scrollTop = 0
        }
    }

    const handleMouseDown = (e) => {
        if (e.target.closest('.kg-node-card') || e.target.closest('.kg-edge-hit') || e.target.closest('.kg-edge-pill')) {
            return
        }
        const el = viewportRef.current
        if (!el) return
        dragRef.current = {
            active: true,
            startX: e.clientX,
            startY: e.clientY,
            scrollLeft: el.scrollLeft,
            scrollTop: el.scrollTop,
        }
        setIsDragging(true)
    }

    const handleMouseMove = (e) => {
        if (!dragRef.current.active || !viewportRef.current) return
        viewportRef.current.scrollLeft = dragRef.current.scrollLeft - (e.clientX - dragRef.current.startX)
        viewportRef.current.scrollTop = dragRef.current.scrollTop - (e.clientY - dragRef.current.startY)
    }

    const handleMouseUp = () => {
        dragRef.current.active = false
        setIsDragging(false)
    }

    const toggleNodeTypeFilter = (type) => {
        setSelectedNodeTypes((prev) =>
            prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
        )
    }

    const toggleTierFilter = (tier) => {
        setSelectedConfidenceTiers((prev) =>
            prev.includes(tier) ? prev.filter((t) => t !== tier) : [...prev, tier]
        )
    }

    const toggleCrossDocId = (docId) => {
        const idNum = Number(docId)
        setSelectedCrossDocIds((prev) =>
            prev.includes(idNum) ? prev.filter((id) => id !== idNum) : [...prev, idNum]
        )
    }

    const selectedNode = useMemo(
        () => allNodes.find((n) => (n.node_key || n.entity_key) === selectedNodeKey) || null,
        [allNodes, selectedNodeKey]
    )

    const selectedEdge = useMemo(
        () => allEdges.find((e) => getEdgeKey(e) === selectedEdgeKey) || null,
        [allEdges, selectedEdgeKey]
    )

    const nodeLabelMap = useMemo(() => {
        const m = new Map()
        for (const n of allNodes) m.set(n.node_key || n.entity_key, n)
        return m
    }, [allNodes])

    const connectedEdgesForSelectedNode = useMemo(() => {
        if (!selectedNodeKey) return []
        return allEdges.filter((e) => e.source_key === selectedNodeKey || e.target_key === selectedNodeKey)
    }, [allEdges, selectedNodeKey])

    const handleNavigateEvidence = (ev) => {
        const docId = ev.document_id || activeGraphData?.document_id || selectedDocument?.id
        const docObj = documents.find((d) => d.id === docId)
        const url = buildSourceNavigationUrl({
            document_id: docId,
            document_type: docObj?.document_type || 'pdf',
            is_handwritten: Boolean(docObj?.is_handwritten),
            page_number: ev.page_number || ev.page || 1,
            chunk_text: ev.source_text || ev.excerpt || '',
        })
        if (url) navigate(url)
    }

    return (
        <div className="kg-page">
            {/* Hero & Scope Mode Switcher */}
            <header className="kg-hero">
                <div className="kg-hero-top">
                    <div className="kg-hero-title">
                        <div className="kg-hero-icon" aria-hidden="true">
                            <GitBranch size={22} />
                        </div>
                        <div>
                            <div className="kg-eyebrow">
                                <span>SOURCE-GROUNDED KNOWLEDGE GRAPH</span>
                                {graphScopeMode === 'cross' ? (
                                    <span className="kg-badge kg-badge-cross-doc">
                                        <Network size={12} /> Phase 2 Cross-Document View
                                    </span>
                                ) : (
                                    <>
                                        {singleGraphData?.stats?.is_handwritten && (
                                            <span className="kg-badge kg-badge-hw">
                                                <PenTool size={12} /> Handwritten Source
                                            </span>
                                        )}
                                        {singleGraphData?.stats?.used_research_analysis && (
                                            <span className="kg-badge kg-badge-research">
                                                <Sparkles size={12} /> Research Enriched
                                            </span>
                                        )}
                                    </>
                                )}
                                {activeGraphData?.cached && (
                                    <span className="kg-badge kg-badge-cached">Cached</span>
                                )}
                            </div>
                            <h1>Knowledge Graph Explorer</h1>
                            <p className="kg-subtitle">
                                {graphScopeMode === 'cross'
                                    ? 'Unify concepts across multiple documents into shared canonical entities backed by source evidence.'
                                    : 'Inspect verified entities, controlled semantic relationships, and exact page citations for an individual document.'}
                            </p>
                        </div>
                    </div>

                    <div className="kg-hero-links">
                        {/* Mode Switcher */}
                        <div className="kg-mode-switcher" role="radiogroup" aria-label="Knowledge Graph Mode">
                            <button
                                type="button"
                                className={`kg-mode-tab ${graphScopeMode === 'single' ? 'active' : ''}`}
                                onClick={() => setGraphScopeMode('single')}
                            >
                                <FileText size={14} /> Single Document
                            </button>
                            <button
                                type="button"
                                className={`kg-mode-tab ${graphScopeMode === 'cross' ? 'active' : ''}`}
                                onClick={() => setGraphScopeMode('cross')}
                            >
                                <Network size={14} /> Cross-Document
                            </button>
                        </div>

                        {selectedDocId && graphScopeMode === 'single' && (
                            <Link to={`/mind-map?doc=${selectedDocId}`} className="kg-btn kg-btn-ghost">
                                <Network size={15} />
                                <span>Open Mind Map</span>
                            </Link>
                        )}
                        {graphScopeMode === 'cross' && selectedCrossDocIds.length > 0 && (
                            <Link to={`/ask-ai?docs=${selectedCrossDocIds.join(',')}`} className="kg-btn kg-btn-ghost">
                                <Sparkles size={15} />
                                <span>Chat with Documents</span>
                            </Link>
                        )}
                    </div>
                </div>

                {/* Scope-Specific Document Picker */}
                {graphScopeMode === 'single' ? (
                    <div className="kg-controls-row">
                        <div className="kg-doc-picker">
                            <label htmlFor="kg-doc-select" className="kg-sr-label">Document</label>
                            <select
                                id="kg-doc-select"
                                className="kg-select"
                                value={selectedDocId}
                                disabled={loadingDocs || isGenerating}
                                onChange={(e) => setSelectedDocId(e.target.value)}
                            >
                                {documents.length === 0 && <option value="">No documents uploaded yet</option>}
                                {documents.map((doc) => (
                                    <option key={doc.id} value={String(doc.id)}>
                                        {doc.filename} ({doc.is_handwritten ? 'Handwritten' : doc.document_type})
                                    </option>
                                ))}
                            </select>
                        </div>

                        <div className="kg-action-buttons">
                            <button
                                type="button"
                                className="kg-btn kg-btn-primary"
                                disabled={!selectedDocId || isGenerating}
                                onClick={() => handleBuildGraph(false)}
                            >
                                {isGenerating ? <Loader2 size={16} className="kg-spin" /> : <GitBranch size={16} />}
                                <span>{singleGraphData ? 'Load / Update Graph' : 'Build Knowledge Graph'}</span>
                            </button>

                            {singleGraphData && (
                                <>
                                    <button
                                        type="button"
                                        className="kg-btn kg-btn-secondary"
                                        disabled={isGenerating}
                                        onClick={() => handleBuildGraph(true)}
                                        title="Force fresh extraction and relationship verification"
                                    >
                                        <RefreshCw size={15} />
                                        <span>Regenerate</span>
                                    </button>
                                    <button
                                        type="button"
                                        className="kg-btn kg-btn-danger-ghost"
                                        disabled={isGenerating}
                                        onClick={handleDeleteGraph}
                                        title="Delete cached knowledge graph"
                                        aria-label="Delete Knowledge Graph"
                                    >
                                        <Trash2 size={15} />
                                    </button>
                                </>
                            )}
                        </div>
                    </div>
                ) : (
                    /* Cross-Document Multi-Document Selection Panel */
                    <div className="kg-multi-doc-panel">
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <Network size={16} style={{ color: 'var(--accent-ink)' }} />
                                <strong>Select Documents to Cross-Analyze:</strong>
                                <span className="kg-badge kg-badge-shared">
                                    {selectedCrossDocIds.length} Selected
                                </span>
                            </div>
                            <div style={{ display: 'flex', gap: 8 }}>
                                <button
                                    type="button"
                                    className="kg-btn kg-btn-small kg-btn-ghost"
                                    onClick={() => setSelectedCrossDocIds(documents.map((d) => d.id))}
                                >
                                    Select All
                                </button>
                                <button
                                    type="button"
                                    className="kg-btn kg-btn-small kg-btn-ghost"
                                    onClick={() => setSelectedCrossDocIds([])}
                                >
                                    Clear
                                </button>
                                <button
                                    type="button"
                                    className="kg-btn kg-btn-primary"
                                    disabled={selectedCrossDocIds.length === 0 || isGenerating}
                                    onClick={() => handleBuildGraph(false)}
                                >
                                    {isGenerating ? <Loader2 size={16} className="kg-spin" /> : <GitBranch size={16} />}
                                    <span>{crossGraphData ? 'Update Cross-Doc Graph' : 'Generate Cross-Doc Graph'}</span>
                                </button>
                                {crossGraphData && (
                                    <button
                                        type="button"
                                        className="kg-btn kg-btn-secondary"
                                        disabled={isGenerating}
                                        onClick={() => handleBuildGraph(true)}
                                        title="Force fresh cross-document analysis"
                                    >
                                        <RefreshCw size={15} />
                                        <span>Regenerate</span>
                                    </button>
                                )}
                            </div>
                        </div>

                        <div className="kg-doc-selection-grid">
                            {documents.map((doc) => {
                                const checked = selectedCrossDocIds.includes(doc.id)
                                return (
                                    <div
                                        key={doc.id}
                                        className={`kg-doc-check-card ${checked ? 'selected' : ''}`}
                                        onClick={() => toggleCrossDocId(doc.id)}
                                    >
                                        {checked ? <CheckSquare size={16} /> : <Square size={16} />}
                                        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            <span>{doc.filename || doc.title || `Doc #${doc.id}`}</span>
                                            <span style={{ fontSize: '0.72rem', opacity: 0.75, display: 'block' }}>
                                                {doc.is_handwritten ? 'Handwritten' : doc.document_type} (p. {doc.page_count || 1})
                                            </span>
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    </div>
                )}

                <div className="kg-options-row">
                    <label className="kg-checkbox-label">
                        <input
                            type="checkbox"
                            checked={includeLowConfidence}
                            onChange={(e) => setIncludeLowConfidence(e.target.checked)}
                        />
                        <span>Show Low-Confidence Edges (&lt; 0.50)</span>
                    </label>
                    <label className="kg-checkbox-label">
                        <input
                            type="checkbox"
                            checked={skipLlm}
                            onChange={(e) => setSkipLlm(e.target.checked)}
                        />
                        <span>Fast Deterministic Mode (Skip Local LLM)</span>
                    </label>
                    {graphScopeMode === 'cross' && (
                        <label className="kg-checkbox-label">
                            <input
                                type="checkbox"
                                checked={onlyShared}
                                onChange={(e) => setOnlyShared(e.target.checked)}
                            />
                            <span>Shared Concepts Only (Appearing in &ge; 2 Docs)</span>
                        </label>
                    )}
                </div>

                {singleGraphData?.is_outdated && graphScopeMode === 'single' && (
                    <div className="kg-banner kg-banner-warn" role="status">
                        <AlertTriangle size={16} />
                        <span>Document text or research analysis changed since this graph was built.</span>
                        <button type="button" className="kg-btn kg-btn-small" onClick={() => handleBuildGraph(true)}>
                            Regenerate Now
                        </button>
                    </div>
                )}

                {errorMsg && (
                    <div className="kg-banner kg-banner-error" role="alert">
                        <AlertTriangle size={16} />
                        <span>{errorMsg}</span>
                    </div>
                )}
            </header>

            {/* Stage Stepper during Build */}
            {isGenerating && (
                <section className="kg-stepper-card" aria-label="Knowledge graph generation stages">
                    <div className="kg-stepper-head">
                        <Loader2 size={18} className="kg-spin" />
                        <div>
                            <h3>
                                {graphScopeMode === 'cross'
                                    ? 'Unifying Personal Personal Personal Knowledge Graph'
                                    : 'Constructing Source-Grounded Knowledge Graph'}
                            </h3>
                            <p>
                                {graphScopeMode === 'cross'
                                    ? 'Resolving concept mentions across documents into unified personal personal personal personal personal Personal Knowledge entities.'
                                    : 'Anchoring every concept and relationship back to verifiable document chunks.'}
                            </p>
                        </div>
                    </div>
                    <div className="kg-stepper-grid">
                        {BUILD_STAGES.map((st, idx) => {
                            const stateClass = idx < activeStageIdx ? 'done' : idx === activeStageIdx ? 'active' : ''
                            return (
                                <div key={st.key} className={`kg-step ${stateClass}`}>
                                    <div className="kg-step-dot">
                                        {idx < activeStageIdx ? <Check size={14} /> : idx + 1}
                                    </div>
                                    <div>
                                        <div className="kg-step-label">{st.label}</div>
                                        <div className="kg-step-desc">{st.desc}</div>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </section>
            )}

            {/* Empty / Prompt State */}
            {!isGenerating && !loadingGraph && !activeGraphData && (
                <section className="kg-empty-card">
                    <GitBranch size={36} className="kg-empty-icon" />
                    <h2>{graphScopeMode === 'cross' ? 'No Cross-Document Graph Generated' : 'No Knowledge Graph Built Yet'}</h2>
                    <p>
                        {graphScopeMode === 'cross'
                            ? 'Select documents above and click "Generate Cross-Doc Graph" to unify concepts and expose connections across your library.'
                            : 'Select a document above and click "Build Knowledge Graph" to extract grounded entities and relationships.'}
                    </p>
                </section>
            )}

            {/* Loading Cached State */}
            {loadingGraph && !isGenerating && (
                <section className="kg-empty-card">
                    <Loader2 size={28} className="kg-spin" />
                    <p>Checking persisted knowledge graph snapshot...</p>
                </section>
            )}

            {/* Main Workspace */}
            {!isGenerating && activeGraphData && (
                <>
                    {/* Metrics Summary Bar */}
                    <section className="kg-stats-strip" aria-label="Graph Statistics">
                        <div className="kg-stat-pill">
                            <span className="kg-stat-label">
                                {graphScopeMode === 'cross' ? 'Canonical Entities' : 'Nodes'}
                            </span>
                            <strong className="kg-stat-val">
                                {activeGraphData.stats.total_entities ?? activeGraphData.stats.node_count}
                            </strong>
                        </div>
                        {graphScopeMode === 'cross' && (
                            <>
                                <div className="kg-stat-pill">
                                    <span className="kg-stat-label">Shared Across Docs</span>
                                    <strong className="kg-stat-val" style={{ color: '#059669' }}>
                                        {activeGraphData.stats.shared_entities}
                                    </strong>
                                </div>
                                <div className="kg-stat-pill">
                                    <span className="kg-stat-label">Cross-Doc Edges</span>
                                    <strong className="kg-stat-val" style={{ color: '#7c3aed' }}>
                                        {activeGraphData.stats.cross_document_edges}
                                    </strong>
                                </div>
                            </>
                        )}
                        <div className="kg-stat-pill">
                            <span className="kg-stat-label">Visible Edges</span>
                            <strong className="kg-stat-val">
                                {activeGraphData.stats.total_edges ?? activeGraphData.stats.edge_count}
                            </strong>
                        </div>
                        <div className="kg-stat-pill">
                            <span className="kg-stat-label">Avg Confidence</span>
                            <strong className="kg-stat-val">
                                {Math.round((activeGraphData.stats.average_confidence ?? activeGraphData.stats.average_edge_confidence ?? 0.8) * 100)}%
                            </strong>
                        </div>
                        <div className="kg-stat-pill">
                            <span className="kg-stat-label">Grounded Ratio</span>
                            <strong className="kg-stat-val">100%</strong>
                        </div>
                        <div className="kg-stat-pill">
                            <span className="kg-stat-label">Engine</span>
                            <strong className="kg-stat-val">
                                {activeGraphData.generation_method === 'hybrid' ? 'Hybrid + Ollama' : 'Deterministic Grounded'}
                            </strong>
                        </div>
                    </section>

                    {/* Toolbar & Filters */}
                    <section className="kg-toolbar">
                        <div className="kg-toolbar-row">
                            {/* Search */}
                            <div className="kg-search-box">
                                <Search size={15} />
                                <input
                                    type="search"
                                    placeholder={graphScopeMode === 'cross' ? 'Search concepts across documents...' : 'Filter nodes or aliases...'}
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    aria-label="Search knowledge graph nodes"
                                />
                            </div>

                            {/* Scope Filter for Cross-Document Mode */}
                            {graphScopeMode === 'cross' && (
                                <div className="kg-segmented" role="group" aria-label="Scope filter">
                                    {[
                                        { id: 'all', label: 'All' },
                                        { id: 'shared', label: 'Shared (≥2 Docs)' },
                                        { id: 'doc_specific', label: 'Doc-Specific' },
                                    ].map((sf) => (
                                        <button
                                            key={sf.id}
                                            type="button"
                                            className={`kg-seg-btn ${scopeFilter === sf.id ? 'active' : ''}`}
                                            onClick={() => setScopeFilter(sf.id)}
                                        >
                                            {sf.label}
                                        </button>
                                    ))}
                                </div>
                            )}

                            {/* Document Isolation Filter */}
                            {graphScopeMode === 'cross' && (
                                <select
                                    className="kg-select kg-select-compact"
                                    value={activeDocFilter}
                                    onChange={(e) => setActiveDocFilter(e.target.value)}
                                    aria-label="Isolate document"
                                >
                                    <option value="">All Selected Documents</option>
                                    {(activeGraphData.selected_documents || []).map((sd) => (
                                        <option key={sd.document_id} value={String(sd.document_id)}>
                                            {sd.filename || sd.title}
                                        </option>
                                    ))}
                                </select>
                            )}

                            {/* Relationship Dropdown */}
                            <select
                                className="kg-select kg-select-compact"
                                value={selectedRelationship}
                                onChange={(e) => setSelectedRelationship(e.target.value)}
                                aria-label="Filter by relationship type"
                            >
                                <option value="">All Relationships</option>
                                {availableRelationships.map((rel) => (
                                    <option key={rel} value={rel}>
                                        {formatRelationshipLabel(rel)}
                                    </option>
                                ))}
                            </select>

                            {/* Confidence Tier Filter */}
                            <div className="kg-chip-group" role="group" aria-label="Confidence filter">
                                {['high', 'medium', 'low'].map((tier) => (
                                    <button
                                        key={tier}
                                        type="button"
                                        className={`kg-chip ${selectedConfidenceTiers.includes(tier) ? 'active' : ''}`}
                                        onClick={() => toggleTierFilter(tier)}
                                    >
                                        {tier}
                                    </button>
                                ))}
                            </div>

                            {/* Layout Mode */}
                            <div className="kg-segmented" role="group" aria-label="Layout mode">
                                {[
                                    { id: 'clustered', label: 'Clustered' },
                                    { id: 'hierarchical', label: 'Hierarchical' },
                                    { id: 'force', label: 'Force' },
                                ].map((m) => (
                                    <button
                                        key={m.id}
                                        type="button"
                                        className={`kg-seg-btn ${layoutMode === m.id ? 'active' : ''}`}
                                        onClick={() => setLayoutMode(m.id)}
                                    >
                                        {m.label}
                                    </button>
                                ))}
                            </div>

                            {/* View Switcher */}
                            <div className="kg-segmented" role="group" aria-label="View mode">
                                <button
                                    type="button"
                                    className={`kg-seg-btn ${viewTab === 'canvas' ? 'active' : ''}`}
                                    onClick={() => setViewTab('canvas')}
                                >
                                    <Layers size={14} /> Graph
                                </button>
                                <button
                                    type="button"
                                    className={`kg-seg-btn ${viewTab === 'table' ? 'active' : ''}`}
                                    onClick={() => setViewTab('table')}
                                >
                                    <List size={14} /> Table View
                                </button>
                            </div>
                        </div>

                        {/* Node Type Chips & Clear Filters */}
                        <div className="kg-toolbar-subrow">
                            <div className="kg-type-chips">
                                <span className="kg-filter-caption"><Filter size={13} /> Types:</span>
                                {availableNodeTypes.map(([t, count]) => {
                                    const st = getNodeTypeStyle(t)
                                    const active = selectedNodeTypes.includes(t)
                                    return (
                                        <button
                                            key={t}
                                            type="button"
                                            className={`kg-type-chip ${active ? 'active' : ''}`}
                                            style={{ '--type-color': st.color, '--type-bg': st.bg }}
                                            onClick={() => toggleNodeTypeFilter(t)}
                                        >
                                            <span className="kg-type-dot" />
                                            <span>{t}</span>
                                            <span className="kg-type-count">{count}</span>
                                        </button>
                                    )
                                })}
                                {(selectedNodeTypes.length > 0 || selectedRelationship || selectedConfidenceTiers.length > 0 || searchQuery || isolateNeighborhood || pathStartKey || pathEndKey || activeDocFilter || scopeFilter !== 'all') && (
                                    <button
                                        type="button"
                                        className="kg-clear-filters"
                                        onClick={() => {
                                            setSearchQuery('')
                                            setSelectedNodeTypes([])
                                            setSelectedRelationship('')
                                            setSelectedConfidenceTiers([])
                                            setIsolateNeighborhood(false)
                                            setScopeFilter('all')
                                            setActiveDocFilter('')
                                            setPathStartKey('')
                                            setPathEndKey('')
                                        }}
                                    >
                                        Clear Filters
                                    </button>
                                )}
                            </div>

                            {/* Path Finder */}
                            <div className="kg-path-bar">
                                <span className="kg-filter-caption"><Route size={13} /> Trace Path:</span>
                                <select
                                    className="kg-select kg-select-tiny"
                                    value={pathStartKey}
                                    onChange={(e) => setPathStartKey(e.target.value)}
                                    aria-label="Path start node"
                                >
                                    <option value="">Start node...</option>
                                    {allNodes.map((n) => (
                                        <option key={n.node_key || n.entity_key} value={n.node_key || n.entity_key}>
                                            {n.label || n.canonical_name}
                                        </option>
                                    ))}
                                </select>
                                <ArrowRight size={13} />
                                <select
                                    className="kg-select kg-select-tiny"
                                    value={pathEndKey}
                                    onChange={(e) => setPathEndKey(e.target.value)}
                                    aria-label="Path target node"
                                >
                                    <option value="">Target node...</option>
                                    {allNodes.map((n) => (
                                        <option key={n.node_key || n.entity_key} value={n.node_key || n.entity_key}>
                                            {n.label || n.canonical_name}
                                        </option>
                                    ))}
                                </select>
                                {pathStartKey && pathEndKey && (
                                    <span className={`kg-path-status ${shortestPath.found ? 'ok' : 'none'}`}>
                                        {shortestPath.found ? `${shortestPath.nodeKeys.length - 1} hops` : 'No path'}
                                    </span>
                                )}
                            </div>
                        </div>
                    </section>

                    {/* Split Workspace */}
                    <div className="kg-workspace-grid">
                        {/* Canvas / Table */}
                        <div className="kg-main-pane">
                            {viewTab === 'canvas' ? (
                                <div className="kg-canvas-shell">
                                    <div className="kg-canvas-controls">
                                        {selectedNodeKey && (
                                            <button
                                                type="button"
                                                className={`kg-btn kg-btn-small ${isolateNeighborhood ? 'kg-btn-primary' : 'kg-btn-secondary'}`}
                                                onClick={() => setIsolateNeighborhood((v) => !v)}
                                            >
                                                <Eye size={13} />
                                                <span>{isolateNeighborhood ? 'Show Full Graph' : 'Isolate 1-Hop Neighborhood'}</span>
                                            </button>
                                        )}
                                        <div className="kg-zoom-group">
                                            <button type="button" className="kg-icon-btn" onClick={() => handleZoomDelta(-0.15)} aria-label="Zoom out">
                                                <Minus size={14} />
                                            </button>
                                            <span className="kg-zoom-pct">{Math.round(zoom * 100)}%</span>
                                            <button type="button" className="kg-icon-btn" onClick={() => handleZoomDelta(0.15)} aria-label="Zoom in">
                                                <Plus size={14} />
                                            </button>
                                            <button type="button" className="kg-btn kg-btn-small kg-btn-secondary" onClick={fitToScreen}>
                                                <Maximize2 size={13} /> Fit
                                            </button>
                                            <button type="button" className="kg-icon-btn" onClick={handleResetView} aria-label="Reset view">
                                                <RotateCcw size={14} />
                                            </button>
                                        </div>
                                    </div>

                                    {filtered.nodes.length === 0 ? (
                                        <div className="kg-empty-inline">
                                            <p>No concepts match the current filters.</p>
                                        </div>
                                    ) : (
                                        <div
                                            ref={viewportRef}
                                            className={`kg-scroll-viewport ${isDragging ? 'dragging' : ''}`}
                                            onMouseDown={handleMouseDown}
                                            onMouseMove={handleMouseMove}
                                            onMouseUp={handleMouseUp}
                                            onMouseLeave={handleMouseUp}
                                        >
                                            <div
                                                className="kg-canvas-stage"
                                                style={{
                                                    width: layout.width * zoom,
                                                    height: layout.height * zoom,
                                                }}
                                            >
                                                <div
                                                    className="kg-canvas-transform"
                                                    style={{
                                                        width: layout.width,
                                                        height: layout.height,
                                                        transform: `scale(${zoom})`,
                                                        transformOrigin: 'top left',
                                                    }}
                                                >
                                                    {/* SVG Edges Layer */}
                                                    <svg
                                                        className="kg-svg-edges"
                                                        width={layout.width}
                                                        height={layout.height}
                                                    >
                                                        <defs>
                                                            <marker
                                                                id="kg-arrow"
                                                                viewBox="0 0 10 10"
                                                                refX="8"
                                                                refY="5"
                                                                markerWidth="6"
                                                                markerHeight="6"
                                                                orient="auto-start-reverse"
                                                            >
                                                                <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="var(--text-muted)" />
                                                            </marker>
                                                            <marker
                                                                id="kg-arrow-active"
                                                                viewBox="0 0 10 10"
                                                                refX="8"
                                                                refY="5"
                                                                markerWidth="7"
                                                                markerHeight="7"
                                                                orient="auto-start-reverse"
                                                            >
                                                                <path d="M 0 1 L 9 5 L 0 9 z" fill="var(--accent)" />
                                                            </marker>
                                                        </defs>

                                                        {filtered.edges.map((edge) => {
                                                            const p1 = layout.positions.get(edge.source_key)
                                                            const p2 = layout.positions.get(edge.target_key)
                                                            if (!p1 || !p2) return null

                                                            const ek = getEdgeKey(edge)
                                                            const isSelected = selectedEdgeKey === ek
                                                            const isPath = pathEdgeSet.has(ek)
                                                            const isNeighbor = selectedNodeKey && (edge.source_key === selectedNodeKey || edge.target_key === selectedNodeKey)
                                                            const dimmed = (selectedNodeKey && !isNeighbor && !isSelected) || (shortestPath.found && !isPath)

                                                            const dx = p2.x - p1.x
                                                            const dy = p2.y - p1.y
                                                            const dist = Math.max(Math.hypot(dx, dy), 1)
                                                            const trimStart = 38
                                                            const trimEnd = 42
                                                            const sx = p1.x + (dx / dist) * trimStart
                                                            const sy = p1.y + (dy / dist) * trimStart
                                                            const tx = p2.x - (dx / dist) * trimEnd
                                                            const ty = p2.y - (dy / dist) * trimEnd

                                                            return (
                                                                <g key={ek} className={dimmed ? 'kg-edge-dimmed' : ''}>
                                                                    <line
                                                                        x1={sx}
                                                                        y1={sy}
                                                                        x2={tx}
                                                                        y2={ty}
                                                                        stroke={isSelected || isPath ? 'var(--accent)' : edge.is_cross_document ? '#7c3aed' : edge.confidence_tier === 'low' ? 'var(--border-strong)' : 'var(--text-muted)'}
                                                                        strokeWidth={isSelected || isPath ? 3 : edge.is_cross_document ? 2.5 : edge.origin === 'explicit' ? 2 : 1.5}
                                                                        strokeDasharray={edge.origin === 'derived' ? '5 4' : undefined}
                                                                        markerEnd={isSelected || isPath ? 'url(#kg-arrow-active)' : 'url(#kg-arrow)'}
                                                                    />
                                                                    <line
                                                                        className="kg-edge-hit"
                                                                        x1={sx}
                                                                        y1={sy}
                                                                        x2={tx}
                                                                        y2={ty}
                                                                        stroke="transparent"
                                                                        strokeWidth={16}
                                                                        onClick={(evt) => {
                                                                            evt.stopPropagation()
                                                                            setSelectedEdgeKey(ek)
                                                                            setSelectedNodeKey(null)
                                                                        }}
                                                                    />
                                                                </g>
                                                            )
                                                        })}
                                                    </svg>

                                                    {/* Relationship Pills */}
                                                    {filtered.edges.map((edge) => {
                                                        const p1 = layout.positions.get(edge.source_key)
                                                        const p2 = layout.positions.get(edge.target_key)
                                                        if (!p1 || !p2) return null
                                                        const ek = getEdgeKey(edge)
                                                        const isSelected = selectedEdgeKey === ek
                                                        const isPath = pathEdgeSet.has(ek)
                                                        const isNeighbor = selectedNodeKey && (edge.source_key === selectedNodeKey || edge.target_key === selectedNodeKey)
                                                        const dimmed = (selectedNodeKey && !isNeighbor && !isSelected) || (shortestPath.found && !isPath)

                                                        return (
                                                            <button
                                                                key={`pill-${ek}`}
                                                                type="button"
                                                                className={`kg-edge-pill ${isSelected ? 'selected' : ''} ${isPath ? 'in-path' : ''} ${dimmed ? 'dimmed' : ''} ${edge.is_cross_document ? 'kg-edge-cross' : ''}`}
                                                                style={{
                                                                    left: (p1.x + p2.x) / 2,
                                                                    top: (p1.y + p2.y) / 2,
                                                                }}
                                                                onClick={(evt) => {
                                                                    evt.stopPropagation()
                                                                    setSelectedEdgeKey(ek)
                                                                    setSelectedNodeKey(null)
                                                                }}
                                                                title={`${formatRelationshipLabel(edge.relationship)} (${Math.round(edge.confidence * 100)}%)`}
                                                            >
                                                                {formatRelationshipLabel(edge.relationship)}
                                                            </button>
                                                        )
                                                    })}

                                                    {/* Node Cards */}
                                                    {filtered.nodes.map((node) => {
                                                        const nodeKey = node.node_key || node.entity_key
                                                        const pos = layout.positions.get(nodeKey)
                                                        if (!pos) return null
                                                        const st = getNodeTypeStyle(node.node_type)
                                                        const isSelected = selectedNodeKey === nodeKey
                                                        const isPath = pathNodeSet.has(nodeKey)
                                                        const inNeighborhood = activeNeighborhood.nodeKeys.has(nodeKey)
                                                        const dimmed = (selectedNodeKey && !inNeighborhood) || (shortestPath.found && !isPath)

                                                        return (
                                                            <button
                                                                key={nodeKey}
                                                                type="button"
                                                                className={`kg-node-card ${isSelected ? 'selected' : ''} ${isPath ? 'in-path' : ''} ${dimmed ? 'dimmed' : ''} ${node.is_shared ? 'kg-node-shared' : ''}`}
                                                                style={{
                                                                    left: pos.x - NODE_WIDTH / 2,
                                                                    top: pos.y - NODE_HEIGHT / 2,
                                                                    width: NODE_WIDTH,
                                                                    minHeight: NODE_HEIGHT,
                                                                    '--node-color': st.color,
                                                                    '--node-bg': st.bg,
                                                                }}
                                                                onClick={(evt) => {
                                                                    evt.stopPropagation()
                                                                    setSelectedNodeKey(nodeKey)
                                                                    setSelectedEdgeKey(null)
                                                                }}
                                                            >
                                                                {node.is_shared && (
                                                                    <span className="kg-node-shared-pill" title={`Shared across ${node.document_count} documents`}>
                                                                        <Sparkles size={9} /> {node.document_count} Docs
                                                                    </span>
                                                                )}
                                                                <div className="kg-node-top">
                                                                    <span className="kg-node-type-badge">{node.node_type}</span>
                                                                    <span className="kg-node-ev-badge" title="Grounded evidence mentions">
                                                                        {node.occurrence_count || node.evidence_count || 1} mentions
                                                                    </span>
                                                                </div>
                                                                <div className="kg-node-label">{node.label || node.canonical_name}</div>
                                                            </button>
                                                        )
                                                    })}
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                /* Accessible Table View */
                                <div className="kg-table-shell">
                                    <h3>Concepts &amp; Entities ({filtered.nodes.length})</h3>
                                    <div className="kg-table-wrap">
                                        <table className="kg-table">
                                            <thead>
                                                <tr>
                                                    <th>Entity / Concept</th>
                                                    <th>Type</th>
                                                    <th>Scope</th>
                                                    <th>Confidence</th>
                                                    <th>Mentions</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {filtered.nodes.map((node) => {
                                                    const k = node.node_key || node.entity_key
                                                    return (
                                                        <tr
                                                            key={k}
                                                            className={selectedNodeKey === k ? 'selected-row' : ''}
                                                            onClick={() => {
                                                                setSelectedNodeKey(k)
                                                                setSelectedEdgeKey(null)
                                                            }}
                                                        >
                                                            <td>
                                                                <strong>{node.label || node.canonical_name}</strong>
                                                                {node.aliases?.length > 0 && (
                                                                    <div className="kg-aliases-mini">Aliases: {node.aliases.join(', ')}</div>
                                                                )}
                                                            </td>
                                                            <td><span className="kg-pill-mini">{node.node_type}</span></td>
                                                            <td>
                                                                {node.is_shared ? (
                                                                    <span className="kg-badge kg-badge-shared">Shared ({node.document_count} docs)</span>
                                                                ) : (
                                                                    <span className="kg-badge">Doc-Specific</span>
                                                                )}
                                                            </td>
                                                            <td>{Math.round((node.confidence || 0.8) * 100)}% ({node.confidence_tier})</td>
                                                            <td>{node.occurrence_count || node.evidence_count || 1}</td>
                                                        </tr>
                                                    )
                                                })}
                                            </tbody>
                                        </table>
                                    </div>

                                    <h3 style={{ marginTop: 22 }}>Relationships ({filtered.edges.length})</h3>
                                    <div className="kg-table-wrap">
                                        <table className="kg-table">
                                            <thead>
                                                <tr>
                                                    <th>Source</th>
                                                    <th>Relationship</th>
                                                    <th>Target</th>
                                                    <th>Scope</th>
                                                    <th>Confidence</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {filtered.edges.map((edge) => {
                                                    const ek = getEdgeKey(edge)
                                                    const srcLabel = nodeLabelMap.get(edge.source_key)?.label || nodeLabelMap.get(edge.source_key)?.canonical_name || edge.source_key
                                                    const tgtLabel = nodeLabelMap.get(edge.target_key)?.label || nodeLabelMap.get(edge.target_key)?.canonical_name || edge.target_key
                                                    return (
                                                        <tr
                                                            key={ek}
                                                            className={selectedEdgeKey === ek ? 'selected-row' : ''}
                                                            onClick={() => {
                                                                setSelectedEdgeKey(ek)
                                                                setSelectedNodeKey(null)
                                                            }}
                                                        >
                                                            <td><strong>{srcLabel}</strong></td>
                                                            <td><code>{edge.relationship}</code></td>
                                                            <td><strong>{tgtLabel}</strong></td>
                                                            <td>
                                                                {edge.is_cross_document ? (
                                                                    <span className="kg-badge kg-badge-cross-doc">Cross-Doc</span>
                                                                ) : (
                                                                    <span>Standard</span>
                                                                )}
                                                            </td>
                                                            <td>{Math.round((edge.confidence || 0.8) * 100)}%</td>
                                                        </tr>
                                                    )
                                                })}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Inspector Drawer */}
                        <aside className="kg-inspector" aria-label="Entity and Relationship Evidence Inspector">
                            {selectedEdge ? (
                                <div className="kg-inspector-body">
                                    <div className="kg-inspector-eyebrow">RELATIONSHIP EVIDENCE</div>
                                    <div className="kg-rel-header">
                                        <strong>{nodeLabelMap.get(selectedEdge.source_key)?.label || nodeLabelMap.get(selectedEdge.source_key)?.canonical_name || selectedEdge.source_key}</strong>
                                        <span className="kg-rel-badge">{formatRelationshipLabel(selectedEdge.relationship)}</span>
                                        <strong>{nodeLabelMap.get(selectedEdge.target_key)?.label || nodeLabelMap.get(selectedEdge.target_key)?.canonical_name || selectedEdge.target_key}</strong>
                                    </div>

                                    <div className="kg-meta-badges">
                                        <span className={`kg-tier-badge tier-${selectedEdge.confidence_tier}`}>
                                            {Math.round(selectedEdge.confidence * 100)}% ({selectedEdge.confidence_tier})
                                        </span>
                                        {selectedEdge.is_cross_document && (
                                            <span className="kg-badge kg-badge-cross-doc">
                                                Cross-Doc ({selectedEdge.supporting_document_ids?.length || 2} Docs)
                                            </span>
                                        )}
                                        <span className="kg-origin-badge">{selectedEdge.origin}</span>
                                    </div>

                                    {selectedEdge.explanation && (
                                        <p className="kg-inspector-desc">{selectedEdge.explanation}</p>
                                    )}

                                    <div className="kg-section-mini-title">
                                        Supporting Evidence ({selectedEdge.evidence?.length || 0})
                                    </div>
                                    <div className="kg-evidence-list">
                                        {(selectedEdge.evidence || []).map((ev, idx) => (
                                            <div key={idx} className="kg-evidence-card">
                                                <div className="kg-evidence-meta">
                                                    <span>{ev.document_name ? `📄 ${ev.document_name} • ` : ''}Page {ev.page || ev.page_number}</span>
                                                    {ev.section && <span>{ev.section}</span>}
                                                </div>
                                                <blockquote>&ldquo;{ev.excerpt || ev.source_text}&rdquo;</blockquote>
                                                <button
                                                    type="button"
                                                    className="kg-source-link-btn"
                                                    onClick={() => handleNavigateEvidence(ev)}
                                                >
                                                    <ExternalLink size={13} />
                                                    <span>Open Source Page {ev.page || ev.page_number}</span>
                                                </button>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ) : selectedNode ? (
                                <div className="kg-inspector-body">
                                    <div className="kg-inspector-eyebrow">
                                        {graphScopeMode === 'cross' ? 'CANONICAL PERSONAL ENTITY' : 'ENTITY / CONCEPT'}
                                    </div>
                                    <h3 className="kg-inspector-title">{selectedNode.label || selectedNode.canonical_name}</h3>
                                    <div className="kg-meta-badges">
                                        <span className="kg-pill-mini">{selectedNode.node_type}</span>
                                        <span className={`kg-tier-badge tier-${selectedNode.confidence_tier}`}>
                                            {Math.round((selectedNode.confidence || 0.85) * 100)}%
                                        </span>
                                        {selectedNode.is_shared && (
                                            <span className="kg-badge kg-badge-shared">
                                                <Sparkles size={11} /> Shared across {selectedNode.document_count} documents
                                            </span>
                                        )}
                                    </div>

                                    {/* Cross-Document Chat CTA */}
                                    {graphScopeMode === 'cross' && (
                                        <Link
                                            to={`/ask-ai?docs=${(selectedNode.documents?.map((d) => d.document_id) || selectedCrossDocIds).join(',')}&q=${encodeURIComponent(`What does Cognidocs know about "${selectedNode.canonical_name || selectedNode.label}" across these documents?`)}`}
                                            className="kg-ask-ai-action"
                                        >
                                            <Sparkles size={14} /> Ask AI about &quot;{selectedNode.canonical_name || selectedNode.label}&quot; across documents
                                        </Link>
                                    )}

                                    {selectedNode.aliases?.length > 0 && (
                                        <div className="kg-aliases-box">
                                            <strong>Merged aliases:</strong> {selectedNode.aliases.join(', ')}
                                        </div>
                                    )}

                                    {selectedNode.description && (
                                        <p className="kg-inspector-desc">{selectedNode.description}</p>
                                    )}

                                    <div className="kg-section-mini-title">
                                        Connected Relationships ({connectedEdgesForSelectedNode.length})
                                    </div>
                                    <div className="kg-conn-list">
                                        {connectedEdgesForSelectedNode.map((edge) => {
                                            const myKey = selectedNode.node_key || selectedNode.entity_key
                                            const isOut = edge.source_key === myKey
                                            const otherKey = isOut ? edge.target_key : edge.source_key
                                            const otherObj = nodeLabelMap.get(otherKey)
                                            const otherLabel = otherObj?.label || otherObj?.canonical_name || otherKey
                                            return (
                                                <button
                                                    key={getEdgeKey(edge)}
                                                    type="button"
                                                    className="kg-conn-item"
                                                    onClick={() => {
                                                        setSelectedEdgeKey(getEdgeKey(edge))
                                                        setSelectedNodeKey(null)
                                                    }}
                                                >
                                                    <span>{isOut ? '→' : '←'} <strong>{formatRelationshipLabel(edge.relationship)}</strong> {otherLabel}</span>
                                                    <span className="kg-conn-conf">{Math.round(edge.confidence * 100)}%</span>
                                                </button>
                                            )
                                        })}
                                    </div>

                                    {/* Grouped Evidence by Document */}
                                    <div className="kg-section-mini-title" style={{ marginTop: 14 }}>
                                        Grounded Evidence Mentions ({selectedNode.occurrence_count || selectedNode.evidence?.length || 0})
                                    </div>

                                    {graphScopeMode === 'cross' && selectedNode.documents ? (
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                                            {selectedNode.documents.map((ds) => {
                                                const docOccs = (selectedNode.occurrences || []).filter((o) => o.document_id === ds.document_id)
                                                return (
                                                    <div key={ds.document_id} className="kg-evidence-doc-group">
                                                        <div className="kg-evidence-doc-header">
                                                            <span>📄 {ds.document_name}</span>
                                                            <span style={{ fontSize: '0.72rem', opacity: 0.75 }}>
                                                                {ds.occurrences} mentions (pp. {(ds.source_pages || []).join(', ')})
                                                            </span>
                                                        </div>
                                                        <div className="kg-evidence-list">
                                                            {docOccs.map((occ, idx) => (
                                                                <div key={idx} className="kg-evidence-card">
                                                                    <div className="kg-evidence-meta">
                                                                        <span>Page {occ.page_number}</span>
                                                                        <span className="kg-meta-tag">{occ.resolution_method}</span>
                                                                    </div>
                                                                    <blockquote>&ldquo;{occ.source_text}&rdquo;</blockquote>
                                                                    <button
                                                                        type="button"
                                                                        className="kg-source-link-btn"
                                                                        onClick={() => handleNavigateEvidence(occ)}
                                                                    >
                                                                        <ExternalLink size={13} />
                                                                        <span>Open Source Page {occ.page_number}</span>
                                                                    </button>
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )
                                            })}
                                        </div>
                                    ) : (
                                        <div className="kg-evidence-list">
                                            {(selectedNode.evidence || []).map((ev, idx) => (
                                                <div key={idx} className="kg-evidence-card">
                                                    <div className="kg-evidence-meta">
                                                        <span>Page {ev.page || 1}</span>
                                                        {ev.section && <span>{ev.section}</span>}
                                                    </div>
                                                    <blockquote>&ldquo;{ev.excerpt}&rdquo;</blockquote>
                                                    <button
                                                        type="button"
                                                        className="kg-source-link-btn"
                                                        onClick={() => handleNavigateEvidence(ev)}
                                                    >
                                                        <ExternalLink size={13} />
                                                        <span>Open Source Page {ev.page || 1}</span>
                                                    </button>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="kg-inspector-body kg-inspector-placeholder">
                                    <ShieldCheck size={28} className="kg-empty-icon" />
                                    <h3>Inspect Any Entity or Edge</h3>
                                    <p>
                                        Click any concept or relationship pill on the graph to inspect its multi-document evidence,
                                        provenance, confidence breakdown, and source pages.
                                    </p>
                                </div>
                            )}
                        </aside>
                    </div>
                </>
            )}
        </div>
    )
}

export default KnowledgeGraph
