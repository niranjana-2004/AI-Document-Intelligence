import assert from 'node:assert/strict'
import test from 'node:test'
import {
    getFactTypeMeta,
    getDetectionMeta,
    flattenSectionHierarchy,
    filterEvidenceByQuery,
} from './researchPaperUtils.js'

test('getFactTypeMeta and getDetectionMeta return accurate labels and tones', () => {
    assert.equal(getFactTypeMeta('explicit').tone, 'success')
    assert.equal(getFactTypeMeta('derived').tone, 'info')
    assert.equal(getFactTypeMeta('inferred').tone, 'warning')
    assert.equal(getFactTypeMeta('missing').label, 'Not in Paper')

    const detPaper = getDetectionMeta({ classification: 'research_paper', is_research_paper: true, confidence: 0.94 })
    assert.equal(detPaper.tone, 'success')
    assert.equal(detPaper.confidencePct, 94)

    const detOverride = getDetectionMeta({
        classification: 'research_paper',
        is_research_paper: true,
        manual_override: 'research_paper',
        confidence: 0.48,
    })
    assert.equal(detOverride.label, 'Research Paper (Manual Override)')
})

test('flattenSectionHierarchy preserves parent-child depth order', () => {
    const flat = flattenSectionHierarchy([
        {
            id: 'sec-1',
            title: '3. Methodology',
            children: [
                { id: 'sec-2', title: '3.1 Encryption Layer', children: [] },
            ],
        },
        { id: 'sec-3', title: '4. Evaluation', children: [] },
    ])
    assert.deepEqual(
        flat.map((s) => [s.title, s.depth]),
        [
            ['3. Methodology', 0],
            ['3.1 Encryption Layer', 1],
            ['4. Evaluation', 0],
        ]
    )
})

test('filterEvidenceByQuery filters by keyword and fact type', () => {
    const map = {
        'ev-1': {
            id: 'ev-1',
            claim: 'Accuracy reaches 97.4%',
            fact_type: 'explicit',
            source: { page: 5, section: '4. Results', excerpt: 'Accuracy reached 97.4% on UNSW-NB15.' },
        },
        'ev-2': {
            id: 'ev-2',
            claim: 'Derived accuracy delta +6.4 pp',
            fact_type: 'derived',
            source: { page: 6, section: '4. Results', excerpt: '97.4% vs 91.0% baseline.' },
        },
    }
    assert.equal(filterEvidenceByQuery(map, '', 'derived').length, 1)
    assert.equal(filterEvidenceByQuery(map, 'UNSW-NB15', 'all').length, 1)
    assert.equal(filterEvidenceByQuery(map, 'p.6', 'all')[0].id, 'ev-2')
})

test('getDetectionMeta handles borderline, default non-research, and manual non-research override', () => {
    const borderline = getDetectionMeta({ classification: 'borderline_technical', is_research_paper: false, confidence: 0.52 })
    assert.equal(borderline.label, 'Borderline Technical Document')
    assert.equal(borderline.tone, 'warning')
    assert.equal(borderline.confidencePct, 52)

    const manualNon = getDetectionMeta({
        classification: 'non_research',
        is_research_paper: false,
        manual_override: 'non_research',
        confidence: 0.25,
    })
    assert.equal(manualNon.label, 'Non-Research (Manual Override)')
    assert.equal(manualNon.tone, 'neutral')

    const defaultMissing = getFactTypeMeta('unknown_type')
    assert.equal(defaultMissing.label, 'Not in Paper')
    assert.equal(defaultMissing.description, 'Not explicitly stated in the paper.')
})

