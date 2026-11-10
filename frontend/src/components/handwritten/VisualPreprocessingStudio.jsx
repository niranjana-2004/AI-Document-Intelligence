import { useState, useEffect, useRef } from 'react'
import {
    Sliders,
    Layers,
    RotateCcw,
    ZoomIn,
    ZoomOut,
    Download,
    ChevronLeft,
    ChevronRight,
    Split,
    Columns,
    Maximize2,
    Eye,
    CheckCircle2,
    Activity,
    Info,
    RefreshCw,
    Sparkles
} from 'lucide-react'
import { apiRequest, API_BASE_URL } from '../../services/api'

export default function VisualPreprocessingStudio({ documentId, pageNumber }) {
    const [stagesData, setStagesData] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    // Current selected stage index (0 to 5)
    const [selectedStageIdx, setSelectedStageIdx] = useState(5) // default to final enhanced

    // View mode: 'slider' (before/after split slider) | 'side-by-side' | 'single'
    const [viewMode, setViewMode] = useState('slider')

    // Slider divider percentage (0 to 100)
    const [sliderPos, setSliderPos] = useState(50)
    const [isDraggingSlider, setIsDraggingSlider] = useState(false)
    const sliderContainerRef = useRef(null)

    // Zoom level for main viewer (0.5 to 2.5)
    const [zoomLevel, setZoomLevel] = useState(1.0)

    // Authenticated blob URLs map: { [key: string]: string }
    const [imageBlobs, setImageBlobs] = useState({})
    const [thumbBlobs, setThumbBlobs] = useState({})
    const [loadingMainImage, setLoadingMainImage] = useState(false)

    // 1. Fetch Stages Metadata whenever documentId or pageNumber changes
    useEffect(() => {
        let isMounted = true

        const fetchStages = async () => {
            try {
                setLoading(true)
                setError(null)
                const data = await apiRequest(`/handwritten/${documentId}/pages/${pageNumber}/stages`)
                if (isMounted) {
                    setStagesData(data)
                    // Reset to stage 5 (final) or stage 0
                    setSelectedStageIdx(5)
                }
            } catch (err) {
                if (isMounted) {
                    console.error('Failed to load preprocessing stages:', err)
                    setError(err.message || 'Failed to load visual preprocessing stages.')
                }
            } finally {
                if (isMounted) setLoading(false)
            }
        }

        fetchStages()

        return () => {
            isMounted = false
        }
    }, [documentId, pageNumber])

    // Helper to fetch an authenticated image blob
    const fetchBlobUrl = async (url) => {
        const token = localStorage.getItem('access_token')
        const fullUrl = url.startsWith('http') ? url : `${API_BASE_URL}${url}`
        const res = await fetch(fullUrl, {
            headers: token ? { Authorization: `Bearer ${token}` } : {}
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const blob = await res.blob()
        return URL.createObjectURL(blob)
    }

    // 2. Load Thumbnails for all stages in background
    useEffect(() => {
        if (!stagesData?.stages) return
        let active = true
        const createdUrls = []

        const loadThumbs = async () => {
            const newThumbs = {}
            for (const stage of stagesData.stages) {
                try {
                    const blobUrl = await fetchBlobUrl(stage.thumb_url)
                    createdUrls.push(blobUrl)
                    newThumbs[stage.stage_id] = blobUrl
                } catch (e) {
                    console.warn(`Failed to load thumb for ${stage.stage_id}:`, e)
                }
            }
            if (active) {
                setThumbBlobs(prev => ({ ...prev, ...newThumbs }))
            }
        }

        loadThumbs()

        return () => {
            active = false
            createdUrls.forEach(url => URL.revokeObjectURL(url))
        }
    }, [stagesData])

    // 3. Load High-Resolution Images for Original and Active Stage
    const currentStage = stagesData?.stages?.[selectedStageIdx] || null
    const originalStage = stagesData?.stages?.[0] || null
    const finalStage = stagesData?.stages?.[5] || null

    useEffect(() => {
        if (!stagesData?.stages) return
        let active = true
        const keysToFetch = ['original']
        if (currentStage?.stage_id && currentStage.stage_id !== 'original') {
            keysToFetch.push(currentStage.stage_id)
        }
        if (finalStage?.stage_id && finalStage.stage_id !== 'original') {
            keysToFetch.push(finalStage.stage_id)
        }

        const loadFullImages = async () => {
            setLoadingMainImage(true)
            for (const key of keysToFetch) {
                if (imageBlobs[key]) continue
                const st = stagesData.stages.find(s => s.stage_id === key)
                if (!st) continue
                try {
                    const blobUrl = await fetchBlobUrl(st.image_url)
                    if (active) {
                        setImageBlobs(prev => ({ ...prev, [key]: blobUrl }))
                    }
                } catch (err) {
                    console.error(`Failed to load full image for ${key}:`, err)
                }
            }
            if (active) setLoadingMainImage(false)
        }

        loadFullImages()

        return () => {
            active = false
        }
    }, [stagesData, selectedStageIdx, currentStage?.stage_id])

    // Cleanup full image blobs on unmount
    useEffect(() => {
        return () => {
            Object.values(imageBlobs).forEach(url => URL.revokeObjectURL(url))
        }
    }, [])

    // Slider dragging event handlers
    const handleSliderMove = (clientX) => {
        if (!sliderContainerRef.current) return
        const rect = sliderContainerRef.current.getBoundingClientRect()
        const x = clientX - rect.left
        const percent = Math.max(0, Math.min(100, (x / rect.width) * 100))
        setSliderPos(percent)
    }

    const handleMouseDown = () => setIsDraggingSlider(true)

    useEffect(() => {
        const handleMouseMove = (e) => {
            if (isDraggingSlider) handleSliderMove(e.clientX)
        }
        const handleMouseUp = () => setIsDraggingSlider(false)
        const handleTouchMove = (e) => {
            if (isDraggingSlider && e.touches[0]) handleSliderMove(e.touches[0].clientX)
        }

        if (isDraggingSlider) {
            window.addEventListener('mousemove', handleMouseMove)
            window.addEventListener('mouseup', handleMouseUp)
            window.addEventListener('touchmove', handleTouchMove)
            window.addEventListener('touchend', handleMouseUp)
        }
        return () => {
            window.removeEventListener('mousemove', handleMouseMove)
            window.removeEventListener('mouseup', handleMouseUp)
            window.removeEventListener('touchmove', handleTouchMove)
            window.removeEventListener('touchend', handleMouseUp)
        }
    }, [isDraggingSlider])

    // Navigation through stages
    const handlePrevStage = () => {
        if (selectedStageIdx > 0) setSelectedStageIdx(prev => prev - 1)
    }

    const handleNextStage = () => {
        if (stagesData?.stages && selectedStageIdx < stagesData.stages.length - 1) {
            setSelectedStageIdx(prev => prev + 1)
        }
    }

    // Zoom handlers
    const handleZoomIn = () => setZoomLevel(prev => Math.min(prev + 0.25, 2.5))
    const handleZoomOut = () => setZoomLevel(prev => Math.max(prev - 0.25, 0.5))
    const handleResetZoom = () => setZoomLevel(1.0)

    // Download Enhanced Image
    const handleDownloadEnhanced = () => {
        const enhancedUrl = imageBlobs['final'] || imageBlobs[currentStage?.stage_id]
        if (!enhancedUrl) return
        const a = document.createElement('a')
        a.href = enhancedUrl
        a.download = `cognidocs_enhanced_page_${pageNumber}.png`
        document.body.appendChild(a)
        a.click()
        document.body.removeChild(a)
    }

    if (loading) {
        return (
            <div className="stages-loading-state">
                <RefreshCw size={28} className="spin-icon" style={{ color: 'var(--violet-ink)', marginBottom: '16px' }} />
                <h4>Analyzing Image Preprocessing Stages...</h4>
                <p>Generating intermediate OpenCV deskewing, normalization, and CLAHE outputs.</p>
            </div>
        )
    }

    if (error || !stagesData) {
        return (
            <div className="stages-error-state">
                <Info size={28} style={{ color: 'var(--danger-ink)', marginBottom: '12px' }} />
                <h4>Preprocessing Visualization Unavailable</h4>
                <p>{error || 'Unable to fetch stage outputs for this document page.'}</p>
            </div>
        )
    }

    const originalImgUrl = imageBlobs['original'] || thumbBlobs['original']
    const activeStageImgUrl = imageBlobs[currentStage?.stage_id] || thumbBlobs[currentStage?.stage_id]
    const finalImgUrl = imageBlobs['final'] || thumbBlobs['final'] || activeStageImgUrl

    return (
        <div className="visual-preprocessing-studio">
            {/* 1. TOP CONTROL TOOLBAR */}
            <div className="stages-header-toolbar">
                <div className="stages-title-meta">
                    <div className="stages-badge">
                        <Sparkles size={13} style={{ color: 'var(--cyan-ink)' }} />
                        <span>OpenCV Computer Vision Studio</span>
                    </div>
                    <h3 className="stages-main-title">Page {pageNumber} Processing Transformation</h3>
                    <p className="stages-main-sub">
                        Inspect how raw mobile camera captures are deskewed, shadow-normalized, and contrast-boosted for high-fidelity OCR.
                    </p>
                </div>

                <div className="stages-actions-row">
                    {/* View Mode Toggle */}
                    <div className="view-mode-pill-group">
                        <button
                            type="button"
                            className={`mode-btn ${viewMode === 'slider' ? 'active' : ''}`}
                            onClick={() => setViewMode('slider')}
                            title="Interactive Draggable Split Slider"
                        >
                            <Split size={14} />
                            <span>Split Slider</span>
                        </button>
                        <button
                            type="button"
                            className={`mode-btn ${viewMode === 'side-by-side' ? 'active' : ''}`}
                            onClick={() => setViewMode('side-by-side')}
                            title="Side-by-Side Dual Comparison"
                        >
                            <Columns size={14} />
                            <span>Side by Side</span>
                        </button>
                        <button
                            type="button"
                            className={`mode-btn ${viewMode === 'single' ? 'active' : ''}`}
                            onClick={() => setViewMode('single')}
                            title="Single Stage Detailed Focus"
                        >
                            <Eye size={14} />
                            <span>Stage Focus</span>
                        </button>
                    </div>

                    {/* Zoom Controls */}
                    <div className="stages-zoom-controls">
                        <button type="button" className="stages-icon-btn" onClick={handleZoomOut} title="Zoom Out">
                            <ZoomOut size={15} />
                        </button>
                        <span className="stages-zoom-indicator">{Math.round(zoomLevel * 100)}%</span>
                        <button type="button" className="stages-icon-btn" onClick={handleZoomIn} title="Zoom In">
                            <ZoomIn size={15} />
                        </button>
                        <button type="button" className="stages-icon-btn" onClick={handleResetZoom} title="Reset Zoom (100%)">
                            <RotateCcw size={14} />
                        </button>
                    </div>

                    {/* Download Button */}
                    <button
                        type="button"
                        className="stages-download-btn"
                        onClick={handleDownloadEnhanced}
                        title="Download OCR-ready enhanced image"
                    >
                        <Download size={14} />
                        <span>Download Enhanced</span>
                    </button>
                </div>
            </div>

            {/* 2. MAIN VISUAL COMPARISON VIEWER */}
            <div className="stages-main-viewer-card">
                {/* MODE A: INTERACTIVE SPLIT SLIDER */}
                {viewMode === 'slider' && (
                    <div
                        className="split-slider-viewport"
                        ref={sliderContainerRef}
                        onMouseDown={handleMouseDown}
                        onTouchStart={handleMouseDown}
                    >
                        {/* Layer 1: Underneath (Selected or Final Enhanced Image) */}
                        <div
                            className="slider-layer enhanced-layer"
                            style={{ transform: `scale(${zoomLevel})` }}
                        >
                            {activeStageImgUrl ? (
                                <img
                                    src={activeStageImgUrl}
                                    alt="Enhanced Output"
                                    className="slider-image-content"
                                    draggable={false}
                                />
                            ) : (
                                <div className="image-placeholder-box">Loading Enhanced Stage...</div>
                            )}
                        </div>

                        {/* Layer 2: Clipped Original Image on Top */}
                        <div
                            className="slider-layer original-layer"
                            style={{
                                transform: `scale(${zoomLevel})`,
                                clipPath: `polygon(0 0, ${sliderPos}% 0, ${sliderPos}% 100%, 0 100%)`
                            }}
                        >
                            {originalImgUrl ? (
                                <img
                                    src={originalImgUrl}
                                    alt="Original Scan"
                                    className="slider-image-content"
                                    draggable={false}
                                />
                            ) : (
                                <div className="image-placeholder-box">Loading Original...</div>
                            )}
                        </div>

                        {/* Draggable Divider Line & Handle */}
                        <div
                            className="slider-divider-line"
                            style={{ left: `${sliderPos}%` }}
                        >
                            <div className="slider-handle-knob">
                                <span className="slider-arrows">⇄</span>
                            </div>
                        </div>

                        {/* Floating Labels */}
                        <div className="slider-pill-label left">
                            <span className="dot original-dot"></span>
                            <span>Original Upload</span>
                        </div>
                        <div className="slider-pill-label right">
                            <span className="dot enhanced-dot"></span>
                            <span>{currentStage ? currentStage.title : 'Enhanced Output'}</span>
                        </div>
                    </div>
                )}

                {/* MODE B: SIDE-BY-SIDE COMPARISON */}
                {viewMode === 'side-by-side' && (
                    <div className="side-by-side-grid">
                        <div className="side-card">
                            <div className="side-card-header">
                                <span className="side-tag original">Original Photograph</span>
                                <span className="side-metric">{originalStage?.metrics?.width}×{originalStage?.metrics?.height}px</span>
                            </div>
                            <div className="side-card-body" style={{ overflow: 'auto' }}>
                                <img
                                    src={originalImgUrl}
                                    alt="Original"
                                    className="side-image"
                                    style={{ transform: `scale(${zoomLevel})` }}
                                />
                            </div>
                        </div>

                        <div className="side-card">
                            <div className="side-card-header">
                                <span className="side-tag enhanced">
                                    Stage {currentStage?.stage_number}: {currentStage?.title}
                                </span>
                                <span className="side-metric">{currentStage?.metrics?.execution_time_ms}ms</span>
                            </div>
                            <div className="side-card-body" style={{ overflow: 'auto' }}>
                                <img
                                    src={activeStageImgUrl}
                                    alt={currentStage?.title}
                                    className="side-image"
                                    style={{ transform: `scale(${zoomLevel})` }}
                                />
                            </div>
                        </div>
                    </div>
                )}

                {/* MODE C: SINGLE STAGE FOCUS */}
                {viewMode === 'single' && (
                    <div className="single-stage-viewport">
                        <div className="single-stage-header-overlay">
                            <span className="single-stage-badge">Stage {currentStage?.stage_number} of 6</span>
                            <h4>{currentStage?.title}</h4>
                        </div>
                        <div className="single-stage-canvas-scroll">
                            {activeStageImgUrl ? (
                                <img
                                    src={activeStageImgUrl}
                                    alt={currentStage?.title}
                                    className="single-stage-image"
                                    style={{ transform: `scale(${zoomLevel})` }}
                                />
                            ) : (
                                <div className="image-placeholder-box">Loading Image...</div>
                            )}
                        </div>
                    </div>
                )}
            </div>

            {/* 3. INTERACTIVE PROCESSING TIMELINE (HORIZONTAL STAGE SELECTOR) */}
            <div className="stages-timeline-container">
                <div className="stages-timeline-header">
                    <h4>OpenCV Transformation Timeline</h4>
                    <span className="stages-timeline-hint">Select a stage below to inspect its exact computer vision output</span>
                </div>

                <div className="stages-timeline-track">
                    {stagesData.stages.map((stage, idx) => {
                        const isSelected = selectedStageIdx === idx
                        const thumbUrl = thumbBlobs[stage.stage_id] || imageBlobs[stage.stage_id]

                        return (
                            <button
                                key={stage.stage_id}
                                type="button"
                                className={`stage-card-btn ${isSelected ? 'selected' : ''}`}
                                onClick={() => setSelectedStageIdx(idx)}
                            >
                                <div className="stage-card-thumb-wrap">
                                    {thumbUrl ? (
                                        <img
                                            src={thumbUrl}
                                            alt={stage.title}
                                            className="stage-card-thumb"
                                            loading="lazy"
                                        />
                                    ) : (
                                        <div className="stage-thumb-placeholder">
                                            <span className="stage-num-dim">{stage.stage_number}</span>
                                        </div>
                                    )}
                                    <span className="stage-number-badge">0{stage.stage_number}</span>
                                    {isSelected && <div className="stage-active-indicator" />}
                                </div>

                                <div className="stage-card-info">
                                    <h5 className="stage-card-title">{stage.title}</h5>
                                    <span className="stage-card-sub">{stage.subtitle}</span>
                                </div>
                            </button>
                        )
                    })}
                </div>
            </div>

            {/* 4. ACTIVE STAGE DETAILED SPECIFICATIONS & METRICS */}
            {currentStage && (
                <div className="stage-detail-panel">
                    <div className="stage-detail-nav">
                        <button
                            type="button"
                            className="stage-step-nav-btn"
                            onClick={handlePrevStage}
                            disabled={selectedStageIdx === 0}
                        >
                            <ChevronLeft size={16} />
                            <span>Previous Step</span>
                        </button>

                        <div className="stage-stepper-indicator">
                            <span className="stepper-pill">
                                Stage {currentStage.stage_number} / {stagesData.stages.length}
                            </span>
                        </div>

                        <button
                            type="button"
                            className="stage-step-nav-btn"
                            onClick={handleNextStage}
                            disabled={selectedStageIdx === stagesData.stages.length - 1}
                        >
                            <span>Next Step</span>
                            <ChevronRight size={16} />
                        </button>
                    </div>

                    <div className="stage-detail-grid">
                        <div className="stage-detail-main">
                            <div className="stage-badge-inline">
                                <CheckCircle2 size={15} style={{ color: 'var(--success-ink)' }} />
                                <span>{currentStage.subtitle}</span>
                            </div>
                            <h4 className="stage-detail-title">{currentStage.title}</h4>
                            <p className="stage-detail-desc">{currentStage.description}</p>
                            <div className="stage-tech-detail">
                                <span className="tech-tag">OpenCV Implementation:</span>
                                <code>{currentStage.technical_detail}</code>
                            </div>
                        </div>

                        {/* Real Mathematical Metrics */}
                        <div className="stage-metrics-card">
                            <h5 className="metrics-card-title">
                                <Activity size={14} style={{ color: 'var(--violet-ink)' }} />
                                <span>Stage Operational Metrics</span>
                            </h5>

                            <div className="metrics-table">
                                <div className="metric-row">
                                    <span className="metric-label">Resolution</span>
                                    <span className="metric-value">{currentStage.metrics.width} × {currentStage.metrics.height} px</span>
                                </div>

                                <div className="metric-row">
                                    <span className="metric-label">Execution Time</span>
                                    <span className="metric-value highlight-cyan">{currentStage.metrics.execution_time_ms} ms</span>
                                </div>

                                <div className="metric-row">
                                    <span className="metric-label">Mean Brightness</span>
                                    <span className="metric-value">{currentStage.metrics.mean_brightness} / 255</span>
                                </div>

                                <div className="metric-row">
                                    <span className="metric-label">Dynamic Contrast (σ)</span>
                                    <span className="metric-value">{currentStage.metrics.contrast_std}</span>
                                </div>

                                {currentStage.metrics.detected_angle !== undefined && (
                                    <div className="metric-row">
                                        <span className="metric-label">Detected Skew Angle</span>
                                        <span className="metric-value highlight-violet">
                                            {currentStage.metrics.detected_angle > 0 ? `+${currentStage.metrics.detected_angle}°` : `${currentStage.metrics.detected_angle}°`}
                                        </span>
                                    </div>
                                )}

                                {currentStage.metrics.clip_limit !== undefined && (
                                    <div className="metric-row">
                                        <span className="metric-label">CLAHE Tile Limit</span>
                                        <span className="metric-value">{currentStage.metrics.clip_limit} (grid {currentStage.metrics.tile_grid})</span>
                                    </div>
                                )}

                                {currentStage.metrics.sigma_color !== undefined && (
                                    <div className="metric-row">
                                        <span className="metric-label">Bilateral Smoothing</span>
                                        <span className="metric-value">d={currentStage.metrics.diameter}, σ={currentStage.metrics.sigma_color}</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}

