# Building Tailwind CSS for Production

This project uses Tailwind CSS with a local build process instead of loading from a CDN.

## Quick Start

### Install Dependencies

```bash
npm install
```

### Build CSS for Production

To build the minified production CSS:

```bash
npm run build:css
```

This will:
- Read the source file from `src/css/input.css`
- Process Tailwind directives
- Generate optimized, minified CSS
- Output to `static/css/tailwind.css`

### Development Build (with source maps)

For development with readable CSS:

```bash
npm run build:css:dev
```

### Watch Mode (auto-rebuild on changes)

For automatic rebuilding during development:

```bash
npm run watch:css
```

## Configuration Files

- **`tailwind.config.js`** - Tailwind configuration with content paths and theme customization
- **`postcss.config.js`** - PostCSS configuration for Tailwind processing
- **`src/css/input.css`** - Source CSS file with Tailwind directives and custom styles

## Content Paths

The Tailwind configuration scans these paths for class usage:

- `./templates/**/*.html` - Main templates
- `./mcp/templates/**/*.html` - MCP templates
- `./mcp/dashboard/templates/**/*.html` - Dashboard templates
- `./ipfs_kit_py/mcp/dashboard/templates/**/*.html` - Package templates
- `./static/**/*.js` - Static JavaScript files
- `./mcp/dashboard/static/**/*.js` - Dashboard JavaScript
- `./ipfs_kit_py/**/*.py` - Python files with HTML strings

## Important Notes

### ⚠️ No CDN in Production

This project **does not use** `cdn.tailwindcss.com` in production. All CSS is built and served locally from `/static/css/tailwind.css`.

### Fallback System

The dashboard includes a fallback system (`/static/js/fallback-system.js`) that:
1. Tries to load local assets first
2. Falls back to CDN only if local assets fail (development/testing)
3. Provides inline CSS as a last resort

### Building Before Deployment

Always run `npm run build:css` before deployment to ensure the latest CSS is generated.

### CI/CD Integration

Add the build step to your CI/CD pipeline:

```yaml
# Example GitHub Actions
- name: Build Tailwind CSS
  run: npm run build:css
```

## Custom Styles

Custom component and utility classes are defined in `src/css/input.css`:

- `.btn`, `.btn-primary`, `.btn-success`, etc. - Button components
- `.card` - Card component
- `.tab-button` - Tab navigation component
- Custom utilities for scrollbar hiding, text balancing, etc.

## Safelist

Commonly used dynamic classes are safelisted in `tailwind.config.js` to ensure they're always included even if not detected during the content scan.
