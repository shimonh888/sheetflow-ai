'use client'

import { useMemo } from 'react'
import {
    BarChart,
    Bar,
    LineChart,
    Line,
    PieChart,
    Pie,
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    Cell,
} from 'recharts'

interface ChartConfig {
    id: string
    type: 'bar' | 'line' | 'pie' | 'area'
    title: string
    x_axis?: string
    y_axis?: string
    data_key?: string
    color?: string
}

interface ChartContainerProps {
    config: ChartConfig
    data: any[]
}

// Color palette for charts
const COLORS = [
    '#8884d8',
    '#82ca9d',
    '#ffc658',
    '#ff7c7c',
    '#8dd1e1',
    '#a4de6c',
    '#d0ed57',
    '#ffa07a',
]

export default function ChartContainer({ config, data }: ChartContainerProps) {
    const chartColor = config.color || COLORS[0]

    const renderChart = useMemo(() => {
        if (!data || data.length === 0) {
            return (
                <div className="h-full flex items-center justify-center text-dark-400">
                    No data available
                </div>
            )
        }

        const xKey = config.x_axis || Object.keys(data[0])[0]
        const yKey = config.y_axis || config.data_key || Object.keys(data[0])[1]

        const commonProps = {
            data,
            margin: { top: 20, right: 30, left: 20, bottom: 20 },
        }

        switch (config.type) {
            case 'bar':
                return (
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart {...commonProps}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                            <XAxis
                                dataKey={xKey}
                                tick={{ fill: '#94a3b8', fontSize: 12 }}
                                axisLine={{ stroke: '#334155' }}
                            />
                            <YAxis
                                tick={{ fill: '#94a3b8', fontSize: 12 }}
                                axisLine={{ stroke: '#334155' }}
                            />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: '#1e293b',
                                    border: '1px solid #334155',
                                    borderRadius: '8px',
                                    color: '#f1f5f9'
                                }}
                            />
                            <Legend />
                            <Bar
                                dataKey={yKey}
                                fill={chartColor}
                                radius={[4, 4, 0, 0]}
                            />
                        </BarChart>
                    </ResponsiveContainer>
                )

            case 'line':
                return (
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart {...commonProps}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                            <XAxis
                                dataKey={xKey}
                                tick={{ fill: '#94a3b8', fontSize: 12 }}
                                axisLine={{ stroke: '#334155' }}
                            />
                            <YAxis
                                tick={{ fill: '#94a3b8', fontSize: 12 }}
                                axisLine={{ stroke: '#334155' }}
                            />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: '#1e293b',
                                    border: '1px solid #334155',
                                    borderRadius: '8px',
                                    color: '#f1f5f9'
                                }}
                            />
                            <Legend />
                            <Line
                                type="monotone"
                                dataKey={yKey}
                                stroke={chartColor}
                                strokeWidth={2}
                                dot={{ fill: chartColor, strokeWidth: 2 }}
                                activeDot={{ r: 6, fill: chartColor }}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                )

            case 'area':
                return (
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart {...commonProps}>
                            <defs>
                                <linearGradient id={`gradient-${config.id}`} x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor={chartColor} stopOpacity={0.3} />
                                    <stop offset="95%" stopColor={chartColor} stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                            <XAxis
                                dataKey={xKey}
                                tick={{ fill: '#94a3b8', fontSize: 12 }}
                                axisLine={{ stroke: '#334155' }}
                            />
                            <YAxis
                                tick={{ fill: '#94a3b8', fontSize: 12 }}
                                axisLine={{ stroke: '#334155' }}
                            />
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: '#1e293b',
                                    border: '1px solid #334155',
                                    borderRadius: '8px',
                                    color: '#f1f5f9'
                                }}
                            />
                            <Legend />
                            <Area
                                type="monotone"
                                dataKey={yKey}
                                stroke={chartColor}
                                fill={`url(#gradient-${config.id})`}
                                strokeWidth={2}
                            />
                        </AreaChart>
                    </ResponsiveContainer>
                )

            case 'pie':
                const pieDataKey = config.data_key || yKey
                return (
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Pie
                                data={data}
                                dataKey={pieDataKey}
                                nameKey={xKey}
                                cx="50%"
                                cy="50%"
                                outerRadius={80}
                                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                                labelLine={{ stroke: '#64748b' }}
                            >
                                {data.map((_, index) => (
                                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                ))}
                            </Pie>
                            <Tooltip
                                contentStyle={{
                                    backgroundColor: '#1e293b',
                                    border: '1px solid #334155',
                                    borderRadius: '8px',
                                    color: '#f1f5f9'
                                }}
                            />
                            <Legend />
                        </PieChart>
                    </ResponsiveContainer>
                )

            default:
                return (
                    <div className="h-full flex items-center justify-center text-dark-400">
                        Unknown chart type: {config.type}
                    </div>
                )
        }
    }, [config, data, chartColor])

    return (
        <div className="chart-card h-[350px]">
            <h3 className="text-lg font-semibold text-white mb-4">
                {config.title}
            </h3>
            <div className="h-[280px]">
                {renderChart}
            </div>
        </div>
    )
}
