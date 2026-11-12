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