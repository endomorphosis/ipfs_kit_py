#!/usr/bin/env python3
"""
WebSocket Streaming Example

This script demonstrates how to use the IPFS Kit WebSocket streaming APIs
for efficient bidirectional content streaming.

Usage:
    python websocket_streaming_example.py --mode=stream --path=ipfs://QmExample
    python websocket_streaming_example.py --mode=upload --file=/path/to/file.mp4
    python websocket_streaming_example.py --mode=bidirectional

Requirements:
    pip install websockets
"""

import argparse
import anyio
import json
import mimetypes
import os
import time
from typing import Optional, Dict, Any

import websockets


async def stream_from_ipfs(uri: str, path: str, chunk_size: int = 1024 * 1024) -> None:
    """
    Stream content from IPFS using WebSocket API.
    
    Args:
        uri: WebSocket API endpoint
        path: IPFS path or CID to stream
        chunk_size: Size of each chunk in bytes
    """
    print(f"Streaming {path} from IPFS...")
    
    # Prepare request params
    request_params = {
        "path": path,
        "chunk_size": chunk_size,
        "cache": True
    }
    
    # Detect mime type if possible
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type:
        request_params["mime_type"] = mime_type
    
    # Connect to WebSocket
    async with websockets.connect(uri) as websocket:
        # Send request
        await websocket.send(json.dumps(request_params))
        
        # Prepare to receive content
        total_bytes = 0
        output_file = None
        filename = path.split("/")[-1]
        
        try:
            # Process messages
            while True:
                # Wait for message
                message = await websocket.recv()
                
                # Handle different message types
                if isinstance(message, str):
                    # JSON message (metadata or status)
                    data = json.loads(message)
                    
                    if data.get("type") == "metadata":
                        # Got metadata, prepare for content
                        print(f"Metadata received:")
                        print(f"  Content type: {data.get('content_type')}")
                        print(f"  Content length: {data.get('content_length')} bytes")
                        
                        # Create output file
                        output_file = open(filename, "wb")
                        
                    elif data.get("type") == "complete":
                        # Download complete
                        print(f"Download complete: {total_bytes} bytes received")
                        break
                        
                    elif data.get("type") == "error":
                        # Error occurred
                        print(f"Error: {data.get('error')}")
                        break
                        
                elif isinstance(message, bytes):
                    # Binary chunk
                    if output_file:
                        output_file.write(message)
                        total_bytes += len(message)
                        print(f"Received {total_bytes} bytes...\r", end="")
                    
        finally:
            # Close output file
            if output_file:
                output_file.close()
                print(f"Content saved to {filename}")


async def upload_to_ipfs(uri: str, file_path: str, chunk_size: int = 1024 * 1024) -> None:
    """
    Upload content to IPFS using WebSocket API.
    
    Args:
        uri: WebSocket API endpoint
        file_path: Path to local file to upload
        chunk_size: Size of each chunk in bytes
    """
    print(f"Uploading {file_path} to IPFS...")
    
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found")
        return
    
    # Get file size
    file_size = os.path.getsize(file_path)
    filename = os.path.basename(file_path)
    
    # Detect mime type
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"
    
    # Connect to WebSocket
    async with websockets.connect(uri) as websocket:
        # Prepare metadata
        metadata = {
            "type": "metadata",
            "filename": filename,
            "content_type": mime_type,
            "metadata": {
                "size": file_size,
                "upload_time": time.time()
            }
        }
        
        # Send metadata
        await websocket.send(json.dumps(metadata))
        
        # Send file chunks
        with open(file_path, "rb") as f:
            bytes_sent = 0
            while True:
                # Read chunk
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                
                # Send chunk
                await websocket.send(chunk)
                
                # Update progress
                bytes_sent += len(chunk)
                progress = bytes_sent / file_size * 100
                print(f"Uploaded {bytes_sent}/{file_size} bytes ({progress:.1f}%)...\r", end="")
        
        # Send completion message
        await websocket.send(json.dumps({"type": "complete"}))
        print("\nUpload complete. Waiting for server response...")
        
        # Wait for result
        while True:
            # Receive message
            message = await websocket.recv()
            
            # Process message
            if isinstance(message, str):
                data = json.loads(message)
                
                if data.get("type") == "result":
                    # Upload result
                    if data.get("success"):
                        print(f"Upload successful!")
                        print(f"CID: {data.get('cid')}")
                        print(f"Size: {data.get('size')} bytes")
                    else:
                        print(f"Upload failed: {data.get('error')}")
                    break
                    
                elif data.get("type") == "error":
                    # Error occurred
                    print(f"Error: {data.get('error')}")
                    break


