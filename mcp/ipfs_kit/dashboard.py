"""
Manages the creation of the server dashboard HTML template.
"""
from pathlib import Path


class DashboardTemplateManager:
    """Manages the creation and content of the dashboard template."""

    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir
        self.dashboard_file = self.templates_dir / "dashboard.html"

    def create_dashboard_template(self):
        """Creates the dashboard.html template file if it doesn't exist."""
        html_content = self._get_template_base_structure()

        if not self.dashboard_file.exists():
            with open(self.dashboard_file, "w") as f:
                f.write(html_content)

    def _get_template_base_structure(self) -> str:
        """Returns the HTML structure for the dashboard."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="30">
    <title>MCP Server Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #1a202c; color: #e2e8f0; font-family: sans-serif; }
        .card { background-color: #2d3748; }
        .health-excellent, .health-good { color: #48bb78; }
        .health-poor { color: #f56565; }
        .status-online { color: #48bb78; }
        .status-degraded { color: #ed8936; }
    </style>
</head>
<body class="p-4 sm:p-8">
    <h1 class="text-3xl sm:text-4xl font-bold mb-8 text-white">MCP Server Dashboard</h1>

    <!-- Filesystem Backends Panel -->
    <div class="card rounded-lg p-6">
        <h2 class="text-2xl font-semibold mb-4 text-white">Filesystem Backends</h2>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {% for backend in backend_status %}
            <div class="bg-gray-800 p-4 rounded-lg shadow-md border-l-4
                        {% if backend.health in ['good', 'excellent'] %} border-green-500
                        {% elif backend.health == 'poor' %} border-red-500
                        {% else %} border-yellow-500 {% endif %}">
                <h3 class="text-xl font-bold mb-2 text-white">{{ backend.name }}</h3>
                <p><strong>Status:</strong> <span class="capitalize font-semibold status-{{ backend.status | lower }}">{{ backend.status }}</span></p>
                <p><strong>Health:</strong> <span class="capitalize font-semibold health-{{ backend.health | lower }}">{{ backend.health }}</span></p>
                <div class="mt-4">
                    <p class="text-sm text-gray-400">Storage Usage</p>
                    <div class="w-full bg-gray-700 rounded-full h-2.5 mt-1">
                        <div class="bg-blue-500 h-2.5 rounded-full" style="width: {{ (backend.storage_used / backend.storage_total * 100) | round(1) }}%"></div>
                    </div>
                    <p class="text-right text-sm font-mono">{{ "%.1f" | format(backend.storage_used) }} / {{ backend.storage_total }} GB</p>
                </div>
                <div class="mt-4">
                    <p class="text-sm text-gray-400">Live Traffic</p>
                    <p class="font-mono"><strong>In:</strong> {{ "%.2f" | format(backend.traffic_in) }} Mbps</p>
                    <p class="font-mono"><strong>Out:</strong> {{ "%.2f" | format(backend.traffic_out) }} Mbps</p>
                </div>
            </div>
            {% else %}
            <p>No backend status available.</p>
            {% endfor %}
        </div>
    </div>

</body>
</html>
"""