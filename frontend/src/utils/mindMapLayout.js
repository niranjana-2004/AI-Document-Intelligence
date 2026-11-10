export const HORIZONTAL_GAP = 310
export const MIN_VERTICAL_SLOT = 86
export const MIN_ZOOM = 0.2
export const MAX_ZOOM = 2.0

/**
 * Computes consistent box dimensions per node tier matching mind-map.css rules.
 */
export function getNodeSize(node) {
    const labelLen = (node?.label || '').length
    if (node?.type === 'root') {
        const lines = Math.max(1, Math.ceil(labelLen / 19))
        return { width: 240, height: 50 + lines * 20 }
    }
    if (node?.type === 'topic') {
        const lines = Math.max(1, Math.ceil(labelLen / 19))
        return { width: 210, height: 42 + lines * 18 }
    }
    const lines = Math.max(1, Math.ceil(labelLen / 18))
    return { width: 190, height: 38 + lines * 17 }
}

/**
 * Recursively assigns tree layout coordinates and computes full dynamic bounding box
 * covering all visible nodes, connectors, and safe outer padding.
 */
export function computeMindMapLayout(mindMapData, collapsedIds = new Set()) {
    if (!mindMapData || !mindMapData.root) {
        return {
            nodes: [],
            edges: [],
            bounds: { minX: 0, maxX: 0, minY: 0, maxY: 0, width: 0, height: 0 },
        }
    }

    const nodes = []
    const edges = []

    function getSubtreeHeight(node) {
        const { height } = getNodeSize(node)
        const selfSlot = Math.max(MIN_VERTICAL_SLOT, height + 16)
        if (!node.children || node.children.length === 0 || collapsedIds.has(node.id)) {
            return selfSlot
        }
        const childrenHeight = node.children.reduce((acc, child) => acc + getSubtreeHeight(child), 0)
        return Math.max(selfSlot, childrenHeight)
    }

    function assignCoordinates(node, depth, topY) {
        const subtreeHeight = getSubtreeHeight(node)
        const size = getNodeSize(node)
        const nodeX = depth * HORIZONTAL_GAP
        const nodeY = topY + subtreeHeight / 2

        nodes.push({
            ...node,
            x: nodeX,
            y: nodeY,
            width: size.width,
            height: size.height,
            depth,
            isCollapsed: collapsedIds.has(node.id),
            hasChildren: Boolean(node.children && node.children.length > 0),
            childCount: node.children ? node.children.length : 0,
        })

        if (node.children && !collapsedIds.has(node.id)) {
            let currentY = topY
            for (const child of node.children) {
                const childSubtreeH = getSubtreeHeight(child)
                const childPos = assignCoordinates(child, depth + 1, currentY)

                edges.push({
                    id: `${node.id}->${child.id}`,
                    x1: nodeX + size.width / 2,
                    y1: nodeY,
                    x2: childPos.x - childPos.width / 2,
                    y2: childPos.y,
                    relationship: child.relationship || 'contains',
                })

                currentY += childSubtreeH
            }
        }

        return { x: nodeX, y: nodeY, width: size.width, height: size.height }
    }

    assignCoordinates(mindMapData.root, 0, 0)

    const rawMinX = Math.min(...nodes.map(n => n.x - n.width / 2))
    const rawMaxX = Math.max(...nodes.map(n => n.x + n.width / 2))
    const rawMinY = Math.min(...nodes.map(n => n.y - n.height / 2))
    const rawMaxY = Math.max(...nodes.map(n => n.y + n.height / 2))

    const H_PAD = 48
    const V_PAD = 44

    const minX = rawMinX - H_PAD
    const maxX = rawMaxX + H_PAD
    const minY = rawMinY - V_PAD
    const maxY = rawMaxY + V_PAD

    return {
        nodes,
        edges,
        bounds: {
            minX,
            maxX,
            minY,
            maxY,
            width: maxX - minX,
            height: maxY - minY,
        },
    }
}

/**
 * Clamps pan coordinates dynamically to generous bounds derived from actual graph bounds
 * so any edge/bottom node remains freely reachable while preventing losing the graph.
 */
export function clampView(candidate, bounds, viewportWidth, viewportHeight) {
    const zoom = Math.min(Math.max(MIN_ZOOM, candidate.zoom), MAX_ZOOM)
    if (!bounds || bounds.width <= 0 || viewportWidth <= 0 || viewportHeight <= 0) {
        return { zoom, x: candidate.x, y: candidate.y }
    }

    const boundAX = viewportWidth * 0.2 - bounds.maxX * zoom
    const boundBX = viewportWidth * 0.8 - bounds.minX * zoom
    const minPanX = Math.min(boundAX, boundBX)
    const maxPanX = Math.max(boundAX, boundBX)

    const boundAY = viewportHeight * 0.2 - bounds.maxY * zoom
    const boundBY = viewportHeight * 0.8 - bounds.minY * zoom
    const minPanY = Math.min(boundAY, boundBY)
    const maxPanY = Math.max(boundAY, boundBY)

    return {
        zoom,
        x: Math.min(Math.max(candidate.x, minPanX), maxPanX),
        y: Math.min(Math.max(candidate.y, minPanY), maxPanY),
    }
}

/**
 * Calculates optimal camera transform { zoom, x, y } to fit and center the entire graph
 * within the viewport, preserving readability on small mobile screens when requested.
 */
export function computeFitTransform(
    bounds,
    viewportWidth,
    viewportHeight,
    { enforceReadableMobileFloor = false } = {}
) {
    if (!bounds || bounds.width <= 0 || bounds.height <= 0) {
        return { zoom: 1.0, x: 140, y: 200 }
    }

    const vw = Math.max(240, viewportWidth)
    const vh = Math.max(240, viewportHeight)

    const scaleX = vw / bounds.width
    const scaleY = vh / bounds.height
    const rawFitScale = Math.min(scaleX, scaleY)

    const floor = enforceReadableMobileFloor && vw < 640 ? 0.52 : MIN_ZOOM
    const targetZoom = Math.min(Math.max(rawFitScale, floor), 1.0)

    const graphCenterX = (bounds.minX + bounds.maxX) / 2
    const graphCenterY = (bounds.minY + bounds.maxY) / 2

    let targetX
    if (bounds.width * targetZoom > vw) {
        // Keep left-most root branch cleanly inside viewport edge when horizontally wider
        targetX = -bounds.minX * targetZoom + 12
    } else {
        targetX = vw / 2 - graphCenterX * targetZoom
    }

    const targetY = vh / 2 - graphCenterY * targetZoom

    return {
        zoom: Number(targetZoom.toFixed(3)),
        x: Math.round(targetX),
        y: Math.round(targetY),
    }
}

/**
 * Returns default 100% view centered cleanly on the Root node.
 */
export function computeResetTransform(layout, viewportWidth, viewportHeight) {
    const vw = Math.max(240, viewportWidth)
    const vh = Math.max(240, viewportHeight)
    const rootNode = layout?.nodes?.find(n => n.type === 'root' || n.depth === 0)
    if (!rootNode) {
        return { zoom: 1.0, x: 160, y: Math.round(vh / 2) }
    }

    const targetZoom = 1.0
    const leftAnchor = Math.min(200, Math.round(vw * 0.25))
    const rootHalfW = (rootNode.width || 240) / 2
    const targetX = Math.max(leftAnchor, rootHalfW + 32) - rootNode.x * targetZoom
    const targetY = vh / 2 - rootNode.y * targetZoom

    return clampView(
        { zoom: targetZoom, x: Math.round(targetX), y: Math.round(targetY) },
        layout.bounds,
        vw,
        vh
    )
}
