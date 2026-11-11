import { useEffect, useRef, useState } from 'react'
import {
    Mic,
    Square,
    Volume2,
    Play,
    Pause,
    RotateCcw,
    Edit3,
    Check,
    X,
    AlertTriangle,
    Loader2,
} from 'lucide-react'
import {
    VOICE_STATES,
    VOICE_STATE_LABELS,
    formatRecordingTimer,
} from '../utils/voiceUtils'
import '../styles/voice-assistant.css'

export function VoiceStatusBanner({
    voiceState,
    recordingSeconds,
    voiceError,
    audioPaused,
    onStopRecording,
    onTogglePausePlayback,
    onStopPlayback,
    onRetry,
    onDismissError,
}) {
    if (
        voiceState === VOICE_STATES.IDLE ||
        voiceState === VOICE_STATES.REVIEWING
    ) {
        return null
    }

    const label = VOICE_STATE_LABELS[voiceState] || ''

    return (
        <div
            className={`voice-status-banner voice-state-${voiceState.toLowerCase()}`}
            role="status"
            aria-live="polite"
        >
            <div className="voice-status-left">
                {voiceState === VOICE_STATES.LISTENING && (
                    <>
                        <span className="voice-live-dot" aria-hidden="true" />
                        <span className="voice-status-text">{label}</span>
                        <span className="voice-mini-bars" aria-hidden="true">
                            <span />
                            <span />
                            <span />
                            <span />
                        </span>
                        <span className="voice-timer-pill">
                            {formatRecordingTimer(recordingSeconds)}
                        </span>
                    </>
                )}

                {(voiceState === VOICE_STATES.PROCESSING_AUDIO ||
                    voiceState === VOICE_STATES.TRANSCRIBING ||
                    voiceState === VOICE_STATES.THINKING) && (
                    <>
                        <Loader2 size={15} className="voice-spin-icon" aria-hidden="true" />
                        <span className="voice-status-text">{label}</span>
                    </>
                )}

                {voiceState === VOICE_STATES.SPEAKING && (
                    <>
                        <Volume2 size={15} className="voice-speak-icon" aria-hidden="true" />
                        <span className="voice-status-text">
                            {audioPaused ? 'Paused speech' : label}
                        </span>
                    </>
                )}

                {voiceState === VOICE_STATES.ERROR && (
                    <>
                        <AlertTriangle size={15} className="voice-error-icon" aria-hidden="true" />
                        <div className="voice-error-copy">
                            <strong>{VOICE_STATE_LABELS.ERROR}</strong>
                            <span>{voiceError || 'Please try again or type your question instead.'}</span>
                        </div>
                    </>
                )}
            </div>

            <div className="voice-status-actions">
                {voiceState === VOICE_STATES.LISTENING && (
                    <button
                        type="button"
                        className="voice-action-btn voice-stop-rec-btn"
                        onClick={onStopRecording}
                        aria-label="Stop recording"
                    >
                        <Square size={12} aria-hidden="true" />
                        <span>Stop</span>
                    </button>
                )}

                {voiceState === VOICE_STATES.SPEAKING && (
                    <>
                        <button
                            type="button"
                            className="voice-action-btn"
                            onClick={onTogglePausePlayback}
                            aria-label={audioPaused ? 'Play speech' : 'Pause speech'}
                        >
                            {audioPaused ? (
                                <>
                                    <Play size={12} aria-hidden="true" />
                                    <span>Play</span>
                                </>
                            ) : (
                                <>
                                    <Pause size={12} aria-hidden="true" />
                                    <span>Pause</span>
                                </>
                            )}
                        </button>
                        <button
                            type="button"
                            className="voice-action-btn voice-stop-play-btn"
                            onClick={onStopPlayback}
                            aria-label="Stop speech"
                        >
                            <Square size={12} aria-hidden="true" />
                            <span>Stop</span>
                        </button>
                    </>
                )}

                {voiceState === VOICE_STATES.ERROR && (
                    <>
                        {onRetry && (
                            <button
                                type="button"
                                className="voice-action-btn"
                                onClick={onRetry}
                                aria-label="Try voice input again"
                            >
                                <RotateCcw size={12} aria-hidden="true" />
                                <span>Try again</span>
                            </button>
                        )}
                        <button
                            type="button"
                            className="voice-dismiss-btn"
                            onClick={onDismissError}
                            aria-label="Dismiss voice notice"
                        >
                            <X size={13} aria-hidden="true" />
                        </button>
                    </>
                )}
            </div>
        </div>
    )
}

