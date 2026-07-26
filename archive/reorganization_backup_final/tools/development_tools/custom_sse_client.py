#!/usr/bin/env python3
"""
Custom SSE Client for MCP Integration

This module provides a custom implementation of a Server-Sent Events (SSE) client
that is specifically designed to work with MCP servers. This implementation
avoids the encoding issues found in some third-party SSE client libraries.
"""

import json
import time
import threading
import queue
import requests
import re
from urllib.parse import urlparse

class Event:
    """Represents a Server-Sent Event."""
    
    def __init__(self, event_id=None, event_type="message", data=None):
        self.id = event_id
        self.event = event_type
        self.data = data or ""
    
    def __str__(self):
        return f"Event(id={self.id}, event={self.event}, data={self.data})"

class CustomSSEClient:
    """
    A custom implementation of a Server-Sent Events client that handles
    connections to SSE endpoints and parses the event stream properly.
    """
    
    def __init__(self, url, headers=None, last_event_id=None, retry=3000):
        """
        Initialize a new SSE client.
        
        Args:
            url (str): The URL of the SSE endpoint.
            headers (dict, optional): Additional headers to send with the request.
            last_event_id (str, optional): The ID of the last event received.
            retry (int, optional): The retry interval in milliseconds.
        """
        self.url = url
        self.headers = headers or {}
        self.headers.update({
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache'
        })
        
        if last_event_id:
            self.headers['Last-Event-ID'] = last_event_id
        
        self.retry = retry
        self.running = False
        self.connection = None
        self._event_queue = queue.Queue()
        self._thread = None
    
    def start(self):
        """Start the SSE connection in a background thread."""
        if self.running:
            return
        
        self.running = True
        self._thread = threading.Thread(target=self._connect_and_listen)
        self._thread.daemon = True
        self._thread.start()
    
    def stop(self):
        """Stop the SSE connection."""
        self.running = False
        if self.connection:
            self.connection.close()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
    
    def events(self):
        """
        Generator that yields events as they are received from the server.
        
        Yields:
            Event: The next event from the server.
        """
        while self.running:
            try:
                yield self._event_queue.get(timeout=0.1)
            except queue.Empty:
                continue
    
    def _connect_and_listen(self):
        """Connect to the SSE endpoint and start listening for events."""
        while self.running:
            try:
                # Using a session to maintain connection state
                session = requests.Session()
                
                # Stream the response to handle events as they arrive
                self.connection = session.get(
                    self.url,
                    headers=self.headers,
                    stream=True,
                    timeout=10
                )
                
                # Check for successful connection
                if self.connection.status_code != 200:
                    raise ValueError(f"Failed to connect to SSE endpoint: {self.connection.status_code} {self.connection.reason}")
                
                # Process the event stream
                self._process_stream(self.connection)
                
            except (requests.RequestException, ValueError) as e:
                if self.running:
                    print(f"SSE connection error: {str(e)}")
                    print(f"Reconnecting in {self.retry/1000} seconds...")
                    time.sleep(self.retry / 1000)
            except Exception as e:
                if self.running:
                    print(f"Unexpected error in SSE client: {str(e)}")
                    time.sleep(self.retry / 1000)
            finally:
                if self.connection:
                    self.connection.close()
    
    def _process_stream(self, response):
        """
        Process the SSE stream from the response.
        
        Args:
            response (Response): The response object from requests.
        """
        event_id = None
        event_type = "message"
        data_buffer = []
        
        # Process the stream line by line
        for line in response.iter_lines(decode_unicode=True):
            # Skip null lines or comments
            if not line or line.startswith(':'):
                continue
            
            # End of event - yield it and reset buffers
            if line.strip() == "":
                if data_buffer:
                    data = "\n".join(data_buffer)
                    # Try to parse as JSON if it looks like JSON
                    if data.strip().startswith('{') or data.strip().startswith('['):
                        try:
                            parsed_data = json.loads(data)
                        except json.JSONDecodeError:
                            parsed_data = data
                    else:
                        parsed_data = data
                    
                    event = Event(event_id, event_type, parsed_data)
                    self._event_queue.put(event)
                    
                    # Reset for next event
                    data_buffer = []
                    event_type = "message"
                    # Keep event_id as it persists until a new one is received
                continue
            
            # Parse the field: value format
            match = re.match(r'^([^:]+):(?: (.*))?$', line)
            if match:
                field, value = match.groups()
                value = value or ""
                
                if field == "id":
                    event_id = value
                elif field == "event":
                    event_type = value
                elif field == "data":
                    data_buffer.append(value)
                elif field == "retry":
                    try:
                        self.retry = int(value)
                    except ValueError:
                        pass
            else:
                # Malformed line - add to data buffer anyway
                data_buffer.append(line)

