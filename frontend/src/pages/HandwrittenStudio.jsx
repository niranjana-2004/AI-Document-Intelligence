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
    ListFilter,
    MessageSquare,
    GraduationCap,
    ChevronDown,
    ChevronUp,
    CheckCheck,
    X,
    Layout,
    Edit3
} from 'lucide-react'
import { apiRequest, API_BASE_URL } from '../services/api'
import PageTransition from '../components/motion/PageTransition'
import VisualPreprocessingStudio from '../components/handwritten/VisualPreprocessingStudio'
import HandwrittenSummaryTab from '../components/handwritten/HandwrittenSummaryTab'
import HandwrittenConceptsTab from '../components/handwritten/HandwrittenConceptsTab'
import HandwrittenQuizTab from '../components/handwritten/HandwrittenQuizTab'
import HandwrittenFlashcardsTab from '../components/handwritten/HandwrittenFlashcardsTab'
import HandwrittenChatTab from '../components/handwritten/HandwrittenChatTab'
import AIHealthIndicator from '../components/handwritten/AIHealthIndicator'
import '../styles/handwritten.css'

export default function HandwrittenStudio() {
    const { documentId } = useParams()

    const [document, setDocument] = useState(null)
    const [pages, setPages] = useState([])
    const [currentPageIndex, setCurrentPageIndex] = useState(0)
    const [viewMode, setViewMode] = useState('processed') // 'processed' | 'original'
    const [zoomLevel, setZoomLevel] = useState(1.0)
    const [activeTab, setActiveTab] = useState('transcription') // 'transcription' | 'enhancement' | 'summary' | 'concepts' | 'quiz' | 'flashcards' | 'chat'
    const [transcriptionUpdated, setTranscriptionUpdated] = useState(Date.now())

    // Transcription editor states
    const [transcriptionText, setTranscriptionText] = useState('')
    const [isSaving, setIsSaving] = useState(false)
    const [saveSuccess, setSaveSuccess] = useState(false)
    const [copied, setCopied] = useState(false)
    const [isOcrProcessing, setIsOcrProcessing] = useState(false)
    const [reprocessingLineId, setReprocessingLineId] = useState(null)
    const [showLineBreakdown, setShowLineBreakdown] = useState(false)
    const [transcriptionDisplayMode, setTranscriptionDisplayMode] = useState('formatted') // 'formatted' | 'editor'

    // Subject states
    const [subjectDropdownOpen, setSubjectDropdownOpen] = useState(false)
    const [isDetectingSubject, setIsDetectingSubject] = useState(false)

    // Technical OCR Review states
    const [reviewOpen, setReviewOpen] = useState(false)
    const [reviewingCorrId, setReviewingCorrId] = useState(null)

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
            setTranscriptionUpdated(Date.now())
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
            setTranscriptionUpdated(Date.now())
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
                setTranscriptionUpdated(Date.now())
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

    // Subject management handlers
    const handleSelectSubject = async (newSubject) => {
        try {
            setSubjectDropdownOpen(false)
            setDocument(prev => prev ? { ...prev, subject: newSubject } : prev)
            await apiRequest(`/handwritten/${documentId}/subject`, {
                method: 'PATCH',
                body: JSON.stringify({ subject: newSubject })
            })
        } catch (err) {
            console.error('Failed to update subject:', err)
        }
    }

    const handleDetectSubject = async () => {
        try {
            setIsDetectingSubject(true)
            const res = await apiRequest(`/handwritten/${documentId}/subject/detect`, {
                method: 'POST'
            })
            if (res?.subject) {
                setDocument(prev => prev ? { ...prev, subject: res.subject } : prev)
            }
        } catch (err) {
            console.error('Failed to detect subject:', err)
        } finally {
            setIsDetectingSubject(false)
            setSubjectDropdownOpen(false)
        }
    }

    // Metrics
    const wordCount = transcriptionText.trim() ? transcriptionText.trim().split(/\s+/).length : 0
    const charCount = transcriptionText.length
    const confidence = currentPage?.confidence_score ?? null
    const confidenceRating = confidence >= 80 ? 'high' : confidence >= 60 ? 'medium' : 'low'
    const ocrLines = currentPage?.ocr_metadata?.lines || []
    const technicalCorrections = currentPage?.ocr_metadata?.technical_corrections || []
    const acceptedCount = technicalCorrections.filter(c => c.status === 'accepted').length
    const suggestedCount = technicalCorrections.filter(c => c.status === 'suggested').length

    const handleCorrectionAction = async (correctionId, action) => {
        if (!currentPage) return
        try {
            setReviewingCorrId(correctionId)
            const res = await apiRequest(`/handwritten/${documentId}/pages/${currentPage.page_number}/corrections/${correctionId}`, {
                method: 'PATCH',
                body: JSON.stringify({ action })
            })
            if (res && res.edited_transcription) {
                setTranscriptionText(res.edited_transcription)
                setPages(prev => prev.map((p, idx) => {
                    if (idx === currentPageIndex) {
                        const meta = { ...(p.ocr_metadata || {}) }
                        meta.technical_corrections = (meta.technical_corrections || []).map(c => 
                            c.id === correctionId ? { ...c, status: action === 'accept' ? 'accepted' : 'rejected' } : c
                        )
                        return { ...p, edited_transcription: res.edited_transcription, ocr_metadata: meta }
                    }
                    return p
                }))
                setTranscriptionUpdated(Date.now())
            }
        } catch (err) {
            console.error('Failed to update correction:', err)
        } finally {
            setReviewingCorrId(null)
        }
    }

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

                        {/* Interactive Subject Badge / Selector */}
                        <div className="studio-subject-wrapper">
                            <button
                                type="button"
                                className="studio-subject-btn"
                                onClick={() => setSubjectDropdownOpen(!subjectDropdownOpen)}
                                title="Click to view or change academic discipline"
                            >
                                <GraduationCap size={14} style={{ color: '#c084fc' }} />
                                <span>{document.subject || 'Humanities & General'}</span>
                                <ChevronDown size={13} style={{ opacity: 0.7 }} />
                            </button>

                            {subjectDropdownOpen && (
                                <div className="studio-subject-dropdown">
                                    <div className="studio-subject-dropdown-header">
                                        <span>Academic Discipline</span>
                                        <button
                                            type="button"
                                            onClick={handleDetectSubject}
                                            disabled={isDetectingSubject}
                                            style={{ background: 'transparent', border: 'none', color: '#c084fc', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '10px' }}
                                            title="Auto-detect subject with AI"
                                        >
                                            <Sparkles size={11} className={isDetectingSubject ? 'spin-icon' : ''} />
                                            <span>{isDetectingSubject ? 'Detecting...' : 'Auto-Detect'}</span>
                                        </button>
                                    </div>
                                    {(document.available_subjects || [
                                        'Computer Science & Networking',
                                        'Artificial Intelligence & Data Science',
                                        'Mathematics & Statistics',
                                        'Physics & Engineering',
                                        'Chemistry & Materials',
                                        'Biology & Life Sciences',
                                        'Economics & Business',
                                        'Humanities & General'
                                    ]).map((subj) => (
                                        <button
                                            key={subj}
                                            type="button"
                                            className={`studio-subject-item ${document.subject === subj ? 'active' : ''}`}
                                            onClick={() => handleSelectSubject(subj)}
                                        >
                                            <span>{subj}</span>
                                            {document.subject === subj && <Check size={13} style={{ color: '#c084fc' }} />}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
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

                    {/* Topbar Right Actions */}
                    <div className="studio-topbar-right">
                        <AIHealthIndicator />

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
                                <PenTool size={15} />
                                <span>Transcription</span>
                            </button>
                            <button
                                type="button"
                                className={`workspace-tab-btn ${activeTab === 'enhancement' ? 'active' : ''}`}
                                onClick={() => setActiveTab('enhancement')}
                            >
                                <Sliders size={15} />
                                <span>Preprocessing</span>
                            </button>
                            <button
                                type="button"
                                className={`workspace-tab-btn ${activeTab === 'summary' ? 'active' : ''}`}
                                onClick={() => setActiveTab('summary')}
                            >
                                <FileText size={15} />
                                <span>Study Summary</span>
                            </button>
                            <button
                                type="button"
                                className={`workspace-tab-btn ${activeTab === 'concepts' ? 'active' : ''}`}
                                onClick={() => setActiveTab('concepts')}
                            >
                                <Sparkles size={15} />
                                <span>Concepts</span>
                            </button>
                            <button
                                type="button"
                                className={`workspace-tab-btn ${activeTab === 'quiz' ? 'active' : ''}`}
                                onClick={() => setActiveTab('quiz')}
                            >
                                <BrainCircuit size={15} />
                                <span>AI Quiz</span>
                            </button>
                            <button
                                type="button"
                                className={`workspace-tab-btn ${activeTab === 'flashcards' ? 'active' : ''}`}
                                onClick={() => setActiveTab('flashcards')}
                            >
                                <Layers size={15} />
                                <span>Flashcards</span>
                            </button>
                            <button
                                type="button"
                                className={`workspace-tab-btn ${activeTab === 'chat' ? 'active' : ''}`}
                                onClick={() => setActiveTab('chat')}
                            >
                                <MessageSquare size={15} />
                                <span>Chat Notes</span>
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
                                            {/* Formatted vs Editor Mode Toggle */}
                                            <div style={{ display: 'flex', background: 'rgba(15, 23, 42, 0.7)', padding: '2px', borderRadius: '7px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
                                                <button
                                                    type="button"
                                                    style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '4px 9px', fontSize: '11px', fontWeight: 600, background: transcriptionDisplayMode === 'formatted' ? 'rgba(168, 85, 247, 0.25)' : 'transparent', color: transcriptionDisplayMode === 'formatted' ? '#d8b4fe' : '#94a3b8', border: 'none', borderRadius: '5px', cursor: 'pointer' }}
                                                    onClick={() => setTranscriptionDisplayMode('formatted')}
                                                    title="View formatted academic layout"
                                                >
                                                    <Layout size={12} />
                                                    <span>Formatted</span>
                                                </button>
                                                <button
                                                    type="button"
                                                    style={{ display: 'flex', alignItems: 'center', gap: '5px', padding: '4px 9px', fontSize: '11px', fontWeight: 600, background: transcriptionDisplayMode === 'editor' ? 'rgba(168, 85, 247, 0.25)' : 'transparent', color: transcriptionDisplayMode === 'editor' ? '#d8b4fe' : '#94a3b8', border: 'none', borderRadius: '5px', cursor: 'pointer' }}
                                                    onClick={() => setTranscriptionDisplayMode('editor')}
                                                    title="Edit transcription text"
                                                >
                                                    <Edit3 size={12} />
                                                    <span>Editor</span>
                                                </button>
                                            </div>

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

                                    {/* Technical OCR Recovery & Review Section */}
                                    {technicalCorrections.length > 0 && (
                                        <div className="technical-recovery-panel">
                                            <div 
                                                className="technical-recovery-header"
                                                onClick={() => setReviewOpen(prev => !prev)}
                                                title="Click to toggle Technical Terminology Review"
                                            >
                                                <div className="technical-recovery-title">
                                                    <Sparkles size={14} style={{ color: '#c084fc' }} />
                                                    <span>Technical Terminology Recovery</span>
                                                    <span className="recovery-badge-count">
                                                        {technicalCorrections.length} {technicalCorrections.length === 1 ? 'term' : 'terms'}
                                                        {acceptedCount > 0 ? ` (${acceptedCount} recovered)` : ''}
                                                    </span>
                                                </div>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                    <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                                                        {reviewOpen ? 'Hide' : 'Review Terms'}
                                                    </span>
                                                    {reviewOpen ? <ChevronUp size={14} color="#94a3b8" /> : <ChevronDown size={14} color="#94a3b8" />}
                                                </div>
                                            </div>

                                            {reviewOpen && (
                                                <div className="technical-recovery-body">
                                                    {technicalCorrections.map((corr) => (
                                                        <div key={corr.id} className="recovery-item-card">
                                                            <div className="recovery-item-left">
                                                                <div className="recovery-terms-comparison">
                                                                    <span className="recovery-raw-term" title="Raw OCR output">
                                                                        {corr.original_text}
                                                                    </span>
                                                                    <span style={{ color: '#64748b' }}>→</span>
                                                                    <span className="recovery-suggested-term" title="Domain-recovered term">
                                                                        {corr.suggested_text}
                                                                    </span>
                                                                    <span className={`recovery-status-pill ${corr.status}`}>
                                                                        {corr.status}
                                                                    </span>
                                                                    <span className="recovery-evidence-pill">
                                                                        {Math.round(corr.confidence * 100)}% evidence
                                                                    </span>
                                                                </div>
                                                                <div className="recovery-evidence-row">
                                                                    {(corr.evidence || []).map((ev, evIdx) => (
                                                                        <span key={evIdx} className="recovery-evidence-pill" title={ev}>
                                                                            {ev}
                                                                        </span>
                                                                    ))}
                                                                </div>
                                                            </div>

                                                            <div className="recovery-actions">
                                                                {corr.status !== 'accepted' && (
                                                                    <button
                                                                        type="button"
                                                                        className="btn-recovery-action btn-recovery-accept"
                                                                        onClick={() => handleCorrectionAction(corr.id, 'accept')}
                                                                        disabled={reviewingCorrId === corr.id}
                                                                        title="Accept this technical term recovery"
                                                                    >
                                                                        <Check size={11} />
                                                                        <span>Accept</span>
                                                                    </button>
                                                                )}
                                                                {corr.status !== 'rejected' && (
                                                                    <button
                                                                        type="button"
                                                                        className="btn-recovery-action btn-recovery-reject"
                                                                        onClick={() => handleCorrectionAction(corr.id, 'reject')}
                                                                        disabled={reviewingCorrId === corr.id}
                                                                        title="Reject or revert this suggestion"
                                                                    >
                                                                        <X size={11} />
                                                                        <span>{corr.status === 'accepted' ? 'Revert' : 'Reject'}</span>
                                                                    </button>
                                                                )}
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Content View: Formatted Layout View vs Raw Editor View */}
                                    {transcriptionDisplayMode === 'formatted' && currentPage?.ocr_metadata?.structured_layout?.blocks?.length > 0 ? (
                                        <div className="structured-doc-view">
                                            {currentPage.ocr_metadata.structured_layout.blocks.map((block) => (
                                                <div key={block.id} className="structured-block">
                                                    {block.type === 'title' && (
                                                        <h3 className="structured-block-title">
                                                            {block.text}
                                                            {block.confidence && (
                                                                <span className="uncertainty-pill" style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#c084fc', borderColor: 'rgba(168, 85, 247, 0.3)' }}>
                                                                    {block.confidence}%
                                                                </span>
                                                            )}
                                                        </h3>
                                                    )}
                                                    {block.type === 'heading' && (
                                                        <h4 className="structured-block-heading">
                                                            {block.text}
                                                            {block.confidence && (
                                                                <span className="uncertainty-pill" style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', borderColor: 'rgba(56, 189, 248, 0.3)' }}>
                                                                    {block.confidence}%
                                                                </span>
                                                            )}
                                                        </h4>
                                                    )}
                                                    {block.type === 'list' && (
                                                        <ul className="structured-block-list">
                                                            {(block.items || []).map((item, itemIdx) => (
                                                                <li key={itemIdx}>{item}</li>
                                                            ))}
                                                        </ul>
                                                    )}
                                                    {block.type === 'math' && (
                                                        <div className="structured-block-math">
                                                            {block.text}
                                                        </div>
                                                    )}
                                                    {block.type === 'paragraph' && (
                                                        <p className="structured-block-paragraph">
                                                            {block.text}
                                                            {block.confidence < 65 && (
                                                                <span className="uncertainty-pill" title="Low OCR confidence on this line">
                                                                    Uncertain ({block.confidence}%)
                                                                </span>
                                                            )}
                                                        </p>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
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
                                    )}

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
                                <HandwrittenSummaryTab
                                    documentId={documentId}
                                    transcriptionUpdated={transcriptionUpdated}
                                />
                            )}

                            {/* TAB 4: KEY CONCEPTS (PHASE 3) */}
                            {activeTab === 'concepts' && (
                                <HandwrittenConceptsTab
                                    documentId={documentId}
                                    transcriptionUpdated={transcriptionUpdated}
                                />
                            )}

                            {/* TAB 5: AI QUIZ GENERATOR (PHASE 3) */}
                            {activeTab === 'quiz' && (
                                <HandwrittenQuizTab
                                    documentId={documentId}
                                    transcriptionUpdated={transcriptionUpdated}
                                />
                            )}

                            {/* TAB 6: 3D FLASHCARDS (PHASE 3) */}
                            {activeTab === 'flashcards' && (
                                <HandwrittenFlashcardsTab
                                    documentId={documentId}
                                    transcriptionUpdated={transcriptionUpdated}
                                />
                            )}

                            {/* TAB 7: CHAT WITH NOTES (PHASE 3) */}
                            {activeTab === 'chat' && (
                                <HandwrittenChatTab
                                    documentId={documentId}
                                    transcriptionUpdated={transcriptionUpdated}
                                />
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </PageTransition>
    )
}
