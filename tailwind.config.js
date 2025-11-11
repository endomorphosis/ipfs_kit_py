/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./mcp/templates/**/*.html",
    "./mcp/dashboard/templates/**/*.html",
    "./ipfs_kit_py/mcp/dashboard/templates/**/*.html",
    "./static/**/*.js",
    "./mcp/dashboard/static/**/*.js",
    "./ipfs_kit_py/mcp/dashboard/static/**/*.js",
    // Include specific Python files with HTML strings (avoid node_modules)
    "./ipfs_kit_py/**/*.py",
    "./mcp/**/*.py",
    "./*.py",
  ],
  theme: {
    extend: {
      colors: {
        // Custom colors for IPFS Kit dashboard
        'ipfs-blue': '#3b82f6',
        'ipfs-green': '#10b981',
        'ipfs-purple': '#8b5cf6',
      },
      fontFamily: {
        'inter': ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
      },
    },
  },
  plugins: [],
  // Safelist commonly used utility classes to ensure they're included
  safelist: [
    'bg-blue-500',
    'bg-green-500',
    'bg-yellow-500',
    'bg-red-500',
    'bg-purple-500',
    'bg-indigo-500',
    'bg-orange-500',
    'hover:bg-blue-600',
    'hover:bg-green-600',
    'hover:bg-yellow-600',
    'hover:bg-red-600',
    'hover:bg-purple-600',
    'hover:bg-indigo-600',
    'hover:bg-orange-600',
    'text-white',
    'text-gray-800',
    'text-gray-600',
    'text-gray-700',
  ],
}