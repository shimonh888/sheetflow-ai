'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
    Plus,
    BarChart3,
    LogOut,
    User,
    FileSpreadsheet,
    X,
    Folder,
    ChevronLeft,
    Search,
    AlertTriangle
} from 'lucide-react'
import DashboardCard from '@/components/DashboardCard'
import LoadingSpinner from '@/components/LoadingSpinner'
import {
    listDashboards,
    listDriveFiles,
    createDashboard,
    deleteDashboard,
    getCurrentUser,
    Dashboard,
    DriveFile
} from '@/lib/api'

// Debounce hook for search
function useDebounce<T>(value: T, delay: number): T {
    const [debouncedValue, setDebouncedValue] = useState<T>(value)

    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedValue(value)
        }, delay)

        return () => {
            clearTimeout(handler)
        }
    }, [value, delay])

    return debouncedValue
}

interface FolderBreadcrumb {
    id: string | null
    name: string
}

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

    // Folder navigation state
    const [currentFolderId, setCurrentFolderId] = useState<string | null>(null)
    const [folderStack, setFolderStack] = useState<FolderBreadcrumb[]>([
        { id: null, name: 'My Drive' }
    ])

    // Search state
    const [searchQuery, setSearchQuery] = useState('')
    const debouncedSearch = useDebounce(searchQuery, 300)

    // Delete modal state
    const [deleteModal, setDeleteModal] = useState<{
        isOpen: boolean
        dashboardId: string | null
        dashboardTitle: string
        isDeleting: boolean
    }>({
        isOpen: false,
        dashboardId: null,
        dashboardTitle: '',
        isDeleting: false
    })

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

    // Load drive files when folder or search changes
    const loadDriveFiles = useCallback(async (folderId: string | null, search: string) => {
        setIsLoadingFiles(true)
        try {
            const data = await listDriveFiles({
                folderId: folderId || undefined,
                search: search || undefined
            })
            setDriveFiles(data.files)
        } catch (error) {
            console.error('Failed to load drive files:', error)
        } finally {
            setIsLoadingFiles(false)
        }
    }, [])

    // Effect to reload files when folder or search changes
    useEffect(() => {
        if (showFilePicker) {
            loadDriveFiles(currentFolderId, debouncedSearch)
        }
    }, [showFilePicker, currentFolderId, debouncedSearch, loadDriveFiles])

    const openFilePicker = () => {
        setShowFilePicker(true)
        setCurrentFolderId(null)
        setFolderStack([{ id: null, name: 'My Drive' }])
        setSearchQuery('')
    }

    const closeFilePicker = () => {
        setShowFilePicker(false)
        setSearchQuery('')
        setCurrentFolderId(null)
        setFolderStack([{ id: null, name: 'My Drive' }])
    }

    const navigateToFolder = (file: DriveFile) => {
        setCurrentFolderId(file.id)
        setFolderStack(prev => [...prev, { id: file.id, name: file.name }])
        setSearchQuery('') // Clear search when navigating
    }

    const navigateBack = () => {
        if (folderStack.length > 1) {
            const newStack = [...folderStack]
            newStack.pop()
            setFolderStack(newStack)
            setCurrentFolderId(newStack[newStack.length - 1].id)
        }
    }

    const navigateToBreadcrumb = (index: number) => {
        const newStack = folderStack.slice(0, index + 1)
        setFolderStack(newStack)
        setCurrentFolderId(newStack[newStack.length - 1].id)
    }

    const handleSelectFile = async (file: DriveFile) => {
        if (file.is_folder) {
            navigateToFolder(file)
            return
        }

        // Navigate to preview page instead of creating immediately
        closeFilePicker()
        router.push(`/dashboard/preview/${file.id}?name=${encodeURIComponent(file.name)}`)
    }

    // Delete handlers
    const openDeleteModal = (id: string, title: string) => {
        setDeleteModal({
            isOpen: true,
            dashboardId: id,
            dashboardTitle: title,
            isDeleting: false
        })
    }

    const closeDeleteModal = () => {
        setDeleteModal({
            isOpen: false,
            dashboardId: null,
            dashboardTitle: '',
            isDeleting: false
        })
    }

    const confirmDelete = async () => {
        if (!deleteModal.dashboardId) return

        setDeleteModal(prev => ({ ...prev, isDeleting: true }))
        try {
            await deleteDashboard(deleteModal.dashboardId)
            setDashboards(prev => prev.filter(d => d.id !== deleteModal.dashboardId))
            closeDeleteModal()
        } catch (error) {
            console.error('Failed to delete dashboard:', error)
            setDeleteModal(prev => ({ ...prev, isDeleting: false }))
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
                            <DashboardCard
                                key={dashboard.id}
                                dashboard={dashboard as any}
                                onDelete={openDeleteModal}
                            />
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

            {/* Enhanced File Picker Modal */}
            {showFilePicker && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
                    <div className="glass-card w-full max-w-2xl max-h-[80vh] flex flex-col">
                        {/* Header */}
                        <div className="flex items-center justify-between p-6 border-b border-white/10">
                            <h2 className="text-xl font-semibold text-white">
                                Select Excel File from Drive
                            </h2>
                            <button
                                onClick={closeFilePicker}
                                className="p-2 rounded-lg hover:bg-white/5 text-dark-300 hover:text-white transition-colors"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Search Bar */}
                        <div className="px-6 py-3 border-b border-white/10">
                            <div className="relative">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                                <input
                                    type="text"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    placeholder="Search files..."
                                    className="w-full pl-10 pr-4 py-2 bg-white/5 border border-white/10 rounded-lg text-white placeholder-dark-400 focus:outline-none focus:border-primary-500/50 transition-colors"
                                />
                            </div>
                        </div>

                        {/* Breadcrumbs */}
                        {!searchQuery && (
                            <div className="px-6 py-2 border-b border-white/10 flex items-center gap-2 text-sm overflow-x-auto">
                                {folderStack.length > 1 && (
                                    <button
                                        onClick={navigateBack}
                                        className="p-1 rounded hover:bg-white/5 text-dark-300 hover:text-white transition-colors flex-shrink-0"
                                    >
                                        <ChevronLeft className="w-4 h-4" />
                                    </button>
                                )}
                                {folderStack.map((folder, index) => (
                                    <div key={folder.id ?? 'root'} className="flex items-center gap-2 flex-shrink-0">
                                        {index > 0 && <span className="text-dark-500">/</span>}
                                        <button
                                            onClick={() => navigateToBreadcrumb(index)}
                                            className={`hover:text-primary-400 transition-colors ${index === folderStack.length - 1
                                                ? 'text-white font-medium'
                                                : 'text-dark-400'
                                                }`}
                                        >
                                            {folder.name}
                                        </button>
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* File List */}
                        <div className="flex-1 overflow-y-auto p-6">
                            {isLoadingFiles ? (
                                <LoadingSpinner message="Loading files from Google Drive..." />
                            ) : driveFiles.length > 0 ? (
                                <div className="space-y-2">
                                    {driveFiles.map((file) => (
                                        <button
                                            key={file.id}
                                            onClick={() => handleSelectFile(file)}
                                            disabled={isCreating && !file.is_folder}
                                            className="w-full flex items-center gap-4 p-4 rounded-xl hover:bg-white/5 transition-colors text-left disabled:opacity-50"
                                        >
                                            {file.is_folder ? (
                                                <Folder className="w-8 h-8 text-yellow-400 flex-shrink-0" />
                                            ) : (
                                                <FileSpreadsheet className="w-8 h-8 text-green-400 flex-shrink-0" />
                                            )}
                                            <div className="flex-1 min-w-0">
                                                <p className="text-white font-medium truncate">
                                                    {file.name}
                                                </p>
                                                <p className="text-sm text-dark-400">
                                                    {file.is_folder
                                                        ? 'Folder'
                                                        : (
                                                            <>
                                                                {file.modified_time
                                                                    ? new Date(file.modified_time).toLocaleDateString()
                                                                    : 'Unknown date'}
                                                                {file.size && ` • ${(file.size / 1024).toFixed(1)} KB`}
                                                            </>
                                                        )}
                                                </p>
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-center py-8 text-dark-400">
                                    <FileSpreadsheet className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                    <p>
                                        {searchQuery
                                            ? 'No files found matching your search'
                                            : 'No Excel files found in this folder'}
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Delete Confirmation Modal */}
            {deleteModal.isOpen && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
                    <div className="glass-card w-full max-w-md p-6">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
                                <AlertTriangle className="w-5 h-5 text-red-400" />
                            </div>
                            <h2 className="text-xl font-semibold text-white">Delete Dashboard</h2>
                        </div>

                        <p className="text-dark-300 mb-6">
                            Are you sure you want to delete <strong className="text-white">{deleteModal.dashboardTitle}</strong>?
                            This action cannot be undone.
                        </p>

                        <div className="flex gap-3 justify-end">
                            <button
                                onClick={closeDeleteModal}
                                disabled={deleteModal.isDeleting}
                                className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-white transition-colors disabled:opacity-50"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmDelete}
                                disabled={deleteModal.isDeleting}
                                className="px-4 py-2 rounded-lg bg-red-500 hover:bg-red-600 text-white transition-colors disabled:opacity-50 inline-flex items-center gap-2"
                            >
                                {deleteModal.isDeleting ? (
                                    <>
                                        <LoadingSpinner size="sm" />
                                        Deleting...
                                    </>
                                ) : (
                                    'Delete'
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
