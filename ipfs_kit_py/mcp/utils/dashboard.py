"""
Console dashboard for MCP file watcher.

This module provides a terminal-based dashboard for displaying
file watcher status, recent changes, and error information.
"""

import os
import threading
import time
from datetime import datetime
from typing import List, Optional

# Console formatting characters
BOX_CHARS = {
    "tl": "┌",
    "tr": "┐",
    "bl": "└",
    "br": "┘",  # corners
    "h": "─",
    "v": "│",  # horizontal and vertical
    "t": "┬",
    "b": "┴",
    "l": "├",
    "r": "┤",  # T-junctions
    "x": "┼",  # cross
}

# Console colors
COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bg_black": "\033[40m",
    "bg_red": "\033[41m",
    "bg_green": "\033[42m",
    "bg_yellow": "\033[43m",
    "bg_blue": "\033[44m",
    "bg_magenta": "\033[45m",
    "bg_cyan": "\033[46m",
    "bg_white": "\033[47m",
}


class MCPDashboard:
    """Terminal-based dashboard for MCP file watcher."""

    def __init__(self, update_interval: float = 1.0, use_colors: bool = True):
        """
        Initialize the dashboard.

        Args:
            update_interval: Update interval in seconds
            use_colors: Whether to use colors in output
        """
        self.update_interval = update_interval
        self.use_colors = use_colors

        # Internal state
        self.running = False
        self.update_thread = None
        self.lock = threading.Lock()

        # Dashboard data
        self.server_status = "Starting"
        self.watcher_status = "Initializing"
        self.files_changed = []
        self.max_files_to_show = 5
        self.recent_errors = []
        self.max_errors_to_show = 3
        self.start_time = time.time()
        self.last_restart_time = None
        self.restart_count = 0
        self.file_count = 0
        self.error_count = 0
        self.fixed_count = 0
        self.last_update_time = None

        # Try to get terminal size
        try:
            self.term_width, self.term_height = os.get_terminal_size()
        except (AttributeError, OSError):
            # Default if cannot determine
            self.term_width = 80
            self.term_height = 24

    def start(self):
        """Start the dashboard updates."""
        if self.running:
            return

        self.running = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()

    def stop(self):
        """Stop the dashboard updates."""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=2)
            self.update_thread = None

    def update_server_status(self, status: str):
        """Update server status."""
        with self.lock:
            self.server_status = status

    def update_watcher_status(self, status: str):
        """Update watcher status."""
        with self.lock:
            self.watcher_status = status

    def add_file_change(self, file_path: str, status: str = "changed"):
        """Add a file change event."""
        with self.lock:
            self.files_changed.insert(
                0,
                {
                    "file": os.path.basename(file_path),
                    "path": file_path,
                    "status": status,
                    "time": time.time(),
                },
            )
            # Limit the list size
            self.files_changed = self.files_changed[: self.max_files_to_show * 2]
            self.file_count += 1
            self.last_update_time = time.time()

    def add_error(self, file_path: str, error_msg: str, line_number: Optional[int] = None):
        """Add an error event."""
        with self.lock:
            # Extract first line of error message for summary
            summary = error_msg.split("\n")[0]
            if len(summary) > 50:
                summary = summary[:47] + "..."

            self.recent_errors.insert(
                0,
                {
                    "file": os.path.basename(file_path),
                    "path": file_path,
                    "message": error_msg,
                    "summary": summary,
                    "line": line_number,
                    "time": time.time(),
                    "fixed": False,
                },
            )
            # Limit the list size
            self.recent_errors = self.recent_errors[: self.max_errors_to_show * 2]
            self.error_count += 1
            self.last_update_time = time.time()

    def mark_error_fixed(self, file_path: str):
        """Mark errors for a file as fixed."""
        with self.lock:
            fixed_any = False
            for error in self.recent_errors:
                if error["path"] == file_path and not error["fixed"]:
                    error["fixed"] = True
                    fixed_any = True

            if fixed_any:
                self.fixed_count += 1
                self.last_update_time = time.time()

    def record_restart(self):
        """Record a server restart."""
        with self.lock:
            self.last_restart_time = time.time()
            self.restart_count += 1
            self.server_status = "Restarting"
            self.last_update_time = time.time()

    def _update_loop(self):
        """Run the dashboard update loop."""
        while self.running:
            try:
                self._draw_dashboard()
                time.sleep(self.update_interval)
            except Exception as e:
                print(f"Dashboard error: {e}")
                # Short sleep to avoid high CPU usage on repeated errors
                time.sleep(0.5)

    def _draw_dashboard(self):
        """Draw the dashboard to the console."""
        # Update terminal size
        try:
            self.term_width, self.term_height = os.get_terminal_size()
        except (AttributeError, OSError):
            # Use defaults if can't determine
            pass

        # Construct dashboard sections
        with self.lock:
            # Calculate uptime
            uptime = time.time() - self.start_time
            uptime_str = self._format_duration(uptime)

            # Format server status with color
            status_color = self._get_status_color(self.server_status)
            server_status = (
                f"{status_color}{self.server_status}{COLORS['reset']}"
                if self.use_colors
                else self.server_status
            )

            # Format last restart time
            last_restart = "Never"
            if self.last_restart_time:
                seconds_ago = time.time() - self.last_restart_time
                last_restart = f"{self._format_duration(seconds_ago)} ago"

            # Create dashboard content
            header = self._format_header("MCP SERVER WATCHER")

            # Status section
            status_lines = [
                f"Server Status: {server_status}",
                f"Watcher Status: {self.watcher_status}",
                f"Uptime: {uptime_str}",
                f"Last Restart: {last_restart} (Total: {self.restart_count})",
                f"Files Changed: {self.file_count} | Errors: {self.error_count} | Fixed: {self.fixed_count}",
            ]

            status_section = self._create_box("STATUS", status_lines, width=self.term_width - 4)

            # Recent Files section
            files_lines = []
            for i, change in enumerate(self.files_changed[: self.max_files_to_show]):
                # Format timestamp
                time_str = datetime.fromtimestamp(change["time"]).strftime("%H:%M:%S")

                # Format status with color if enabled
                status = change["status"]
                if self.use_colors:
                    if status == "changed":
                        status = f"{COLORS['green']}changed{COLORS['reset']}"
                    elif status == "error":
                        status = f"{COLORS['red']}error{COLORS['reset']}"
                    elif status == "fixed":
                        status = f"{COLORS['green']}fixed{COLORS['reset']}"

                # Add file info
                files_lines.append(f"[{time_str}] {change['file']} - {status}")

            if not files_lines:
                files_lines = ["No files changed yet"]

            files_section = self._create_box(
                "RECENT FILES", files_lines, width=self.term_width // 2 - 3
            )

            # Recent Errors section
            errors_lines = []
            for i, error in enumerate(self.recent_errors[: self.max_errors_to_show]):
                # Format timestamp
                time_str = datetime.fromtimestamp(error["time"]).strftime("%H:%M:%S")

                # Format with line number if available
                line_info = f" (line {error['line']})" if error["line"] else ""

                # Format status with color
                status = "FIXED" if error["fixed"] else "ERROR"
                if self.use_colors:
                    status = (
                        f"{COLORS['green']}FIXED{COLORS['reset']}"
                        if error["fixed"]
                        else f"{COLORS['red']}ERROR{COLORS['reset']}"
                    )

                # Add error info
                errors_lines.append(f"[{time_str}] {error['file']}{line_info}: {status}")
                errors_lines.append(f"  {error['summary']}")

            if not errors_lines:
                errors_lines = ["No errors detected"]

            errors_section = self._create_box(
                "RECENT ERRORS", errors_lines, width=self.term_width // 2 - 3
            )

            # Combine files and errors sections side by side
            combined_lines = self._combine_boxes_horizontally(files_section, errors_section)

            # Final dashboard
            dashboard_lines = [header, "", status_section, ""] + combined_lines
            dashboard = "\n".join(dashboard_lines)

            # Clear screen and display dashboard
            self._clear_screen()
            print(dashboard)

    def _format_header(self, title: str) -> str:
        """Format the dashboard header."""
        if self.use_colors:
            # Centered title with color
            padding = (self.term_width - len(title)) // 2
            return f"{COLORS['bold']}{COLORS['cyan']}{' ' * padding}{title}{' ' * padding}{COLORS['reset']}"
        else:
            # Simple centered title
            padding = (self.term_width - len(title)) // 2
            return f"{' ' * padding}{title}{' ' * padding}"

    def _create_box(self, title: str, content_lines: List[str], width: int = 50) -> List[str]:
        """Create a box with the given title and content."""
        # Calculate inner width (accounting for border and padding)
        inner_width = width - 4  # 2 for borders, 2 for padding

        # Create the box
        box_lines = []

        # Top border with title
        if title:
            title_str = f" {title} "
            left_border = BOX_CHARS["tl"] + BOX_CHARS["h"] * 1
            right_border = (
                BOX_CHARS["h"] * (width - len(left_border) - len(title_str) - 1) + BOX_CHARS["tr"]
            )
            box_lines.append(f"{left_border}{title_str}{right_border}")
        else:
            box_lines.append(BOX_CHARS["tl"] + BOX_CHARS["h"] * (width - 2) + BOX_CHARS["tr"])

        # Content lines
        for line in content_lines:
            # Truncate or pad the line to fit inner width
            if len(line) > inner_width:
                display_line = line[: inner_width - 3] + "..."
            else:
                display_line = line + " " * (inner_width - len(line))

            box_lines.append(f"{BOX_CHARS['v']} {display_line} {BOX_CHARS['v']}")

        # Bottom border
        box_lines.append(BOX_CHARS["bl"] + BOX_CHARS["h"] * (width - 2) + BOX_CHARS["br"])

        return box_lines

    def _combine_boxes_horizontally(self, left_box: List[str], right_box: List[str]) -> List[str]:
        """Combine two boxes side by side."""
        # Determine the number of lines needed
        max_lines = max(len(left_box), len(right_box))

        # Pad the shorter box with empty lines
        if len(left_box) < max_lines:
            left_box += [""] * (max_lines - len(left_box))
        if len(right_box) < max_lines:
            right_box += [""] * (max_lines - len(right_box))

        # Combine the lines
        combined_lines = []
        for i in range(max_lines):
            left_line = left_box[i] if i < len(left_box) else ""
            right_line = right_box[i] if i < len(right_box) else ""
            combined_lines.append(f"{left_line}  {right_line}")

        return combined_lines

    def _clear_screen(self):
        """Clear the terminal screen."""
        # Use platform-appropriate clear screen command
        if os.name == "nt": # Windows,
            os.system("cls")
        else:  # Unix/Linux/MacOS
            os.system("clear")

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to a readable string."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            return f"{int(minutes)}m {int(remaining_seconds)}s"
        else:
            hours = seconds // 3600
            remaining = seconds % 3600
            minutes = remaining // 60
            return f"{int(hours)}h {int(minutes)}m"

    def _get_status_color(self, status: str) -> str:
        """Get appropriate color for a status string."""
        if not self.use_colors:
            return ""

        status = status.lower()
        if "error" in status or "fail" in status or "critical" in status:
            return COLORS["red"]
        elif "warn" in status:
            return COLORS["yellow"]
        elif "start" in status or "init" in status:
            return COLORS["cyan"]
        elif "ready" in status or "running" in status or "ok" in status:
            return COLORS["green"]
        elif "restart" in status:
            return COLORS["magenta"]
        else:
            return COLORS["reset"]
