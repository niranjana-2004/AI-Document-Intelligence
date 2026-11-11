/**
 * Frontend voice state constants, browser MediaRecorder capability detection,
 * MIME negotiation, and user-friendly fallback error mapping.
 */

export const VOICE_STATES = {
    IDLE: 'IDLE',
    LISTENING: 'LISTENING',
    PROCESSING_AUDIO: 'PROCESSING_AUDIO',
    TRANSCRIBING: 'TRANSCRIBING',
    REVIEWING: 'REVIEWING',
    THINKING: 'THINKING',
    SPEAKING: 'SPEAKING',
    ERROR: 'ERROR',
}

export const VOICE_STATE_LABELS = {
    IDLE: 'Ask by voice',
    LISTENING: 'Listening...',
    PROCESSING_AUDIO: 'Processing audio...',
    TRANSCRIBING: 'Understanding your question...',
    REVIEWING: 'Review your question',
    THINKING: 'Searching your documents...',
    SPEAKING: 'Speaking...',
    ERROR: 'Voice input failed',
}

export const MAX_RECORDING_SECONDS = 85

const MIME_CANDIDATES = [
    { mimeType: 'audio/webm;codecs=opus', extension: '.webm' },
    { mimeType: 'audio/webm', extension: '.webm' },
    { mimeType: 'audio/ogg;codecs=opus', extension: '.ogg' },
    { mimeType: 'audio/ogg', extension: '.ogg' },
    { mimeType: 'audio/mp4', extension: '.mp4' },
    { mimeType: 'audio/wav', extension: '.wav' },
]

export function isVoiceRecordingSupported(
    nav = typeof navigator !== 'undefined' ? navigator : undefined,
    Recorder = typeof MediaRecorder !== 'undefined' ? MediaRecorder : undefined
) {
    return Boolean(nav?.mediaDevices?.getUserMedia && typeof Recorder !== 'undefined')
}

export function getSupportedRecordingMimeType(
    Recorder = typeof MediaRecorder !== 'undefined' ? MediaRecorder : undefined
) {
    if (typeof Recorder === 'undefined' || typeof Recorder.isTypeSupported !== 'function') {
        return { mimeType: '', extension: '.webm' }
    }
    for (const candidate of MIME_CANDIDATES) {
        try {
            if (Recorder.isTypeSupported(candidate.mimeType)) {
                return candidate
            }
        } catch {
            // Continue checking supported container formats
        }
    }
    return { mimeType: '', extension: '.webm' }
}

export function extensionForMimeType(mimeType) {
    const base = String(mimeType || '').split(';')[0].trim().toLowerCase()
    if (base === 'audio/ogg' || base === 'application/ogg') return '.ogg'
    if (base === 'audio/mp4' || base === 'audio/m4a' || base === 'audio/x-m4a') return '.mp4'
    if (base === 'audio/wav' || base === 'audio/x-wav' || base === 'audio/wave') return '.wav'
    if (base === 'audio/mpeg' || base === 'audio/mp3') return '.mp3'
    return '.webm'
}

export function mapMicrophoneError(err) {
    const name = String(err?.name || '')
    const msg = String(err?.message || '').toLowerCase()

    if (
        name === 'NotAllowedError' ||
        name === 'PermissionDeniedError' ||
        name === 'SecurityError' ||
        msg.includes('permission denied') ||
        msg.includes('denied')
    ) {
        return 'Microphone permission was denied. You can type your question instead.'
    }

    if (
        name === 'NotFoundError' ||
        name === 'DevicesNotFoundError' ||
        name === 'OverconstrainedError' ||
        msg.includes('not found') ||
        msg.includes('no microphone')
    ) {
        return 'No microphone was detected.'
    }

    if (name === 'NotSupportedError' || msg.includes('not supported')) {
        return 'Voice recording is not supported in this browser.'
    }

    return 'Unable to start voice recording. Please try again or type your question instead.'
}

export function mapVoiceApiError(err, stage = 'stt') {
    const raw = String(err?.message || '').trim()
    const lower = raw.toLowerCase()

    if (stage === 'tts') {
        return "Voice playback isn't available right now. Your answer is still shown above."
    }

    if (
        err?.status === 422 ||
        lower.includes('no speech detected') ||
        lower.includes('recorded audio is empty') ||
        lower.includes('too short')
    ) {
        return 'No speech detected. Please try again.'
    }

    if (err?.status === 413 || lower.includes('exceeds maximum')) {
        return raw || 'Recording exceeds maximum allowed duration or size.'
    }

    if (err?.status === 415 || lower.includes('unsupported')) {
        return raw || 'Unsupported recording format.'
    }

    if (err?.status === 503 || lower.includes('recognition')) {
        return "I couldn't understand the recording. Please try again or edit the transcript."
    }

    return raw || "I couldn't understand the recording. Please try again or edit the transcript."
}

export function formatRecordingTimer(seconds) {
    const total = Math.max(0, Math.floor(Number(seconds) || 0))
    const mins = Math.floor(total / 60)
    const secs = total % 60
    return `${mins}:${String(secs).padStart(2, '0')}`
}

