/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Ink — slightly warmed neutrals (subtle red undertone) for backgrounds
        // and chrome. Pure cool slate would clash with ruby; warming the deep
        // tones a few degrees keeps the whole UI feeling cohesive.
        ink: {
          50:  '#f8f5f5',
          100: '#e8e2e2',
          200: '#cfc5c5',
          300: '#9e9090',
          400: '#6f6363',
          500: '#4d4242',
          600: '#332b2b',
          700: '#1f1818',
          800: '#120c0c',
          900: '#0a0606',
        },
        // Ruby — the primary brand accent. From subtle deep wine (900) to a
        // bright crimson highlight (400). Deliberately darker than typical
        // "red" Tailwind palettes; aiming for gemstone, not stoplight.
        ruby: {
          50:  '#fdf2f4',
          100: '#fbe5ea',
          200: '#f7c1cb',
          300: '#f29bab',
          400: '#e11d48',  // crimson highlight
          500: '#be123c',  // primary action
          600: '#9f1239',  // hover / depth
          700: '#7e1133',  // ring / border
          800: '#5e0d28',  // glow
          900: '#3a0918',  // deep wine
          950: '#1f0510',  // near-black ruby
        },
        // Crimson — accent layer for highlights, hovers, and glow effects.
        crimson: {
          400: '#ff4d6d',
          500: '#e11d48',
          600: '#c2185b',
        },
        // Wine — deep neutral-to-warm bridge for cards and elevated surfaces.
        wine: {
          900: '#1a0a0e',
          800: '#23101a',
          700: '#2d1822',
        },
      },
      fontFamily: {
        sans: ['var(--font-sans)', 'ui-sans-serif', 'system-ui', '-apple-system', 'Inter', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
        display: ['var(--font-display)', '"Cormorant Garamond"', 'Georgia', 'serif'],
      },
      boxShadow: {
        'ruby-glow':       '0 0 24px -4px rgba(225, 29, 72, 0.25)',
        'ruby-glow-lg':    '0 0 48px -8px rgba(225, 29, 72, 0.35)',
        'ruby-inner':      'inset 0 1px 0 0 rgba(255, 255, 255, 0.04), inset 0 0 24px -8px rgba(225, 29, 72, 0.18)',
        'card-elevated':   '0 12px 32px -16px rgba(0, 0, 0, 0.6), 0 4px 12px -4px rgba(159, 18, 57, 0.18)',
      },
      animation: {
        'fade-in':       'fadeIn 0.6s ease-out forwards',
        'fade-in-up':    'fadeInUp 0.7s cubic-bezier(0.22, 1, 0.36, 1) forwards',
        'fade-in-up-d2': 'fadeInUp 0.7s cubic-bezier(0.22, 1, 0.36, 1) 0.15s forwards',
        'fade-in-up-d3': 'fadeInUp 0.7s cubic-bezier(0.22, 1, 0.36, 1) 0.3s forwards',
        'subtle-pulse':  'subtlePulse 4s ease-in-out infinite',
        'shimmer':       'shimmer 8s linear infinite',
        'glow-soft':     'glowSoft 4s ease-in-out infinite',
        'spin-slow':     'spin 3s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeInUp: {
          '0%':   { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        subtlePulse: {
          '0%, 100%': { opacity: '0.55' },
          '50%':      { opacity: '0.95' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '0% 50%' },
          '50%':  { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
        glowSoft: {
          '0%, 100%': { boxShadow: '0 0 24px -8px rgba(225, 29, 72, 0.25)' },
          '50%':      { boxShadow: '0 0 36px -6px rgba(225, 29, 72, 0.45)' },
        },
      },
    },
  },
  plugins: [],
};
