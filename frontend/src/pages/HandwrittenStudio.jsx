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
    CheckCircle2,
    Layers,
    PenTool,
    Save,
    Copy,
    Check,
    RefreshCw,
    AlertTriangle,
    Eye,
    ListFilter
} from 'lucide-react'
import { apiRequest, API_BASE_URL } from '../services/api'
import PageTransition from '../components/motion/PageTransition'
import VisualPreprocessingStudio from '../components/handwritten/VisualPreprocessingStudio'
import '../styles/handwritten.css'

export default function HandwrittenStudio() {
    const { documentId } = useParams()

    const [document, setDocument] = useState(null)
    const [pages, setPages] = useState([])
    const [currentPageIndex, setCurrentPageIndex] = useState(0)
    const [viewMode, setViewMode] = useState('processed') // 'processed' | 'original'
    const [zoomLevel, setZoomLevel] = useState(1.0)
    const [activeTab, setActiveTab] = useState('transcription') // 'transcription' | 'enhancement' | 'summary' | 'quiz'

    // Transcription editor states
    const [transcriptionText, setTranscriptionText] = useState('')
    const [isSaving, setIsSaving] = useState(false)
    const [saveSuccess, setSaveSuccess] = useState(false)
    const [copied, setCopied] = useState(false)
    const [isOcrProcessing, setIsOcrProcessing] = useState(false)
    const [reprocessingLineId, setReprocessingLineId] = useState(null)
    const [showLineBreakdown, setShowLineBreakdown] = useState(false)

    // Image & Document Loading states
    const [imageBlobUrl, setImageBlobUrl] = useState(null)
    const [loadingImage, setLoadingImage] = useState(true)
    const [loadingDoc, setLoadingDoc] = useState(true)
    const [error, setError] = useState(null)

    // 1. Fetch document and page metadata
    const fetchDetails = async () => {
        try {
            setLoadingDoc(true)
            const docData = await apiRequest(`/handwritten/${documentId}`)
            setDocument(docData)
            const docPages = docData?.pages || []
            setPages(docPages)

            if (docPages.length > 0 && docPages[currentPageIndex]) {
                const current = docPages[currentPageIndex]
                setTranscriptionText(current.edited_transcription || current.raw_transcription || '')
            }
            setError(null)
        } catch (err) {
            setError(err.message || 'Failed to load document details.')
        } finally {
            setLoadingDoc(false)
        }
    }

    useEffect(() => {
        fetchDetails()
    }, [documentId])

    // 2. Synchronize transcription text when active page changes
    const currentPage = pages[currentPageIndex] || null

    useEffect(() => {
        if (currentPage) {
            setTranscriptionText(currentPage.edited_transcription || currentPage.raw_transcription || '')
            setSaveSuccess(false)
        }
    }, [currentPageIndex, pages])

    // 3. Load page image securely as Blob with JWT token
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
    }, [documentId, currentPageIndex, viewMode, currentPage?.page_number])

    // Navigation handlers
    const handlePrevPage = () => {
        if (currentPageIndex > 0) setCurrentPageIndex(prev => prev - 1)
    }

    const handleNextPage = () => {
        if (currentPageIndex < pages.length - 1) setCurrentPageIndex(prev => prev + 1)
    }

    const handleZoomIn = () => setZoomLevel(prev => Math.min(prev + 0.25, 2.5))
    const handleZoomOut = () => setZoomLevel(prev => Math.max(prev - 0.25, 0.5))
    const handleResetZoom = () => setZoomLevel(1.0)

    // Save transcription correction
    const handleSaveTranscription = async () => {
        if (!currentPage) return
        try {
            setIsSaving(true)
            const res = await apiRequest(`/handwritten/${documentId}/pages/${currentPage.page_number}/transcription`, {
                method: 'PUT',
                body: JSON.stringify({ transcription: transcriptionText })
            })

            // Update local page state
            setPages(prev => prev.map((p, idx) => {
                if (idx === currentPageIndex) {
                    return { ...p, edited_transcription: transcriptionText }
                }
                return p
            }))

            setSaveSuccess(true)
            setTimeout(() => setSaveSuccess(false), 2500)
        } catch (err) {
            alert(err.message || 'Failed to save transcription.')
        } finally {
            setIsSaving(false)
        }
    }

    // Run OCR for current page or all pages
    const handleRunOcr = async (allPages = false) => {
        if (!currentPage) return
        try {
            setIsOcrProcessing(true)
            if (allPages) {
                await apiRequest(`/handwritten/${documentId}/ocr`, { method: 'POST' })
            } else {
                await apiRequest(`/handwritten/${documentId}/pages/${currentPage.page_number}/ocr`, { method: 'POST' })
            }
            await fetchDetails()
        } catch (err) {
            alert(err.message || 'OCR processing failed.')
        } finally {
            setIsOcrProcessing(false)
        }
    }

    // Reprocess a single line
    const handleReprocessLine = async (lineIndex) => {
        if (!currentPage) return
        try {
            setReprocessingLineId(lineIndex)
            const res = await apiRequest(`/handwritten/${documentId}/pages/${currentPage.page_number}/lines/${lineIndex}/ocr`, {
                method: 'POST'
            })
            if (res && res.text !== undefined) {
                setPages(prev => prev.map((p, idx) => {
                    if (idx === currentPageIndex) {
                        const updatedLines = (p.ocr_metadata?.lines || []).map(l =>
                            l.line_index === lineIndex
                                ? { ...l, text: res.text, confidence: res.confidence, is_uncertain: res.confidence < 60 }
                                : l
                        )
                        return {
                            ...p,
                            confidence_score: res.page_confidence,
                            edited_transcription: res.full_transcription,
                            raw_transcription: res.full_transcription,
                            ocr_metadata: { ...p.ocr_metadata, lines: updatedLines }
                        }
                    }
                    return p
                }))
                setTranscriptionText(res.full_transcription)
            }
        } catch (err) {
            alert(err.message || `Failed to reprocess line ${lineIndex}.`)
        } finally {
            setReprocessingLineId(null)
        }
    }

    // Copy to clipboard
    const handleCopy = () => {
        if (!transcriptionText) return
        navigator.clipboard.writeText(transcriptionText)
        setCopied(true)
        setTimeout(() => setCopied(false), 2000)
    }

    // Metrics
    const wordCount = transcriptionText.trim() ? transcriptionText.trim().split(/\s+/).length : 0
    const charCount = transcriptionText.length
    const confidence = currentPage?.confidence_score ?? null
    const confidenceRating = confidence >= 80 ? 'high' : confidence >= 60 ? 'medium' : 'low'
    const ocrLines = currentPage?.ocr_metadata?.lines || []

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
                                className={`workspace-tab-btn ${activeTab === 'transcription' ? 'active' : ''}`}
                                onClick={() => setActiveTab('transcription')}
                            >
                                <PenTool size={16} />
                                <span>Digital Transcription</span>
                            </button>
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
                            {/* TAB 1: DIGITAL TRANSCRIPTION (PHASE 2) */}
                            {activeTab === 'transcription' && (
                                <div className="transcription-editor-box">
                                    <div className="transcription-toolbar">
                                        <div className="transcription-meta-group">
                                            {confidence !== null ? (
                                                <span className={`confidence-indicator-pill ${confidenceRating}`}>
                                                    <CheckCircle2 size={12} />
                                                    <span>{confidence}% Confidence</span>
                                                </span>
                                            ) : (
                                                <span className="confidence-indicator-pill medium">
                                                    <AlertTriangle size={12} />
                                                    <span>Pending OCR</span>
                                                </span>
                                            )}
                                            <span className="transcription-stat-pill">
                                                {wordCount} {wordCount === 1 ? 'word' : 'words'}
                                            </span>
                                            <span className="transcription-stat-pill">
                                                {charCount} chars
                                            </span>
                                        </div>

                                        <div className="transcription-actions-group">
                                            <button
                                                type="button"
                                                className="btn-studio-action"
                                                onClick={() => handleRunOcr(false)}
                                                disabled={isOcrProcessing}
                                                title="Re-run TrOCR on this page"
                                            >
                                                <RefreshCw size={13} className={isOcrProcessing ? 'spin-icon' : ''} />
                                                <span>{isOcrProcessing ? 'Extracting...' : 'Run OCR'}</span>
                                            </button>

                                            <button
                                                type="button"
                                                className="btn-studio-action"
                                                onClick={handleCopy}
                                                disabled={!transcriptionText}
                                                title="Copy transcription text"
                                            >
                                                {copied ? <Check size={13} style={{ color: '#34d399' }} /> : <Copy size={13} />}
                                                <span>{copied ? 'Copied!' : 'Copy'}</span>
                                            </button>

                                            <button
                                                type="button"
                                                className={`btn-studio-action btn-studio-primary ${saveSuccess ? 'btn-studio-saved' : ''}`}
                                                onClick={handleSaveTranscription}
                                                disabled={isSaving}
                                            >
                                                {saveSuccess ? (
                                                    <>
                                                        <Check size={14} />
                                                        <span>Saved!</span>
                                                    </>
                                                ) : (
                                                    <>
                                                        <Save size={14} />
                                                        <span>{isSaving ? 'Saving...' : 'Save Changes'}</span>
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    </div>

                                    {/* Editable Text Area */}
                                    <textarea
                                        className="transcription-textarea"
                                        value={transcriptionText}
                                        onChange={(e) => setTranscriptionText(e.target.value)}
                                        placeholder={
                                            isOcrProcessing
                                                ? "Analyzing handwriting lines with TrOCR small... Please wait a moment."
                                                : "Recognized transcription will appear here. Click 'Run OCR' above to extract handwriting, or type directly to edit."
                                        }
                                        rows={12}
                                    />

                                    {/* Line Breakdown Toggle */}
                                    {ocrLines.length > 0 && (
                                        <div className="transcription-lines-panel">
                                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                                                <h4 style={{ margin: 0, fontSize: '13px', fontWeight: 700, color: 'var(--text-secondary)' }}>
                                                    Detected Lines ({ocrLines.length})
                                                </h4>
                                                <button
                                                    type="button"
                                                    onClick={() => setShowLineBreakdown(!showLineBreakdown)}
                                                    style={{ background: 'transparent', border: 'none', color: '#c084fc', fontSize: '12px', cursor: 'pointer' }}
                                                >
                                                    {showLineBreakdown ? 'Hide Details' : 'Show Line Confidences'}
                                                </button>
                                            </div>

                                            {showLineBreakdown && (
                                                <div>
                                                    {ocrLines.map((line) => (
                                                        <div
                                                            key={line.line_index}
                                                            className={`line-item-card ${line.is_uncertain ? 'uncertain' : ''}`}
                                                        >
                                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '36px' }}>
                                                                <span className="line-number-tag">L{line.line_index}</span>
                                                            </div>
                                                            <div style={{ flex: 1, minWidth: 0 }}>
                                                                <span className="line-text-display">{line.text || '(empty stroke)'}</span>
                                                                {line.bbox && (
                                                                    <span style={{ display: 'block', fontSize: '10px', color: '#64748b', marginTop: '2px', fontFamily: 'monospace' }}>
                                                                        [x:{line.bbox[0]}, y:{line.bbox[1]}, {line.bbox[2]}×{line.bbox[3]}px]
                                                                    </span>
                                                                )}
                                                            </div>
                                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                                <span
                                                                    className="line-conf-badge"
                                                                    style={{
                                                                        background: line.confidence >= 80 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                                                                        color: line.confidence >= 80 ? '#34d399' : '#fbbf24'
                                                                    }}
                                                                >
                                                                    {line.confidence}%
                                                                </span>
                                                                <button
                                                                    type="button"
                                                                    onClick={() => handleReprocessLine(line.line_index)}
                                                                    disabled={reprocessingLineId === line.line_index}
                                                                    title="Reprocess this line with TrOCR"
                                                                    style={{
                                                                        background: 'rgba(255,255,255,0.06)',
                                                                        border: '1px solid rgba(255,255,255,0.1)',
                                                                        borderRadius: '4px',
                                                                        color: '#c084fc',
                                                                        padding: '4px 6px',
                                                                        cursor: 'pointer',
                                                                        display: 'flex',
                                                                        alignItems: 'center'
                                                                    }}
                                                                >
                                                                    <RefreshCw size={11} className={reprocessingLineId === line.line_index ? 'spin-icon' : ''} />
                                                                </button>
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* TAB 2: IMAGE PREPROCESSING (VISUAL PREPROCESSING STUDIO) */}
                            {activeTab === 'enhancement' && (
                                <VisualPreprocessingStudio
                                    documentId={documentId}
                                    pageNumber={currentPage?.page_number || (currentPageIndex + 1)}
                                />
                            )}

                            {/* TAB 3: STUDY SUMMARY (PHASE 3) */}
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

                            {/* TAB 4: QUIZ & FLASHCARDS (PHASE 7) */}
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
