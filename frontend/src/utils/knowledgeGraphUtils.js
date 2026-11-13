/**
 * Deterministic layout, filtering, neighborhood isolation, and shortest-path
 * helpers for the Cognidocs Source-Grounded Knowledge Graph UI.
 */

export const NODE_WIDTH = 196
export const NODE_HEIGHT = 64

export const NODE_TYPE_STYLES = {
    Attack: { color: '#dc2626', bg: 'rgba(220, 38, 38, 0.12)', label: 'Attack' },
    Protocol: { color: '#0284c7', bg: 'rgba(2, 132, 199, 0.12)', label: 'Protocol' },
    Defense: { color: '#059669', bg: 'rgba(5, 150, 105, 0.12)', label: 'Defense' },
    Method: { color: '#7c3aed', bg: 'rgba(124, 58, 237, 0.12)', label: 'Method' },
    Model: { color: '#6d28d9', bg: 'rgba(109, 40, 217, 0.12)', label: 'Model' },
    Dataset: { color: '#d97706', bg: 'rgba(217, 119, 6, 0.12)', label: 'Dataset' },
    Metric: { color: '#0d9488', bg: 'rgba(13, 148, 136, 0.12)', label: 'Metric' },
    Problem: { color: '#e11d48', bg: 'rgba(225, 29, 72, 0.12)', label: 'Problem' },
    Result: { color: '#16a34a', bg: 'rgba(22, 163, 74, 0.12)', label: 'Result' },
    Limitation: { color: '#ea580c', bg: 'rgba(234, 88, 12, 0.12)', label: 'Limitation' },
    FutureWork: { color: '#4f46e5', bg: 'rgba(79, 70, 229, 0.12)', label: 'Future Work' },
    System: { color: '#0891b2', bg: 'rgba(8, 145, 178, 0.12)', label: 'System' },
    Organization: { color: '#9333ea', bg: 'rgba(147, 51, 234, 0.12)', label: 'Organization' },
    Person: { color: '#2563eb', bg: 'rgba(37, 99, 235, 0.12)', label: 'Person' },
    Concept: { color: '#0f766e', bg: 'rgba(15, 118, 110, 0.12)', label: 'Concept' },
    Entity: { color: '#475569', bg: 'rgba(71, 85, 105, 0.12)', label: 'Entity' },
}

export function getNodeTypeStyle(nodeType) {
    return NODE_TYPE_STYLES[nodeType] || NODE_TYPE_STYLES.Concept
}

export function formatRelationshipLabel(rel) {
    return String(rel || 'related_to').replace(/_/g, ' ')
}

export function getEdgeKey(edge) {
    return `${edge.source_key}::${edge.relationship}::${edge.target_key}`
}

/**
 * Compute 1-hop neighborhood (connected nodes and connecting edges) around `centerKey`.
 */
export function getNeighborhood(edges, centerKey) {
    const nodeKeys = new Set()
    const edgeKeys = new Set()
    if (!centerKey) {
        return { nodeKeys, edgeKeys }
    }
    nodeKeys.add(centerKey)
    for (const edge of edges || []) {
        if (edge.source_key === centerKey || edge.target_key === centerKey) {
            nodeKeys.add(edge.source_key)
            nodeKeys.add(edge.target_key)
            edgeKeys.add(getEdgeKey(edge))
        }
    }
    return { nodeKeys, edgeKeys }
}

/**
 * Find shortest path between `startKey` and `endKey` across undirected projection of visible edges.
 */
