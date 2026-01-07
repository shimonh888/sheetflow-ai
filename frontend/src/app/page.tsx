'use client'

import { useState } from 'react'
import {
    FileSpreadsheet,
    BarChart3,
    RefreshCw,
    Shield,
    Zap,
    ArrowRight,
    Sparkles,
    Files
} from 'lucide-react'

export default function Home() {
    const [isLoading, setIsLoading] = useState(false)

    const handleLogin = async () => {
        setIsLoading(true)
        try {
            const response = await fetch('/api/auth/login')
            const data = await response.json()
            window.location.href = data.auth_url
        } catch (error) {
            console.error('Login failed:', error)
            setIsLoading(false)
        }
    }

    const features = [
        {
            icon: Files,
            title: 'Multi-File Intelligence',
            description: 'AI analyzes and joins data across multiple Excel files with context-aware matching'
        },
        {
            icon: RefreshCw,
            title: 'Live Sync',
            description: 'One-click refresh pulls latest data from Google Drive instantly'
        },
        {
            icon: Shield,
            title: 'Schema Drift Protection',
            description: 'Auto-remaps renamed columns instead of breaking your dashboards'
        },
        {
            icon: Zap,
            title: 'AI-Powered Charts',
            description: 'Gemini suggests optimal visualizations based on your data structure'
        }
    ]

    return (
        <main className="flex-1">
            {/* Hero Section */}
            <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
                {/* Background gradient orbs - Neon Green */}
                <div className="absolute inset-0 overflow-hidden">
                    <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary-400/20 rounded-full blur-3xl animate-pulse-soft" />
                    <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-primary-500/20 rounded-full blur-3xl animate-pulse-soft" style={{ animationDelay: '1s' }} />
                </div>

                <div className="relative z-10 max-w-6xl mx-auto px-6 py-20 text-center">
                    {/* Badge */}
                    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary-400/10 border border-primary-400/20 mb-8">
                        <Sparkles className="w-4 h-4 text-primary-400" />
                        <span className="text-sm text-primary-400">Powered by Gemini AI</span>
                    </div>

                    {/* Main heading */}
                    <h1 className="text-5xl md:text-7xl font-bold mb-6">
                        <span className="gradient-text">Excel to Dashboard</span>
                        <br />
                        <span className="text-white">in Seconds</span>
                    </h1>

                    {/* Subheading */}
                    <p className="text-xl text-dark-300 max-w-2xl mx-auto mb-12">
                        Connect your Google Drive, select Excel files, and watch as AI
                        transforms messy spreadsheets into beautiful, live dashboards.
                    </p>

                    {/* CTA Buttons */}
                    <div className="flex flex-col sm:flex-row gap-4 justify-center">
                        <button
                            onClick={handleLogin}
                            disabled={isLoading}
                            className="btn-primary inline-flex items-center justify-center gap-2 text-lg"
                        >
                            {isLoading ? (
                                <>
                                    <div className="spinner w-5 h-5" />
                                    Connecting...
                                </>
                            ) : (
                                <>
                                    <svg className="w-5 h-5" viewBox="0 0 24 24">
                                        <path
                                            fill="currentColor"
                                            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                                        />
                                        <path
                                            fill="currentColor"
                                            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                                        />
                                        <path
                                            fill="currentColor"
                                            d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                                        />
                                        <path
                                            fill="currentColor"
                                            d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                                        />
                                    </svg>
                                    Connect Google Drive
                                </>
                            )}
                        </button>

                        <a href="#features" className="btn-secondary inline-flex items-center justify-center gap-2 text-lg">
                            Learn More
                            <ArrowRight className="w-5 h-5" />
                        </a>
                    </div>
                </div>
            </section>

            {/* Features Section */}
            <section id="features" className="py-20 px-6">
                <div className="max-w-6xl mx-auto">
                    <div className="text-center mb-16">
                        <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
                            Why SheetFlow AI?
                        </h2>
                        <p className="text-dark-300 max-w-2xl mx-auto">
                            Traditional BI tools require hours of setup. SheetFlow AI gives you
                            insights in seconds with the power of generative AI.
                        </p>
                    </div>

                    <div className="grid md:grid-cols-2 gap-6">
                        {features.map((feature, index) => (
                            <div
                                key={index}
                                className="glass-card p-8 group hover:border-primary-400/30 transition-all duration-300"
                            >
                                <div className="w-12 h-12 rounded-xl bg-primary-400/10 flex items-center justify-center mb-4 group-hover:bg-primary-400/20 transition-colors">
                                    <feature.icon className="w-6 h-6 text-primary-400" />
                                </div>
                                <h3 className="text-xl font-semibold text-white mb-2">
                                    {feature.title}
                                </h3>
                                <p className="text-dark-300">
                                    {feature.description}
                                </p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* How it Works */}
            <section className="py-20 px-6 bg-dark-800/50">
                <div className="max-w-6xl mx-auto">
                    <div className="text-center mb-16">
                        <h2 className="text-3xl md:text-4xl font-bold text-white mb-4">
                            How It Works
                        </h2>
                    </div>

                    <div className="grid md:grid-cols-3 gap-8">
                        {[
                            {
                                step: '01',
                                title: 'Connect',
                                description: 'Link your Google Drive with secure OAuth2 authentication'
                            },
                            {
                                step: '02',
                                title: 'Select & Describe',
                                description: 'Choose Excel files and add context to help AI understand your data'
                            },
                            {
                                step: '03',
                                title: 'Visualize',
                                description: 'AI cleans, joins, and generates beautiful charts instantly'
                            }
                        ].map((item, index) => (
                            <div key={index} className="text-center">
                                <div className="text-6xl font-bold gradient-text mb-4">
                                    {item.step}
                                </div>
                                <h3 className="text-xl font-semibold text-white mb-2">
                                    {item.title}
                                </h3>
                                <p className="text-dark-300">
                                    {item.description}
                                </p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Footer */}
            <footer className="py-8 px-6 border-t border-white/10">
                <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
                    <div className="flex items-center gap-2">
                        <BarChart3 className="w-6 h-6 text-primary-400" />
                        <span className="font-semibold text-white">SheetFlow AI</span>
                    </div>
                    <p className="text-dark-400 text-sm">
                        © 2024 SheetFlow AI. Built with ❤️ and Gemini.
                    </p>
                </div>
            </footer>
        </main>
    )
}