async def bidirectional_streaming(uri: str) -> None:
    """
    Demonstrate bidirectional streaming using the WebSocket API.
    
    Args:
        uri: WebSocket API endpoint
    """
    print("Connected to bidirectional streaming endpoint")
    print("Type 'get [path]' to retrieve content")
    print("Type 'add [file]' to upload content")
    print("Type 'pin [cid]' to pin content")
    print("Type 'exit' to quit")
    
    # Connect to WebSocket
    async with websockets.connect(uri) as websocket:
        # Receive welcome message
        welcome = await websocket.recv()
        welcome_data = json.loads(welcome)
        print(f"Server: {welcome_data.get('message')}")
        
        # Set up stdin reader task
        stdin_queue = asyncio.Queue()
        
        # Function to read from stdin
        async def stdin_reader():
            while True:
                # Read line from stdin
                line = await asyncio.get_event_loop().run_in_executor(
                    None, input, "> "
                )
                
                # Put in queue
                await stdin_queue.put(line)
                
                # Check for exit
                if line.lower() == "exit":
                    break
        
        # Start stdin reader task
        reader_task = asyncio.create_task(stdin_reader())
        
        try:
            # Main loop
            while True:
                # Create tasks for stdin and websocket
                stdin_task = asyncio.create_task(stdin_queue.get())
                ws_task = asyncio.create_task(websocket.recv())
                
                # Wait for either task to complete
                done, pending = await asyncio.wait(
                    [stdin_task, ws_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Cancel pending tasks
                for task in pending:
                    task.cancel()
                
                # Process completed tasks
                for task in done:
                    if task is stdin_task:
                        # Handle stdin input
                        command = task.result()
                        
                        # Check for exit command
                        if command.lower() == "exit":
                            # Send close command
                            await websocket.send(json.dumps({"command": "close"}))
                            await asyncio.sleep(0.5)  # Give server time to respond
                            return
                        
                        # Parse command
                        parts = command.split(" ", 1)
                        if len(parts) < 2:
                            print("Invalid command format. Use: command argument")
                            continue
                            
                        cmd, arg = parts
                        
                        if cmd.lower() == "get":
                            # Request content
                            await websocket.send(json.dumps({
                                "command": "get",
                                "path": arg
                            }))
                            print(f"Requested content: {arg}")
                            
                        elif cmd.lower() == "add":
                            # Check if file exists
                            if not os.path.exists(arg):
                                print(f"Error: File {arg} not found")
                                continue
                                
                            # Prepare upload
                            file_size = os.path.getsize(arg)
                            filename = os.path.basename(arg)
                            mime_type, _ = mimetypes.guess_type(arg)
                            if not mime_type:
                                mime_type = "application/octet-stream"
                                
                            # Send add command
                            await websocket.send(json.dumps({
                                "command": "add",
                                "filename": filename,
                                "content_type": mime_type,
                                "metadata": {
                                    "size": file_size,
                                    "upload_time": time.time()
                                }
                            }))
                            
                            # Wait for ready message
                            msg = await websocket.recv()
                            data = json.loads(msg)
                            if data.get("type") != "ready":
                                print(f"Error: {data.get('error', 'Unexpected response')}")
                                continue
                                
                            # Send file chunks
                            with open(arg, "rb") as f:
                                bytes_sent = 0
                                while True:
                                    # Read chunk
                                    chunk = f.read(1024 * 1024)  # 1MB chunks
                                    if not chunk:
                                        break
                                    
                                    # Send chunk
                                    await websocket.send(chunk)
                                    
                                    # Update progress
                                    bytes_sent += len(chunk)
                                    progress = bytes_sent / file_size * 100
                                    print(f"Uploaded {bytes_sent}/{file_size} bytes ({progress:.1f}%)...\r", end="")
                            
                            # Send completion message
                            await websocket.send(json.dumps({"command": "complete"}))
                            print("\nUpload complete. Waiting for server response...")
                            
                        elif cmd.lower() == "pin":
                            # Pin content
                            await websocket.send(json.dumps({
                                "command": "pin",
                                "cid": arg
                            }))
                            print(f"Requested pinning of {arg}")
                            
                        else:
                            print(f"Unknown command: {cmd}")
                            
                    elif task is ws_task:
                        # Handle WebSocket message
                        message = task.result()
                        
                        # Process message
                        if isinstance(message, str):
                            # JSON message
                            try:
                                data = json.loads(message)
                                msg_type = data.get("type", "")
                                
                                if msg_type == "metadata":
                                    # Content metadata
                                    print(f"Metadata received:")
                                    print(f"  Content type: {data.get('content_type')}")
                                    print(f"  Content length: {data.get('content_length')} bytes")
                                    
                                    # Create output file
                                    output_path = data.get("path", "").split("/")[-1]
                                    if not output_path or output_path == "":
                                        output_path = "download.bin"
                                        
                                    global output_file
                                    output_file = open(output_path, "wb")
                                    
                                elif msg_type == "complete":
                                    # Download complete
                                    if 'output_file' in globals():
                                        output_file.close()
                                        print(f"Download complete: {data.get('bytes_sent', 0)} bytes received")
                                        
                                elif msg_type == "result":
                                    # Operation result
                                    if data.get("success"):
                                        print(f"Operation successful:")
                                        if "cid" in data:
                                            print(f"  CID: {data.get('cid')}")
                                        if "size" in data:
                                            print(f"  Size: {data.get('size')} bytes")
                                    else:
                                        print(f"Operation failed: {data.get('error', 'Unknown error')}")
                                        
                                elif msg_type == "pin_result":
                                    # Pin operation result
                                    if data.get("success"):
                                        print(f"Successfully pinned {data.get('cid')}")
                                    else:
                                        print(f"Failed to pin: {data.get('error', 'Unknown error')}")
                                        
                                elif msg_type == "error":
                                    # Error message
                                    print(f"Error: {data.get('error')}")
                                    
                                elif msg_type == "goodbye":
                                    # Connection closing
                                    print(f"Server: {data.get('message')}")
                                    return
                                    
                                else:
                                    # Unknown message type
                                    print(f"Server: {message}")
                                    
                            except json.JSONDecodeError:
                                # Not JSON, print as text
                                print(f"Server: {message}")
                                
                        elif isinstance(message, bytes):
                            # Binary data - content chunk
                            if 'output_file' in globals():
                                output_file.write(message)
                                print(f"Received {len(message)} bytes\r", end="")
                                
                        else:
                            # Unknown message type
                            print(f"Received unknown message type: {type(message)}")
        
        finally:
            # Cancel stdin reader task
            reader_task.cancel()
            
            # Close output file if open
            if 'output_file' in globals() and output_file is not None:
                output_file.close()


async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="IPFS Kit WebSocket Streaming Example")
    parser.add_argument("--mode", choices=["stream", "upload", "bidirectional"], 
                       default="bidirectional", help="Streaming mode")
    parser.add_argument("--path", type=str, help="IPFS path or CID to stream")
    parser.add_argument("--file", type=str, help="File path to upload")
    parser.add_argument("--host", type=str, default="localhost", help="WebSocket host")
    parser.add_argument("--port", type=int, default=8000, help="WebSocket port")
    args = parser.parse_args()
    
    # Build WebSocket URIs
    ws_uri_base = f"ws://{args.host}:{args.port}"
    stream_uri = f"{ws_uri_base}/ws/stream"
    upload_uri = f"{ws_uri_base}/ws/upload"
    bidirectional_uri = f"{ws_uri_base}/ws/bidirectional"
    
    # Run appropriate mode
    if args.mode == "stream":
        if not args.path:
            print("Error: --path is required for stream mode")
            return
        await stream_from_ipfs(stream_uri, args.path)
        
    elif args.mode == "upload":
        if not args.file:
            print("Error: --file is required for upload mode")
            return
        await upload_to_ipfs(upload_uri, args.file)
        
    elif args.mode == "bidirectional":
        await bidirectional_streaming(bidirectional_uri)


if __name__ == "__main__":
    asyncio.run(main())
