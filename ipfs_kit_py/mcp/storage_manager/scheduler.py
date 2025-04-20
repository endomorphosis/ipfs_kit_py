"""
Migration scheduler for automated content migration.

This module implements the MigrationScheduler class that handles
scheduling and automatic execution of migration policies based on
time schedules.
"""

import logging
import time
import threading
import json
import os
import pytz
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from croniter import croniter
from ipfs_kit_py.mcp.controllers.migration_controller import MigrationController

# Configure logger
logger = logging.getLogger(__name__)


class ScheduleType:
    """Types of schedules supported by the migration scheduler."""
    CRON = "cron"
    INTERVAL = "interval"
    ONE_TIME = "one_time"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class MigrationSchedule:
    """
    Schedule for automatic migration policy execution.

    Represents when a migration policy should be automatically executed.
    """
    def __init__(
        self,
        name: str,
        policy_name: str,
        schedule_type: str,
        schedule_value: Any,
        description: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a migration schedule.

        Args:
            name: Unique name for this schedule
            policy_name: Name of policy to execute
            schedule_type: Type of schedule (cron, interval, one_time, daily, weekly, monthly)
            schedule_value: Value for the schedule (depends on schedule_type)
            description: Schedule description
            options: Additional schedule options
        """
        self.name = name
        self.policy_name = policy_name
        self.schedule_type = schedule_type
        self.schedule_value = schedule_value
        self.description = description or f"Schedule for {policy_name}"
        self.options = options or {}

        # Execution tracking
        self.last_executed = None
        self.next_execution = None
        self.execution_count = 0
        self.enabled = True

        # Parse schedule and set next execution time
        self._parse_schedule()

    def _parse_schedule(self):
        """Parse the schedule and calculate next execution time."""
        now = time.time()
        timezone = self.options.get("timezone")

        if timezone:
            try:
                tz = pytz.timezone(timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                logger.warning(f"Unknown timezone: {timezone}, using UTC")
                tz = pytz.UTC
        else:
            tz = pytz.UTC

        # Calculate next execution time based on schedule type
        if self.schedule_type == ScheduleType.CRON:
            # Cron schedule (e.g. "0 3 * * *" for daily at 3am)
            cron_expr = self.schedule_value

            try:
                # Convert current time to tz-aware datetime
                dt_now = datetime.fromtimestamp(now, tz)

                # Create croniter
                iter = croniter(cron_expr, dt_now)

                # Get next execution time
                next_dt = iter.get_next(datetime)
                self.next_execution = next_dt.timestamp()
            except Exception as e:
                logger.error(f"Error parsing cron expression '{cron_expr}': {e}")
                self.next_execution = None

        elif self.schedule_type == ScheduleType.INTERVAL:
            # Interval in seconds
            interval = int(self.schedule_value)

            # Next execution is now + interval
            self.next_execution = now + interval

        elif self.schedule_type == ScheduleType.ONE_TIME:
            # One-time execution at specific time
            if isinstance(self.schedule_value, (int, float)):
                # Timestamp
                self.next_execution = float(self.schedule_value)
            elif isinstance(self.schedule_value, str):
                # ISO format datetime string
                try:
                    dt = datetime.fromisoformat(self.schedule_value)
                    # If string doesn't specify timezone, use the provided one
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=tz)
                    self.next_execution = dt.timestamp()
                except ValueError:
                    logger.error(f"Error parsing datetime string '{self.schedule_value}'")
                    self.next_execution = None
            else:
                logger.error(f"Invalid one_time schedule value: {self.schedule_value}")
                self.next_execution = None

        elif self.schedule_type == ScheduleType.DAILY:
            # Daily at specific time (format: "HH:MM")
            try:
                hour, minute = map(int, self.schedule_value.split(":"))

                # Convert current time to tz-aware datetime
                dt_now = datetime.fromtimestamp(now, tz)

                # Create datetime for today at specified time
                dt_next = dt_now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                # If that time has passed today, schedule for tomorrow
                if dt_next <= dt_now:
                    dt_next = dt_next + timedelta(days=1)

                self.next_execution = dt_next.timestamp()
            except Exception as e:
                logger.error(f"Error parsing daily schedule '{self.schedule_value}': {e}")
                self.next_execution = None

        elif self.schedule_type == ScheduleType.WEEKLY:
            # Weekly on specific day and time (format: "day_of_week,HH:MM")
            try:
                day_of_week, time_str = self.schedule_value.split(",")
                day_map = {
                    "mon": 0,
                    "tue": 1,
                    "wed": 2,
                    "thu": 3,
                    "fri": 4,
                    "sat": 5,
                    "sun": 6,
                }

                # Convert day name to integer
                if day_of_week.lower() in day_map:
                    day_num = day_map[day_of_week.lower()]
                else:
                    day_num = int(day_of_week)

                hour, minute = map(int, time_str.split(":"))

                # Convert current time to tz-aware datetime
                dt_now = datetime.fromtimestamp(now, tz)

                # Calculate days until next occurrence
                days_ahead = (day_num - dt_now.weekday()) % 7

                # Create datetime for next occurrence
                dt_next = dt_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                dt_next = dt_next + timedelta(days=days_ahead)

                # If that time has passed today and it's the target day, schedule for next week
                if days_ahead == 0 and dt_next <= dt_now:
                    dt_next = dt_next + timedelta(days=7)

                self.next_execution = dt_next.timestamp()
            except Exception as e:
                logger.error(f"Error parsing weekly schedule '{self.schedule_value}': {e}")
                self.next_execution = None

        elif self.schedule_type == ScheduleType.MONTHLY:
            # Monthly on specific day and time (format: "day_of_month,HH:MM")
            try:
                day_of_month, time_str = self.schedule_value.split(",")
                day = int(day_of_month)
                hour, minute = map(int, time_str.split(":"))

                # Convert current time to tz-aware datetime
                dt_now = datetime.fromtimestamp(now, tz)

                # Create datetime for this month's occurrence
                dt_next = dt_now.replace(
                    day=min(day, 28), hour=hour, minute=minute, second=0, microsecond=0
                )

                # If that time has passed this month, schedule for next month
                if dt_next <= dt_now:
                    # Move to next month
                    if dt_next.month == 12:
                        dt_next = dt_next.replace(year=dt_next.year + 1, month=1)
                    else:
                        dt_next = dt_next.replace(month=dt_next.month + 1)

                    # Handle day overflow (e.g., trying to schedule for February 31)
                    if day > 28:
                        try:
                            dt_next = dt_next.replace(day=day)
                        except ValueError:
                            # Get last day of month
                            last_day = (
                                dt_next.replace(
                                    day=1,
                                    month=dt_next.month + 1 if dt_next.month < 12 else 1,
                                    year=dt_next.year if dt_next.month < 12 else dt_next.year + 1,
                                )
                                - timedelta(days=1)
                            ).day
                            dt_next = dt_next.replace(day=last_day)

                self.next_execution = dt_next.timestamp()
            except Exception as e:
                logger.error(f"Error parsing monthly schedule '{self.schedule_value}': {e}")
                self.next_execution = None
        else:
            logger.error(f"Unsupported schedule type: {self.schedule_type}")
            self.next_execution = None

    def update_next_execution(self):
        """Update the next execution time based on the schedule."""
        # For one-time schedules, don't update if already executed
        if self.schedule_type == ScheduleType.ONE_TIME and self.last_executed is not None:
            self.next_execution = None
            return

        # For interval schedules, simply add the interval to the last execution
        if self.schedule_type == ScheduleType.INTERVAL and self.last_executed is not None:
            interval = int(self.schedule_value)
            self.next_execution = self.last_executed + interval
            return

        # For other schedule types, recalculate based on current time
        self._parse_schedule()

    def is_due(self) -> bool:
        """
        Check if this schedule is due for execution.

        Returns:
            True if schedule should be executed now
        """
        if not self.enabled or self.next_execution is None:
            return False

        return time.time() >= self.next_execution

    def record_execution(self):
        """Record an execution of this schedule."""
        self.last_executed = time.time()
        self.execution_count += 1
        self.update_next_execution()

    def to_dict(self) -> Dict[str, Any]:
        """Convert schedule to dictionary representation."""
        return {
            "name": self.name,
            "policy_name": self.policy_name,
            "schedule_type": self.schedule_type,
            "schedule_value": self.schedule_value,
            "description": self.description,
            "options": self.options,
            "last_executed": self.last_executed,
            "next_execution": self.next_execution,
            "execution_count": self.execution_count,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MigrationSchedule":
        """Create schedule from dictionary representation."""
        schedule = cls(
            name=data["name"],
            policy_name=data["policy_name"],
            schedule_type=data["schedule_type"],
            schedule_value=data["schedule_value"],
            description=data.get("description"),
            options=data.get("options", {}),
        )

        # Set execution properties
        schedule.last_executed = data.get("last_executed")
        schedule.next_execution = data.get("next_execution")
        schedule.execution_count = data.get("execution_count", 0)
        schedule.enabled = data.get("enabled", True)

        return schedule


class MigrationScheduler:
    """
    Scheduler for automatic migration policy execution.

    Manages scheduling and execution of migration policies based on
    time schedules.
    """
    def __init__(
        self,
        migration_controller: MigrationController,
        schedules: Optional[List[MigrationSchedule]] = None,
        options: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize the migration scheduler.

        Args:
            migration_controller: MigrationController instance
            schedules: Initial migration schedules
            options: Configuration options
        """
        self.migration_controller = migration_controller
        self.schedules = {s.name: s for s in (schedules or [])}
        self.options = options or {}

        # Scheduler thread
        self.scheduler_thread = None
        self.running = False
        self.scheduler_lock = threading.Lock()

        # Statistics
        self.stats = {
            "total_executions": 0,
            "last_execution": None,
            "successful_executions": 0,
            "failed_executions": 0,
        }

        # Configuration
        self.check_interval = self.options.get("check_interval", 60)  # seconds

        # Load schedules from persistent storage
        self._load_state()

    def _load_state(self):
        """Load scheduler state from persistent storage."""
        state_path = self.options.get("state_path")

        if state_path and os.path.exists(state_path):
            try:
                with open(state_path, "r") as f:
                    state = json.load(f)

                # Load schedules
                for schedule_data in state.get("schedules", []):
                    schedule = MigrationSchedule.from_dict(schedule_data)
                    self.schedules[schedule.name] = schedule

                # Load stats
                if "stats" in state:
                    self.stats.update(state["stats"])

                logger.info(f"Loaded {len(self.schedules)} migration schedules")
            except Exception as e:
                logger.error(f"Failed to load scheduler state: {e}")

    def _save_state(self):
        """Save scheduler state to persistent storage."""
        state_path = self.options.get("state_path")

        if state_path:
            try:
                # Convert schedules to dict
                schedules_data = [schedule.to_dict() for schedule in self.schedules.values()]

                state = {
                    "schedules": schedules_data,
                    "stats": self.stats,
                    "updated_at": time.time(),
                }

                with open(state_path, "w") as f:
                    json.dump(state, f, indent=2)

                logger.info(f"Saved scheduler state with {len(schedules_data)} schedules")
            except Exception as e:
                logger.error(f"Failed to save scheduler state: {e}")

    def add_schedule(self, schedule: MigrationSchedule) -> bool:
        """
        Add a new migration schedule.

        Args:
            schedule: Migration schedule to add

        Returns:
            True if schedule was added successfully
        """
        if schedule.name in self.schedules:
            logger.warning(f"Schedule with name '{schedule.name}' already exists")
            return False

        # Verify that the policy exists
        policies = self.migration_controller.list_policies()
        policy_names = [p["name"] for p in policies]

        if schedule.policy_name not in policy_names:
            logger.warning(f"Policy '{schedule.policy_name}' not found")
            return False

        self.schedules[schedule.name] = schedule

        # Save updated state
        self._save_state()

        return True

    def remove_schedule(self, schedule_name: str) -> bool:
        """
        Remove a migration schedule.

        Args:
            schedule_name: Name of schedule to remove

        Returns:
            True if schedule was removed successfully
        """
        if schedule_name not in self.schedules:
            logger.warning(f"Schedule '{schedule_name}' not found")
            return False

        del self.schedules[schedule_name]

        # Save updated state
        self._save_state()

        return True

    def update_schedule(self, schedule_name: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing migration schedule.

        Args:
            schedule_name: Name of schedule to update
            updates: Dictionary of properties to update

        Returns:
            True if schedule was updated successfully
        """
        if schedule_name not in self.schedules:
            logger.warning(f"Schedule '{schedule_name}' not found")
            return False

        schedule = self.schedules[schedule_name]

        # Update properties that don't require rescheduling
        if "description" in updates:
            schedule.description = updates["description"]

        if "options" in updates:
            schedule.options.update(updates["options"])

        if "enabled" in updates:
            schedule.enabled = updates["enabled"]

        # Update properties that require rescheduling
        reschedule = False

        if "policy_name" in updates:
            # Verify that the policy exists
            policies = self.migration_controller.list_policies()
            policy_names = [p["name"] for p in policies]

            if updates["policy_name"] not in policy_names:
                logger.warning(f"Policy '{updates['policy_name']}' not found")
                return False

            schedule.policy_name = updates["policy_name"]

        if "schedule_type" in updates:
            schedule.schedule_type = updates["schedule_type"]
            reschedule = True

        if "schedule_value" in updates:
            schedule.schedule_value = updates["schedule_value"]
            reschedule = True

        # Recalculate next execution time if needed
        if reschedule:
            schedule._parse_schedule()

        # Save updated state
        self._save_state()

        return True

    def list_schedules(self) -> List[Dict[str, Any]]:
        """
        List all migration schedules.

        Returns:
            List of schedule information dictionaries
        """
        # Sort schedules by next execution time
        sorted_schedules = sorted(
            self.schedules.values(),
            key=lambda s: s.next_execution if s.next_execution else float("inf"),
        )

        return [self._format_schedule_info(s) for s in sorted_schedules]

    def get_schedule(self, schedule_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific schedule.

        Args:
            schedule_name: Name of schedule to get

        Returns:
            Schedule information dictionary or None if not found
        """
        if schedule_name not in self.schedules:
            return None

        schedule = self.schedules[schedule_name]
        return self._format_schedule_info(schedule)

    def _format_schedule_info(self, schedule: MigrationSchedule) -> Dict[str, Any]:
        """Format schedule information for API responses."""
        # Format timestamps as ISO format if present
        last_executed_iso = None
        next_execution_iso = None

        if schedule.last_executed:
            last_executed_iso = datetime.fromtimestamp(schedule.last_executed).isoformat()

        if schedule.next_execution:
            next_execution_iso = datetime.fromtimestamp(schedule.next_execution).isoformat()

        # Calculate time until next execution
        time_until_next = None
        if schedule.next_execution:
            time_until_next = max(0, schedule.next_execution - time.time())

        return {
            "name": schedule.name,
            "policy_name": schedule.policy_name,
            "schedule_type": schedule.schedule_type,
            "schedule_value": schedule.schedule_value,
            "description": schedule.description,
            "enabled": schedule.enabled,
            "last_executed": schedule.last_executed,
            "last_executed_iso": last_executed_iso,
            "next_execution": schedule.next_execution,
            "next_execution_iso": next_execution_iso,
            "time_until_next": time_until_next,
            "execution_count": schedule.execution_count,
            "options": schedule.options,
        }

    def trigger_schedule(self, schedule_name: str) -> Dict[str, Any]:
        """
        Manually trigger a schedule to run now.

        Args:
            schedule_name: Name of schedule to trigger

        Returns:
            Dictionary with operation result
        """
        if schedule_name not in self.schedules:
            return {"success": False, "error": f"Schedule '{schedule_name}' not found"}

        schedule = self.schedules[schedule_name]

        if not schedule.enabled:
            return {
                "success": False,
                "error": f"Schedule '{schedule_name}' is disabled",
            }

        # Execute the policy
        result = self._execute_schedule(schedule)

        return {
            "success": result["success"],
            "schedule": schedule_name,
            "policy": schedule.policy_name,
            "execution_time": result.get("execution_time"),
            "result": result,
        }

    def _execute_schedule(self, schedule: MigrationSchedule) -> Dict[str, Any]:
        """
        Execute a schedule by running its associated policy.

        Args:
            schedule: Schedule to execute

        Returns:
            Dictionary with execution result
        """
        start_time = time.time()

        try:
            logger.info(f"Executing schedule '{schedule.name}' for policy '{schedule.policy_name}'")

            # Run the policy
            result = self.migration_controller.run_policy(schedule.policy_name)

            # Record execution
            schedule.record_execution()

            # Update statistics
            self.stats["total_executions"] += 1
            self.stats["last_execution"] = time.time()

            if result.get("success", False):
                self.stats["successful_executions"] += 1
            else:
                self.stats["failed_executions"] += 1

            # Save updated state
            self._save_state()

            # Add execution time
            result["execution_time"] = time.time() - start_time

            return result

        except Exception as e:
            logger.exception(f"Error executing schedule '{schedule.name}': {e}")

            # Record execution anyway
            schedule.record_execution()

            # Update statistics
            self.stats["total_executions"] += 1
            self.stats["last_execution"] = time.time()
            self.stats["failed_executions"] += 1

            # Save updated state
            self._save_state()

            return {
                "success": False,
                "error": str(e),
                "execution_time": time.time() - start_time,
            }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get scheduler statistics.

        Returns:
            Dictionary with scheduler statistics
        """
        # Count schedules by status
        enabled_count = 0
        due_count = 0

        for schedule in self.schedules.values():
            if schedule.enabled:
                enabled_count += 1
                if schedule.is_due():
                    due_count += 1

        stats = {
            "total_schedules": len(self.schedules),
            "enabled_schedules": enabled_count,
            "due_schedules": due_count,
            "total_executions": self.stats["total_executions"],
            "successful_executions": self.stats["successful_executions"],
            "failed_executions": self.stats["failed_executions"],
            "last_execution": self.stats["last_execution"],
            "scheduler_running": self.running,
        }

        # Add next due schedule
        next_due = None
        next_due_time = float("inf")

        for schedule in self.schedules.values():
            if (
                schedule.enabled
                and schedule.next_execution
                and schedule.next_execution < next_due_time
            ):
                next_due = schedule.name
                next_due_time = schedule.next_execution

        if next_due:
            stats["next_due_schedule"] = next_due
            stats["next_due_time"] = next_due_time
            stats["next_due_time_iso"] = datetime.fromtimestamp(next_due_time).isoformat()

        return stats

    def start_scheduler(self) -> bool:
        """
        Start the background scheduler thread.

        Returns:
            True if scheduler was started
        """
        with self.scheduler_lock:
            if self.running:
                return False

            self.running = True
            self.scheduler_thread = threading.Thread(
                target=self._scheduler_loop, name="MigrationScheduler", daemon=True
            )
            self.scheduler_thread.start()
            logger.info("Started migration scheduler thread")

            return True

    def stop_scheduler(self, wait: bool = True) -> bool:
        """
        Stop the background scheduler thread.

        Args:
            wait: Whether to wait for thread to stop

        Returns:
            True if scheduler was stopped
        """
        with self.scheduler_lock:
            if not self.running:
                return False

            self.running = False

            if wait and self.scheduler_thread:
                self.scheduler_thread.join(timeout=5)

            logger.info("Stopped migration scheduler thread")
            return True

    def _scheduler_loop(self):
        """Main scheduler loop for executing schedules."""
        logger.info("Migration scheduler thread started")

        try:
            while self.running:
                try:
                    # Check for due schedules
                    time.time()

                    for schedule_name, schedule in list(self.schedules.items()):
                        if schedule.enabled and schedule.is_due():
                            try:
                                self._execute_schedule(schedule)
                            except Exception as e:
                                logger.error(f"Error executing schedule '{schedule_name}': {e}")

                    # Sleep for check interval
                    time.sleep(self.check_interval)

                except Exception as loop_error:
                    logger.error(f"Error in scheduler loop: {loop_error}")
                    time.sleep(60)  # Sleep longer on error

        except Exception as e:
            logger.exception(f"Fatal error in scheduler thread: {e}")
        finally:
            logger.info("Migration scheduler thread stopped")

    def create_schedule(
        self,
        name: str,
        policy_name: str,
        schedule_type: str,
        schedule_value: Any,
        description: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a new migration schedule.

        Args:
            name: Unique name for this schedule
            policy_name: Name of policy to execute
            schedule_type: Type of schedule
            schedule_value: Value for the schedule
            description: Schedule description
            options: Additional schedule options
            enabled: Whether schedule is enabled

        Returns:
            Dictionary with operation result
        """
        try:
            # Verify that the policy exists
            policies = self.migration_controller.list_policies()
            policy_names = [p["name"] for p in policies]

            if policy_name not in policy_names:
                return {"success": False, "error": f"Policy '{policy_name}' not found"}

            # Check if schedule already exists
            if name in self.schedules:
                return {"success": False, "error": f"Schedule '{name}' already exists"}

            # Create schedule
            schedule = MigrationSchedule(
                name=name,
                policy_name=policy_name,
                schedule_type=schedule_type,
                schedule_value=schedule_value,
                description=description,
                options=options,
            )

            # Set enabled status
            schedule.enabled = enabled

            # Add schedule
            self.schedules[name] = schedule

            # Save updated state
            self._save_state()

            return {"success": True, "schedule": self._format_schedule_info(schedule)}

        except Exception as e:
            logger.exception(f"Error creating schedule: {e}")
            return {"success": False, "error": str(e)}

    def create_daily_schedule(
        self,
        name: str,
        policy_name: str,
        time_str: str,
        description: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a daily schedule at a specific time.

        Args:
            name: Unique name for this schedule
            policy_name: Name of policy to execute
            time_str: Time string in format "HH:MM"
            description: Schedule description
            options: Additional schedule options

        Returns:
            Dictionary with operation result
        """
        return self.create_schedule(
            name=name,
            policy_name=policy_name,
            schedule_type=ScheduleType.DAILY,
            schedule_value=time_str,
            description=description or f"Daily at {time_str}",
            options=options,
        )

    def create_weekly_schedule(
        self,
        name: str,
        policy_name: str,
        day_of_week: Union[str, int],
        time_str: str,
        description: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a weekly schedule on a specific day and time.

        Args:
            name: Unique name for this schedule
            policy_name: Name of policy to execute
            day_of_week: Day of week (0-6 or "mon", "tue", etc.)
            time_str: Time string in format "HH:MM"
            description: Schedule description
            options: Additional schedule options

        Returns:
            Dictionary with operation result
        """
        # Format day of week
        if isinstance(day_of_week, int):
            day_num = day_of_week
            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            day_name = day_names[day_num % 7]
        else:
            day_name = day_of_week.capitalize()

        return self.create_schedule(
            name=name,
            policy_name=policy_name,
            schedule_type=ScheduleType.WEEKLY,
            schedule_value=f"{day_of_week},{time_str}",
            description=description or f"Weekly on {day_name} at {time_str}",
            options=options,
        )

    def create_monthly_schedule(
        self,
        name: str,
        policy_name: str,
        day_of_month: int,
        time_str: str,
        description: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a monthly schedule on a specific day and time.

        Args:
            name: Unique name for this schedule
            policy_name: Name of policy to execute
            day_of_month: Day of month (1-31)
            time_str: Time string in format "HH:MM"
            description: Schedule description
            options: Additional schedule options

        Returns:
            Dictionary with operation result
        """
        return self.create_schedule(
            name=name,
            policy_name=policy_name,
            schedule_type=ScheduleType.MONTHLY,
            schedule_value=f"{day_of_month},{time_str}",
            description=description or f"Monthly on day {day_of_month} at {time_str}",
            options=options,
        )

    def create_interval_schedule(
        self,
        name: str,
        policy_name: str,
        interval_seconds: int,
        description: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a schedule that runs at a regular interval.

        Args:
            name: Unique name for this schedule
            policy_name: Name of policy to execute
            interval_seconds: Interval between executions in seconds
            description: Schedule description
            options: Additional schedule options

        Returns:
            Dictionary with operation result
        """
        # Format interval for description
        if interval_seconds < 60:
            interval_desc = f"{interval_seconds} seconds"
        elif interval_seconds < 3600:
            interval_desc = f"{interval_seconds // 60} minutes"
        elif interval_seconds < 86400:
            interval_desc = f"{interval_seconds // 3600} hours"
        else:
            interval_desc = f"{interval_seconds // 86400} days"

        return self.create_schedule(
            name=name,
            policy_name=policy_name,
            schedule_type=ScheduleType.INTERVAL,
            schedule_value=interval_seconds,
            description=description or f"Every {interval_desc}",
            options=options,
        )

    def create_cron_schedule(
        self,
        name: str,
        policy_name: str,
        cron_expression: str,
        description: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a schedule based on a cron expression.

        Args:
            name: Unique name for this schedule
            policy_name: Name of policy to execute
            cron_expression: Cron expression (e.g. "0 3 * * *")
            description: Schedule description
            options: Additional schedule options

        Returns:
            Dictionary with operation result
        """
        return self.create_schedule(
            name=name,
            policy_name=policy_name,
            schedule_type=ScheduleType.CRON,
            schedule_value=cron_expression,
            description=description or f"Cron: {cron_expression}",
            options=options,
        )
```
