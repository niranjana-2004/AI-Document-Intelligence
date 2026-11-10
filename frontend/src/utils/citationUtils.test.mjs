import assert from 'node:assert/strict'
import test from 'node:test'
import {
    toggleDocumentSelection,
    isInsufficientEvidenceText,
    buildSourceNavigationUrl,
    splitHighlightedText,
} from './citationUtils.js'

test('toggleDocumentSelection supports single, rapid consecutive multi-doc, and deselection', () => {
    // Normal single-document selection
    const afterA = toggleDocumentSelection([], 5)
    assert.deepEqual(afterA, [5])

    // Simulated React queued functional updaters for rapid same-tick clicks (select A, immediately select B)
    const queue = [
        (prev) => toggleDocumentSelection(prev, 5),
        (prev) => toggleDocumentSelection(prev, 13),
    ]
    let state = []
    for (const updater of queue) {
        state = updater(state)
    }
    assert.deepEqual(state, [5, 13])

    // Deselection preserves remaining document
    const afterRemoveA = toggleDocumentSelection(state, 5)
    assert.deepEqual(afterRemoveA, [13])

    // Re-adding and rapid deselection back to empty
    const queueToggleBack = [
        (prev) => toggleDocumentSelection(prev, 48),
        (prev) => toggleDocumentSelection(prev, 13),
        (prev) => toggleDocumentSelection(prev, 48),
    ]
    let multiState = state
    for (const updater of queueToggleBack) {
        multiState = updater(multiState)
    }
    assert.deepEqual(multiState, [5])
})

test('isInsufficientEvidenceText detects short refusals without flagging cited multi-section answers', () => {
    assert.equal(
        isInsufficientEvidenceText("I couldn't find enough information in the uploaded document to answer that question."),
        true
    )
    assert.equal(
        isInsufficientEvidenceText(
            '**Overview**\nCephVault uses modular isolation [1] while CSS styles HTML documents [2]. ' +
            'Hardware TPM details for older kernels are not mentioned in the provided summary, '.repeat(4)
        ),
        false
    )
})

test('buildSourceNavigationUrl routes printed PDF and handwritten notes with page and highlight params', () => {
    const pdfUrl = buildSourceNavigationUrl({
        document_id: 5,
        document_type: 'PDF',
        source_type: 'printed',
        page_number: 59,
        excerpt: 'CephVault employs modular design for code isolation and security.',
    })
    assert.equal(pdfUrl.startsWith('/documents?doc=5&page=59&highlight='), true)

    const hwUrl = buildSourceNavigationUrl({
        document_id: 12,
        document_type: 'HANDWRITTEN',
        source_type: 'handwritten',
        page_number: 2,
        excerpt: 'The backlog queue fills up with unacknowledged requests.',
    })
    assert.equal(hwUrl.startsWith('/handwritten/12?page=2&highlight='), true)
})

test('splitHighlightedText finds excerpt match cleanly', () => {
    const split = splitHighlightedText(
        'Line one. However, any design pattern is not inherently insecure. Line three.',
        'However, any design pattern is not inherently insecure'
    )
    assert.ok(split)
    assert.equal(split.match, 'However, any design pattern is not inherently insecure')
})

