import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#f5f7fa',      // HDFC light gray page background
        surface:    '#ffffff',      // white sidebar/cards
        panel:      '#eef2f7',      // light panel for message bubbles
        hdfc: {
          blue:     '#004c97',      // HDFC primary blue
          blueDark: '#003a76',      // darker blue for hover
          blueDeep: '#00285a',      // deepest blue (header)
          blueMid:  '#1565c0',      // mid blue
          red:      '#e31837',      // HDFC primary red
          redDark:  '#c01230',      // red hover
          redLight: '#ff2244',      // red active
        },
        border: '#d0dae6',          // light blue-gray border
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

export default config
