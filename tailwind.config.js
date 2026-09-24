/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0B0F0E',
        sidebar: '#101615',
        card: '#151C1A',
        elevated: '#1B2421',
        line: '#26322E',
        brand: '#22C55E',
        brandHover: '#16A34A',
        ink: '#F3F7F5',
        muted: '#94A39D',
        faint: '#64736D',
        warn: '#F59E0B',
        crit: '#EF4444',
        info: '#22D3EE',
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', 'Segoe UI', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
};
