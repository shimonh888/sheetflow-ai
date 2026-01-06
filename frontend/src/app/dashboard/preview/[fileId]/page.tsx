'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import {
    BarChart3,
    ArrowLeft,
    Sparkles,
    BarChart2,
    LineChart,
    PieChart,
    Activity,
    ChevronDown,
    ChevronUp,
    Check,
    Loader2
} from 'lucide-react'
import LoadingSpinner from '@/components/LoadingSpinner'
import {
    previewDashboard,
    createDashboard,
    ChartProposal,
    PreviewResponse
} from '@/lib/api'

// Chart type options
const CHART_TYPES = [
    { value: 'bar', label: 'Bar Chart', icon: BarChart2 },
    { value: 'line', label: 'Line Chart', icon: LineChart },
    { value: 'pie', label: 'Pie Chart', icon: PieChart },
    { value: 'area', label: 'Area Chart', icon: Activity },
    { value: 'scatter', label: 'Scatter Plot', icon: Sparkles },
] as const

type ChartType = typeof CHART_TYPES[number]['value']

interface EditableProposal extends ChartProposal {
    isExpanded: boolean
}

export default function PreviewPage({ params }: { params: { fileId: string } }) {
    const router = useRouter()
    const searchParams = useSearchParams()
    const fileName = searchParams.get('name') || 'Excel File'
    const fileId = params.fileId

    const [isLoading, setIsLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [previewData, setPreviewData] = useState<PreviewResponse | null>(null)
    const [proposals, setProposals] = useState<EditableProposal[]>([])
    const [isCreating, setIsCreating] = useState(false)

    useEffect(() => {
        const token = localStorage.getItem('sheetflow_token')
        if (!token) {
            router.push('/')
            return
        }

        loadPreview()
    }, [fileId, fileName])

    const loadPreview = async () => {
        setIsLoading(true)
        setError(null)

        try {
            const data = await previewDashboard(fileId, fileName)
            setPreviewData(data)
            // Convert proposals to editable format
            setProposals(data.proposals.map(p => ({
                ...p,
                isExpanded: false
            })))
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to analyze file')
        } finally {
            setIsLoading(false)
        }
    }

    const updateProposal = (index: number, updates: Partial<EditableProposal>) => {
        setProposals(prev => prev.map((p, i) =>
            i === index ? { ...p, ...updates } : p
        ))
    }

    const toggleExpanded = (index: number) => {
        setProposals(prev => prev.map((p, i) =>
            i === index ? { ...p, isExpanded: !p.isExpanded } : p
        ))
    }

    const handleCreateDashboard = async () => {
        if (!previewData) return

        setIsCreating(true)
        try {
            // Convert editable proposals back to ChartProposal format
            const charts: ChartProposal[] = proposals.map(({ isExpanded, ...rest }) => rest)

            const dashboard = await createDashboard({
                file_id: fileId,
                file_name: fileName,
                charts
            })

            router.push(`/dashboard/${dashboard.id}`)
        } catch (err) {
            console.error('Failed to create dashboard:', err)
            setError(err instanceof Error ? err.message : 'Failed to create dashboard')
            setIsCreating(false)
        }
    }

    const getChartIcon = (type: string) => {
        const chartType = CHART_TYPES.find(t => t.value === type)
        return chartType ? chartType.icon : BarChart2
    }

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-[#1a1a1a]">
                <div className="text-center">
                    <LoadingSpinner size="lg" message="Analyzing your data..." />
                    <p className="text-gray-400 mt-4 text-sm">
                        The AI is reviewing your Excel file to suggest the best visualizations
                    </p>
                </div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-[#1a1a1a]">
                <div className="text-center max-w-md">
                    <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mx-auto mb-4">
                        <span className="text-3xl">⚠️</span>
                    </div>
                    <h2 className="text-xl font-semibold text-white mb-2">Analysis Failed</h2>
                    <p className="text-gray-400 mb-6">{error}</p>
                    <div className="flex gap-3 justify-center">
                        <button
                            onClick={() => router.push('/dashboards')}
                            className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-white transition-colors"
                        >
                            Go Back
                        </button>
                        <button
                            onClick={loadPreview}
                            className="px-4 py-2 rounded-lg bg-[#14FF6E] hover:bg-[#10cc58] text-black font-medium transition-colors"
                        >
                            Try Again
                        </button>
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-[#1a1a1a]">
            {/* Header */}
            <header className="border-b border-white/10 bg-[#1a1a1a]/80 backdrop-blur-sm sticky top-0 z-10">
                <div className="max-w-6xl mx-auto px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <button
                                onClick={() => router.push('/dashboards')}
                                className="p-2 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors"
                            >
                                <ArrowLeft className="w-5 h-5" />
                            </button>
                            <div className="flex items-center gap-3">
                                <BarChart3 className="w-8 h-8 text-[#14FF6E]" />
                                <div>
                                    <h1 className="text-lg font-semibold text-white">Preview Your Charts</h1>
                                    <p className="text-sm text-gray-400">{fileName}</p>
                                </div>
                            </div>
                        </div>

                        <button
                            onClick={handleCreateDashboard}
                            disabled={isCreating || proposals.length === 0}
                            className="px-6 py-2.5 rounded-lg bg-[#14FF6E] hover:bg-[#10cc58] text-black font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-2"
                        >
                            {isCreating ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Creating...
                                </>
                            ) : (
                                <>
                                    <Check className="w-4 h-4" />
                                    Create My Dashboard
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="max-w-6xl mx-auto px-6 py-8">
                {/* Info Banner */}
                <div className="bg-[#14FF6E]/10 border border-[#14FF6E]/20 rounded-xl p-4 mb-8 flex items-start gap-3">
                    <Sparkles className="w-5 h-5 text-[#14FF6E] flex-shrink-0 mt-0.5" />
                    <div>
                        <p className="text-white font-medium">AI-Suggested Visualizations</p>
                        <p className="text-gray-400 text-sm mt-1">
                            Based on your data, we've suggested {proposals.length} chart{proposals.length !== 1 ? 's' : ''}.
                            Feel free to edit titles or change chart types before creating your dashboard.
                        </p>
                    </div>
                </div>

                {/* Data Summary */}
                {previewData?.data_summary && (
                    <div className="mb-8 flex gap-4 overflow-x-auto pb-2">
                        <div className="bg-[#2D332F] rounded-lg px-4 py-2 flex-shrink-0">
                            <p className="text-gray-400 text-xs">Rows</p>
                            <p className="text-white font-semibold">{previewData.data_summary.row_count}</p>
                        </div>
                        <div className="bg-[#2D332F] rounded-lg px-4 py-2 flex-shrink-0">
                            <p className="text-gray-400 text-xs">Columns</p>
                            <p className="text-white font-semibold">{previewData.data_summary.columns.length}</p>
                        </div>
                        <div className="bg-[#2D332F] rounded-lg px-4 py-2 flex-shrink-0">
                            <p className="text-gray-400 text-xs">Sheets</p>
                            <p className="text-white font-semibold">{previewData.sheet_names.length}</p>
                        </div>
                    </div>
                )}

                {/* Chart Proposals Grid */}
                {proposals.length > 0 ? (
                    <div className="grid md:grid-cols-2 gap-6">
                        {proposals.map((proposal, index) => {
                            const ChartIcon = getChartIcon(proposal.type)

                            return (
                                <div
                                    key={proposal.id}
                                    className="bg-[#2D332F] rounded-xl border border-white/5 overflow-hidden"
                                >
                                    {/* Card Header */}
                                    <div className="p-5 border-b border-white/5">
                                        <div className="flex items-start gap-4">
                                            <div className="w-12 h-12 rounded-lg bg-[#14FF6E]/10 flex items-center justify-center flex-shrink-0">
                                                <ChartIcon className="w-6 h-6 text-[#14FF6E]" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                {/* Editable Title */}
                                                <input
                                                    type="text"
                                                    value={proposal.title}
                                                    onChange={(e) => updateProposal(index, { title: e.target.value })}
                                                    className="w-full bg-transparent text-white font-semibold text-lg border-b border-transparent hover:border-white/20 focus:border-[#14FF6E] focus:outline-none transition-colors pb-1"
                                                    placeholder="Chart Title"
                                                />

                                                {/* Chart Type Dropdown */}
                                                <div className="mt-2 relative">
                                                    <select
                                                        value={proposal.type}
                                                        onChange={(e) => updateProposal(index, { type: e.target.value as ChartType })}
                                                        className="w-full appearance-none bg-white/5 text-gray-300 text-sm rounded-lg px-3 py-2 pr-8 border border-white/10 focus:border-[#14FF6E] focus:outline-none cursor-pointer"
                                                    >
                                                        {CHART_TYPES.map(type => (
                                                            <option key={type.value} value={type.value} className="bg-[#2D332F]">
                                                                {type.label}
                                                            </option>
                                                        ))}
                                                    </select>
                                                    <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Axis Info */}
                                    <div className="px-5 py-3 bg-white/[0.02] flex gap-6 text-sm">
                                        {proposal.x_axis && (
                                            <div>
                                                <span className="text-gray-500">X-Axis:</span>
                                                <span className="text-gray-300 ml-2">{proposal.x_axis}</span>
                                            </div>
                                        )}
                                        {proposal.y_axis && (
                                            <div>
                                                <span className="text-gray-500">Y-Axis:</span>
                                                <span className="text-gray-300 ml-2">{proposal.y_axis}</span>
                                            </div>
                                        )}
                                        {proposal.data_key && !proposal.y_axis && (
                                            <div>
                                                <span className="text-gray-500">Data:</span>
                                                <span className="text-gray-300 ml-2">{proposal.data_key}</span>
                                            </div>
                                        )}
                                    </div>

                                    {/* AI Reasoning (Collapsible) */}
                                    <div className="border-t border-white/5">
                                        <button
                                            onClick={() => toggleExpanded(index)}
                                            className="w-full px-5 py-3 flex items-center justify-between text-left hover:bg-white/[0.02] transition-colors"
                                        >
                                            <span className="text-sm text-gray-400 flex items-center gap-2">
                                                <Sparkles className="w-4 h-4 text-[#14FF6E]" />
                                                AI Reasoning
                                            </span>
                                            {proposal.isExpanded ? (
                                                <ChevronUp className="w-4 h-4 text-gray-400" />
                                            ) : (
                                                <ChevronDown className="w-4 h-4 text-gray-400" />
                                            )}
                                        </button>

                                        {proposal.isExpanded && (
                                            <div className="px-5 pb-4">
                                                <p className="text-sm text-gray-400 italic">
                                                    "{proposal.reasoning}"
                                                </p>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                ) : (
                    <div className="text-center py-12 bg-[#2D332F] rounded-xl">
                        <BarChart2 className="w-12 h-12 text-gray-600 mx-auto mb-4" />
                        <p className="text-gray-400">No chart suggestions available</p>
                        <p className="text-gray-500 text-sm mt-1">The AI couldn't determine suitable charts for this data</p>
                    </div>
                )}
            </main>
        </div>
    )
}
