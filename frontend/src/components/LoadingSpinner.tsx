'use client'

import { Loader2 } from 'lucide-react'
import clsx from 'clsx'

interface LoadingSpinnerProps {
    size?: 'sm' | 'md' | 'lg'
    className?: string
    message?: string
}

export default function LoadingSpinner({ size = 'md', className, message }: LoadingSpinnerProps) {
    const sizeClasses = {
        sm: 'w-4 h-4',
        md: 'w-8 h-8',
        lg: 'w-12 h-12',
    }

    return (
        <div className={clsx('flex flex-col items-center justify-center gap-3', className)}>
            <Loader2 className={clsx(sizeClasses[size], 'text-primary-400 animate-spin')} />
            {message && (
                <p className="text-dark-300 text-sm animate-pulse">{message}</p>
            )}
        </div>
    )
}
