import assert from 'node:assert/strict'
import test from 'node:test'
import {
    VOICE_STATES,
    VOICE_STATE_LABELS,
    VOICE_RECOVERY_DECISIONS,
    resolveVoiceReviewChoice,
    isVoiceRecordingSupported,
    getSupportedRecordingMimeType,
    extensionForMimeType,
    mapMicrophoneError,
    mapVoiceApiError,
    formatRecordingTimer,
} from './voiceUtils.js'

test('VOICE_STATES and labels expose expected foundation states', () => {
    assert.equal(VOICE_STATES.IDLE, 'IDLE')
    assert.equal(VOICE_STATES.LISTENING, 'LISTENING')
    assert.equal(VOICE_STATES.PROCESSING_AUDIO, 'PROCESSING_AUDIO')
    assert.equal(VOICE_STATES.TRANSCRIBING, 'TRANSCRIBING')
    assert.equal(VOICE_STATES.REVIEWING, 'REVIEWING')
    assert.equal(VOICE_STATES.THINKING, 'THINKING')
    assert.equal(VOICE_STATES.SPEAKING, 'SPEAKING')
    assert.equal(VOICE_STATES.ERROR, 'ERROR')

    assert.equal(VOICE_STATE_LABELS.LISTENING, 'Listening...')
    assert.equal(VOICE_STATE_LABELS.TRANSCRIBING, 'Understanding your question...')
    assert.equal(VOICE_STATE_LABELS.THINKING, 'Searching your documents...')
    assert.equal(VOICE_STATE_LABELS.SPEAKING, 'Speaking...')
})

test('browser capability and MIME negotiation pick compatible formats cleanly', () => {
    assert.equal(isVoiceRecordingSupported({}, undefined), false)
    assert.equal(
        isVoiceRecordingSupported({ mediaDevices: { getUserMedia: async () => {} } }, function MockRec() {}),
        true
    )

    const MockRecorderWebm = {
        isTypeSupported: (mime) => mime === 'audio/webm;codecs=opus',
    }
    assert.deepEqual(getSupportedRecordingMimeType(MockRecorderWebm), {
        mimeType: 'audio/webm;codecs=opus',
        extension: '.webm',
    })

    const MockRecorderOgg = {
        isTypeSupported: (mime) => mime === 'audio/ogg;codecs=opus',
    }
    assert.deepEqual(getSupportedRecordingMimeType(MockRecorderOgg), {
        mimeType: 'audio/ogg;codecs=opus',
        extension: '.ogg',
    })

    assert.equal(extensionForMimeType('audio/webm;codecs=opus'), '.webm')
    assert.equal(extensionForMimeType('audio/mp4'), '.mp4')
    assert.equal(extensionForMimeType('audio/wav'), '.wav')
})

test('microphone and API error mappers match user-facing recovery guidance', () => {
    assert.equal(
        mapMicrophoneError({ name: 'NotAllowedError', message: 'Permission denied' }),
        'Microphone permission was denied. You can type your question instead.'
    )
    assert.equal(
        mapMicrophoneError({ name: 'NotFoundError', message: 'Requested device not found' }),
        'No microphone was detected.'
    )
    assert.equal(
        mapMicrophoneError({ name: 'NotSupportedError', message: 'Not supported' }),
        'Voice recording is not supported in this browser.'
    )

    assert.equal(
        mapVoiceApiError({ status: 422, message: 'No speech detected. Please try again.' }, 'stt'),
        'No speech detected. Please try again.'
    )
    assert.equal(
        mapVoiceApiError({ status: 503, message: 'Speech recognition failed' }, 'stt'),
        "I couldn't understand the recording. Please try again or edit the transcript."
    )
    assert.equal(
        mapVoiceApiError({ status: 503, message: 'TTS offline' }, 'tts'),
        "Voice playback isn't available right now. Your answer is still shown above."
    )
})

test('formatRecordingTimer formats mm:ss cleanly', () => {
    assert.equal(formatRecordingTimer(0), '0:00')
    assert.equal(formatRecordingTimer(4.8), '0:04')
    assert.equal(formatRecordingTimer(75), '1:15')
})

test('resolveVoiceReviewChoice respects safety gate decisions and manual edit locks', () => {
    assert.equal(VOICE_RECOVERY_DECISIONS.RECOVERED, 'RECOVERED')
    assert.equal(VOICE_RECOVERY_DECISIONS.SUGGESTED, 'SUGGESTED')
    assert.equal(VOICE_RECOVERY_DECISIONS.AMBIGUOUS, 'AMBIGUOUS')

    assert.deepEqual(
        resolveVoiceReviewChoice({
            raw_transcript: 'What is a swion flood?',
            recovered_transcript: 'What is a SYN flood?',
            decision: 'RECOVERED',
            recovery_applied: true,
        }),
        { choice: 'recovered', activeText: 'What is a SYN flood?' }
    )

    assert.deepEqual(
        resolveVoiceReviewChoice({
            raw_transcript: 'What is sin?',
            recovered_transcript: 'What is sin?',
            decision: 'SUGGESTED',
            recovery_applied: false,
        }),
        { choice: 'raw', activeText: 'What is sin?' }
    )

    assert.deepEqual(
        resolveVoiceReviewChoice(
            {
                raw_transcript: 'What is a swion flood?',
                recovered_transcript: 'What is a SYN flood?',
                decision: 'RECOVERED',
                recovery_applied: true,
            },
            true
        ),
        { choice: 'manual', activeText: 'What is a swion flood?' }
    )
})

