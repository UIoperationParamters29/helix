/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // Red & blue DNA theme
        helix: {
          red: '#ef4444',
          'red-dark': '#b91c1c',
          'red-light': '#fca5a5',
          blue: '#3b82f6',
          'blue-dark': '#1d4ed8',
          'blue-light': '#93c5fd',
          // Backgrounds
          bg: '#0a0e1a',
          'bg-card': '#111827',
          'bg-elev': '#1f2937',
          'border': '#374151',
          // Text
          'text': '#f1f5f9',
          'text-dim': '#94a3b8',
          'text-mute': '#64748b',
        },
      },
      fontFamily: {
        sans: ['ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
      },
      keyframes: {
        fadeIn: { '0%': { opacity: 0 }, '100%': { opacity: 1 } },
        slideUp: {
          '0%': { transform: 'translateY(8px)', opacity: 0 },
          '100%': { transform: 'translateY(0)', opacity: 1 },
        },
      },
    },
  },
  plugins: [],
};
