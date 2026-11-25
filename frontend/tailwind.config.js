/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#14130F',
        paper: '#FAF9F5',
        surface: '#FFFFFF',
        mist: '#F2F0E9',
        line: '#E5E2D9',
        lineStrong: '#D6D2C6',
        muted: '#6E6B62',
        faint: '#9A968C',
        accent: '#C2410C',
        accentSoft: '#F6EAE2',
        pass: '#15803D',
        passSoft: '#E7F2EA',
        warn: '#B45309',
        warnSoft: '#FBF0DF',
        fail: '#B91C1C',
        failSoft: '#FBEAEA',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['"Fragment Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0.04em' }],
      },
      borderRadius: { xl: '0.875rem', '2xl': '1.125rem' },
      boxShadow: {
        card: '0 1px 2px rgba(20,19,15,0.04), 0 8px 24px -16px rgba(20,19,15,0.18)',
        lift: '0 2px 4px rgba(20,19,15,0.05), 0 18px 40px -24px rgba(20,19,15,0.28)',
      },
      transitionTimingFunction: { smooth: 'cubic-bezier(0.22, 1, 0.36, 1)' },
      keyframes: {
        fadeUp: { '0%': { opacity: '0', transform: 'translateY(8px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        fadeIn: { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        pulseSoft: { '0%,100%': { opacity: '1' }, '50%': { opacity: '0.45' } },
        sweep: { '0%': { transform: 'translateX(-100%)' }, '100%': { transform: 'translateX(100%)' } },
      },
      animation: {
        fadeUp: 'fadeUp 0.5s cubic-bezier(0.22,1,0.36,1) both',
        fadeIn: 'fadeIn 0.4s ease-out both',
        pulseSoft: 'pulseSoft 2s ease-in-out infinite',
        sweep: 'sweep 1.6s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