export function VoiceTranscriptReview({
    transcript,
    metadata,
    onChangeTranscript,
    onSubmitTranscript,
    onCancelTranscript,
    disabled = false,
}) {
    const [isEditing, setIsEditing] = useState(false)
    const editInputRef = useRef(null)

    useEffect(() => {
        if (isEditing && editInputRef.current) {
            editInputRef.current.focus()
            const len = editInputRef.current.value.length
            editInputRef.current.setSelectionRange(len, len)
        }
    }, [isEditing])

    const canSubmit = !disabled && Boolean((transcript || '').trim())

    return (
        <section
            className="voice-transcript-review"
            aria-label="Voice transcript review"
        >
            <div className="voice-review-header">
                <div className="voice-review-title-group">
                    <Mic size={14} className="voice-review-mic" aria-hidden="true" />
                    <span className="voice-review-label">You said:</span>
                    {metadata?.duration_seconds != null && (
                        <span className="voice-review-meta">
                            {metadata.duration_seconds}s · Local STT
                        </span>
                    )}
                </div>
                <button
                    type="button"
                    className="voice-dismiss-btn"
                    onClick={onCancelTranscript}
                    aria-label="Cancel voice transcript"
                    title="Cancel"
                >
                    <X size={14} aria-hidden="true" />
                </button>
            </div>

            {isEditing ? (
                <textarea
                    ref={editInputRef}
                    className="voice-review-editor"
                    value={transcript}
                    onChange={(e) => onChangeTranscript(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault()
                            if (canSubmit) onSubmitTranscript()
                        } else if (e.key === 'Escape') {
                            e.preventDefault()
                            onCancelTranscript()
                        }
                    }}
                    rows={2}
                    disabled={disabled}
                    aria-label="Edit voice transcript before asking"
                />
            ) : (
                <p className="voice-review-quote">
                    &ldquo;{transcript}&rdquo;
                </p>
            )}

            <div className="voice-review-actions">
                <button
                    type="button"
                    className="voice-review-btn voice-review-edit-btn"
                    onClick={() => setIsEditing((prev) => !prev)}
                    disabled={disabled}
                >
                    <Edit3 size={13} aria-hidden="true" />
                    <span>{isEditing ? 'Done Editing' : 'Edit'}</span>
                </button>

                <div className="voice-review-submit-group">
                    <button
                        type="button"
                        className="voice-review-btn voice-review-cancel-btn"
                        onClick={onCancelTranscript}
                        disabled={disabled}
                    >
                        Cancel
                    </button>
                    <button
                        type="button"
                        className="voice-review-btn voice-review-ask-btn"
                        onClick={onSubmitTranscript}
                        disabled={!canSubmit}
                        aria-label="Ask question with reviewed transcript"
                    >
                        <Check size={13} aria-hidden="true" />
                        <span>Ask</span>
                    </button>
                </div>
            </div>
        </section>
    )
}

export function VoiceMicButton({
    voiceState,
    disabled,
    supported,
    onToggleMic,
}) {
    const isListening = voiceState === VOICE_STATES.LISTENING
    const isBusy =
        voiceState === VOICE_STATES.PROCESSING_AUDIO ||
        voiceState === VOICE_STATES.TRANSCRIBING ||
        voiceState === VOICE_STATES.THINKING

    return (
        <button
            type="button"
            className={`voice-mic-btn ${isListening ? 'is-listening' : ''} ${
                !supported ? 'is-unsupported' : ''
            }`}
            onClick={onToggleMic}
            disabled={disabled || isBusy}
            aria-label={
                isListening
                    ? 'Stop voice recording'
                    : 'Ask a question by voice'
            }
            aria-pressed={isListening}
            title={
                !supported
                    ? 'Voice recording is not supported in this browser'
                    : isListening
                    ? 'Click to stop recording'
                    : 'Ask a question by voice'
            }
        >
            {isListening ? (
                <>
                    <span className="voice-mic-rec-dot" aria-hidden="true" />
                    <span>Listening...</span>
                </>
            ) : (
                <>
                    <Mic size={15} aria-hidden="true" />
                    <span>Ask by voice</span>
                </>
            )}
        </button>
    )
}

export function MessagePlaybackControls({
    msgId,
    activePlaybackMsgId,
    isLoadingTts,
    isSpeaking,
    isPaused,
    onPlay,
    onTogglePause,
    onStop,
}) {
    const isThisMessage = activePlaybackMsgId === msgId
    const isThisLoading = isThisMessage && isLoadingTts
    const isThisActive = isThisMessage && (isSpeaking || isPaused)

    if (isThisLoading) {
        return (
            <span className="msg-voice-loading" role="status">
                <Loader2 size={12} className="voice-spin-icon" aria-hidden="true" />
                <span>Preparing voice...</span>
            </span>
        )
    }

    if (isThisActive) {
        return (
            <div className="msg-voice-controls" role="group" aria-label="Speech playback controls">
                <button
                    type="button"
                    className="assistant-voice-btn active"
                    onClick={onTogglePause}
                    aria-label={isPaused ? 'Play answer audio' : 'Pause answer audio'}
                >
                    {isPaused ? (
                        <>
                            <Play size={12} aria-hidden="true" />
                            <span>Play</span>
                        </>
                    ) : (
                        <>
                            <Pause size={12} aria-hidden="true" />
                            <span>Pause</span>
                        </>
                    )}
                </button>
                <button
                    type="button"
                    className="assistant-voice-btn voice-stop-chip"
                    onClick={onStop}
                    aria-label="Stop answer audio"
                >
                    <Square size={11} aria-hidden="true" />
                    <span>Stop</span>
                </button>
            </div>
        )
    }

    return (
        <button
            type="button"
            className="assistant-voice-btn"
            onClick={onPlay}
            aria-label="Listen to answer aloud"
            title="Play grounded answer aloud"
        >
            <Volume2 size={13} aria-hidden="true" />
            <span>Listen</span>
        </button>
    )
}

