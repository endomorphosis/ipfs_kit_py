#!/usr/bin/env python3
"""
IPFS Kit WebSocket Notification Client Example

This example demonstrates how to use the WebSocket notification system to
subscribe to real-time events from IPFS Kit. It connects to the notification
endpoint, subscribes to various event types, and displays notifications as
they arrive.

Usage:
python notification_client_example.py --url ws://localhost:8000/ws/notifications
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from typing import Dict, List, Set, Any, Optional
from urllib.parse import urlparse

try:
    import websockets
except ImportError:
    print("Error: websockets package not found. Install with 'pip install websockets'.")
    sys.exit(1)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('notification_client')


class IPFSNotificationClient:
    """Client for IPFS Kit WebSocket notification system."""
    
    def __init__(self, url: str, subscriptions: Optional[List[str]] = None, 
                filters: Optional[Dict[str, Any]] = None):
        """
        Initialize the notification client.
        
        Args:
            url: WebSocket URL for the notification endpoint
            subscriptions: List of notification types to subscribe to (None for all)
            filters: Optional filters to apply to notifications
        """
        self.url = url
        self.subscriptions = subscriptions or ["all_events"]
        self.filters = filters or {}
        self.websocket = None
        self.connected = False
        self.connection_id = None
        
        # Notification statistics
        self.stats = {
            "notifications_received": 0,
            "notifications_by_type": {},
            "connection_time": None,
            "last_activity": None
        }
        
        # Optional handlers for specific notification types
        self.handlers = {}
    
    async def connect(self) -> bool:
        """
        Connect to the notification WebSocket.
        
        Returns:
            bool: True if connection was successful
        """
        try:
            self.websocket = await websockets.connect(self.url)
            self.connected = True
            self.stats["connection_time"] = time.time()
            
            # Wait for welcome message
            welcome = await self.websocket.recv()
            welcome_data = json.loads(welcome)
            
            if welcome_data.get("type") == "welcome":
                logger.info(f"Connected to notification service: {welcome_data.get('message')}")
                self.connection_id = welcome_data.get("connection_id")
                
                # Subscribe to specified notification types
                await self.subscribe(self.subscriptions, self.filters)
                return True
            else:
                logger.error(f"Unexpected welcome message: {welcome_data}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to notification service: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from the WebSocket."""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            self.connected = False
            logger.info("Disconnected from notification service")
    
    async def subscribe(self, notification_types: List[str], 
                       filters: Optional[Dict[str, Any]] = None) -> bool:
        """
        Subscribe to specific notification types.
        
        Args:
            notification_types: List of notification types to subscribe to
            filters: Optional filters to apply to notifications
            
        Returns:
            bool: True if subscription was successful
        """
        if not self.connected or not self.websocket:
            logger.error("Not connected to notification service")
            return False
        
        try:
            # Send subscription request
            await self.websocket.send(json.dumps({
                "action": "subscribe",
                "notification_types": notification_types,
                "filters": filters
            }))
            
            # Wait for confirmation
            response = await self.websocket.recv()
            confirmation = json.loads(response)
            
            if confirmation.get("type") == "subscription_confirmed":
                subscribed_types = confirmation.get("notification_types", [])
                logger.info(f"Subscribed to: {', '.join(subscribed_types)}")
                
                # Check for invalid types
                invalid_types = confirmation.get("invalid_types", [])
                if invalid_types:
                    logger.warning(f"Invalid notification types: {', '.join(invalid_types)}")
                
                return True
            else:
                logger.error(f"Unexpected subscription response: {confirmation}")
                return False
                
        except Exception as e:
            logger.error(f"Error subscribing to notifications: {e}")
            return False
    
    async def unsubscribe(self, notification_types: List[str]) -> bool:
        """
        Unsubscribe from specific notification types.
        
        Args:
            notification_types: List of notification types to unsubscribe from
            
        Returns:
            bool: True if unsubscription was successful
        """
        if not self.connected or not self.websocket:
            logger.error("Not connected to notification service")
            return False
        
        try:
            # Send unsubscription request
            await self.websocket.send(json.dumps({
                "action": "unsubscribe",
                "notification_types": notification_types
            }))
            
            # Wait for confirmation
            response = await self.websocket.recv()
            confirmation = json.loads(response)
            
            if confirmation.get("type") == "unsubscription_confirmed":
                remaining = confirmation.get("notification_types", [])
                logger.info(f"Unsubscribed from specified types. Remaining subscriptions: {', '.join(remaining)}")
                return True
            else:
                logger.error(f"Unexpected unsubscription response: {confirmation}")
                return False
                
        except Exception as e:
            logger.error(f"Error unsubscribing from notifications: {e}")
            return False
    
    async def get_history(self, limit: int = 10, 
                         notification_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get notification history.
        
        Args:
            limit: Maximum number of history items to retrieve
            notification_type: Optional specific notification type to filter by
            
        Returns:
            List of historical notifications
        """
        if not self.connected or not self.websocket:
            logger.error("Not connected to notification service")
            return []
        
        try:
            # Request history
            await self.websocket.send(json.dumps({
                "action": "get_history",
                "limit": limit,
                "notification_type": notification_type
            }))
            
            # Wait for response
            response = await self.websocket.recv()
            history_data = json.loads(response)
            
            if history_data.get("type") == "history":
                events = history_data.get("events", [])
                logger.info(f"Retrieved {len(events)} historical events")
                return events
            else:
                logger.error(f"Unexpected history response: {history_data}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting notification history: {e}")
            return []
    
    async def get_connection_info(self) -> Dict[str, Any]:
        """
        Get information about the current connection.
        
        Returns:
            Dict with connection information
        """
        if not self.connected or not self.websocket:
            logger.error("Not connected to notification service")
            return {}
        
        try:
            # Request connection info
            await self.websocket.send(json.dumps({
                "action": "get_info"
            }))
            
            # Wait for response
            response = await self.websocket.recv()
            info_data = json.loads(response)
            
            if info_data.get("type") == "connection_info":
                info = info_data.get("info", {})
                logger.info(f"Retrieved connection info: {json.dumps(info, indent=2)}")
                return info
            else:
                logger.error(f"Unexpected connection info response: {info_data}")
                return {}
                
        except Exception as e:
            logger.error(f"Error getting connection info: {e}")
            return {}
    
    def add_handler(self, notification_type: str, handler_func: callable) -> None:
        """
        Add a handler function for a specific notification type.
        
        Args:
            notification_type: Type of notification to handle
            handler_func: Function that takes a notification as parameter
        """
        self.handlers[notification_type] = handler_func
        logger.info(f"Added handler for notification type: {notification_type}")
    
    async def listen(self, duration: Optional[float] = None) -> None:
        """
        Listen for notifications until disconnected or duration expires.
        
        Args:
            duration: Optional maximum duration to listen for in seconds
        """
        if not self.connected or not self.websocket:
            logger.error("Not connected to notification service")
            return
        
        logger.info("Listening for notifications...")
        
        start_time = time.time()
        try:
            while True:
                # Check if duration has expired
                if duration and time.time() - start_time > duration:
                    logger.info(f"Listening duration ({duration}s) expired")
                    break
                
                # Receive message with timeout
                try:
                    message = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    self.stats["last_activity"] = time.time()
                    
                    # Parse and handle notification
                    notification = json.loads(message)
                    
                    # Process the notification
                    if notification.get("type") == "notification":
                        self._process_notification(notification)
                    elif notification.get("type") == "system_notification":
                        # System notifications go to all clients
                        self._process_notification(notification)
                    elif notification.get("type") == "error":
                        logger.error(f"Error from server: {notification.get('error')}")
                    
                except asyncio.TimeoutError:
                    # No message received within timeout, send ping
                    await self._send_ping()
                    continue
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
            self.connected = False
        except Exception as e:
            logger.error(f"Error listening for notifications: {e}")
        finally:
            self.connected = False
    
    async def _send_ping(self) -> None:
        """Send a ping to keep the connection alive."""
        if self.connected and self.websocket:
            try:
                await self.websocket.send(json.dumps({
                    "action": "ping"
                }))
            except Exception as e:
                logger.error(f"Error sending ping: {e}")
    
    def _process_notification(self, notification: Dict[str, Any]) -> None:
        """Process a received notification."""
        notification_type = notification.get("notification_type")
        
        # Update statistics
        self.stats["notifications_received"] += 1
        
        if notification_type:
            if notification_type not in self.stats["notifications_by_type"]:
                self.stats["notifications_by_type"][notification_type] = 0
            self.stats["notifications_by_type"][notification_type] += 1
        
        # Print notification details
        logger.info(f"Received notification: {notification.get('notification_type', 'unknown')}")
        logger.info(f"Data: {json.dumps(notification.get('data', {}), indent=2)}")
        
        # Call type-specific handler if registered
        if notification_type and notification_type in self.handlers:
            try:
                self.handlers[notification_type](notification)
            except Exception as e:
                logger.error(f"Error in notification handler for {notification_type}: {e}")


async def print_notification_stats(client: IPFSNotificationClient, interval: int = 10) -> None:
    """
    Periodically print notification statistics.
    
    Args:
        client: Notification client instance
        interval: Update interval in seconds
    """
    while client.connected:
        # Calculate time connected
        if client.stats["connection_time"]:
            duration = time.time() - client.stats["connection_time"]
            hours, remainder = divmod(int(duration), 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            time_str = "00:00:00"
        
        print(f"\n--- Notification Stats ({time_str}) ---")
        print(f"Total notifications received: {client.stats['notifications_received']}")
        
        if client.stats["notifications_by_type"]:
            print("Notifications by type:")
            for n_type, count in sorted(
                client.stats["notifications_by_type"].items(), 
                key=lambda x: x[1], 
                reverse=True
            ):
                print(f"  {n_type}: {count}")
        
        # Wait for next update
        await asyncio.sleep(interval)


async def run_client(args):
    """Run the notification client with command line arguments."""
    # Create notification client
    client = IPFSNotificationClient(
        url=args.url,
        subscriptions=args.subscribe,
        filters=args.filter
    )
    
    # Connect to notification service
    if not await client.connect():
        logger.error("Failed to connect to notification service")
        return
    
    # Start stats display in background if verbose
    if args.verbose:
        asyncio.create_task(print_notification_stats(client))
    
    # Add custom handlers for specific notification types
    client.add_handler("content_added", lambda n: 
        print(f"\n✅ NEW CONTENT: {n['data'].get('cid')} - {n['data'].get('filename')}"))
    
    client.add_handler("pin_added", lambda n:
        print(f"\n📌 PINNED: {n['data'].get('cid')}"))
    
    client.add_handler("system_error", lambda n:
        print(f"\n❌ ERROR: {n['data'].get('operation')} - {n['data'].get('error')}"))
    
    # If history requested, fetch it
    if args.history:
        history = await client.get_history(limit=args.history)
        if history:
            print(f"\n--- Recent Notifications ({len(history)}) ---")
            for event in history:
                print(f"{event.get('notification_type', 'unknown')}: "
                      f"{json.dumps(event.get('data', {}), indent=2)}")
        else:
            print("No notification history available")
    
    # Listen for notifications
    try:
        await client.listen(duration=args.duration)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        await client.disconnect()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="IPFS Kit WebSocket Notification Client")
    
    parser.add_argument("--url", type=str, 
                      default="ws://localhost:8000/ws/notifications",
                      help="WebSocket URL for the notification endpoint")
    
    parser.add_argument("--subscribe", type=str, nargs="+",
                      default=["all_events"],
                      help="Notification types to subscribe to")
    
    parser.add_argument("--filter", type=json.loads, 
                      default=None,
                      help="JSON string with notification filters")
    
    parser.add_argument("--duration", type=float, 
                      default=None,
                      help="How long to listen for notifications (seconds)")
    
    parser.add_argument("--history", type=int, 
                      default=0,
                      help="Number of historical events to retrieve")
    
    parser.add_argument("--verbose", "-v", action="store_true",
                      help="Enable verbose output including statistics")
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    
    try:
        asyncio.run(run_client(args))
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)