export function computeShortestPath(edges, startKey, endKey) {
    if (!startKey || !endKey) {
        return { found: false, nodeKeys: [], edgeKeys: [] }
    }
    if (startKey === endKey) {
        return { found: true, nodeKeys: [startKey], edgeKeys: [] }
    }

    const adjacency = new Map()
    for (const edge of edges || []) {
        const ek = getEdgeKey(edge)
        if (!adjacency.has(edge.source_key)) adjacency.set(edge.source_key, [])
        if (!adjacency.has(edge.target_key)) adjacency.set(edge.target_key, [])
        adjacency.get(edge.source_key).push({ next: edge.target_key, edgeKey: ek })
        adjacency.get(edge.target_key).push({ next: edge.source_key, edgeKey: ek })
    }

    const queue = [startKey]
    const visited = new Set([startKey])
    const parent = new Map()

    while (queue.length > 0) {
        const current = queue.shift()
        if (current === endKey) {
            const nodeKeys = []
            const edgeKeys = []
            let cursor = endKey
            while (cursor !== undefined) {
                nodeKeys.unshift(cursor)
                const step = parent.get(cursor)
                if (!step) break
                edgeKeys.unshift(step.edgeKey)
                cursor = step.prev
            }
            return { found: true, nodeKeys, edgeKeys }
        }
        for (const neighbor of adjacency.get(current) || []) {
            if (!visited.has(neighbor.next)) {
                visited.add(neighbor.next)
                parent.set(neighbor.next, { prev: current, edgeKey: neighbor.edgeKey })
                queue.push(neighbor.next)
            }
        }
    }

    return { found: false, nodeKeys: [], edgeKeys: [] }
}

/**
 * Filter nodes and edges cleanly according to active UI filters, neighborhood focus, and search query.
 */
export function filterKnowledgeGraph(nodes, edges, options = {}) {
    const {
        searchQuery = '',
        selectedNodeTypes = [],
        selectedRelationships = [],
        selectedConfidenceTiers = [],
        focusNodeKey = null,
        isolateNeighborhood = false,
        scopeFilter = 'all', // 'all' | 'shared' | 'doc_specific'
        activeDocumentId = null,
    } = options

    const q = String(searchQuery || '').trim().toLowerCase()
    const typeSet = new Set(selectedNodeTypes)
    const relSet = new Set(selectedRelationships)
    const tierSet = new Set(selectedConfidenceTiers)

    const neighborhood = isolateNeighborhood && focusNodeKey
        ? getNeighborhood(edges, focusNodeKey)
        : null

    let visibleNodes = (nodes || []).filter((n) => {
        const nodeKey = n.node_key || n.entity_key
        const label = n.label || n.canonical_name
        if (typeSet.size > 0 && !typeSet.has(n.node_type)) return false
        if (neighborhood && !neighborhood.nodeKeys.has(nodeKey)) return false

        // Scope filter for cross-document graphs
        if (scopeFilter === 'shared' && !n.is_shared) return false
        if (scopeFilter === 'doc_specific' && n.is_shared) return false

        // Document filter for specific document isolation
        if (activeDocumentId) {
            const docIdNum = Number(activeDocumentId)
            const inDocs = (n.documents || []).some((d) => d.document_id === docIdNum)
            const inOccs = (n.occurrences || []).some((o) => o.document_id === docIdNum)
            const inSingleDoc = n.document_id === docIdNum
            if (!inDocs && !inOccs && !inSingleDoc) return false
        }

        if (q) {
            const labelMatch = String(label || '').toLowerCase().includes(q)
            const aliasMatch = (n.aliases || []).some((a) => String(a).toLowerCase().includes(q))
            const typeMatch = String(n.node_type || '').toLowerCase().includes(q)
            if (!labelMatch && !aliasMatch && !typeMatch) return false
        }
        return true
    })

    const visibleNodeKeys = new Set(visibleNodes.map((n) => n.node_key || n.entity_key))

    // If search matched nodes, optionally retain directly connected edges among visible nodes
    const visibleEdges = (edges || []).filter((e) => {
        if (!visibleNodeKeys.has(e.source_key) || !visibleNodeKeys.has(e.target_key)) return false
        if (relSet.size > 0 && !relSet.has(e.relationship)) return false
        if (tierSet.size > 0 && !tierSet.has(e.confidence_tier)) return false
        if (neighborhood && !neighborhood.edgeKeys.has(getEdgeKey(e))) return false
        if (activeDocumentId) {
            const docIdNum = Number(activeDocumentId)
            const hasDoc = (e.supporting_document_ids || []).includes(docIdNum)
            const inSingleDoc = e.document_id === docIdNum
            if (!hasDoc && !inSingleDoc) return false
        }
        return true
    })

    return {
        nodes: visibleNodes,
        edges: visibleEdges,
    }
}

