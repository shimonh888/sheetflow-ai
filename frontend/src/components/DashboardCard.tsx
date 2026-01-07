'use client'

import Link from 'next/link'
import { FileSpreadsheet, Clock, BarChart2, Trash2, Files } from 'lucide-react'
import clsx from 'clsx'

interface FileSource {
    id: string
    file_name: string
    file_context: string | null
}

interface Dashboard {
    id: string
    file_name: string
    title?: string | null
    sheet_names?: string[]
    last_synced?: string
    last_sync_status?: string
    file_sources?: FileSource[]
}

interface DashboardCardProps {
    dashboard: Dashboard
    onDelete?: (id: string, title: string) => void
}

export default function DashboardCard({ dashboard, onDelete }: DashboardCardProps) {
    const formatDate = (date: string | undefined) => {
        if (!date) return 'Never'
        return new Date(date).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        })
    }

    const statusColors = {
        success: 'text-primary-400',
        error: 'text-red-400',
        schema_drift: 'text-yellow-400',
    }

    const handleDelete = (e: React.MouseEvent) => {
        e.preventDefault()
        e.stopPropagation()
        if (onDelete) {
            onDelete(dashboard.id, dashboard.title || dashboard.file_name)
        }
    }

    const fileCount = dashboard.file_sources?.length || 1

    return (
        <Link href={`/dashboard/${dashboard.id}`}>
            <div className="glass-card p-6 group cursor-pointer hover:border-primary-400/30 transition-all duration-300 hover:shadow-lg hover:shadow-primary-400/10 relative">
                {/* Delete button - Neon Green theme */}
                {onDelete && (
                    <button
                        onClick={handleDelete}
                        className="absolute top-4 right-4 p-2 rounded-lg bg-primary-400/10 text-primary-400 opacity-0 group-hover:opacity-100 hover:bg-primary-400/20 transition-all duration-200 z-10"
                        title="Delete dashboard"
                    >
                        <Trash2 className="w-4 h-4" />
                    </button>
                )}

                <div className="flex items-start justify-between mb-4">
                    <div className="w-12 h-12 rounded-xl bg-primary-400/10 flex items-center justify-center group-hover:bg-primary-400/20 transition-colors">
                        {fileCount > 1 ? (
                            <Files className="w-6 h-6 text-primary-400" />
                        ) : (
                            <FileSpreadsheet className="w-6 h-6 text-primary-400" />
                        )}
                    </div>

                    {dashboard.last_sync_status && (
                        <span className={clsx(
                            'text-xs px-2 py-1 rounded-full bg-white/5',
                            statusColors[dashboard.last_sync_status as keyof typeof statusColors] || 'text-dark-400'
                        )}>
                            {dashboard.last_sync_status === 'schema_drift' ? 'Schema Changed' :
                                dashboard.last_sync_status.charAt(0).toUpperCase() + dashboard.last_sync_status.slice(1)}
                        </span>
                    )}
                </div>

                <h3 className="text-lg font-semibold text-white mb-1 group-hover:text-primary-400 transition-colors">
                    {dashboard.title || dashboard.file_name}
                </h3>

                <p className="text-sm text-dark-400 mb-4 truncate">
                    {fileCount > 1 ? `${fileCount} files` : dashboard.file_name}
                </p>

                <div className="flex items-center justify-between text-xs text-dark-400">
                    <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        <span>{formatDate(dashboard.last_synced)}</span>
                    </div>

                    {dashboard.sheet_names && dashboard.sheet_names.length > 0 && (
                        <div className="flex items-center gap-1">
                            <BarChart2 className="w-3 h-3" />
                            <span>{dashboard.sheet_names.length} sheets</span>
                        </div>
                    )}
                </div>
            </div>
        </Link>
    )
}
