import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
    title: 'SheetFlow AI - Excel to Dashboard',
    description: 'AI-powered Excel to Dashboard SaaS. Connect Google Drive, select Excel files, and let AI generate live, syncable dashboards.',
    keywords: ['excel', 'dashboard', 'ai', 'google drive', 'data visualization'],
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en" className="dark">
            <body className={inter.className}>
                <div className="min-h-screen flex flex-col">
                    {children}
                </div>
            </body>
        </html>
    )
}
