/**
 * Shared utilities for source-grounded citations, deep-link URLs,
 * and deterministic passage highlighting inside Cognidocs viewers.
 */

const INSUFFICIENT_PHRASES = [
    "couldn't find enough information",
    'could not find enough information',
    'do not contain sufficient information',
    'does not contain sufficient information',
    'insufficient information to answer',
    'not enough information in the uploaded',
    'cannot find the answer in the provided',
    'not mentioned in the provided',
    'no information in the uploaded',
]

const REFUSAL_PREFIXES = [
    "i couldn't find",
    'i could not find',
    'i cannot find',
    'there is not enough information',
    "there isn't enough information",
    'the provided sources do not',
    'the uploaded document does not',
    'the uploaded documents do not',
    'based on the provided sources, there is no',
    "unfortunately, i couldn't find",
    "sorry, i couldn't find",
]

export function isInsufficientEvidenceText(text) {
    if (!text || typeof text !== 'string') return false
    const normalized = text.replace(/\s+/g, ' ').trim().toLowerCase()
    if (!normalized) return true
    if (normalized.length <= 320 && normalized.includes("i couldn't find enough information in the uploaded document to answer that question.")) {
        return true
    }
    if (normalized.length <= 320 && REFUSAL_PREFIXES.some((p) => normalized.startsWith(p))) {
        return true
    }
    const hasInlineCitation = /\[(?:source\s*)?\d+\b/.test(normalized)
    if (!hasInlineCitation && normalized.length <= 280 && INSUFFICIENT_PHRASES.some((phrase) => normalized.includes(phrase))) {
        return true
    }
    return false
}

export function extractSearchableSnippet(rawExcerpt) {
    if (!rawExcerpt || typeof rawExcerpt !== 'string') return ''
    let cleaned = rawExcerpt
        .replace(/---\s*Page\s+\d+\s*---\s*/gi, ' ')
        .replace(/^\.{2,}\s*/, '')
        .replace(/\s*\.{2,}$/, '')
        .replace(/\s+/g, ' ')
        .trim()

    if (cleaned.length <= 100) return cleaned
    const slice = cleaned.slice(0, 100)
    const lastSpace = slice.lastIndexOf(' ')
    return (lastSpace > 45 ? slice.slice(0, lastSpace) : slice).trim()
}

export function buildSourceNavigationUrl(source) {
    if (!source || !source.document_id) return null
    const isHandwritten =
        source.source_type === 'handwritten' ||
        (source.document_type && String(source.document_type).toLowerCase().includes('handwritten'))

    const rawText = source.excerpt || source.content || source.source_text || ''
    const snippet = extractSearchableSnippet(rawText)
    const params = new URLSearchParams()

    if (isHandwritten) {
        if (source.page_number != null) {
            params.set('page', String(source.page_number))
        }
        if (snippet) {
            params.set('highlight', snippet)
        }
        const qs = params.toString()
        return `/handwritten/${source.document_id}${qs ? `?${qs}` : ''}`
    }

    params.set('doc', String(source.document_id))
    if (source.page_number != null) {
        params.set('page', String(source.page_number))
    }
    if (snippet) {
        params.set('highlight', snippet)
    }
    return `/documents?${params.toString()}`
}

/**
 * Finds the character range { start, end } inside `text` that best matches `query`.
 * Tries exact substring -> flexible-whitespace match -> best overlapping sentence.
 */
export function findBestHighlightRange(text, query) {
    if (!text || !query || typeof text !== 'string' || typeof query !== 'string') {
        return null
    }

    const qClean = extractSearchableSnippet(query)
    if (!qClean || qClean.length < 4) return null

    // 1. Direct case-insensitive substring
    const textLower = text.toLowerCase()
    const qLower = qClean.toLowerCase()
    const directIdx = textLower.indexOf(qLower)
    if (directIdx !== -1) {
        return { start: directIdx, end: directIdx + qClean.length }
    }

    // 2. Try first 55 chars with flexible whitespace matching (handles line breaks inside PDFs)
    const probe = qClean.slice(0, Math.min(55, qClean.length))
    const words = probe.split(/\s+/).filter((w) => w.length > 0)
    if (words.length >= 2) {
        const escaped = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
        const flexRegex = new RegExp(escaped.join('\\s+'), 'i')
        const match = flexRegex.exec(text)
        if (match) {
            return { start: match.index, end: match.index + match[0].length }
        }
    }

    // 3. Fallback: sentence / line with strongest non-trivial token overlap
    const meaningfulQueryWords = new Set(
        qLower
            .split(/[^a-z0-9]+/i)
            .filter((w) => w.length >= 3)
    )
    if (meaningfulQueryWords.size < 2) return null

    let bestRange = null
    let bestScore = 0
    const segRegex = /[^\n.!?]+(?:[.!?]+|$)/g
    let segMatch
    while ((segMatch = segRegex.exec(text)) !== null) {
        const seg = segMatch[0]
        if (seg.trim().length < 12) continue
        const segWords = new Set(seg.toLowerCase().split(/[^a-z0-9]+/i).filter((w) => w.length >= 3))
        let overlap = 0
        for (const w of meaningfulQueryWords) {
            if (segWords.has(w)) overlap++
        }
        const ratio = overlap / meaningfulQueryWords.size
        if (overlap >= 2 && ratio > bestScore) {
            bestScore = ratio
            const trimmedLead = seg.length - seg.trimStart().length
            const trimmedTrail = seg.length - seg.trimEnd().length
            bestRange = {
                start: segMatch.index + trimmedLead,
                end: segMatch.index + seg.length - trimmedTrail,
            }
        }
    }

    return bestScore >= 0.35 ? bestRange : null
}

/**
 * Splits `text` into { before, match, after } around the best matching highlight span,
 * or returns null if no match is found.
 */
export function splitHighlightedText(text, query) {
    if (!text || !query) return null
    const range = findBestHighlightRange(text, query)
    if (!range) return null
    return {
        before: text.slice(0, range.start),
        match: text.slice(range.start, range.end),
        after: text.slice(range.end),
    }
}
