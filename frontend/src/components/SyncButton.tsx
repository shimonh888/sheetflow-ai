'use client'

import { useState } from 'react'
import { RefreshCw, Check, AlertTriangle } from 'lucide-react'
import clsx from 'clsx'

interface SyncButtonProps {
    dashboardId: string
    onSyncComplete?: (data: any) => void
    lastSynced?: string | null
}

export default function SyncButton({ dashboardId, onSyncComplete, lastSynced }: SyncButtonProps) {
    const [isSyncing, setIsSyncing] = useState(false)
    const [syncStatus, setSyncStatus] = useState<'idle' | 'success' | 'error' | 'drift'>('idle')
    const [message, setMessage] = useState<string | null>(null)

    const handleSync = async () => {
        setIsSyncing(true)
        setSyncStatus('idle')
        setMessage(null)

        try {
            const token = localStorage.getItem('sheetflow_token')
            if (!token) {
                throw new Error('Not authenticated')
            }

            const response = await fetch(`/api/dashboards/${dashboardId}/refresh?token=${token}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    force_reprocess: false,
                    accept_schema_drift: true,
                }),
            })

            if (!response.ok) {
                throw new Error('Sync failed')
            }

            const data = await response.json()

            if (data.schema_drift_detected) {
                setSyncStatus('drift')
                setMessage('Schema changes detected and auto-mapped')
            } else {
                setSyncStatus('success')
                setMessage('Dashboard synced successfully')
            }

            // Call callback with updated data
            if (onSyncComplete && data.chart_data) {
                onSyncComplete(data)
            }

            // Reset status after delay
            setTimeout(() => {
                setSyncStatus('idle')
                setMessage(null)
            }, 3000)

        } catch (error) {
            console.error('Sync error:', error)
            setSyncStatus('error')
            setMessage('Sync failed. Please try again.')
        } finally {
            setIsSyncing(false)
        }
    }

    const formatLastSynced = (date: string | null | undefined) => {
        if (!date) return 'Never synced'
        const d = new Date(date)
        return d.toLocaleString()
    }

    return (
        <div className="flex items-center gap-4">
            <button
                onClick={handleSync}
                disabled={isSyncing}
                className={clsx(
                    'inline-flex items-center gap-2 px-5 py-2.5 rounded-xl font-medium',
                    'transition-all duration-200 transform',
                    {
                        'bg-gradient-to-r from-primary-500 to-primary-600 text-white hover:scale-105 active:scale-95':
                            syncStatus === 'idle' && !isSyncing,
                        'bg-primary-600/50 text-white cursor-wait': isSyncing,
                        'bg-green-500/20 text-green-400 border border-green-500/30': syncStatus === 'success',
                        'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30': syncStatus === 'drift',
                        'bg-red-500/20 text-red-400 border border-red-500/30': syncStatus === 'error',
                    }
                )}
            >
                {isSyncing ? (
                    <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        Syncing...
                    </>
                ) : syncStatus === 'success' ? (
                    <>
                        <Check className="w-4 h-4" />
                        Synced!
                    </>
                ) : syncStatus === 'drift' ? (
                    <>
                        <AlertTriangle className="w-4 h-4" />
                        Schema Updated
                    </>
                ) : syncStatus === 'error' ? (
                    <>
                        <AlertTriangle className="w-4 h-4" />
                        Failed
                    </>
                ) : (
                    <>
                        <RefreshCw className="w-4 h-4" />
                        Sync Now
                    </>
                )}
            </button>

            <div className="text-sm text-dark-400">
                {message || `Last synced: ${formatLastSynced(lastSynced)}`}
            </div>
        </div>
    )
}
