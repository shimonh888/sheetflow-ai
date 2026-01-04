'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
    Plus,
    BarChart3,
    LogOut,
    User,
    FileSpreadsheet,
    X
} from 'lucide-react'
import DashboardCard from '@/components/DashboardCard'
import LoadingSpinner from '@/components/LoadingSpinner'
import {
    listDashboards,
    listDriveFiles,
    createDashboard,
    getCurrentUser,
    Dashboard,
    DriveFile
} from '@/lib/api'

export default function DashboardsPage() {
    const router = useRouter()
    const [dashboards, setDashboards] = useState<Dashboard[]>([])
    const [isLoading, setIsLoading] = useState(true)
    const [user, setUser] = useState<any>(null)

    // File picker state
    const [showFilePicker, setShowFilePicker] = useState(false)
    const [driveFiles, setDriveFiles] = useState<DriveFile[]>([])
    const [isLoadingFiles, setIsLoadingFiles] = useState(false)
    const [isCreating, setIsCreating] = useState(false)

    useEffect(() => {
        const token = localStorage.getItem('sheetflow_token')
        if (!token) {
            router.push('/')
            return
        }

        loadData()
    }, [router])

    const loadData = async () => {
        try {
            const [dashboardsData, userData] = await Promise.all([
                listDashboards(),
                getCurrentUser(),
            ])
            setDashboards(dashboardsData.items)
            setUser(userData)
        } catch (error) {
            console.error('Failed to load data:', error)
        } finally {
            setIsLoading(false)
        }
    }

    const handleLogout = () => {
        localStorage.removeItem('sheetflow_token')
        router.push('/')
    }

    const openFilePicker = async () => {
        setShowFilePicker(true)
        setIsLoadingFiles(true)

        try {
            const data = await listDriveFiles()
            setDriveFiles(data.files)
        } catch (error) {
            console.error('Failed to load drive files:', error)
        } finally {
            setIsLoadingFiles(false)
        }
    }

    const handleSelectFile = async (file: DriveFile) => {
        setIsCreating(true)

        try {
            const dashboard = await createDashboard({
                file_id: file.id,
                file_name: file.name,
            })

            setShowFilePicker(false)
            router.push(`/dashboard/${dashboard.id}`)
        } catch (error) {
            console.error('Failed to create dashboard:', error)
            setIsCreating(false)
        }
    }

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <LoadingSpinner size="lg" message="Loading dashboards..." />
            </div>
        )
    }

    return (
        <div className="min-h-screen">
            {/* Header */}
            <header className="border-b border-white/10 bg-dark-900/50 backdrop-blur-sm sticky top-0 z-10">
                <div className="max-w-7xl mx-auto px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <BarChart3 className="w-8 h-8 text-primary-400" />
                            <span className="text-xl font-bold text-white">SheetFlow AI</span>
                        </div>

                        <div className="flex items-center gap-4">
                            {user && (
                                <div className="flex items-center gap-2 text-dark-300">
                                    {user.picture_url ? (
                                        <img
                                            src={user.picture_url}
                                            alt={user.name}
                                            className="w-8 h-8 rounded-full"
                                        />
                                    ) : (
                                        <User className="w-5 h-5" />
                                    )}
                                    <span className="text-sm hidden sm:inline">{user.email}</span>
                                </div>
                            )}

                            <button
                                onClick={handleLogout}
                                className="p-2 rounded-lg hover:bg-white/5 text-dark-300 hover:text-white transition-colors"
                                title="Logout"
                            >
                                <LogOut className="w-5 h-5" />
                            </button>
                        </div>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="max-w-7xl mx-auto px-6 py-8">
                <div className="flex items-center justify-between mb-8">
                    <h1 className="text-2xl font-bold text-white">My Dashboards</h1>

                    <button
                        onClick={openFilePicker}
                        className="btn-primary inline-flex items-center gap-2"
                    >
                        <Plus className="w-5 h-5" />
                        New Dashboard
                    </button>
                </div>

                {dashboards.length > 0 ? (
                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {dashboards.map((dashboard) => (
                            <DashboardCard key={dashboard.id} dashboard={dashboard as any} />
                        ))}
                    </div>
                ) : (
                    <div className="glass-card p-12 text-center">
                        <FileSpreadsheet className="w-16 h-16 text-dark-500 mx-auto mb-4" />
                        <h2 className="text-xl font-semibold text-white mb-2">
                            No Dashboards Yet
                        </h2>
                        <p className="text-dark-400 mb-6">
                            Create your first dashboard by selecting an Excel file from Google Drive.
                        </p>
                        <button
                            onClick={openFilePicker}
                            className="btn-primary inline-flex items-center gap-2"
                        >
                            <Plus className="w-5 h-5" />
                            Create Dashboard
                        </button>
                    </div>
                )}
            </main>

            {/* File Picker Modal */}
            {showFilePicker && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
                    <div className="glass-card w-full max-w-2xl max-h-[80vh] flex flex-col">
                        <div className="flex items-center justify-between p-6 border-b border-white/10">
                            <h2 className="text-xl font-semibold text-white">
                                Select Excel File from Drive
                            </h2>
                            <button
                                onClick={() => setShowFilePicker(false)}
                                className="p-2 rounded-lg hover:bg-white/5 text-dark-300"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="flex-1 overflow-y-auto p-6">
                            {isLoadingFiles ? (
                                <LoadingSpinner message="Loading files from Google Drive..." />
                            ) : driveFiles.length > 0 ? (
                                <div className="space-y-2">
                                    {driveFiles.map((file) => (
                                        <button
                                            key={file.id}
                                            onClick={() => handleSelectFile(file)}
                                            disabled={isCreating}
                                            className="w-full flex items-center gap-4 p-4 rounded-xl hover:bg-white/5 transition-colors text-left disabled:opacity-50"
                                        >
                                            <FileSpreadsheet className="w-8 h-8 text-green-400 flex-shrink-0" />
                                            <div className="flex-1 min-w-0">
                                                <p className="text-white font-medium truncate">
                                                    {file.name}
                                                </p>
                                                <p className="text-sm text-dark-400">
                                                    {file.modified_time
                                                        ? new Date(file.modified_time).toLocaleDateString()
                                                        : 'Unknown date'}
                                                    {file.size && ` • ${(file.size / 1024).toFixed(1)} KB`}
                                                </p>
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-center py-8 text-dark-400">
                                    <FileSpreadsheet className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                    <p>No Excel files found in your Google Drive</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