/**
 * Compute deterministic non-overlapping canvas coordinates for `clustered`, `hierarchical`, or `force`.
 */
export function computeKnowledgeGraphLayout(nodes, edges, mode = 'clustered') {
    const list = nodes || []
    if (list.length === 0) {
        return { positions: new Map(), width: 960, height: 600 }
    }

    const positions = new Map()
    const padX = 110
    const padY = 90
    const cellW = NODE_WIDTH + 68
    const cellH = NODE_HEIGHT + 74

    const getNodeKey = (n) => n.node_key || n.entity_key

    if (mode === 'hierarchical') {
        const inDegree = new Map()
        const outAdj = new Map()
        for (const n of list) {
            const k = getNodeKey(n)
            inDegree.set(k, 0)
            outAdj.set(k, [])
        }
        for (const e of edges || []) {
            if (inDegree.has(e.source_key) && inDegree.has(e.target_key) && e.source_key !== e.target_key) {
                inDegree.set(e.target_key, inDegree.get(e.target_key) + 1)
                outAdj.get(e.source_key).push(e.target_key)
            }
        }

        const level = new Map()
        const queue = []
        for (const n of list) {
            const k = getNodeKey(n)
            if ((inDegree.get(k) || 0) === 0) {
                level.set(k, 0)
                queue.push(k)
            }
        }
        if (queue.length === 0) {
            const topNode = [...list].sort((a, b) => (b.importance_score || 0) - (a.importance_score || 0))[0]
            const topK = getNodeKey(topNode)
            level.set(topK, 0)
            queue.push(topK)
        }

        let head = 0
        while (head < queue.length) {
            const cur = queue[head++]
            const curLvl = level.get(cur) || 0
            for (const nxt of outAdj.get(cur) || []) {
                if (!level.has(nxt) || (level.get(nxt) < curLvl + 1 && curLvl + 1 <= 5)) {
                    level.set(nxt, Math.min(5, curLvl + 1))
                    queue.push(nxt)
                }
            }
        }

        const buckets = new Map()
        for (const n of list) {
            const k = getNodeKey(n)
            const lvl = level.has(k) ? level.get(k) : 1
            if (!buckets.has(lvl)) buckets.set(lvl, [])
            buckets.get(lvl).push(n)
        }

        const sortedLevels = [...buckets.keys()].sort((a, b) => a - b)
        let maxRows = 1
        sortedLevels.forEach((lvl) => {
            maxRows = Math.max(maxRows, buckets.get(lvl).length)
        })

        const colGap = NODE_WIDTH + 130
        const rowGap = NODE_HEIGHT + 52
        const totalH = Math.max(580, padY * 2 + maxRows * rowGap)

        sortedLevels.forEach((lvl, colIdx) => {
            const colNodes = buckets.get(lvl).sort((a, b) => (b.importance_score || 0) - (a.importance_score || 0))
            const startY = Math.max(padY, (totalH - colNodes.length * rowGap) / 2)
            colNodes.forEach((n, rowIdx) => {
                const k = getNodeKey(n)
                positions.set(k, {
                    x: padX + colIdx * colGap + NODE_WIDTH / 2,
                    y: startY + rowIdx * rowGap + NODE_HEIGHT / 2,
                })
            })
        })

        return {
            positions,
            width: Math.max(1050, padX * 2 + sortedLevels.length * colGap),
            height: totalH,
        }
    }

    // Default Clustered seed positions (grouped by node_type cleanly)
    const groups = new Map()
    for (const n of list) {
        const g = n.node_type || 'Concept'
        if (!groups.has(g)) groups.set(g, [])
        groups.get(g).push(n)
    }

    const sortedGroups = [...groups.entries()].sort((a, b) => b[1].length - a[1].length)
    const colsPerRow = Math.max(3, Math.ceil(Math.sqrt(list.length * 1.25)))
    let cursorCol = 0
    let cursorRow = 0
    let maxColSeen = 0
    let maxRowSeen = 0

    for (const [, groupNodes] of sortedGroups) {
        groupNodes.sort((a, b) => (b.importance_score || 0) - (a.importance_score || 0))
        for (const n of groupNodes) {
            const k = getNodeKey(n)
            positions.set(k, {
                x: padX + cursorCol * cellW + NODE_WIDTH / 2,
                y: padY + cursorRow * cellH + NODE_HEIGHT / 2,
            })
            maxColSeen = Math.max(maxColSeen, cursorCol)
            maxRowSeen = Math.max(maxRowSeen, cursorRow)
            cursorCol += 1
            if (cursorCol >= colsPerRow) {
                cursorCol = 0
                cursorRow += 1
            }
        }
        if (cursorCol !== 0) {
            cursorCol = 0
            cursorRow += 1
        }
    }

    let width = Math.max(1020, padX * 2 + (maxColSeen + 1) * cellW)
    let height = Math.max(660, padY * 2 + (maxRowSeen + 1) * cellH)

    if (mode === 'force' && list.length > 1) {
        const coords = new Map()
        for (const n of list) {
            const k = getNodeKey(n)
            const p = positions.get(k)
            coords.set(k, { x: p.x, y: p.y })
        }

        const keys = list.map((n) => getNodeKey(n))
        const idealDist = 235
        const kRepel = 42000

        for (let iter = 0; iter < 42; iter++) {
            const disp = new Map(keys.map((k) => [k, { dx: 0, dy: 0 }]))

            for (let i = 0; i < keys.length; i++) {
                for (let j = i + 1; j < keys.length; j++) {
                    const k1 = keys[i]
                    const k2 = keys[j]
                    const p1 = coords.get(k1)
                    const p2 = coords.get(k2)
                    const vx = p1.x - p2.x
                    const vy = p1.y - p2.y
                    const distSq = Math.max(vx * vx + vy * vy, 600)
                    const dist = Math.sqrt(distSq)
                    const force = kRepel / distSq
                    const fx = (vx / dist) * force
                    const fy = (vy / dist) * force
                    disp.get(k1).dx += fx
                    disp.get(k1).dy += fy
                    disp.get(k2).dx -= fx
                    disp.get(k2).dy -= fy
                }
            }

            for (const e of edges || []) {
                if (!coords.has(e.source_key) || !coords.has(e.target_key)) continue
                const p1 = coords.get(e.source_key)
                const p2 = coords.get(e.target_key)
                const vx = p2.x - p1.x
                const vy = p2.y - p1.y
                const dist = Math.max(Math.sqrt(vx * vx + vy * vy), 1)
                const pull = (dist - idealDist) * 0.08
                const fx = (vx / dist) * pull
                const fy = (vy / dist) * pull
                disp.get(e.source_key).dx += fx
                disp.get(e.source_key).dy += fy
                disp.get(e.target_key).dx -= fx
                disp.get(e.target_key).dy -= fy
            }

            const maxStep = Math.max(8, 28 - iter * 0.45)
            for (const k of keys) {
                const d = disp.get(k)
                const dLen = Math.max(Math.sqrt(d.dx * d.dx + d.dy * d.dy), 1)
                const step = Math.min(dLen, maxStep)
                const cur = coords.get(k)
                cur.x += (d.dx / dLen) * step
                cur.y += (d.dy / dLen) * step
            }
        }

        // Re-normalize coordinates into clean padded viewport bounds
        let minX = Infinity
        let minY = Infinity
        let maxX = -Infinity
        let maxY = -Infinity
        for (const p of coords.values()) {
            minX = Math.min(minX, p.x)
            minY = Math.min(minY, p.y)
            maxX = Math.max(maxX, p.x)
            maxY = Math.max(maxY, p.y)
        }
        const offsetX = padX + NODE_WIDTH / 2 - minX
        const offsetY = padY + NODE_HEIGHT / 2 - minY
        for (const k of keys) {
            const p = coords.get(k)
            positions.set(k, { x: p.x + offsetX, y: p.y + offsetY })
        }
        width = Math.max(1020, (maxX - minX) + padX * 2 + NODE_WIDTH)
        height = Math.max(660, (maxY - minY) + padY * 2 + NODE_HEIGHT)
    }

    return { positions, width, height }
}