class MCPSSEClientHandler:
    """
    A high-level handler for MCP Server-Sent Events communication.
    
    This class manages a CustomSSEClient and provides methods to interact
    with an MCP server through its SSE interface.
    """
    
    def __init__(self, sse_url, tool_call_url=None):
        """
        Initialize a new MCP SSE client handler.
        
        Args:
            sse_url (str): The URL of the SSE endpoint.
            tool_call_url (str, optional): The URL for making tool calls. If not provided,
                                          it will be derived from sse_url.
        """
        self.sse_url = sse_url
        
        # Derive tool call URL if not provided
        if not tool_call_url:
            parsed = urlparse(sse_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            tool_call_path = parsed.path.replace("/sse", "/sse/request")
            self.tool_call_url = f"{base_url}{tool_call_path}"
        else:
            self.tool_call_url = tool_call_url
        
        self.client_id = None
        self.sse_client = None
        self.message_queue = queue.Queue()
        self.running = False
        self.server_info = None
        self._listener_thread = None
    
    def start(self):
        """
        Start the connection to the MCP server.
        
        Returns:
            bool: True if connection was successful, False otherwise.
        """
        try:
            print(f"Connecting to SSE endpoint: {self.sse_url}")
            self.sse_client = CustomSSEClient(self.sse_url)
            self.running = True
            
            # Start SSE client
            self.sse_client.start()
            
            # Start listener thread to process events
            self._listener_thread = threading.Thread(target=self._event_listener)
            self._listener_thread.daemon = True
            self._listener_thread.start()
            
            # Wait for init message
            print("Waiting for init message...")
            init_timeout = 5
            start_time = time.time()
            
            while time.time() - start_time < init_timeout:
                try:
                    msg = self.message_queue.get(timeout=1)
                    if msg.get("event") == "init":
                        self.client_id = msg.get("data", {}).get("client_id")
                        self.server_info = msg.get("data", {}).get("server_info")
                        print(f"Connected! Client ID: {self.client_id}")
                        print(f"Server Info: {json.dumps(self.server_info, indent=2)}")
                        return True
                except queue.Empty:
                    continue
            
            print("Timed out waiting for init message")
            self.stop()
            return False
            
        except Exception as e:
            print(f"Error connecting to SSE endpoint: {str(e)}")
            return False
    
    def _event_listener(self):
        """Process events from the SSE client and put them in the message queue."""
        try:
            for event in self.sse_client.events():
                if not self.running:
                    break
                
                message = {
                    "id": event.id,
                    "event": event.event,
                    "data": event.data
                }
                
                # Only log non-heartbeat messages
                if event.event != "heartbeat":
                    event_data = json.dumps(event.data) if isinstance(event.data, dict) else str(event.data)
                    print(f"Received event: {event.event}")
                    print(f"Data: {event_data}")
                
                self.message_queue.put(message)
        except Exception as e:
            if self.running:
                print(f"Event listener error: {str(e)}")
    
    def call_tool(self, tool_name, arguments, timeout=10):
        """
        Call a tool on the MCP server.
        
        Args:
            tool_name (str): The name of the tool to call.
            arguments (dict): The arguments to pass to the tool.
            timeout (int, optional): The timeout in seconds to wait for a response.
        
        Returns:
            dict or None: The result of the tool call, or None if the call failed.
        """
        if not self.client_id:
            print("Not connected to MCP server")
            return None
        
        print(f"\n=== Calling tool: {tool_name} ===\n")
        print(f"Arguments: {json.dumps(arguments, indent=2)}")
        
        request_id = str(time.time())  # Simple unique ID
        
        payload = {
            "client_id": self.client_id,
            "request_id": request_id,
            "type": "tool_call",
            "tool_name": tool_name,
            "arguments": arguments
        }
        
        try:
            # Send tool call request
            response = requests.post(self.tool_call_url, json=payload)
            
            if response.status_code != 200:
                print(f"Tool call request failed: {response.status_code}")
                print(f"Response: {response.text}")
                return None
            
            # Wait for tool response
            print(f"Tool call request sent, waiting for response...")
            
            # Wait for response with timeout
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                try:
                    msg = self.message_queue.get(timeout=0.5)
                    
                    if msg.get("event") == "tool_response" and msg.get("data", {}).get("request_id") == request_id:
                        result = msg.get("data", {}).get("result")
                        print("Tool call successful!")
                        print("Result:")
                        
                        if isinstance(result, dict):
                            print(json.dumps(result, indent=2))
                        else:
                            print(result)
                        
                        return result
                    
                    # Put other messages back in the queue
                    self.message_queue.put(msg)
                
                except queue.Empty:
                    continue
            
            print("Timed out waiting for tool response")
            return None
            
        except Exception as e:
            print(f"Error calling tool: {str(e)}")
            return None
    
    def stop(self):
        """Stop the connection to the MCP server."""
        self.running = False
        if self.sse_client:
            self.sse_client.stop()
        
        print("Connection closed")


def test_mcp_connection(sse_url="http://localhost:8002/sse"):
    """
    Test the connection to an MCP server using the custom SSE client.
    
    Args:
        sse_url (str, optional): The URL of the SSE endpoint.
    
    Returns:
        bool: True if all tests passed, False otherwise.
    """
    print(f"\n=== MCP Connection Test using Custom SSE Client ===\n")
    
    # Create and start client
    client = MCPSSEClientHandler(sse_url)
    if not client.start():
        print("Failed to connect to MCP server")
        return False
    
    try:
        # Test health check
        health_result = client.call_tool("health_check", {})
        if not health_result:
            print("Health check failed")
            return False
        
        # Test IPFS functionality
        test_path = "/mcp-test/custom-client-test.txt"
        test_content = f"Test content from custom SSE client at {time.time()}"
        
        write_result = client.call_tool("ipfs_files_write", {
            "path": test_path,
            "content": test_content
        })
        
        if not write_result or not write_result.get("success"):
            print("IPFS files_write failed")
            return False
        
        read_result = client.call_tool("ipfs_files_read", {
            "path": test_path
        })
        
        if not read_result:
            print("IPFS files_read failed")
            return False
        
        result_content = read_result.get("content", "")
        if result_content != test_content:
            print("IPFS read content doesn't match written content")
            print(f"Expected: {test_content}")
            print(f"Actual: {result_content}")
            return False
        
        print("\n=== IPFS functionality tests passed! ===\n")
        
        # Test model functionality
        list_models_result = client.call_tool("list_models", {})
        if not list_models_result:
            print("list_models failed")
            return False
        
        # If we have models, try creating an endpoint
        if list_models_result.get("models") and len(list_models_result.get("models")) > 0:
            model_name = next(iter(list_models_result.get("models").keys()))
            
            endpoint_result = client.call_tool("create_endpoint", {
                "model_name": model_name
            })
            
            if not endpoint_result or not endpoint_result.get("success"):
                print(f"create_endpoint failed for model {model_name}")
                return False
            
            print("\n=== Model functionality tests passed! ===\n")
        
        print("\n=== Test Results ===\n")
        print("All tests passed! The MCP server is working correctly with the custom SSE client.")
        print("Claude should now be able to connect to this server.")
        return True
        
    finally:
        client.stop()

if __name__ == "__main__":
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Test MCP connection with custom SSE client")
    parser.add_argument("--url", default="http://localhost:8002/sse", help="SSE URL of the MCP server")
    
    args = parser.parse_args()
    success = test_mcp_connection(args.url)
    sys.exit(0 if success else 1)
