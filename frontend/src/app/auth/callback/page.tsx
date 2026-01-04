'use client'

import { useEffect, useState } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { Loader2, CheckCircle, XCircle } from 'lucide-react'

export default function AuthCallback() {
    const searchParams = useSearchParams()
    const router = useRouter()
    const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const token = searchParams.get('token')

        if (token) {
            // Store token in localStorage
            localStorage.setItem('sheetflow_token', token)
            setStatus('success')

            // Redirect to dashboard list after short delay
            setTimeout(() => {
                router.push('/dashboards')
            }, 1500)
        } else {
            setStatus('error')
            setError('No authentication token received')
        }
    }, [searchParams, router])

    return (
        <div className="min-h-screen flex items-center justify-center">
            <div className="glass-card p-12 text-center max-w-md">
                {status === 'loading' && (
                    <>
                        <Loader2 className="w-16 h-16 text-primary-400 animate-spin mx-auto mb-6" />
                        <h1 className="text-2xl font-bold text-white mb-2">
                            Authenticating...
                        </h1>
                        <p className="text-dark-300">
                            Please wait while we complete your login.
                        </p>
                    </>
                )}

                {status === 'success' && (
                    <>
                        <CheckCircle className="w-16 h-16 text-green-400 mx-auto mb-6" />
                        <h1 className="text-2xl font-bold text-white mb-2">
                            Welcome!
                        </h1>
                        <p className="text-dark-300">
                            Redirecting to your dashboards...
                        </p>
                    </>
                )}

                {status === 'error' && (
                    <>
                        <XCircle className="w-16 h-16 text-red-400 mx-auto mb-6" />
                        <h1 className="text-2xl font-bold text-white mb-2">
                            Authentication Failed
                        </h1>
                        <p className="text-dark-300 mb-6">
                            {error || 'Something went wrong. Please try again.'}
                        </p>
                        <button
                            onClick={() => router.push('/')}
                            className="btn-primary"
                        >
                            Return Home
                        </button>
                    </>
                )}
            </div>
        </div>
    )
}
