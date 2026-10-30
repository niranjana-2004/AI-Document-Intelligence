import { motion, useReducedMotion } from 'motion/react'

export default function PageTransition({ children, className = '' }) {
    const shouldReduceMotion = useReducedMotion()

    if (shouldReduceMotion) {
        return <div className={className}>{children}</div>
    }

    return (
        <motion.div
            className={className}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{
                duration: 0.35,
                ease: [0.16, 1, 0.3, 1],
            }}
        >
            {children}
        </motion.div>
    )
}

