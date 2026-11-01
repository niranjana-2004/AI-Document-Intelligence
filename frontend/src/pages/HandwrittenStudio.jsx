import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
    ArrowLeft,
    ChevronLeft,
    ChevronRight,
    ZoomIn,
    ZoomOut,
    RotateCcw,
    Sliders,
    Sparkles,
    FileText,
    BrainCircuit,
    HelpCircle,
    CheckCircle2,
    Layers,
    PenTool
} from 'lucide-react'
import { apiRequest, API_BASE_URL } from '../services/api'
import PageTransition from '../components/motion/PageTransition'
import '../styles/handwritten.css'

export default function HandwrittenStudio() {
    const { documentId } = useParams()

    const [document, setDocument] = useState(null)
    const [pages, setPages] = useState([])
    const [currentPageIndex, setCurrentPageIndex] = useState(0)
    const [viewMode, setViewMode] = useState('processed') // 'processed' | 'original'
    const [zoomLevel, setZoomLevel] = useState(1.0)
    const [activeTab, setActiveTab] = useState('enhancement') // 'enhancement' | 'transcription' | 'summary' | 'quiz'

    const [imageBlobUrl, setImageBlobUrl] = useState(null)
    const [loadingImage, setLoadingImage] = useState(true)
    const [loadingDoc, setLoadingDoc] = useState(true)
    const [error, setError] = useState(null)

    // 1. Fetch document and page metadata
    useEffect(() => {
        let isMounted = true

        const fetchDetails = async () => {
            try {
                setLoadingDoc(true)
                const docData = await apiRequest(`/handwritten/${documentId}`)
                if (!isMounted) return

                setDocument(docData)
                setPages(docData?.pages || [])
                setError(null)
            } catch (err) {
                if (isMounted) setError(err.message || 'Failed to load document details.')
            } finally {
                if (isMounted) setLoadingDoc(false)
            }
        }

        fetchDetails()
        return () => { isMounted = false }
    }, [documentId])

    // 2. Load page image securely as Blob with JWT token
    const currentPage = pages[currentPageIndex] || null

    useEffect(() => {
        if (!currentPage) return
        let objectUrl = null

        const loadImage = async () => {
            try {
                setLoadingImage(true)
                const token = localStorage.getItem('access_token')
                const imgEndpoint = `/handwritten/${documentId}/pages/${currentPage.page_number}/image?version=${viewMode}`
                
                const res = await fetch(`${API_BASE_URL}${imgEndpoint}`, {
                    headers: token ? { Authorization: `Bearer ${token}` } : {}
                })

                if (!res.ok) throw new Error('Failed to load image from server.')

                const blob = await res.blob()
                objectUrl = URL.createObjectURL(blob)
                setImageBlobUrl(objectUrl)
            } catch (err) {
                console.error('Image load error:', err)
            } finally {
                setLoadingImage(false)
            }
        }

        loadImage()

        return () => {
            if (objectUrl) URL.revokeObjectURL(objectUrl)
        }
    }, [documentId, currentPageIndex, viewMode, currentPage])

    const handlePrevPage = () => {
        if (currentPageIndex > 0) setCurrentPageIndex(prev => prev - 1)
    }

    const handleNextPage = () => {
        if (currentPageIndex < pages.length - 1) setCurrentPageIndex(prev => prev + 1)
    }

    const handleZoomIn = () => setZoomLevel(prev => Math.min(prev + 0.25, 2.5))
    const handleZoomOut = () => setZoomLevel(prev => Math.max(prev - 0.25, 0.5))
    const handleResetZoom = () => setZoomLevel(1.0)

    if (loadingDoc) {
        return (
            <div style={{ textAlign: 'center', padding: '100px 24px', color: 'var(--text-muted)' }}>
                <p>Loading Handwritten Document Studio...</p>
            </div>
        )
    }

    if (error || !document) {
        return (
            <div style={{ textAlign: 'center', padding: '100px 24px', color: '#f87171' }}>
                <p>{error || 'Document not found.'}</p>
                <Link to="/handwritten" className="btn-open-studio" style={{ marginTop: '16px' }}>
                    <ArrowLeft size={16} />
                    <span>Return to Library</span>
                </Link>
            </div>
        )
    }

    return (
        <PageTransition>
            <div className="studio-container">
                {/* Topbar */}
                <header className="studio-topbar">
                    <div className="studio-topbar-left">
                        <Link to="/handwritten" className="btn-back-nav">
                            <ArrowLeft size={16} />
                            <span>Notes Library</span>
                        </Link>
                        <h2 className="studio-doc-title" title={document.filename}>
                            {document.filename}
                        </h2>
                    </div>

                    {/* Pagination */}
                    {pages.length > 0 && (
                        <div className="studio-pagination">
                            <button
                                type="button"
                                className="page-stepper-btn"
                                onClick={handlePrevPage}
                                disabled={currentPageIndex === 0}
                                title="Previous page"
                            >
                                <ChevronLeft size={18} />
                            </button>
                            <span className="page-counter-pill">
                                Page {currentPageIndex + 1} of {pages.length}
                            </span>
                            <button
                                type="button"
                                className="page-stepper-btn"
                                onClick={handleNextPage}
                                disabled={currentPageIndex === pages.length - 1}
                                title="Next page"
                            >
                                <ChevronRight size={18} />
                            </button>
                        </div>
                    )}

                    {/* Switcher: Enhanced vs Original */}
                    <div className="view-switcher">
                        <button
                            type="button"
                            className={`view-switch-btn ${viewMode === 'processed' ? 'active' : ''}`}
                            onClick={() => setViewMode('processed')}
                        >
                            Enhanced
                        </button>
                        <button
                            type="button"
                            className={`view-switch-btn ${viewMode === 'original' ? 'active' : ''}`}
                            onClick={() => setViewMode('original')}
                        >
                            Original Scan
                        </button>
                    </div>
                </header>

                {/* Dual-Pane Layout */}
                <div className="studio-dual-pane">
                    {/* LEFT PANE: Image Viewer */}
                    <div className="studio-viewer-pane">
                        <div className="viewer-toolbar">
                            <div className="viewer-controls">
                                <button
                                    type="button"
                                    className="viewer-tool-btn"
                                    onClick={handleZoomIn}
                                    title="Zoom In"
                                >
                                    <ZoomIn size={16} />
                                </button>
                                <button
                                    type="button"
                                    className="viewer-tool-btn"
                                    onClick={handleZoomOut}
                                    title="Zoom Out"
                                >
                                    <ZoomOut size={16} />
                                </button>
                                <button
                                    type="button"
                                    className="viewer-tool-btn"
                                    onClick={handleResetZoom}
                                    title="Reset Zoom"
                                >
                                    <RotateCcw size={16} />
                                </button>
                            </div>

                            <span style={{ fontSize: '12px', color: '#94a3b8' }}>
                                Zoom: {Math.round(zoomLevel * 100)}%
                            </span>
                        </div>

                        <div className="viewer-canvas-scroll">
                            {loadingImage ? (
                                <p style={{ color: '#64748b', fontSize: '13px' }}>Rendering page image...</p>
                            ) : imageBlobUrl ? (
                                <img
                                    src={imageBlobUrl}
                                    alt={`Page ${currentPageIndex + 1}`}
                                    className="viewer-image"
                                    style={{ transform: `scale(${zoomLevel})` }}
                                />
                            ) : (
                                <p style={{ color: '#64748b', fontSize: '13px' }}>No image preview available</p>
                            )}
                        </div>
                    </div>

                    {/* RIGHT PANE: Multi-Tab Workspace */}
                    <div className="studio-workspace-pane">
                        <div className="workspace-tabs-header">
                            <button
                                type="button"
                                className={`workspace-tab-btn ${activeTab === 'enhancement' ? 'active' : ''}`}
                                onClick={() => setActiveTab('enhancement')}
                            >
                                <Sliders size={16} />
                                <span>Image Preprocessing</span>
                            </button>
                            <button
                                type="button"
                                className={`workspace-tab-btn ${activeTab === 'transcription' ? 'active' : ''}`}
                                onClick={() => setActiveTab('transcription')}
                            >
                                <PenTool size={16} />
                                <span>Transcription (Phase 2)</span>
                            </button>
                            <button
                                type="button"
                                className={`workspace-tab-btn ${activeTab === 'summary' ? 'active' : ''}`}
                                onClick={() => setActiveTab('summary')}
                            >
                                <FileText size={16} />
                                <span>Study Summary (Phase 3)</span>
                            </button>
                            <button
                                type="button"
                                className={`workspace-tab-btn ${activeTab === 'quiz' ? 'active' : ''}`}
                                onClick={() => setActiveTab('quiz')}
                            >
                                <BrainCircuit size={16} />
                                <span>Quiz & Flashcards (Phase 7)</span>
                            </button>
                        </div>

                        <div className="workspace-tab-content">
                            {activeTab === 'enhancement' && (
                                <div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                                        <CheckCircle2 size={18} style={{ color: '#10b981' }} />
                                        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>
                                            Computer Vision Preprocessing Applied
                                        </h3>
                                    </div>
                                    <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '24px' }}>
                                        This page has undergone automated multi-stage enhancement using OpenCV to optimize contrast and stroke sharpness before feeding into the OCR line detector.
                                    </p>

                                    <div className="pipeline-step-card">
                                        <div className="pipeline-step-icon">
                                            <RotateCcw size={18} />
                                        </div>
                                        <div className="pipeline-step-body">
                                            <h4>Automated Deskewing</h4>
                                            <p>Text orientation was analyzed via minAreaRect contours, and affine rotation was applied to straighten tilted handwriting lines.</p>
                                        </div>
                                    </div>

                                    <div className="pipeline-step-card">
                                        <div className="pipeline-step-icon">
                                            <Sliders size={18} />
                                        </div>
                                        <div className="pipeline-step-body">
                                            <h4>CLAHE Contrast Enhancement</h4>
                                            <p>Contrast Limited Adaptive Histogram Equalization amplified faint pencil and pale ink strokes without blowing out document highlights.</p>
                                        </div>
                                    </div>

                                    <div className="pipeline-step-card">
                                        <div className="pipeline-step-icon">
                                            <Layers size={18} />
                                        </div>
                                        <div className="pipeline-step-body">
                                            <h4>Shadow & Denoising Filter</h4>
                                            <p>Background illumination division neutralized mobile camera shadows, and bilateral filtering smoothed paper textures while preserving stroke edges.</p>
                                        </div>
                                    </div>

                                    <div style={{ marginTop: '24px', padding: '16px', borderRadius: '12px', background: 'rgba(139, 92, 246, 0.08)', border: '1px solid rgba(139, 92, 246, 0.25)' }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', color: '#c084fc', fontWeight: 600, fontSize: '13px' }}>
                                            <Sparkles size={16} />
                                            <span>Ready for Phase 2: OCR Recognition</span>
                                        </div>
                                        <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                                            The preprocessed page is ready for line-level handwriting extraction with TrOCR-small and mathematical LaTeX conversion.
                                        </p>
                                    </div>
                                </div>
                            )}

                            {activeTab === 'transcription' && (
                                <div style={{ textAlign: 'center', padding: '40px 16px', color: 'var(--text-secondary)' }}>
                                    <PenTool size={36} style={{ color: '#8b5cf6', margin: '0 auto 16px' }} />
                                    <h4 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)', fontSize: '16px' }}>
                                        Transcription Studio (Phase 2)
                                    </h4>
                                    <p style={{ fontSize: '13px', maxWidth: '380px', margin: '0 auto' }}>
                                        In Phase 2, this workspace will display side-by-side editable transcription text with confidence scores and mathematical formula previews.
                                    </p>
                                </div>
                            )}

                            {activeTab === 'summary' && (
                                <div style={{ textAlign: 'center', padding: '40px 16px', color: 'var(--text-secondary)' }}>
                                    <FileText size={36} style={{ color: '#38bdf8', margin: '0 auto 16px' }} />
                                    <h4 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)', fontSize: '16px' }}>
                                        Study Summaries (Phase 3)
                                    </h4>
                                    <p style={{ fontSize: '13px', maxWidth: '380px', margin: '0 auto' }}>
                                        Extract key concepts, bulleted takeaways, and lecture overviews powered by local Llama 3.2.
                                    </p>
                                </div>
                            )}

                            {activeTab === 'quiz' && (
                                <div style={{ textAlign: 'center', padding: '40px 16px', color: 'var(--text-secondary)' }}>
                                    <BrainCircuit size={36} style={{ color: '#a855f7', margin: '0 auto 16px' }} />
                                    <h4 style={{ margin: '0 0 8px 0', color: 'var(--text-primary)', fontSize: '16px' }}>
                                        Interactive Study Suite (Phase 7)
                                    </h4>
                                    <p style={{ fontSize: '13px', maxWidth: '380px', margin: '0 auto' }}>
                                        Generate interactive multiple-choice quizzes and 3D flip flashcards directly derived from these handwritten lecture notes.
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </PageTransition>
    )
}

