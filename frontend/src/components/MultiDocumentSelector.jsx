import { useState, useMemo, useEffect } from 'react'
import {
    Search,
    X,
    Check,
    FileText,
    PenTool,
    AlertCircle,
} from 'lucide-react'

/**
 * Derives file extension / format badge text from a document object.
 */
function getFormatBadge(doc) {
    if (doc.filename && doc.filename.includes('.')) {
        const ext = doc.filename.split('.').pop()
        if (ext) return ext.toUpperCase()
    }
    if (doc.document_type) {
        const dt = doc.document_type.toLowerCase()
        if (dt.includes('pdf')) return 'PDF'
        if (dt.includes('word') || dt.includes('docx')) return 'DOCX'
        if (dt.includes('text') || dt.includes('plain') || dt.includes('txt')) return 'TXT'
        if (dt.includes('image') || dt.includes('webp') || dt.includes('png') || dt.includes('jpg')) return 'IMG'
        if (dt.includes('handwritten')) return 'HW'
    }
    return 'DOC'
}

/**
 * Checks whether a document is handwritten.
 */
function isHandwrittenDoc(doc) {
    if (doc.is_handwritten === true || doc.is_handwritten === 1) return true
    const dt = (doc.document_type || '').toLowerCase()
    if (dt.includes('handwritten')) return true
    const fn = (doc.filename || '').toLowerCase()
    if (fn.includes('handwritten') || fn.includes('-hw') || fn.includes('_hw')) return true
    return false
}

/**
 * MultiDocumentSelector component:
 * Provides a searchable, filterable, dark-academic multi-select interface
 * for scoping cross-document inquiries in Cognidocs Ask AI.
 */
