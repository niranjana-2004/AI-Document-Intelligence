export const FACT_TYPE_META = {
    explicit: {
        label: 'Explicit',
        tone: 'success',
        description: 'Directly stated verbatim in the source paper.',
    },
    derived: {
        label: 'Derived',
        tone: 'info',
        description: 'Computed directly from explicit numbers in the paper.',
    },
    inferred: {
        label: 'Inferred',
        tone: 'warning',
        description: 'Low-temperature interpretation supported by cited passages.',
    },
    missing: {
        label: 'Not in Paper',
        tone: 'neutral',
        description: 'Not explicitly stated in the paper.',
    },
}

export function getFactTypeMeta(factType) {
    return FACT_TYPE_META[factType] || FACT_TYPE_META.missing
}

export function getDetectionMeta(paperDetection) {
    const cls = paperDetection?.classification || 'non_research'
    const confPct = Math.round((Number(paperDetection?.confidence || 0)) * 100)
    if (cls === 'research_paper' || paperDetection?.is_research_paper) {
        return {
            label: paperDetection?.manual_override === 'research_paper'
                ? 'Research Paper (Manual Override)'
                : 'Research Paper Detected',
            tone: 'success',
            confidencePct: confPct,
        }
    }
    if (cls === 'borderline_technical') {
        return {
            label: 'Borderline Technical Document',
            tone: 'warning',
            confidencePct: confPct,
        }
    }
    return {
        label: paperDetection?.manual_override === 'non_research'
            ? 'Non-Research (Manual Override)'
            : 'Not a Research Paper',
        tone: 'neutral',
        confidencePct: confPct,
    }
}

export function flattenSectionHierarchy(sections, depth = 0) {
    if (!Array.isArray(sections) || sections.length === 0) return []
    const rows = []
    for (const sec of sections) {
        if (!sec || typeof sec !== 'object') continue
        rows.push({
            ...sec,
            depth,
        })
        if (Array.isArray(sec.children) && sec.children.length > 0) {
            rows.push(...flattenSectionHierarchy(sec.children, depth + 1))
        }
    }
    return rows
}

export function filterEvidenceByQuery(evidenceMap, query = '', factTypeFilter = 'all') {
    if (!evidenceMap || typeof evidenceMap !== 'object') return []
    const q = String(query || '').trim().toLowerCase()
    return Object.values(evidenceMap).filter((item) => {
        if (!item) return false
        if (factTypeFilter !== 'all' && item.fact_type !== factTypeFilter) {
            return false
        }
        if (!q) return true
        const hay = [
            item.id,
            item.claim,
            item.source?.section,
            item.source?.excerpt,
            item.source?.figure_or_table,
            item.source?.page != null ? `p.${item.source.page} page ${item.source.page}` : '',
        ]
            .filter(Boolean)
            .join(' ')
            .toLowerCase()
        return hay.includes(q)
    })
}

