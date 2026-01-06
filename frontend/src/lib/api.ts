/**
 * SheetFlow AI - API Client
 * Functions for communicating with the backend API.
 */

// Use internal Docker URL for server-side requests, public URL for client-side
const API_BASE = typeof window === 'undefined'
    ? (process.env.API_URL || 'http://backend:8000')  // Server-side (SSR)
    : (process.env.NEXT_PUBLIC_API_URL || 'http://backend:8000')  // Client-side

function getToken(): string | null {
    if (typeof window === 'undefined') return null
    return localStorage.getItem('sheetflow_token')
}

function buildUrl(path: string, params?: Record<string, string>): string {
    const url = new URL(path, API_BASE)
    const token = getToken()
    if (token) {
        url.searchParams.set('token', token)
    }
    if (params) {
        Object.entries(params).forEach(([key, value]) => {
            url.searchParams.set(key, value)
        })
    }
    return url.toString()
}

async function fetchWithAuth<T>(
    path: string,
    options: RequestInit = {}
): Promise<T> {
    const url = buildUrl(path)

    const response = await fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers,
        },
    })

    if (response.status === 401) {
        // Token expired, redirect to login
        if (typeof window !== 'undefined') {
            localStorage.removeItem('sheetflow_token')
            window.location.href = '/'
        }
        throw new Error('Unauthorized')
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }))
        throw new Error(error.detail || 'Request failed')
    }

    return response.json()
}

// Auth
export async function getAuthUrl(): Promise<{ auth_url: string }> {
    const response = await fetch(`${API_BASE}/api/auth/login`)
    return response.json()
}

export async function getCurrentUser(): Promise<any> {
    return fetchWithAuth('/api/auth/me')
}

// Dashboards
export interface Dashboard {
    id: string
    file_id: string
    file_name: string
    title: string | null
    description: string | null
    sheet_names: string[]
    dashboard_config: any
    last_synced: string | null
    last_sync_status: string | null
    last_sync_message: string | null
    is_public: boolean
    created_at: string
    updated_at: string
}

export interface DashboardListResponse {
    items: Dashboard[]
    total: number
    page: number
    page_size: number
}

export async function listDashboards(
    page: number = 1,
    pageSize: number = 20
): Promise<DashboardListResponse> {
    return fetchWithAuth(`/api/dashboards?page=${page}&page_size=${pageSize}`)
}

export async function getDashboard(id: string): Promise<Dashboard> {
    return fetchWithAuth(`/api/dashboards/${id}`)
}

export async function createDashboard(data: {
    file_id: string
    file_name: string
    title?: string
    charts?: ChartProposal[]  // User-edited chart configs
}): Promise<Dashboard> {
    return fetchWithAuth('/api/dashboards', {
        method: 'POST',
        body: JSON.stringify(data),
    })
}

export async function deleteDashboard(id: string): Promise<void> {
    await fetchWithAuth(`/api/dashboards/${id}`, { method: 'DELETE' })
}

// Chart Preview
export interface ChartProposal {
    id: string
    type: 'bar' | 'line' | 'pie' | 'area' | 'scatter'
    title: string
    x_axis: string | null
    y_axis: string | null
    data_key: string | null
    color: string
    reasoning: string
}

export interface DataSummary {
    columns: string[]
    numeric_cols: string[]
    categorical_cols: string[]
    date_cols: string[]
    row_count: number
}

export interface PreviewResponse {
    file_id: string
    file_name: string
    sheet_names: string[]
    proposals: ChartProposal[]
    data_summary: DataSummary
    preview_data: any
}

export async function previewDashboard(
    fileId: string,
    fileName: string
): Promise<PreviewResponse> {
    return fetchWithAuth('/api/dashboards/preview', {
        method: 'POST',
        body: JSON.stringify({
            file_id: fileId,
            file_name: fileName
        }),
    })
}

export interface RefreshResponse {
    success: boolean
    message: string
    dashboard_id: string
    last_synced: string
    schema_drift_detected: boolean
    schema_drift_info: any[] | null
    chart_data: any
}

export async function refreshDashboard(
    id: string,
    options?: { force_reprocess?: boolean; accept_schema_drift?: boolean }
): Promise<RefreshResponse> {
    return fetchWithAuth(`/api/dashboards/${id}/refresh`, {
        method: 'POST',
        body: JSON.stringify(options || {}),
    })
}

export async function getDashboardData(id: string): Promise<{
    dashboard_id: string
    last_synced: string | null
    sheet_names: string[]
    charts: any[]
    data: any
}> {
    return fetchWithAuth(`/api/dashboards/${id}/data`)
}

// Drive files
export interface DriveFile {
    id: string
    name: string
    mime_type: string
    modified_time: string | null
    size: number | null
    is_folder: boolean
}

export interface DriveFilesResponse {
    files: DriveFile[]
    next_page_token: string | null
    current_folder_id: string | null
}

export async function listDriveFiles(options?: {
    pageToken?: string
    folderId?: string
    search?: string
}): Promise<DriveFilesResponse> {
    const params: Record<string, string> = {}
    if (options?.pageToken) params.page_token = options.pageToken
    if (options?.folderId) params.folder_id = options.folderId
    if (options?.search) params.search = options.search

    const queryString = Object.entries(params)
        .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
        .join('&')

    const path = queryString
        ? `/api/dashboards/drive-files?${queryString}`
        : `/api/dashboards/drive-files`

    return fetchWithAuth(path)
}
