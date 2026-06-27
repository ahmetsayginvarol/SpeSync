/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f4ff',
          100: '#dce6fd',
          500: '#3b5bdb',
          600: '#2f4ac4',
          700: '#2540a8',
          900: '#1a2d70',
        },
      },
    },
  },
  plugins: [],
}
