import { useEffect, useState, useRef } from 'react'
import { useInView } from 'motion/react'

export default function AnimatedCounter({
    value = 0,
    duration = 1.2,
    prefix = '',
    suffix = '',
    className = '',
}) {
    const ref = useRef(null)
    const isInView = useInView(ref, { once: true, margin: '-20px' })
    const [displayValue, setDisplayValue] = useState(0)

    useEffect(() => {
        if (!isInView) return

        const target = typeof value === 'number' ? value : parseInt(value, 10) || 0
        if (target === 0) {
            return
        }

        let startTime = null
        let animationFrame = null

        const easeOutExpo = (t) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t))

        const step = (timestamp) => {
            if (!startTime) startTime = timestamp
            const elapsed = (timestamp - startTime) / 1000
            const progress = Math.min(elapsed / duration, 1)
            const easedProgress = easeOutExpo(progress)
            const current = Math.round(easedProgress * target)

            setDisplayValue(current)

            if (progress < 1) {
                animationFrame = requestAnimationFrame(step)
            } else {
                setDisplayValue(target)
            }
        }

        animationFrame = requestAnimationFrame(step)

        return () => {
            if (animationFrame) cancelAnimationFrame(animationFrame)
        }
    }, [value, duration, isInView])

    return (
        <span ref={ref} className={className}>
            {prefix}
            {displayValue.toLocaleString()}
            {suffix}
        </span>
    )
}
