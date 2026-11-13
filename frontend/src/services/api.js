export const API_BASE_URL = import.meta.env?.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export async function apiRequest(endpoint, options = {}) {
    const token = localStorage.getItem('access_token')

    const headers = {
        ...(options.headers || {}),
    }

    if (token) {
        headers.Authorization = `Bearer ${token}`
    }

    if (options.body && !(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json'
    }

    const response = await fetch(
        `${API_BASE_URL}${endpoint}`,
        {
            ...options,
            headers,
        }
    )

    const data = await response.json().catch(() => null)

    if (!response.ok) {
        if (response.status === 401) {
            localStorage.removeItem('access_token')
            localStorage.removeItem('user')
        }

        const error = new Error(
            data?.detail || 'Something went wrong. Please try again.'
        )
        error.status = response.status
        throw error
    }

    return data
}

export async function transcribeVoiceAudio(audioBlob, filename = 'recording.webm', options = {}) {
    const formData = new FormData()
    formData.append('audio', audioBlob, filename)
    if (options.documentId != null) {
        formData.append('document_id', String(options.documentId))
    }
    if (Array.isArray(options.documentIds) && options.documentIds.length > 0) {
        formData.append('document_ids', JSON.stringify(options.documentIds))
    }
    return apiRequest('/voice/transcribe', {
        method: 'POST',
        body: formData,
        signal: options.signal,
    })
}

export async function recoverVoiceQuery(payload, options = {}) {
    return apiRequest('/voice/recover-query', {
        method: 'POST',
        body: JSON.stringify(payload),
        signal: options.signal,
    })
}

export async function synthesizeVoiceSpeech(text, options = {}) {
    const token = localStorage.getItem('access_token')
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
    }
    if (token) {
        headers.Authorization = `Bearer ${token}`
    }

    const response = await fetch(`${API_BASE_URL}/voice/speak`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ text }),
        signal: options.signal,
    })

    if (!response.ok) {
        if (response.status === 401) {
            localStorage.removeItem('access_token')
            localStorage.removeItem('user')
        }
        const errData = await response.json().catch(() => null)
        const error = new Error(
            errData?.detail || "Voice playback isn't available right now."
        )
        error.status = response.status
        throw error
    }

    const blob = await response.blob()
    return {
        blob,
        engine: response.headers.get('X-TTS-Engine') || 'local-tts',
        model: response.headers.get('X-TTS-Model') || '',
        processingMs: response.headers.get('X-TTS-Processing-Ms') || null,
    }
}

export async function analyzeResearchPaper(documentId, options = {}) {
    return apiRequest(`/documents/${documentId}/research-analysis`, {
        method: 'POST',
        body: JSON.stringify({
            force_refresh: Boolean(options.forceRefresh),
            classification_override: options.classificationOverride || null,
            skip_llm: Boolean(options.skipLlm),
        }),
        signal: options.signal,
    })
}

export async function getResearchPaperAnalysis(documentId, options = {}) {
    return apiRequest(`/documents/${documentId}/research-analysis`, {
        method: 'GET',
        signal: options.signal,
    })
}

export async function generateKnowledgeGraph(documentId, options = {}) {
    return apiRequest(`/documents/${documentId}/knowledge-graph`, {
        method: 'POST',
        body: JSON.stringify({
            force_refresh: Boolean(options.forceRefresh),
            include_low_confidence: Boolean(options.includeLowConfidence),
            skip_llm: Boolean(options.skipLlm),
            max_nodes: options.maxNodes ?? 32,
        }),
        signal: options.signal,
    })
}

export async function getKnowledgeGraph(documentId, options = {}) {
    const params = new URLSearchParams()
    if (options.includeLowConfidence) {
        params.set('include_low_confidence', 'true')
    }
    const qs = params.toString()
    return apiRequest(`/documents/${documentId}/knowledge-graph${qs ? `?${qs}` : ''}`, {
        method: 'GET',
        signal: options.signal,
    })
}

export async function regenerateKnowledgeGraph(documentId, options = {}) {
    return apiRequest(`/documents/${documentId}/knowledge-graph/regenerate`, {
        method: 'POST',
        body: JSON.stringify({
            force_refresh: true,
            include_low_confidence: Boolean(options.includeLowConfidence),
            skip_llm: Boolean(options.skipLlm),
            max_nodes: options.maxNodes ?? 32,
        }),
        signal: options.signal,
    })
}

export async function deleteKnowledgeGraph(documentId) {
    return apiRequest(`/documents/${documentId}/knowledge-graph`, {
        method: 'DELETE',
    })
}

export async function generateCrossDocumentKnowledgeGraph(options = {}) {
    return apiRequest('/documents/knowledge-graph/cross-document', {
        method: 'POST',
        body: JSON.stringify({
            document_ids: options.documentIds || [],
            force_refresh: Boolean(options.forceRefresh),
            include_low_confidence: Boolean(options.includeLowConfidence),
            skip_llm: Boolean(options.skipLlm),
            max_nodes: options.maxNodes ?? 60,
            only_shared: Boolean(options.onlyShared),
        }),
        signal: options.signal,
    })
}

export async function getCrossDocumentKnowledgeGraph(graphId, options = {}) {
    const params = new URLSearchParams()
    if (options.includeLowConfidence) params.append('include_low_confidence', 'true')
    if (options.onlyShared) params.append('only_shared', 'true')
    const qs = params.toString()
    return apiRequest(`/documents/knowledge-graph/cross-document/${graphId}${qs ? `?${qs}` : ''}`, {
        method: 'GET',
        signal: options.signal,
    })
}

export async function listCrossDocumentEntities(graphId, options = {}) {
    const params = new URLSearchParams()
    if (options.onlyShared) params.append('only_shared', 'true')
    if (options.query) params.append('q', options.query)
    const qs = params.toString()
    return apiRequest(`/documents/knowledge-graph/cross-document/${graphId}/entities${qs ? `?${qs}` : ''}`, {
        method: 'GET',
        signal: options.signal,
    })
}

export async function getCrossDocumentEntity(graphId, entityKey, options = {}) {
    return apiRequest(`/documents/knowledge-graph/cross-document/${graphId}/entity/${encodeURIComponent(entityKey)}`, {
        method: 'GET',
        signal: options.signal,
    })
}

export async function deleteCrossDocumentKnowledgeGraph(graphId) {
    return apiRequest(`/documents/knowledge-graph/cross-document/${graphId}`, {
        method: 'DELETE',
    })
}
