'use client'

import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import {
    ArrowLeft,
    FileSpreadsheet,
    Layers,
    AlertTriangle,
    BarChart3
} from 'lucide-react'
import SyncButton from '@/components/SyncButton'
import ChartContainer from '@/components/ChartContainer'
import LoadingSpinner from '@/components/LoadingSpinner'
import { getDashboard, getDashboardData, Dashboard } from '@/lib/api'

interface ChartConfig {
    id: string
    type: 'bar' | 'line' | 'pie' | 'area'
    title: string
    x_axis?: string
    y_axis?: string
    data_key?: string
    color?: string
}

export default function DashboardPage() {
    const params = useParams()
    const router = useRouter()
    const dashboardId = params.id as string

    const [dashboard, setDashboard] = useState<Dashboard | null>(null)
    const [charts, setCharts] = useState<ChartConfig[]>([])
    const [chartData, setChartData] = useState<Record<string, any[]>>({})
    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    const loadDashboard = useCallback(async () => {
        try {
            const [dashboardData, dataResponse] = await Promise.all([
                getDashboard(dashboardId),
                getDashboardData(dashboardId).catch(() => null),
            ])

            setDashboard(dashboardData)

            if (dataResponse) {
                setCharts(dataResponse.charts || [])
                setChartData(dataResponse.data || {})
            } else if (dashboardData.dashboard_config?.charts) {
                setCharts(dashboardData.dashboard_config.charts)
            }
        } catch (err: any) {
            setError(err.message || 'Failed to load dashboard')
        } finally {
            setIsLoading(false)
        }
    }, [dashboardId])

    useEffect(() => {
        loadDashboard()
    }, [loadDashboard])

    const handleSyncComplete = (data: any) => {
        if (data.chart_data) {
            setChartData(data.chart_data)
        }
        // Reload dashboard to get updated config
        loadDashboard()
    }

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <LoadingSpinner size="lg" message="Loading dashboard..." />
            </div>
        )
    }

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="glass-card p-12 text-center max-w-md">
                    <AlertTriangle className="w-16 h-16 text-red-400 mx-auto mb-6" />
                    <h1 className="text-2xl font-bold text-white mb-2">Error</h1>
                    <p className="text-dark-300 mb-6">{error}</p>
                    <button
                        onClick={() => router.push('/dashboards')}
                        className="btn-primary"
                    >
                        Back to Dashboards
                    </button>
                </div>
            </div>
        )
    }

    if (!dashboard) {
        return null
    }

    return (
        <div className="min-h-screen">
            {/* Header */}
            <header className="border-b border-white/10 bg-dark-900/50 backdrop-blur-sm sticky top-0 z-10">
                <div className="max-w-7xl mx-auto px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <button
                                onClick={() => router.push('/dashboards')}
                                className="p-2 rounded-lg hover:bg-white/5 transition-colors"
                            >
                                <ArrowLeft className="w-5 h-5 text-dark-300" />
                            </button>

                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-xl bg-primary-500/10 flex items-center justify-center">
                                    <FileSpreadsheet className="w-5 h-5 text-primary-400" />
                                </div>
                                <div>
                                    <h1 className="text-xl font-semibold text-white">
                                        {dashboard.title || dashboard.file_name}
                                    </h1>
                                    <div className="flex items-center gap-3 text-sm text-dark-400">
                                        <span>{dashboard.file_name}</span>
                                        {dashboard.sheet_names && dashboard.sheet_names.length > 0 && (
                                            <span className="flex items-center gap-1">
                                                <Layers className="w-3 h-3" />
                                                {dashboard.sheet_names.length} sheets
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>
                        </div>

                        <SyncButton
                            dashboardId={dashboardId}
                            lastSynced={dashboard.last_synced}
                            onSyncComplete={handleSyncComplete}
                        />
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="max-w-7xl mx-auto px-6 py-8">
                {/* Schema Drift Warning */}
                {dashboard.last_sync_status === 'schema_drift' && (
                    <div className="glass-card p-4 mb-6 border-yellow-500/30 bg-yellow-500/5">
                        <div className="flex items-center gap-3">
                            <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0" />
                            <div>
                                <p className="text-yellow-300 font-medium">Schema Changes Detected</p>
                                <p className="text-yellow-400/70 text-sm">
                                    {dashboard.last_sync_message || 'Column names or structure changed. Charts were auto-remapped.'}
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                {/* Charts Grid */}
                {charts.length > 0 ? (
                    <div className="grid md:grid-cols-2 gap-6">
                        {charts.map((chart) => (
                            <ChartContainer
                                key={chart.id}
                                config={chart}
                                data={chartData[chart.id] || chartData.raw_data || []}
                            />
                        ))}
                    </div>
                ) : (
                    <div className="glass-card p-12 text-center">
                        <BarChart3 className="w-16 h-16 text-dark-500 mx-auto mb-4" />
                        <h2 className="text-xl font-semibold text-white mb-2">
                            No Charts Yet
                        </h2>
                        <p className="text-dark-400 mb-6">
                            Click "Sync Now" to fetch data and generate charts automatically.
                        </p>
                        <SyncButton
                            dashboardId={dashboardId}
                            lastSynced={dashboard.last_synced}
                            onSyncComplete={handleSyncComplete}
                        />
                    </div>
                )}

                {/* Raw Data Preview */}
                {chartData.raw_data && chartData.raw_data.length > 0 && (
                    <div className="mt-8">
                        <h2 className="text-lg font-semibold text-white mb-4">Data Preview</h2>
                        <div className="glass-card overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="border-b border-white/10">
                                            {Object.keys(chartData.raw_data[0]).slice(0, 8).map((key) => (
                                                <th
                                                    key={key}
                                                    className="px-4 py-3 text-left text-dark-300 font-medium"
                                                >
                                                    {key}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {chartData.raw_data.slice(0, 10).map((row, i) => (
                                            <tr
                                                key={i}
                                                className="border-b border-white/5 hover:bg-white/5"
                                            >
                                                {Object.entries(row).slice(0, 8).map(([key, value]) => (
                                                    <td key={key} className="px-4 py-3 text-dark-200">
                                                        {String(value)}
                                                    </td>
                                                ))}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                            {chartData.raw_data.length > 10 && (
                                <div className="px-4 py-3 text-center text-dark-400 text-sm border-t border-white/10">
                                    Showing 10 of {chartData.raw_data.length} rows
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </main>
        </div>
    )
}
