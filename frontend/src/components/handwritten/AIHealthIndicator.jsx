import React, { useState, useEffect, useRef } from 'react'
import {
    CheckCircle2,
    AlertTriangle,
    XCircle,
    RefreshCw,
    Cpu,
    Copy,
    Check,
    ChevronDown,
    Server,
    Layers
} from 'lucide-react'
import { apiRequest } from '../../services/api'

export default function AIHealthIndicator({ className = '', onStatusChange = null }) {
    const [health, setHealth] = useState({
        status: 'connecting', // 'connected' | 'model_missing' | 'unavailable' | 'connecting'
        message: 'Checking local AI service...',
        base_url: 'http://127.0.0.1:11434',
        required_model: 'llama3.2',
        available_models: [],
        response_time_ms: null,
        cached: false
    })
    const [loading, setLoading] = useState(false)
    const [isOpen, setIsOpen] = useState(false)
    const [copiedCmd, setCopiedCmd] = useState(false)
    const popoverRef = useRef(null)

    const fetchHealth = async (forceRefresh = false) => {
        try {
            setLoading(true)
            const endpoint = `/handwritten/ai/health${forceRefresh ? '?force_refresh=true' : ''}`
            const data = await apiRequest(endpoint)
            if (data && data.status) {
                setHealth(data)
                if (onStatusChange) onStatusChange(data.status, data)
            }
        } catch (err) {
            const fallback = {
                status: 'unavailable',
                message: err.message || 'Cannot reach local Ollama AI service.',
                base_url: health.base_url || 'http://127.0.0.1:11434',
                required_model: health.required_model || 'llama3.2',
                available_models: [],
                response_time_ms: null,
                cached: false
            }
            setHealth(fallback)
            if (onStatusChange) onStatusChange('unavailable', fallback)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchHealth(false)

        // Periodic light polling every 45 seconds
        const timer = setInterval(() => {
            fetchHealth(false)
        }, 45000)

        return () => clearInterval(timer)
    }, [])

    // Close popover when clicking outside
    useEffect(() => {
        function handleClickOutside(event) {
            if (popoverRef.current && !popoverRef.current.contains(event.target)) {
                setIsOpen(false)
            }
        }
        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    const handleCopyCommand = (cmd) => {
        navigator.clipboard.writeText(cmd)
        setCopiedCmd(true)
        setTimeout(() => setCopiedCmd(false), 2000)
    }

    const getStatusConfig = () => {
        switch (health.status) {
            case 'connected':
                return {
                    label: 'AI Online',
                    dotClass: 'status-dot-connected',
                    badgeClass: 'ai-badge-connected',
                    icon: <CheckCircle2 size={13} className="ai-status-icon connected" />
                }
            case 'model_missing':
                return {
                    label: 'Model Missing',
                    dotClass: 'status-dot-warning',
                    badgeClass: 'ai-badge-warning',
                    icon: <AlertTriangle size={13} className="ai-status-icon warning" />
                }
            case 'unavailable':
                return {
                    label: 'AI Offline',
                    dotClass: 'status-dot-offline',
                    badgeClass: 'ai-badge-offline',
                    icon: <XCircle size={13} className="ai-status-icon offline" />
                }
            case 'connecting':
            default:
                return {
                    label: 'AI Connecting...',
                    dotClass: 'status-dot-connecting',
                    badgeClass: 'ai-badge-connecting',
                    icon: <RefreshCw size={12} className="ai-status-icon spin-icon" />
                }
        }
    }

    const cfg = getStatusConfig()

    return (
        <div className={`ai-health-indicator-wrap ${className}`} ref={popoverRef}>
            {/* Pill trigger */}
            <button
                type="button"
                className={`ai-health-pill ${cfg.badgeClass} ${isOpen ? 'active' : ''}`}
                onClick={() => setIsOpen(!isOpen)}
                title="Cognidocs AI Service Health status (Click to view details)"
                aria-expanded={isOpen}
            >
                <span className={`ai-status-dot ${cfg.dotClass}`} />
                <span className="ai-pill-label">{cfg.label}</span>
                {health.status === 'connected' && (
                    <span className="ai-pill-sub">{health.required_model}</span>
                )}
                <ChevronDown size={12} className={`ai-pill-chevron ${isOpen ? 'rotated' : ''}`} />
            </button>

            {/* Dropdown Popover */}
            {isOpen && (
                <div className="ai-health-popover">
                    <div className="ai-popover-header">
                        <div className="ai-popover-title-row">
                            <div className="ai-popover-title">
                                <Cpu size={15} style={{ color: 'var(--accent-violet, #a855f7)' }} />
                                <strong>Local AI Intelligence</strong>
                            </div>
                            <span className={`ai-mini-tag ${health.status}`}>
                                {health.status === 'connected' ? 'Connected' : (health.status === 'model_missing' ? 'Model Missing' : 'Unreachable')}
                            </span>
                        </div>
                        {health.response_time_ms !== null && (
                            <span className="ai-latency-tag">
                                Ping: {health.response_time_ms} ms
                            </span>
                        )}
                    </div>

                    <div className="ai-popover-body">
                        {/* Status Message */}
                        <p className="ai-popover-message">
                            {health.message}
                        </p>

                        {/* Connection Details */}
                        <div className="ai-details-grid">
                            <div className="ai-detail-row">
                                <span className="ai-detail-key">Endpoint:</span>
                                <code className="ai-detail-val">{health.base_url}</code>
                            </div>
                            <div className="ai-detail-row">
                                <span className="ai-detail-key">Target Model:</span>
                                <code className="ai-detail-val">{health.required_model}</code>
                            </div>
                        </div>

                        {/* Actionable Solution if not connected */}
                        {health.status === 'model_missing' && (
                            <div className="ai-action-card warning">
                                <span className="ai-action-title">Run this command in terminal to download:</span>
                                <div className="ai-code-copy-row">
                                    <code>ollama pull {health.required_model}</code>
                                    <button
                                        type="button"
                                        className="btn-ai-copy"
                                        onClick={() => handleCopyCommand(`ollama pull ${health.required_model}`)}
                                        title="Copy command"
                                    >
                                        {copiedCmd ? <Check size={13} style={{ color: '#34d399' }} /> : <Copy size={13} />}
                                    </button>
                                </div>
                            </div>
                        )}

                        {health.status === 'unavailable' && (
                            <div className="ai-action-card danger">
                                <span className="ai-action-title">To start local Ollama server, run:</span>
                                <div className="ai-code-copy-row">
                                    <code>ollama serve</code>
                                    <button
                                        type="button"
                                        className="btn-ai-copy"
                                        onClick={() => handleCopyCommand('ollama serve')}
                                        title="Copy command"
                                    >
                                        {copiedCmd ? <Check size={13} style={{ color: '#34d399' }} /> : <Copy size={13} />}
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Installed models list */}
                        {health.available_models && health.available_models.length > 0 && (
                            <div className="ai-installed-models-section">
                                <span className="ai-section-label">
                                    <Layers size={11} style={{ marginRight: '4px' }} />
                                    Installed Models ({health.available_models.length}):
                                </span>
                                <div className="ai-models-tags">
                                    {health.available_models.map((m, idx) => (
                                        <span
                                            key={idx}
                                            className={`ai-model-pill ${m.includes(health.required_model) ? 'active' : ''}`}
                                        >
                                            {m}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Popover Footer */}
                    <div className="ai-popover-footer">
                        <span className="ai-cache-indicator">
                            {health.cached ? 'Status: Cached (20s TTL)' : 'Status: Fresh ping'}
                        </span>
                        <button
                            type="button"
                            className="btn-ai-refresh"
                            onClick={() => fetchHealth(true)}
                            disabled={loading}
                        >
                            <RefreshCw size={12} className={loading ? 'spin-icon' : ''} />
                            <span>{loading ? 'Checking...' : 'Check Connection'}</span>
                        </button>
                    </div>
                </div>
            )}
        </div>
    )
}
