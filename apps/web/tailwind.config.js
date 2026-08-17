/** @type {import('tailwindcss').Config} */
// Colour tokens carried over verbatim from the ProGearSalesAI reference app so
// the two demos read as one product family.
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        'primary': '#1a1a2e',
        'primary-light': '#16213e',
        'accent': '#ff6b35',
        'accent-light': '#ff8c5a',
        'court-orange': '#e85d04',
        'court-brown': '#8b4513',
        'court-tan': '#d4a574',
        'hoop-red': '#c41e3a',
        'net-white': '#fafafa',
        'tech-purple': '#8b5cf6',
        'tech-purple-light': '#a78bfa',
        'okta-blue': '#007dc1',
        'okta-blue-light': '#0ea5e9',
        'success-green': '#22c55e',
        'error-red': '#ef4444',
        'neutral-bg': '#0d0d14',
        'neutral-border': '#2a2a3e',
      },
      fontFamily: {
        'display': ['Inter', 'system-ui', 'sans-serif'],
        'mono': ['JetBrains Mono', 'Courier New', 'monospace'],
      },
    },
  },
  plugins: [],
};
