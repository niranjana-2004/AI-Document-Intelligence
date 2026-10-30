import { useState, useRef } from 'react'
import { motion, useSpring, useMotionValue } from 'motion/react'
import {
    Sparkles,
    Cpu,
    CheckCircle2,
    Database,
    Zap,
    Search,
} from 'lucide-react'

export default function WorkflowIllustration() {
    const containerRef = useRef(null)
    const [isHovered, setIsHovered] = useState(false)

    // Mouse tilt tracking with smooth spring physics
    const mouseX = useMotionValue(0)
    const mouseY = useMotionValue(0)
    const rotateX = useSpring(mouseY, { stiffness: 120, damping: 18 })
    const rotateY = useSpring(mouseX, { stiffness: 120, damping: 18 })

    const handleMouseMove = (e) => {
        if (!containerRef.current) return
        const rect = containerRef.current.getBoundingClientRect()
        const x = e.clientX - rect.left - rect.width / 2
        const y = e.clientY - rect.top - rect.height / 2
        mouseX.set((x / (rect.width / 2)) * 8)
        mouseY.set(-(y / (rect.height / 2)) * 8)
    }

    const handleMouseLeave = () => {
        mouseX.set(0)
        mouseY.set(0)
        setIsHovered(false)
    }

    return (
        <div
            ref={containerRef}
            className="workflow-stage-container"
            onMouseMove={handleMouseMove}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={handleMouseLeave}
            style={{ perspective: 1200 }}
        >
            <motion.div
                className="workflow-stage-content"
                style={{
                    rotateX,
                    rotateY,
                    transformStyle: 'preserve-3d',
                }}
            >
                {/* Background ambient glow behind core */}
                <div className="stage-ambient-glow" aria-hidden="true" />

                {/* Animated connecting SVG energy lines */}
                <svg
                    className="workflow-svg-connections"
                    viewBox="0 0 680 440"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                    aria-hidden="true"
                >
                    <defs>
                        <linearGradient id="beamGradientLeft" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="#38BDF8" stopOpacity="0.8" />
                            <stop offset="100%" stopColor="#8B5CF6" stopOpacity="1" />
                        </linearGradient>
                        <linearGradient id="beamGradientRight" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" stopColor="#8B5CF6" stopOpacity="1" />
                            <stop offset="100%" stopColor="#38BDF8" stopOpacity="0.8" />
                        </linearGradient>
                        <filter id="glowEffect" x="-20%" y="-20%" width="140%" height="140%">
                            <feGaussianBlur stdDeviation="3" result="blur" />
                            <feComposite in="SourceGraphic" in2="blur" operator="over" />
                        </filter>
                    </defs>

                    {/* Left Stream: Document to Central Engine */}
                    <path
                        d="M 180 160 C 250 160, 260 220, 340 220"
                        stroke="rgba(139, 92, 246, 0.25)"
                        strokeWidth="2"
                    />
                    <path
                        d="M 180 160 C 250 160, 260 220, 340 220"
                        stroke="url(#beamGradientLeft)"
                        strokeWidth="2.5"
                        strokeDasharray="8 12"
                        className="animated-flow-line"
                        filter="url(#glowEffect)"
                    />

                    {/* Bottom-Left Stream: Vector Chunks to Central Engine */}
                    <path
                        d="M 190 320 C 250 320, 270 240, 340 220"
                        stroke="rgba(56, 189, 248, 0.2)"
                        strokeWidth="2"
                    />
                    <path
                        d="M 190 320 C 250 320, 270 240, 340 220"
                        stroke="url(#beamGradientLeft)"
                        strokeWidth="2"
                        strokeDasharray="6 10"
                        className="animated-flow-line-reverse"
                    />

                    {/* Right Stream: Central Engine to Grounded Answer */}
                    <path
                        d="M 340 220 C 420 220, 440 170, 500 170"
                        stroke="rgba(139, 92, 246, 0.25)"
                        strokeWidth="2"
                    />
                    <path
                        d="M 340 220 C 420 220, 440 170, 500 170"
                        stroke="url(#beamGradientRight)"
                        strokeWidth="2.5"
                        strokeDasharray="8 12"
                        className="animated-flow-line"
                        filter="url(#glowEffect)"
                    />

                    {/* Bottom-Right Stream: Engine to Semantic Verification */}
                    <path
                        d="M 340 220 C 420 220, 440 310, 510 310"
                        stroke="rgba(56, 189, 248, 0.2)"
                        strokeWidth="2"
                    />
                    <path
                        d="M 340 220 C 420 220, 440 310, 510 310"
                        stroke="url(#beamGradientRight)"
                        strokeWidth="2"
                        strokeDasharray="6 10"
                        className="animated-flow-line"
                    />
                </svg>

                {/* 1. LEFT CARD: Ingested Document Card */}
                <motion.div
                    className="workflow-card left-card"
                    animate={{
                        y: [-6, 6, -6],
                        rotate: [-0.8, 0.8, -0.8],
                    }}
                    transition={{
                        duration: 5,
                        repeat: Infinity,
                        ease: 'easeInOut',
                    }}
                    style={{ transformStyle: 'preserve-3d', translateZ: 30 }}
                >
                    <div className="card-top-chip">
                        <span className="file-badge-pdf">PDF</span>
                        <span className="card-filename">Q3_System_Architecture.pdf</span>
                    </div>

                    <div className="card-body-preview">
                        <div className="preview-line long" />
                        <div className="preview-line medium" />
                        <div className="preview-line short" />
                    </div>

                    <div className="card-footer-metrics">
                        <span className="status-dot-pulse" />
                        <span>32 Chunks Extracted</span>
                        <span className="badge-dim">1536-dim</span>
                    </div>
                </motion.div>

                {/* 2. LOWER-LEFT CHIP: Dense Vector Embeddings */}
                <motion.div
                    className="floating-chip lower-left"
                    animate={{
                        y: [5, -5, 5],
                    }}
                    transition={{
                        duration: 4.2,
                        repeat: Infinity,
                        ease: 'easeInOut',
                    }}
                    style={{ transformStyle: 'preserve-3d', translateZ: 45 }}
                >
                    <Database size={13} className="text-cyan" />
                    <span>Sentence-Transformers Embeddings</span>
                </motion.div>

                {/* 3. CENTER: Glowing Intelligence Core & Pulsing Rings */}
                <div className="workflow-core-center" style={{ transformStyle: 'preserve-3d', translateZ: 50 }}>
                    {/* Concentric rotating SVG energy rings */}
                    <div className="core-ring-spin-cw" aria-hidden="true">
                        <svg viewBox="0 0 160 160" width="160" height="160">
                            <circle
                                cx="80"
                                cy="80"
                                r="72"
                                fill="none"
                                stroke="rgba(139, 92, 246, 0.4)"
                                strokeWidth="1.5"
                                strokeDasharray="14 10"
                            />
                        </svg>
                    </div>

                    <div className="core-ring-spin-ccw" aria-hidden="true">
                        <svg viewBox="0 0 130 130" width="130" height="130">
                            <circle
                                cx="65"
                                cy="65"
                                r="58"
                                fill="none"
                                stroke="rgba(56, 189, 248, 0.5)"
                                strokeWidth="1.5"
                                strokeDasharray="8 8"
                            />
                        </svg>
                    </div>

                    {/* Central Glowing Orb with Icon */}
                    <motion.div
                        className="core-intelligence-orb"
                        animate={{
                            scale: isHovered ? [1.06, 1.14, 1.06] : [1, 1.06, 1],
                            boxShadow: [
                                '0 0 35px rgba(139, 92, 246, 0.5), inset 0 0 20px rgba(56, 189, 248, 0.4)',
                                '0 0 55px rgba(139, 92, 246, 0.8), inset 0 0 30px rgba(56, 189, 248, 0.6)',
                                '0 0 35px rgba(139, 92, 246, 0.5), inset 0 0 20px rgba(56, 189, 248, 0.4)',
                            ],
                        }}
                        transition={{
                            duration: 3,
                            repeat: Infinity,
                            ease: 'easeInOut',
                        }}
                    >
                        <Cpu size={26} className="core-icon" />
                        <span className="core-label">CogniCore</span>
                    </motion.div>
                </div>

                {/* 4. UPPER-CENTER CHIP: Cosine Metric Badge */}
                <motion.div
                    className="floating-chip upper-center"
                    animate={{
                        y: [-4, 4, -4],
                    }}
                    transition={{
                        duration: 3.8,
                        repeat: Infinity,
                        ease: 'easeInOut',
                    }}
                    style={{ transformStyle: 'preserve-3d', translateZ: 60 }}
                >
                    <Search size={12} className="text-violet" />
                    <span>Cosine Similarity <strong>0.942</strong></span>
                </motion.div>

                {/* 5. RIGHT CARD: Grounded Synthesized Answer */}
                <motion.div
                    className="workflow-card right-card"
                    animate={{
                        y: [6, -6, 6],
                        rotate: [0.8, -0.8, 0.8],
                    }}
                    transition={{
                        duration: 5.6,
                        repeat: Infinity,
                        ease: 'easeInOut',
                    }}
                    style={{ transformStyle: 'preserve-3d', translateZ: 35 }}
                >
                    <div className="card-top-chip">
                        <Sparkles size={14} className="text-violet" />
                        <span className="card-filename text-accent">Grounded Intelligence</span>
                        <span className="card-badge-verified">
                            <CheckCircle2 size={11} />
                            <span>Verified</span>
                        </span>
                    </div>

                    <div className="card-quote-box">
                        <p>
                            &ldquo;Latency is reduced by <strong>4.2x</strong> through chunk caching and
                            vector similarity ranking.&rdquo;
                        </p>
                    </div>

                    <div className="card-citations-strip">
                        <span className="citation-tag">[1] Architecture §3.2</span>
                        <span className="citation-tag">[2] Benchmarks §5</span>
                    </div>
                </motion.div>

                {/* 6. LOWER-RIGHT CHIP: Local Llama 3.2 Badge */}
                <motion.div
                    className="floating-chip lower-right"
                    animate={{
                        y: [-5, 5, -5],
                    }}
                    transition={{
                        duration: 4.8,
                        repeat: Infinity,
                        ease: 'easeInOut',
                    }}
                    style={{ transformStyle: 'preserve-3d', translateZ: 50 }}
                >
                    <Zap size={12} className="text-cyan" />
                    <span>Llama 3.2 Engine</span>
                    <span className="status-live-indicator" />
                </motion.div>
            </motion.div>
        </div>
    )
}
