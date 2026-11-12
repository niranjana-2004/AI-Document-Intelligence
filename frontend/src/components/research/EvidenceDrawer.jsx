import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { X, ExternalLink, Search, ShieldCheck, BookMarked } from 'lucide-react'
import { buildSourceNavigationUrl } from '../../utils/citationUtils'
import { filterEvidenceByQuery, getFactTypeMeta } from '../../utils/researchPaperUtils'

export default function EvidenceDrawer({
    isOpen,
    onClose,
    selectedClaim,
    analysis,
}) {
    const navigate = useNavigate()
    const [searchQuery, setSearchQuery] = useState('')
    const [factFilter, setFactFilter] = useState('all')

    const evidenceMap = useMemo(() => analysis?.evidence || {}, [analysis?.evidence])

    const selectedSources = useMemo(() => {
        if (!selectedClaim?.field) return []
        if (Array.isArray(selectedClaim.field.sources) && selectedClaim.field.sources.length > 0) {
            return selectedClaim.field.sources
        }
        if (selectedClaim.source) {
            return [selectedClaim.source]
        }
        return []
    }, [selectedClaim])

    const allEvidenceItems = useMemo(
        () => filterEvidenceByQuery(evidenceMap, searchQuery, factFilter),
        [evidenceMap, searchQuery, factFilter]
    )

    if (!isOpen || !analysis) return null

    const handleOpenInViewer = (source) => {
        const targetUrl = buildSourceNavigationUrl({
            document_id: source.document_id || analysis.document_id,
            document_type: analysis.document_type,
            is_handwritten: analysis.is_handwritten,
            source_type: analysis.is_handwritten ? 'handwritten' : 'printed',
            page_number: source.page || 1,
            chunk_id: source.chunk_id,
            excerpt: source.excerpt || '',
        })
        navigate(targetUrl)
    }

    const activeMeta = getFactTypeMeta(selectedClaim?.field?.fact_type || selectedClaim?.factType || 'explicit')

    return (
        <div className="rpa-drawer-backdrop" onClick={onClose} role="presentation">
            <aside
                className="rpa-evidence-drawer"
                onClick={(e) => e.stopPropagation()}
                role="dialog"
                aria-modal="true"
                aria-label="Evidence verification drawer"
            >
                <header className="rpa-drawer-header">
                    <div className="rpa-drawer-title-group">
                        <ShieldCheck size={18} />
                        <div>
                            <h3>Source Evidence Drawer</h3>
                            <p>{analysis.document_filename}</p>
                        </div>
                    </div>
                    <button
                        type="button"
                        className="rpa-drawer-close"
                        onClick={onClose}
                        aria-label="Close evidence drawer"
                    >
                        <X size={18} />
                    </button>
                </header>

                <div className="rpa-drawer-body">
                    {selectedClaim ? (
                        <section className="rpa-drawer-selected">
                            <div className="rpa-drawer-claim-top">
                                <span className="rpa-drawer-claim-label">{selectedClaim.label}</span>
                                <span className={`rpa-fact-chip tone-${activeMeta.tone}`}>
                                    {activeMeta.label}
                                </span>
                            </div>
                            <p className="rpa-drawer-claim-text">
                                {selectedClaim.field?.value || selectedClaim.claimText}
                            </p>

                            <div className="rpa-source-cards">
                                {selectedSources.map((src, idx) => (
                                    <div key={`sel-src-${idx}-${src.chunk_id || idx}`} className="rpa-source-card">
                                        <div className="rpa-source-card-meta">
                                            <span className="rpa-page-pill">Page {src.page || 1}</span>
                                            {src.section && <span className="rpa-sec-pill">{src.section}</span>}
                                            {src.figure_or_table && (
                                                <span className="rpa-fig-pill">{src.figure_or_table}</span>
                                            )}
                                            {src.chunk_id != null && (
                                                <span className="rpa-chunk-pill">Chunk #{src.chunk_id}</span>
                                            )}
                                        </div>

                                        {src.excerpt && (
                                            <blockquote className="rpa-excerpt-quote">
                                                &ldquo;{src.excerpt}&rdquo;
                                            </blockquote>
                                        )}

                                        <div className="rpa-source-card-footer">
                                            <span className="rpa-conf-text">
                                                Match confidence: {Math.round(Number(src.confidence || 0.85) * 100)}%
                                            </span>
                                            <button
                                                type="button"
                                                className="rpa-open-viewer-btn"
                                                onClick={() => handleOpenInViewer(src)}
                                            >
                                                <ExternalLink size={13} />
                                                <span>Open Source Page</span>
                                            </button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </section>
                    ) : null}

                    <section className="rpa-drawer-index">
                        <div className="rpa-drawer-index-header">
                            <div className="rpa-drawer-index-title">
                                <BookMarked size={15} />
                                <h4>All Grounded Evidence ({allEvidenceItems.length})</h4>
                            </div>

                            <div className="rpa-drawer-filters">
                                <div className="rpa-drawer-search">
                                    <Search size={14} />
                                    <input
                                        type="text"
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        placeholder="Filter evidence, section, p.X..."
                                    />
                                </div>
                                <select
                                    className="rpa-drawer-select"
                                    value={factFilter}
                                    onChange={(e) => setFactFilter(e.target.value)}
                                    aria-label="Filter evidence by fact type"
                                >
                                    <option value="all">All Fact Types</option>
                                    <option value="explicit">Explicit Only</option>
                                    <option value="derived">Derived Only</option>
                                    <option value="inferred">Inferred Only</option>
                                </select>
                            </div>
                        </div>

                        <div className="rpa-evidence-list">
                            {allEvidenceItems.map((item) => {
                                const meta = getFactTypeMeta(item.fact_type)
                                const src = item.source || {}
                                return (
                                    <div key={item.id} className="rpa-evidence-item">
                                        <div className="rpa-evidence-item-top">
                                            <span className="rpa-ev-id">{item.id}</span>
                                            <span className={`rpa-fact-chip tone-${meta.tone}`}>{meta.label}</span>
                                            <span className="rpa-page-pill">p.{src.page || 1}</span>
                                            {src.section && <span className="rpa-sec-pill">{src.section}</span>}
                                        </div>
                                        <p className="rpa-ev-claim">{item.claim}</p>
                                        {src.excerpt && (
                                            <blockquote className="rpa-excerpt-quote is-compact">
                                                &ldquo;{src.excerpt}&rdquo;
                                            </blockquote>
                                        )}
                                        <div className="rpa-ev-footer">
                                            <button
                                                type="button"
                                                className="rpa-open-viewer-link"
                                                onClick={() => handleOpenInViewer(src)}
                                            >
                                                <ExternalLink size={12} />
                                                <span>Jump to Page {src.page || 1}</span>
                                            </button>
                                        </div>
                                    </div>
                                )
                            })}
                        </div>
                    </section>
                </div>
            </aside>
        </div>
    )
}
