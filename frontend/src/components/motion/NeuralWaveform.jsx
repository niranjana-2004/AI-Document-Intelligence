import { motion } from 'motion/react'
import { Sparkles, Cpu } from 'lucide-react'

export default function NeuralWaveform({
    isGenerating = false,
    statusText = '',
    compact = false,
    className = '',
}) {
    const bars = [0.4, 0.8, 1, 0.7, 0.5, 0.9, 0.6]

    if (compact) {
        return (
            <div className={`neural-waveform-compact ${className}`}>
                <div className="compact-bars">
                    {bars.map((baseHeight, idx) => (
                        <motion.span
                            key={idx}
                            className="compact-waveform-bar"
                            animate={{
                                height: isGenerating
                                    ? [baseHeight * 8, baseHeight * 22, baseHeight * 12, baseHeight * 26, baseHeight * 8]
                                    : [baseHeight * 8, baseHeight * 12, baseHeight * 8],
                            }}
                            transition={{
                                duration: isGenerating ? 0.75 : 1.8,
                                repeat: Infinity,
                                ease: 'easeInOut',
                                delay: idx * 0.08,
                            }}
                        />
                    ))}
                </div>
                {statusText && <span className="compact-status-label">{statusText}</span>}
            </div>
        )
    }

    return (
        <div className={`neural-waveform-hero ${className}`}>
            <div className="waveform-orb-wrap">
                {/* Outer pulsing energy halo */}
                <motion.div
                    className="waveform-energy-halo"
                    animate={{
                        scale: isGenerating ? [1, 1.25, 1] : [1, 1.08, 1],
                        opacity: isGenerating ? [0.6, 0.95, 0.6] : [0.35, 0.55, 0.35],
                    }}
                    transition={{
                        duration: isGenerating ? 1.4 : 3,
                        repeat: Infinity,
                        ease: 'easeInOut',
                    }}
                />

                {/* Core Icon Sphere */}
                <motion.div
                    className="waveform-core-sphere"
                    animate={{
                        boxShadow: isGenerating
                            ? [
                                  '0 0 25px rgba(139, 92, 246, 0.6)',
                                  '0 0 50px rgba(56, 189, 248, 0.8)',
                                  '0 0 25px rgba(139, 92, 246, 0.6)',
                              ]
                            : '0 0 20px rgba(139, 92, 246, 0.4)',
                    }}
                    transition={{ duration: 1.8, repeat: Infinity }}
                >
                    {isGenerating ? (
                        <Sparkles size={22} className="waveform-active-icon spin-slow" />
                    ) : (
                        <Cpu size={22} className="waveform-idle-icon" />
                    )}
                </motion.div>
            </div>

            {/* Dynamic Waveform Audio/Neural Frequency Bars */}
            <div className="waveform-bars-cluster">
                {bars.map((scale, i) => (
                    <motion.div
                        key={i}
                        className="waveform-bar"
                        animate={{
                            height: isGenerating
                                ? [scale * 12, scale * 38, scale * 18, scale * 44, scale * 12]
                                : [scale * 10, scale * 18, scale * 10],
                        }}
                        transition={{
                            duration: isGenerating ? 0.8 : 2.2,
                            repeat: Infinity,
                            ease: 'easeInOut',
                            delay: i * 0.1,
                        }}
                    />
                ))}
            </div>

            {statusText && (
                <motion.div
                    className="waveform-status-banner"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    key={statusText}
                >
                    <span className="live-status-dot" />
                    <span>{statusText}</span>
                </motion.div>
            )}
        </div>
    )
}

