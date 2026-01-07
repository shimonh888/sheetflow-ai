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
    AlertTriangle,
    Check,
    Files
} from 'lucide-react'
import DashboardCard from '@/components/DashboardCard'
import LoadingSpinner from '@/components/LoadingSpinner'
import {
    listDashboards,
    listDriveFiles,
    deleteDashboard,
    getCurrentUser,
    Dashboard,
    DriveFile,
    FileSourceCreate
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

interface SelectedFile extends DriveFile {
    context: string
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
    const [selectedFiles, setSelectedFiles] = useState<SelectedFile[]>([])
    const [globalDescription, setGlobalDescription] = useState('')

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
        setSelectedFiles([])
        setGlobalDescription('')
    }

    const closeFilePicker = () => {
        setShowFilePicker(false)
        setSearchQuery('')
        setCurrentFolderId(null)
        setFolderStack([{ id: null, name: 'My Drive' }])
        setSelectedFiles([])
        setGlobalDescription('')
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

    const toggleFileSelection = (file: DriveFile) => {
        if (file.is_folder) {
            navigateToFolder(file)
            return
        }

        setSelectedFiles(prev => {
            const isSelected = prev.some(f => f.id === file.id)
            if (isSelected) {
                return prev.filter(f => f.id !== file.id)
            } else {
                return [...prev, { ...file, context: '' }]
            }
        })
    }

    const updateFileContext = (fileId: string, context: string) => {
        setSelectedFiles(prev => prev.map(f =>
            f.id === fileId ? { ...f, context } : f
        ))
    }

    const removeSelectedFile = (fileId: string) => {
        setSelectedFiles(prev => prev.filter(f => f.id !== fileId))
    }

    const handleProceedToPreview = () => {
        if (selectedFiles.length === 0) return

        // Store selected files in sessionStorage for the preview page
        const filesData: FileSourceCreate[] = selectedFiles.map(f => ({
            file_id: f.id,
            file_name: f.name,
            file_context: f.context || null
        }))

        sessionStorage.setItem('sheetflow_selected_files', JSON.stringify(filesData))
        sessionStorage.setItem('sheetflow_global_description', globalDescription)

        closeFilePicker()
        router.push('/dashboard/preview/multi')
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
                            Create your first dashboard by selecting Excel files from Google Drive.
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

            {/* Multi-File Picker Modal */}
            {showFilePicker && (
                <div className="modal-backdrop">
                    <div className="glass-card w-full max-w-4xl max-h-[90vh] flex flex-col">
                        {/* Header */}
                        <div className="flex items-center justify-between p-6 border-b border-white/10">
                            <div>
                                <h2 className="text-xl font-semibold text-white">
                                    Select Excel Files
                                </h2>
                                <p className="text-sm text-dark-400 mt-1">
                                    Select one or more files to create your dashboard
                                </p>
                            </div>
                            <button
                                onClick={closeFilePicker}
                                className="p-2 rounded-lg hover:bg-white/5 text-dark-300 hover:text-white transition-colors"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="flex-1 flex overflow-hidden">
                            {/* Left Panel - File Browser */}
                            <div className="flex-1 flex flex-col border-r border-white/10">
                                {/* Search Bar */}
                                <div className="px-4 py-3 border-b border-white/10">
                                    <div className="relative">
                                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-dark-400" />
                                        <input
                                            type="text"
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            placeholder="Search files..."
                                            className="input-field pl-10"
                                        />
                                    </div>
                                </div>

                                {/* Breadcrumbs */}
                                {!searchQuery && (
                                    <div className="px-4 py-2 border-b border-white/10 flex items-center gap-2 text-sm overflow-x-auto">
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
                                <div className="flex-1 overflow-y-auto p-4">
                                    {isLoadingFiles ? (
                                        <LoadingSpinner message="Loading files..." />
                                    ) : driveFiles.length > 0 ? (
                                        <div className="space-y-2">
                                            {driveFiles.map((file) => {
                                                const isSelected = selectedFiles.some(f => f.id === file.id)
                                                return (
                                                    <button
                                                        key={file.id}
                                                        onClick={() => toggleFileSelection(file)}
                                                        className={`w-full flex items-center gap-4 p-3 rounded-xl transition-all text-left ${isSelected
                                                            ? 'bg-primary-400/10 border border-primary-400/30'
                                                            : 'hover:bg-white/5 border border-transparent'
                                                            }`}
                                                    >
                                                        {file.is_folder ? (
                                                            <Folder className="w-8 h-8 text-yellow-400 flex-shrink-0" />
                                                        ) : (
                                                            <FileSpreadsheet className="w-8 h-8 text-primary-400 flex-shrink-0" />
                                                        )}
                                                        <div className="flex-1 min-w-0">
                                                            <p className="text-white font-medium truncate">
                                                                {file.name}
                                                            </p>
                                                            <p className="text-sm text-dark-400">
                                                                {file.is_folder ? 'Folder' : (
                                                                    <>
                                                                        {file.modified_time
                                                                            ? new Date(file.modified_time).toLocaleDateString()
                                                                            : 'Unknown date'}
                                                                        {file.size && ` • ${(file.size / 1024).toFixed(1)} KB`}
                                                                    </>
                                                                )}
                                                            </p>
                                                        </div>
                                                        {isSelected && !file.is_folder && (
                                                            <Check className="w-5 h-5 text-primary-400 flex-shrink-0" />
                                                        )}
                                                    </button>
                                                )
                                            })}
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

                            {/* Right Panel - Selected Files & Context */}
                            <div className="w-80 flex flex-col bg-dark-800/50">
                                <div className="p-4 border-b border-white/10">
                                    <div className="flex items-center gap-2 text-white font-medium">
                                        <Files className="w-5 h-5 text-primary-400" />
                                        Selected Files ({selectedFiles.length})
                                    </div>
                                </div>

                                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                                    {selectedFiles.length > 0 ? (
                                        <>
                                            {/* Selected files with context */}
                                            {selectedFiles.map((file) => (
                                                <div key={file.id} className="file-card">
                                                    <div className="flex items-start justify-between mb-2">
                                                        <div className="flex items-center gap-2 min-w-0">
                                                            <FileSpreadsheet className="w-4 h-4 text-primary-400 flex-shrink-0" />
                                                            <span className="text-white text-sm font-medium truncate">
                                                                {file.name}
                                                            </span>
                                                        </div>
                                                        <button
                                                            onClick={() => removeSelectedFile(file.id)}
                                                            className="p-1 rounded hover:bg-white/10 text-dark-400 hover:text-white transition-colors flex-shrink-0"
                                                        >
                                                            <X className="w-4 h-4" />
                                                        </button>
                                                    </div>
                                                    <textarea
                                                        value={file.context}
                                                        onChange={(e) => updateFileContext(file.id, e.target.value)}
                                                        placeholder="Add context about this file (e.g., 'This is my sales ledger')"
                                                        className="textarea-field text-sm h-16"
                                                    />
                                                </div>
                                            ))}

                                            {/* Global Dashboard Purpose */}
                                            <div className="pt-4 border-t border-white/10">
                                                <label className="block text-sm font-medium text-white mb-2">
                                                    Dashboard Purpose
                                                </label>
                                                <textarea
                                                    value={globalDescription}
                                                    onChange={(e) => setGlobalDescription(e.target.value)}
                                                    placeholder="Describe the overall goal of this dashboard (e.g., 'Track sales performance across regions')"
                                                    className="textarea-field text-sm h-24"
                                                />
                                            </div>
                                        </>
                                    ) : (
                                        <div className="text-center py-8 text-dark-400">
                                            <Files className="w-12 h-12 mx-auto mb-3 opacity-50" />
                                            <p className="text-sm">
                                                Select files from the list to add them to your dashboard
                                            </p>
                                        </div>
                                    )}
                                </div>

                                {/* Actions */}
                                <div className="p-4 border-t border-white/10">
                                    <button
                                        onClick={handleProceedToPreview}
                                        disabled={selectedFiles.length === 0}
                                        className="btn-primary w-full justify-center"
                                    >
                                        Preview Dashboard
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Delete Confirmation Modal */}
            {deleteModal.isOpen && (
                <div className="modal-backdrop">
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