export default function MultiDocumentSelector({
    isOpen,
    onClose,
    documents = [],
    selectedDocIds = [],
    onToggleDoc,
    onSelectAll,
    onClear,
    loading = false,
}) {
    const [searchQuery, setSearchQuery] = useState('')
    const [typeFilter, setTypeFilter] = useState('all') // 'all' | 'printed' | 'handwritten'

    // Close on Escape key
    useEffect(() => {
        if (!isOpen) return
        const handleKeyDown = (e) => {
            if (e.key === 'Escape') {
                onClose?.()
            }
        }
        window.addEventListener('keydown', handleKeyDown)
        return () => window.removeEventListener('keydown', handleKeyDown)
    }, [isOpen, onClose])

    // Compute type counts for filter tabs
    const counts = useMemo(() => {
        let hwCount = 0
        let printedCount = 0
        documents.forEach((d) => {
            if (isHandwrittenDoc(d)) {
                hwCount++
            } else {
                printedCount++
            }
        })
        return {
            all: documents.length,
            handwritten: hwCount,
            printed: printedCount,
        }
    }, [documents])

    // Filter documents based on search query and type filter
    const filteredDocuments = useMemo(() => {
        const query = searchQuery.trim().toLowerCase()
        return documents.filter((doc) => {
            // Type filter
            const isHw = isHandwrittenDoc(doc)
            if (typeFilter === 'handwritten' && !isHw) return false
            if (typeFilter === 'printed' && isHw) return false

            // Search query filter
            if (query) {
                const fn = (doc.filename || '').toLowerCase()
                const title = (doc.title || '').toLowerCase()
                return fn.includes(query) || title.includes(query)
            }

            return true
        })
    }, [documents, searchQuery, typeFilter])

    // Map of selected documents for the tray
    const selectedDocsList = useMemo(() => {
        const idSet = new Set(selectedDocIds)
        return documents.filter((d) => idSet.has(d.id))
    }, [documents, selectedDocIds])

    if (!isOpen) return null

    return (
        <section
            className="multi-doc-selector-panel"
            role="dialog"
            aria-label="Multi-Document Knowledge Scope Selector"
        >
            {/* SEARCH AND FILTER BAR */}
            <div className="selector-search-and-filters">
                <div className="selector-search-box">
                    <Search size={14} className="selector-search-icon" aria-hidden="true" />
                    <input
                        type="text"
                        className="selector-search-input"
                        placeholder="Search documents by title or filename..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        disabled={loading}
                        aria-label="Filter documents by name"
                        autoFocus
                    />
                    {searchQuery && (
                        <button
                            type="button"
                            className="selector-search-clear"
                            onClick={() => setSearchQuery('')}
                            title="Clear search"
                            aria-label="Clear document search"
                        >
                            <X size={14} />
                        </button>
                    )}
                </div>

                <div className="selector-filter-pills" role="tablist" aria-label="Filter by document type">
                    <button
                        type="button"
                        role="tab"
                        aria-selected={typeFilter === 'all'}
                        className={`filter-pill ${typeFilter === 'all' ? 'active' : ''}`}
                        onClick={() => setTypeFilter('all')}
                        disabled={loading}
                    >
                        All Types ({counts.all})
                    </button>
                    <button
                        type="button"
                        role="tab"
                        aria-selected={typeFilter === 'printed'}
                        className={`filter-pill ${typeFilter === 'printed' ? 'active' : ''}`}
                        onClick={() => setTypeFilter('printed')}
                        disabled={loading}
                    >
                        📄 Printed Docs ({counts.printed})
                    </button>
                    <button
                        type="button"
                        role="tab"
                        aria-selected={typeFilter === 'handwritten'}
                        className={`filter-pill ${typeFilter === 'handwritten' ? 'active' : ''}`}
                        onClick={() => setTypeFilter('handwritten')}
                        disabled={loading}
                    >
                        ✍️ Handwritten ({counts.handwritten})
                    </button>
                </div>
            </div>

            {/* SELECTED DOCUMENTS TRAY */}
            {selectedDocsList.length > 0 && (
                <div className="selector-selected-tray" aria-label="Currently selected documents">
                    <span className="selected-tray-header">
                        Selected Scope ({selectedDocsList.length}):
                    </span>
                    <div className="selected-tray-chips">
                        {selectedDocsList.map((doc) => {
                            const isHw = isHandwrittenDoc(doc)
                            return (
                                <div key={doc.id} className="selected-chip">
                                    <span className="selected-chip-title" title={doc.filename}>
                                        {isHw ? '✍️ ' : '📄 '}
                                        {doc.filename || `Doc #${doc.id}`}
                                    </span>
                                    <button
                                        type="button"
                                        className="selected-chip-remove"
                                        onClick={() => onToggleDoc(doc.id)}
                                        disabled={loading}
                                        title={`Remove ${doc.filename} from scope`}
                                        aria-label={`Remove ${doc.filename}`}
                                    >
                                        <X size={12} />
                                    </button>
                                </div>
                            )
                        })}
                    </div>
                </div>
            )}

            {/* AVAILABLE DOCUMENTS GRID */}
            <div className="selector-docs-grid" role="group" aria-label="Selectable document cards">
                {filteredDocuments.length === 0 ? (
                    <div className="selector-empty-search" style={{ padding: '16px', textAlign: 'center', color: '#94a3b8', fontSize: '12px', gridColumn: '1 / -1' }}>
                        <AlertCircle size={20} style={{ margin: '0 auto 6px', color: '#64748b' }} />
                        <p>No documents match your filter criteria.</p>
                    </div>
                ) : (
                    filteredDocuments.map((doc) => {
                        const isSelected = selectedDocIds.includes(doc.id)
                        const isHw = isHandwrittenDoc(doc)
                        const formatBadge = getFormatBadge(doc)
                        const title = doc.title || doc.filename.replace(/\.[^/.]+$/, '')

                        return (
                            <div
                                key={doc.id}
                                className={`selector-doc-card ${isSelected ? 'selected' : ''} ${loading ? 'disabled' : ''}`}
                                onClick={() => !loading && onToggleDoc(doc.id)}
                                role="checkbox"
                                aria-checked={isSelected}
                                tabIndex={0}
                                onKeyDown={(e) => {
                                    if (e.key === ' ' || e.key === 'Enter') {
                                        e.preventDefault()
                                        if (!loading) onToggleDoc(doc.id)
                                    }
                                }}
                            >
                                <div className="doc-card-left">
                                    <div className="doc-card-checkbox" aria-hidden="true">
                                        {isSelected && <Check size={11} className="doc-card-check-icon" />}
                                    </div>

                                    <div className={`doc-card-icon-wrap ${isHw ? 'hw' : 'printed'}`} aria-hidden="true">
                                        {isHw ? <PenTool size={13} /> : <FileText size={13} />}
                                    </div>

                                    <div className="doc-card-details">
                                        <span className="doc-card-title" title={title}>
                                            {title}
                                        </span>
                                        <span className="doc-card-filename" title={doc.filename}>
                                            {doc.filename}
                                        </span>
                                    </div>
                                </div>

                                <div className="doc-card-badges">
                                    {isHw && (
                                        <span className="badge-hw" title="Handwritten document processed via OCR 3.5">
                                            HANDWRITTEN
                                        </span>
                                    )}
                                    <span className="badge-format">
                                        {formatBadge}
                                    </span>
                                </div>
                            </div>
                        )
                    })
                )}
            </div>

            {/* SELECTOR FOOTER ACTIONS */}
            <div className="selector-footer">
                <span className="selector-footer-info">
                    {selectedDocIds.length === 0
                        ? 'No documents selected (select at least one)'
                        : `${selectedDocIds.length} of ${documents.length} documents selected`}
                </span>

                <div className="selector-footer-actions">
                    <button
                        type="button"
                        className="scope-chip-btn"
                        onClick={onSelectAll}
                        disabled={loading || selectedDocIds.length === documents.length}
                        title="Select all available documents"
                    >
                        Select All
                    </button>
                    <button
                        type="button"
                        className="scope-chip-btn"
                        onClick={onClear}
                        disabled={loading || selectedDocIds.length === 0}
                        title="Clear all selections"
                    >
                        Clear
                    </button>
                    <button
                        type="button"
                        className="scope-chip-btn scope-chip-close"
                        onClick={onClose}
                        title="Finish selection"
                    >
                        Done ✓
                    </button>
                </div>
            </div>
        </section>
    )
}
