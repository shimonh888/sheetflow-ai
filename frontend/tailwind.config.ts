import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Adobe Color Palette - Neon Green Theme
        primary: {
          50: '#f0fff4',
          100: '#c6ffe0',
          200: '#8bffbf',
          300: '#4dff9a',
          400: '#14FF6E',  // Main Neon Green
          500: '#34D572',  // Secondary Green
          600: '#46AA6C',  // Tertiary Green
          700: '#2d8a54',
          800: '#1f6b3f',
          900: '#144d2b',
        },
        dark: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#2D332F',   // Dark Charcoal - card backgrounds
          900: '#1a1f1c',   // Darker background
          950: '#0f1210',   // Darkest background
        },
        // Keep accent colors for highlights
        accent: {
          green: '#14FF6E',
          greenHover: '#10cc58',
          greenLight: 'rgba(20, 255, 110, 0.1)',
          greenBorder: 'rgba(20, 255, 110, 0.2)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'spin-slow': 'spin 2s linear infinite',
        'pulse-soft': 'pulse 3s ease-in-out infinite',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
      },
    },
  },
  plugins: [],
}

export default config
