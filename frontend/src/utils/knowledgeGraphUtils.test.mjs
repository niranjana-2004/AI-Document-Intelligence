import test from 'node:test'
import assert from 'node:assert/strict'

import {
    computeKnowledgeGraphLayout,
    computeShortestPath,
    filterKnowledgeGraph,
    getNeighborhood,
} from './knowledgeGraphUtils.js'

const SAMPLE_NODES = [
    { node_key: 'syn_flood', label: 'SYN Flood', node_type: 'Attack', importance_score: 0.95, aliases: ['Half-Open Attack'] },
    { node_key: 'tcp_handshake', label: 'TCP Three-Way Handshake', node_type: 'Protocol', importance_score: 0.85, aliases: [] },
    { node_key: 'tcb', label: 'TCB', node_type: 'System', importance_score: 0.72, aliases: ['Transmission Control Block'] },
    { node_key: 'syn_cookies', label: 'SYN Cookies', node_type: 'Defense', importance_score: 0.8, aliases: [] },
]

const SAMPLE_EDGES = [
    { source_key: 'syn_flood', target_key: 'tcp_handshake', relationship: 'depends_on', confidence: 0.88, confidence_tier: 'high' },
    { source_key: 'syn_flood', target_key: 'tcb', relationship: 'degrades', confidence: 0.65, confidence_tier: 'medium' },
    { source_key: 'syn_cookies', target_key: 'syn_flood', relationship: 'contradicts', confidence: 0.82, confidence_tier: 'high' },
]

test('filterKnowledgeGraph filters by node type, relationship, and search query', () => {
    const byType = filterKnowledgeGraph(SAMPLE_NODES, SAMPLE_EDGES, { selectedNodeTypes: ['Attack', 'Defense'] })
    assert.equal(byType.nodes.length, 2)
    assert.equal(byType.edges.length, 1)
    assert.equal(byType.edges[0].relationship, 'contradicts')

    const bySearch = filterKnowledgeGraph(SAMPLE_NODES, SAMPLE_EDGES, { searchQuery: 'Transmission Control' })
    assert.equal(bySearch.nodes.length, 1)
    assert.equal(bySearch.nodes[0].node_key, 'tcb')
})

test('getNeighborhood returns exact 1-hop subgraph', () => {
    const { nodeKeys, edgeKeys } = getNeighborhood(SAMPLE_EDGES, 'tcp_handshake')
    assert.ok(nodeKeys.has('tcp_handshake'))
    assert.ok(nodeKeys.has('syn_flood'))
    assert.ok(!nodeKeys.has('syn_cookies'))
    assert.equal(edgeKeys.size, 1)
})

test('computeShortestPath finds valid path across visible graph', () => {
    const res = computeShortestPath(SAMPLE_EDGES, 'syn_cookies', 'tcb')
    assert.equal(res.found, true)
    assert.deepEqual(res.nodeKeys, ['syn_cookies', 'syn_flood', 'tcb'])
    assert.equal(res.edgeKeys.length, 2)
})

test('computeKnowledgeGraphLayout produces finite bounded coordinates for all 3 modes', () => {
    for (const mode of ['clustered', 'hierarchical', 'force']) {
        const layout = computeKnowledgeGraphLayout(SAMPLE_NODES, SAMPLE_EDGES, mode)
        assert.ok(layout.width >= 960)
        assert.ok(layout.height >= 580)
        assert.equal(layout.positions.size, SAMPLE_NODES.length)
        for (const pos of layout.positions.values()) {
            assert.ok(Number.isFinite(pos.x) && pos.x > 0)
            assert.ok(Number.isFinite(pos.y) && pos.y > 0)
        }
    }
})

