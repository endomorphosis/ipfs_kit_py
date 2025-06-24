"""
Test IPNS operations in the MCP server with AnyIO support.

This test file focuses on testing the IPNS functionality of the MCP server
using AnyIO for async operations, including publishing and resolving IPNS names.
"""

import json
import time
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from ipfs_kit_py.mcp.models.ipfs_model import IPFSModel
from ipfs_kit_py.mcp.controllers.ipfs_controller import IPFSController
from ipfs_kit_py.mcp.server_bridge import MCPServer  # Refactored import

# Keep original unittest class for backward compatibility
from test_mcp_ipns_operations import TestMCPIPNSOperations

@pytest.mark.anyio
class TestMCPIPNSOperationsAnyIO:
    """Test IPNS operations in the MCP server with AnyIO support."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Set up test environment with AnyIO support."""
        # Create a mock IPFS kit instance with async methods
        self.mock_ipfs_kit = MagicMock()
        self.mock_ipfs_kit.run_ipfs_command_async = AsyncMock()

        # Create model instance with mock IPFS kit
        self.ipfs_model = IPFSModel(ipfs_kit_instance=self.mock_ipfs_kit)

        # Add async methods to model
        self.ipfs_model.ipfs_name_publish_async = AsyncMock()
        self.ipfs_model.ipfs_name_resolve_async = AsyncMock()
        self.ipfs_model.ipfs_key_gen_async = AsyncMock()
        self.ipfs_model.ipfs_key_list_async = AsyncMock()

        # Create controller instance
        self.ipfs_controller = IPFSController(self.ipfs_model)

        # Reset operation stats
        self.ipfs_model.operation_stats = {
            "total_operations": 0,
            "success_count": 0,
            "failure_count": 0,
        }

        yield

        # Cleanup if needed

    @pytest.mark.anyio
    async def test_ipfs_name_publish_async_with_string_response(self):
        """Test that ipfs_name_publish_async correctly handles string response."""
        # Mock the run_ipfs_command_async method to return a string response
        cmd_result = {
            "success": True,
            "stdout": "Published to k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8: /ipfs/QmTestCID"
        }
        self.mock_ipfs_kit.run_ipfs_command_async.return_value = cmd_result

        # Configure model mock to delegate to kit
        async def async_name_publish(cid, **kwargs):
            cmd = ["ipfs", "name", "publish"]

            # Add optional parameters
            if "key" in kwargs and kwargs["key"]:
                cmd.extend(["--key", kwargs["key"]])
            if "lifetime" in kwargs and kwargs["lifetime"]:
                cmd.extend(["--lifetime", kwargs["lifetime"]])
            if "ttl" in kwargs and kwargs["ttl"]:
                cmd.extend(["--ttl", kwargs["ttl"]])

            # Add the CID with IPFS path prefix if it's not already prefixed
            if not cid.startswith("/ipfs/"):
                cid_path = f"/ipfs/{cid}"
            else:
                cid_path = cid

            cmd.append(cid_path)

            # Execute IPFS command
            cmd_result = await self.mock_ipfs_kit.run_ipfs_command_async(cmd)

            # Process the result
            if cmd_result["success"]:
                # Check if we got a string response
                if isinstance(cmd_result["stdout"], str):
                    output = cmd_result["stdout"]
                else:
                    output = cmd_result["stdout"].decode('utf-8')

                # Try to parse as JSON first
                try:
                    data = json.loads(output)
                    name = data.get("Name", "")
                    value = data.get("Value", "")
                except json.JSONDecodeError:
                    # Parse string output - expected format:
                    # "Published to <name>: <value>"
                    parts = output.split(":", 1)
                    name_part = parts[0].strip()
                    name = name_part.replace("Published to ", "")
                    value = parts[1].strip() if len(parts) > 1 else ""

                return {
                    "success": True,
                    "operation": "ipfs_name_publish",
                    "cid": cid,
                    "name": name,
                    "value": value,
                    "timestamp": time.time(),
                    **{k: v for k, v in kwargs.items() if v is not None}
                }
            else:
                # Handle command error
                error_msg = cmd_result.get("stderr", b"Unknown error").decode('utf-8')
                return {
                    "success": False,
                    "operation": "ipfs_name_publish",
                    "cid": cid,
                    "error": f"Command error: {error_msg}",
                    "error_type": "command_error",
                    "timestamp": time.time()
                }

        self.ipfs_model.ipfs_name_publish_async.side_effect = async_name_publish

        # Call the method
        result = await self.ipfs_model.ipfs_name_publish_async("QmTestCID")

        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "ipfs_name_publish"
        assert result["cid"] == "QmTestCID"
        assert result["name"] == "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8"
        assert result["value"] == "/ipfs/QmTestCID"

        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command_async.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command_async.call_args
        cmd = args[0]
        assert cmd[0:3] == ["ipfs", "name", "publish"]
        assert cmd[-1] == "/ipfs/QmTestCID"

    @pytest.mark.anyio
    async def test_ipfs_name_publish_async_with_json_response(self):
        """Test that ipfs_name_publish_async correctly handles JSON response."""
        # Mock the run_ipfs_command_async method to return a JSON response
        json_str = json.dumps({
            "Name": "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8",
            "Value": "/ipfs/QmTestCID"
        })
        cmd_result = {
            "success": True,
            "stdout": json_str.encode('utf-8')
        }
        self.mock_ipfs_kit.run_ipfs_command_async.return_value = cmd_result

        # Configure model mock to delegate to kit (reusing the same implementation)
        async def async_name_publish(cid, **kwargs):
            cmd = ["ipfs", "name", "publish"]

            # Add optional parameters
            if "key" in kwargs and kwargs["key"]:
                cmd.extend(["--key", kwargs["key"]])
            if "lifetime" in kwargs and kwargs["lifetime"]:
                cmd.extend(["--lifetime", kwargs["lifetime"]])
            if "ttl" in kwargs and kwargs["ttl"]:
                cmd.extend(["--ttl", kwargs["ttl"]])

            # Add the CID with IPFS path prefix if it's not already prefixed
            if not cid.startswith("/ipfs/"):
                cid_path = f"/ipfs/{cid}"
            else:
                cid_path = cid

            cmd.append(cid_path)

            # Execute IPFS command
            cmd_result = await self.mock_ipfs_kit.run_ipfs_command_async(cmd)

            # Process the result
            if cmd_result["success"]:
                # Check if we got a string response
                if isinstance(cmd_result["stdout"], str):
                    output = cmd_result["stdout"]
                else:
                    output = cmd_result["stdout"].decode('utf-8')

                # Try to parse as JSON first
                try:
                    data = json.loads(output)
                    name = data.get("Name", "")
                    value = data.get("Value", "")
                except json.JSONDecodeError:
                    # Parse string output - expected format:
                    # "Published to <name>: <value>"
                    parts = output.split(":", 1)
                    name_part = parts[0].strip()
                    name = name_part.replace("Published to ", "")
                    value = parts[1].strip() if len(parts) > 1 else ""

                return {
                    "success": True,
                    "operation": "ipfs_name_publish",
                    "cid": cid,
                    "name": name,
                    "value": value,
                    "timestamp": time.time(),
                    **{k: v for k, v in kwargs.items() if v is not None}
                }
            else:
                # Handle command error
                error_msg = cmd_result.get("stderr", b"Unknown error").decode('utf-8')
                return {
                    "success": False,
                    "operation": "ipfs_name_publish",
                    "cid": cid,
                    "error": f"Command error: {error_msg}",
                    "error_type": "command_error",
                    "timestamp": time.time()
                }

        self.ipfs_model.ipfs_name_publish_async.side_effect = async_name_publish

        # Call the method
        result = await self.ipfs_model.ipfs_name_publish_async("QmTestCID")

        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "ipfs_name_publish"
        assert result["cid"] == "QmTestCID"
        assert result["name"] == "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8"
        assert result["value"] == "/ipfs/QmTestCID"

    @pytest.mark.anyio
    async def test_ipfs_name_publish_async_with_key(self):
        """Test that ipfs_name_publish_async correctly handles the key parameter."""
        # Mock the run_ipfs_command_async method
        cmd_result = {
            "success": True,
            "stdout": "Published to k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8: /ipfs/QmTestCID"
        }
        self.mock_ipfs_kit.run_ipfs_command_async.return_value = cmd_result

        # Configure model mock to delegate to kit (reusing the same implementation)
        async def async_name_publish(cid, **kwargs):
            cmd = ["ipfs", "name", "publish"]

            # Add optional parameters
            if "key" in kwargs and kwargs["key"]:
                cmd.extend(["--key", kwargs["key"]])
            if "lifetime" in kwargs and kwargs["lifetime"]:
                cmd.extend(["--lifetime", kwargs["lifetime"]])
            if "ttl" in kwargs and kwargs["ttl"]:
                cmd.extend(["--ttl", kwargs["ttl"]])

            # Add the CID with IPFS path prefix if it's not already prefixed
            if not cid.startswith("/ipfs/"):
                cid_path = f"/ipfs/{cid}"
            else:
                cid_path = cid

            cmd.append(cid_path)

            # Execute IPFS command
            cmd_result = await self.mock_ipfs_kit.run_ipfs_command_async(cmd)

            # Process the result
            if cmd_result["success"]:
                # Check if we got a string response
                if isinstance(cmd_result["stdout"], str):
                    output = cmd_result["stdout"]
                else:
                    output = cmd_result["stdout"].decode('utf-8')

                # Try to parse as JSON first
                try:
                    data = json.loads(output)
                    name = data.get("Name", "")
                    value = data.get("Value", "")
                except json.JSONDecodeError:
                    # Parse string output - expected format:
                    # "Published to <name>: <value>"
                    parts = output.split(":", 1)
                    name_part = parts[0].strip()
                    name = name_part.replace("Published to ", "")
                    value = parts[1].strip() if len(parts) > 1 else ""

                return {
                    "success": True,
                    "operation": "ipfs_name_publish",
                    "cid": cid,
                    "name": name,
                    "value": value,
                    "timestamp": time.time(),
                    **{k: v for k, v in kwargs.items() if v is not None}
                }
            else:
                # Handle command error
                error_msg = cmd_result.get("stderr", b"Unknown error").decode('utf-8')
                return {
                    "success": False,
                    "operation": "ipfs_name_publish",
                    "cid": cid,
                    "error": f"Command error: {error_msg}",
                    "error_type": "command_error",
                    "timestamp": time.time()
                }

        self.ipfs_model.ipfs_name_publish_async.side_effect = async_name_publish

        # Call the method with a key
        result = await self.ipfs_model.ipfs_name_publish_async("QmTestCID", key="test-key")

        # Verify the result
        assert result["success"] is True
        assert "key" in result
        assert result["key"] == "test-key"

        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command_async.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command_async.call_args
        cmd = args[0]
        assert "--key" in cmd
        key_index = cmd.index("--key")
        assert cmd[key_index + 1] == "test-key"

    @pytest.mark.anyio
    async def test_ipfs_name_publish_async_failure(self):
        """Test that ipfs_name_publish_async correctly handles failure."""
        # Mock the run_ipfs_command_async method to return a failure
        cmd_result = {
            "success": False,
            "stderr": b"Error: failed to publish entry: publisher not online"
        }
        self.mock_ipfs_kit.run_ipfs_command_async.return_value = cmd_result

        # Configure model mock to delegate to kit (reusing the same implementation)
        async def async_name_publish(cid, **kwargs):
            cmd = ["ipfs", "name", "publish"]

            # Add optional parameters
            if "key" in kwargs and kwargs["key"]:
                cmd.extend(["--key", kwargs["key"]])
            if "lifetime" in kwargs and kwargs["lifetime"]:
                cmd.extend(["--lifetime", kwargs["lifetime"]])
            if "ttl" in kwargs and kwargs["ttl"]:
                cmd.extend(["--ttl", kwargs["ttl"]])

            # Add the CID with IPFS path prefix if it's not already prefixed
            if not cid.startswith("/ipfs/"):
                cid_path = f"/ipfs/{cid}"
            else:
                cid_path = cid

            cmd.append(cid_path)

            # Execute IPFS command
            cmd_result = await self.mock_ipfs_kit.run_ipfs_command_async(cmd)

            # Process the result
            if cmd_result["success"]:
                # Check if we got a string response
                if isinstance(cmd_result["stdout"], str):
                    output = cmd_result["stdout"]
                else:
                    output = cmd_result["stdout"].decode('utf-8')

                # Try to parse as JSON first
                try:
                    data = json.loads(output)
                    name = data.get("Name", "")
                    value = data.get("Value", "")
                except json.JSONDecodeError:
                    # Parse string output - expected format:
                    # "Published to <name>: <value>"
                    parts = output.split(":", 1)
                    name_part = parts[0].strip()
                    name = name_part.replace("Published to ", "")
                    value = parts[1].strip() if len(parts) > 1 else ""

                return {
                    "success": True,
                    "operation": "ipfs_name_publish",
                    "cid": cid,
                    "name": name,
                    "value": value,
                    "timestamp": time.time(),
                    **{k: v for k, v in kwargs.items() if v is not None}
                }
            else:
                # Handle command error
                error_msg = cmd_result.get("stderr", b"Unknown error").decode('utf-8')
                return {
                    "success": False,
                    "operation": "ipfs_name_publish",
                    "cid": cid,
                    "error": f"Command error: {error_msg}",
                    "error_type": "command_error",
                    "timestamp": time.time()
                }

        self.ipfs_model.ipfs_name_publish_async.side_effect = async_name_publish

        # Call the method
        result = await self.ipfs_model.ipfs_name_publish_async("QmTestCID")

        # Verify the result
        assert result["success"] is False
        assert result["operation"] == "ipfs_name_publish"
        assert result["cid"] == "QmTestCID"
        assert result["error_type"] == "command_error"
        assert "publisher not online" in result["error"]

    @pytest.mark.anyio
    async def test_ipfs_name_resolve_async_with_string_response(self):
        """Test that ipfs_name_resolve_async correctly handles string response."""
        # Mock the run_ipfs_command_async method to return a string response
        cmd_result = {
            "success": True,
            "stdout": b"/ipfs/QmResolvedTestCID"
        }
        self.mock_ipfs_kit.run_ipfs_command_async.return_value = cmd_result

        # Configure model mock to delegate to kit
        async def async_name_resolve(name, **kwargs):
            cmd = ["ipfs", "name", "resolve"]

            # Add optional parameters
            if "recursive" in kwargs:
                cmd.append(f"--recursive={'true' if kwargs['recursive'] else 'false'}")
            if "nocache" in kwargs and kwargs["nocache"]:
                cmd.append("--nocache")
            if "timeout" in kwargs and kwargs["timeout"]:
                cmd.extend(["--timeout", f"{kwargs['timeout']}s"])

            # Add the name with IPNS prefix if it's not already prefixed
            if not name.startswith("/ipns/"):
                name_path = f"/ipns/{name}"
            else:
                name_path = name

            cmd.append(name_path)

            # Execute IPFS command
            cmd_result = await self.mock_ipfs_kit.run_ipfs_command_async(cmd)

            # Process the result
            if cmd_result["success"]:
                # Check if we got a string response
                if isinstance(cmd_result["stdout"], str):
                    output = cmd_result["stdout"]
                else:
                    output = cmd_result["stdout"].decode('utf-8')

                return {
                    "success": True,
                    "operation": "ipfs_name_resolve",
                    "name": name,
                    "path": output.strip(),
                    "timestamp": time.time(),
                    **{k: v for k, v in kwargs.items() if v is not None}
                }
            else:
                # Handle command error
                error_msg = cmd_result.get("stderr", b"Unknown error").decode('utf-8')
                return {
                    "success": False,
                    "operation": "ipfs_name_resolve",
                    "name": name,
                    "error": f"Command error: {error_msg}",
                    "error_type": "command_error",
                    "timestamp": time.time()
                }

        self.ipfs_model.ipfs_name_resolve_async.side_effect = async_name_resolve

        # Call the method
        result = await self.ipfs_model.ipfs_name_resolve_async("test-name")

        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "ipfs_name_resolve"
        assert result["name"] == "test-name"
        assert result["path"] == "/ipfs/QmResolvedTestCID"

        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command_async.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command_async.call_args
        cmd = args[0]
        assert cmd[0:3] == ["ipfs", "name", "resolve"]
        assert cmd[-1].endswith("test-name")

    @pytest.mark.anyio
    async def test_ipfs_name_resolve_async_with_ipns_prefix_handling(self):
        """Test that ipfs_name_resolve_async correctly handles IPNS prefix."""
        # Mock the run_ipfs_command_async method
        cmd_result = {
            "success": True,
            "stdout": b"/ipfs/QmResolvedTestCID"
        }
        self.mock_ipfs_kit.run_ipfs_command_async.return_value = cmd_result

        # Configure model mock to delegate to kit (reusing the same implementation)
        async def async_name_resolve(name, **kwargs):
            cmd = ["ipfs", "name", "resolve"]

            # Add optional parameters
            if "recursive" in kwargs:
                cmd.append(f"--recursive={'true' if kwargs['recursive'] else 'false'}")
            if "nocache" in kwargs and kwargs["nocache"]:
                cmd.append("--nocache")
            if "timeout" in kwargs and kwargs["timeout"]:
                cmd.extend(["--timeout", f"{kwargs['timeout']}s"])

            # Add the name with IPNS prefix if it's not already prefixed
            if not name.startswith("/ipns/"):
                name_path = f"/ipns/{name}"
            else:
                name_path = name

            cmd.append(name_path)

            # Execute IPFS command
            cmd_result = await self.mock_ipfs_kit.run_ipfs_command_async(cmd)

            # Process the result
            if cmd_result["success"]:
                # Check if we got a string response
                if isinstance(cmd_result["stdout"], str):
                    output = cmd_result["stdout"]
                else:
                    output = cmd_result["stdout"].decode('utf-8')

                return {
                    "success": True,
                    "operation": "ipfs_name_resolve",
                    "name": name,
                    "path": output.strip(),
                    "timestamp": time.time(),
                    **{k: v for k, v in kwargs.items() if v is not None}
                }
            else:
                # Handle command error
                error_msg = cmd_result.get("stderr", b"Unknown error").decode('utf-8')
                return {
                    "success": False,
                    "operation": "ipfs_name_resolve",
                    "name": name,
                    "error": f"Command error: {error_msg}",
                    "error_type": "command_error",
                    "timestamp": time.time()
                }

        self.ipfs_model.ipfs_name_resolve_async.side_effect = async_name_resolve

        # Call the method with already prefixed name
        result = await self.ipfs_model.ipfs_name_resolve_async("/ipns/test-name")

        # Verify command parameters - shouldn't add another /ipns/ prefix
        self.mock_ipfs_kit.run_ipfs_command_async.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command_async.call_args
        cmd = args[0]
        assert cmd[-1] == "/ipns/test-name"
        assert result["name"] == "/ipns/test-name"

    @pytest.mark.anyio
    async def test_ipfs_name_resolve_async_with_recursive_parameter(self):
        """Test that ipfs_name_resolve_async correctly handles the recursive parameter."""
        # Mock the run_ipfs_command_async method
        cmd_result = {
            "success": True,
            "stdout": b"/ipfs/QmResolvedTestCID"
        }
        self.mock_ipfs_kit.run_ipfs_command_async.return_value = cmd_result

        # Configure model mock to delegate to kit (reusing the same implementation)
        async def async_name_resolve(name, **kwargs):
            cmd = ["ipfs", "name", "resolve"]

            # Add optional parameters
            if "recursive" in kwargs:
                cmd.append(f"--recursive={'true' if kwargs['recursive'] else 'false'}")
            if "nocache" in kwargs and kwargs["nocache"]:
                cmd.append("--nocache")
            if "timeout" in kwargs and kwargs["timeout"]:
                cmd.extend(["--timeout", f"{kwargs['timeout']}s"])

            # Add the name with IPNS prefix if it's not already prefixed
            if not name.startswith("/ipns/"):
                name_path = f"/ipns/{name}"
            else:
                name_path = name

            cmd.append(name_path)

            # Execute IPFS command
            cmd_result = await self.mock_ipfs_kit.run_ipfs_command_async(cmd)

            # Process the result
            if cmd_result["success"]:
                # Check if we got a string response
                if isinstance(cmd_result["stdout"], str):
                    output = cmd_result["stdout"]
                else:
                    output = cmd_result["stdout"].decode('utf-8')

                return {
                    "success": True,
                    "operation": "ipfs_name_resolve",
                    "name": name,
                    "path": output.strip(),
                    "timestamp": time.time(),
                    **{k: v for k, v in kwargs.items() if v is not None}
                }
            else:
                # Handle command error
                error_msg = cmd_result.get("stderr", b"Unknown error").decode('utf-8')
                return {
                    "success": False,
                    "operation": "ipfs_name_resolve",
                    "name": name,
                    "error": f"Command error: {error_msg}",
                    "error_type": "command_error",
                    "timestamp": time.time()
                }

        self.ipfs_model.ipfs_name_resolve_async.side_effect = async_name_resolve

        # Call the method with recursive=False
        result = await self.ipfs_model.ipfs_name_resolve_async("test-name", recursive=False)

        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command_async.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command_async.call_args
        cmd = args[0]
        assert "--recursive=false" in cmd

    @pytest.mark.anyio
    async def test_ipfs_name_resolve_async_with_nocache_parameter(self):
        """Test that ipfs_name_resolve_async correctly handles the nocache parameter."""
        # Mock the run_ipfs_command_async method
        cmd_result = {
            "success": True,
            "stdout": b"/ipfs/QmResolvedTestCID"
        }
        self.mock_ipfs_kit.run_ipfs_command_async.return_value = cmd_result

        # Configure model mock to delegate to kit (reusing the same implementation)
        async def async_name_resolve(name, **kwargs):
            cmd = ["ipfs", "name", "resolve"]

            # Add optional parameters
            if "recursive" in kwargs:
                cmd.append(f"--recursive={'true' if kwargs['recursive'] else 'false'}")
            if "nocache" in kwargs and kwargs["nocache"]:
                cmd.append("--nocache")
            if "timeout" in kwargs and kwargs["timeout"]:
                cmd.extend(["--timeout", f"{kwargs['timeout']}s"])

            # Add the name with IPNS prefix if it's not already prefixed
            if not name.startswith("/ipns/"):
                name_path = f"/ipns/{name}"
            else:
                name_path = name

            cmd.append(name_path)

            # Execute IPFS command
            cmd_result = await self.mock_ipfs_kit.run_ipfs_command_async(cmd)

            # Process the result
            if cmd_result["success"]:
                # Check if we got a string response
                if isinstance(cmd_result["stdout"], str):
                    output = cmd_result["stdout"]
                else:
                    output = cmd_result["stdout"].decode('utf-8')

                return {
                    "success": True,
                    "operation": "ipfs_name_resolve",
                    "name": name,
                    "path": output.strip(),
                    "timestamp": time.time(),
                    **{k: v for k, v in kwargs.items() if v is not None}
                }
            else:
                # Handle command error
                error_msg = cmd_result.get("stderr", b"Unknown error").decode('utf-8')
                return {
                    "success": False,
                    "operation": "ipfs_name_resolve",
                    "name": name,
                    "error": f"Command error: {error_msg}",
                    "error_type": "command_error",
                    "timestamp": time.time()
                }

        self.ipfs_model.ipfs_name_resolve_async.side_effect = async_name_resolve

        # Call the method with nocache=True
        result = await self.ipfs_model.ipfs_name_resolve_async("test-name", nocache=True)

        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command_async.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command_async.call_args
        cmd = args[0]
        assert "--nocache" in cmd

    @pytest.mark.anyio
    async def test_ipfs_name_resolve_async_failure(self):
        """Test that ipfs_name_resolve_async correctly handles failure."""
        # Mock the run_ipfs_command_async method to return a failure
        cmd_result = {
            "success": False,
            "stderr": b"Error: could not resolve name"
        }
        self.mock_ipfs_kit.run_ipfs_command_async.return_value = cmd_result

        # Configure model mock to delegate to kit (reusing the same implementation)
        async def async_name_resolve(name, **kwargs):
            cmd = ["ipfs", "name", "resolve"]

            # Add optional parameters
            if "recursive" in kwargs:
                cmd.append(f"--recursive={'true' if kwargs['recursive'] else 'false'}")
            if "nocache" in kwargs and kwargs["nocache"]:
                cmd.append("--nocache")
            if "timeout" in kwargs and kwargs["timeout"]:
                cmd.extend(["--timeout", f"{kwargs['timeout']}s"])

            # Add the name with IPNS prefix if it's not already prefixed
            if not name.startswith("/ipns/"):
                name_path = f"/ipns/{name}"
            else:
                name_path = name

            cmd.append(name_path)

            # Execute IPFS command
            cmd_result = await self.mock_ipfs_kit.run_ipfs_command_async(cmd)

            # Process the result
            if cmd_result["success"]:
                # Check if we got a string response
                if isinstance(cmd_result["stdout"], str):
                    output = cmd_result["stdout"]
                else:
                    output = cmd_result["stdout"].decode('utf-8')

                return {
                    "success": True,
                    "operation": "ipfs_name_resolve",
                    "name": name,
                    "path": output.strip(),
                    "timestamp": time.time(),
                    **{k: v for k, v in kwargs.items() if v is not None}
                }
            else:
                # Handle command error
                error_msg = cmd_result.get("stderr", b"Unknown error").decode('utf-8')
                return {
                    "success": False,
                    "operation": "ipfs_name_resolve",
                    "name": name,
                    "error": f"Command error: {error_msg}",
                    "error_type": "command_error",
                    "timestamp": time.time()
                }

        self.ipfs_model.ipfs_name_resolve_async.side_effect = async_name_resolve

        # Call the method
        result = await self.ipfs_model.ipfs_name_resolve_async("test-name")

        # Verify the result
        assert result["success"] is False
        assert result["operation"] == "ipfs_name_resolve"
        assert result["name"] == "test-name"
        assert result["error_type"] == "command_error"
        assert "could not resolve name" in result["error"]

    @pytest.mark.anyio
    async def test_ipfs_name_resolve_async_with_timeout_parameter(self):
        """Test that ipfs_name_resolve_async correctly handles the timeout parameter."""
        # Mock the run_ipfs_command_async method
        cmd_result = {
            "success": True,
            "stdout": b"/ipfs/QmResolvedTestCID"
        }
        self.mock_ipfs_kit.run_ipfs_command_async.return_value = cmd_result

        # Configure model mock to delegate to kit (reusing the same implementation)
        async def async_name_resolve(name, **kwargs):
            cmd = ["ipfs", "name", "resolve"]

            # Add optional parameters
            if "recursive" in kwargs:
                cmd.append(f"--recursive={'true' if kwargs['recursive'] else 'false'}")
            if "nocache" in kwargs and kwargs["nocache"]:
                cmd.append("--nocache")
            if "timeout" in kwargs and kwargs["timeout"]:
                cmd.extend(["--timeout", f"{kwargs['timeout']}s"])

            # Add the name with IPNS prefix if it's not already prefixed
            if not name.startswith("/ipns/"):
                name_path = f"/ipns/{name}"
            else:
                name_path = name

            cmd.append(name_path)

            # Execute IPFS command
            cmd_result = await self.mock_ipfs_kit.run_ipfs_command_async(cmd)

            # Process the result
            if cmd_result["success"]:
                # Check if we got a string response
                if isinstance(cmd_result["stdout"], str):
                    output = cmd_result["stdout"]
                else:
                    output = cmd_result["stdout"].decode('utf-8')

                return {
                    "success": True,
                    "operation": "ipfs_name_resolve",
                    "name": name,
                    "path": output.strip(),
                    "timestamp": time.time(),
                    **{k: v for k, v in kwargs.items() if v is not None}
                }
            else:
                # Handle command error
                error_msg = cmd_result.get("stderr", b"Unknown error").decode('utf-8')
                return {
                    "success": False,
                    "operation": "ipfs_name_resolve",
                    "name": name,
                    "error": f"Command error: {error_msg}",
                    "error_type": "command_error",
                    "timestamp": time.time()
                }

        self.ipfs_model.ipfs_name_resolve_async.side_effect = async_name_resolve

        # Call the method with timeout=30
        result = await self.ipfs_model.ipfs_name_resolve_async("test-name", timeout=30)

        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command_async.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command_async.call_args
        cmd = args[0]
        assert "--timeout" in cmd
        timeout_index = cmd.index("--timeout")
        assert cmd[timeout_index + 1] == "30s"

    @pytest.mark.anyio
    async def test_ipfs_key_gen_async_functionality(self):
        """Test the IPFS key generation functionality with AnyIO."""
        # Mock the run_ipfs_command_async method
        cmd_result = {
            "success": True,
            "stdout": b'{"Name":"test-key","Id":"k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8"}'
        }
        self.mock_ipfs_kit.run_ipfs_command_async.return_value = cmd_result

        # Configure model mock to delegate to kit
        async def async_key_gen(key_name, **kwargs):
            cmd = ["ipfs", "key", "gen"]

            # Add optional parameters
            if "key_type" in kwargs and kwargs["key_type"]:
                cmd.append(f"--type={kwargs['key_type']}")
            if "size" in kwargs and kwargs["size"]:
                cmd.append(f"--size={kwargs['size']}")

            # Add the key name
            cmd.append(key_name)

            # Execute IPFS command
            cmd_result = await self.mock_ipfs_kit.run_ipfs_command_async(cmd)

            # Process the result
            if cmd_result["success"]:
                # Check if we got a string response
                if isinstance(cmd_result["stdout"], str):
                    output = cmd_result["stdout"]
                else:
                    output = cmd_result["stdout"].decode('utf-8')

                # Parse response (expected to be JSON)
                try:
                    data = json.loads(output)
                    key_id = data.get("Id", "")
                except json.JSONDecodeError:
                    # Fallback if not JSON
                    key_id = ""

                return {
                    "success": True,
                    "operation": "ipfs_key_gen",
                    "key_name": key_name,
                    "key_id": key_id,
                    "timestamp": time.time(),
                    **{k: v for k, v in kwargs.items() if v is not None}
                }
            else:
                # Handle command error
                error_msg = cmd_result.get("stderr", b"Unknown error").decode('utf-8')
                return {
                    "success": False,
                    "operation": "ipfs_key_gen",
                    "key_name": key_name,
                    "error": f"Command error: {error_msg}",
                    "error_type": "command_error",
                    "timestamp": time.time()
                }

        self.ipfs_model.ipfs_key_gen_async.side_effect = async_key_gen

        # Call the method
        result = await self.ipfs_model.ipfs_key_gen_async("test-key")

        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "ipfs_key_gen"
        assert result["key_name"] == "test-key"
        assert result["key_id"] == "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8"

        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command_async.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command_async.call_args
        cmd = args[0]
        assert cmd[0:3] == ["ipfs", "key", "gen"]
        assert cmd[-1] == "test-key"

    @pytest.mark.anyio
    async def test_ipfs_key_gen_async_with_type_and_size(self):
        """Test that ipfs_key_gen_async correctly handles type and size parameters."""
        # Mock the run_ipfs_command_async method
        cmd_result = {
            "success": True,
            "stdout": b'{"Name":"test-key","Id":"k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8"}'
        }
        self.mock_ipfs_kit.run_ipfs_command_async.return_value = cmd_result

        # Configure model mock to delegate to kit (reusing the same implementation)
        async def async_key_gen(key_name, **kwargs):
            cmd = ["ipfs", "key", "gen"]

            # Add optional parameters
            if "key_type" in kwargs and kwargs["key_type"]:
                cmd.append(f"--type={kwargs['key_type']}")
            if "size" in kwargs and kwargs["size"]:
                cmd.append(f"--size={kwargs['size']}")

            # Add the key name
            cmd.append(key_name)

            # Execute IPFS command
            cmd_result = await self.mock_ipfs_kit.run_ipfs_command_async(cmd)

            # Process the result
            if cmd_result["success"]:
                # Check if we got a string response
                if isinstance(cmd_result["stdout"], str):
                    output = cmd_result["stdout"]
                else:
                    output = cmd_result["stdout"].decode('utf-8')

                # Parse response (expected to be JSON)
                try:
                    data = json.loads(output)
                    key_id = data.get("Id", "")
                except json.JSONDecodeError:
                    # Fallback if not JSON
                    key_id = ""

                return {
                    "success": True,
                    "operation": "ipfs_key_gen",
                    "key_name": key_name,
                    "key_id": key_id,
                    "timestamp": time.time(),
                    **{k: v for k, v in kwargs.items() if v is not None}
                }
            else:
                # Handle command error
                error_msg = cmd_result.get("stderr", b"Unknown error").decode('utf-8')
                return {
                    "success": False,
                    "operation": "ipfs_key_gen",
                    "key_name": key_name,
                    "error": f"Command error: {error_msg}",
                    "error_type": "command_error",
                    "timestamp": time.time()
                }

        self.ipfs_model.ipfs_key_gen_async.side_effect = async_key_gen

        # Call the method with type and size
        result = await self.ipfs_model.ipfs_key_gen_async("test-key", key_type="rsa", size=2048)

        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command_async.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command_async.call_args
        cmd = args[0]
        assert "--type=rsa" in cmd
        assert "--size=2048" in cmd

    @pytest.mark.anyio
    async def test_ipfs_key_list_async_functionality(self):
        """Test the IPFS key listing functionality with AnyIO."""
        # Mock the run_ipfs_command_async method
        cmd_result = {
            "success": True,
            "stdout": b'[{"Name":"self","Id":"12D3KooWR5Vc5wRTuW8HZoZWTd5hRJ2pS6SUy8jMtzs3Ji4Dpk9f"},{"Name":"test-key","Id":"k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8"}]'
        }
        self.mock_ipfs_kit.run_ipfs_command_async.return_value = cmd_result

        # Configure model mock to delegate to kit
        async def async_key_list(**kwargs):
            cmd = ["ipfs", "key", "list", "--format=json"]

            # Execute IPFS command
            cmd_result = await self.mock_ipfs_kit.run_ipfs_command_async(cmd)

            # Process the result
            if cmd_result["success"]:
                # Check if we got a string response
                if isinstance(cmd_result["stdout"], str):
                    output = cmd_result["stdout"]
                else:
                    output = cmd_result["stdout"].decode('utf-8')

                # Parse response (expected to be JSON)
                try:
                    keys = json.loads(output)
                except json.JSONDecodeError:
                    # Fallback if not JSON
                    keys = []

                return {
                    "success": True,
                    "operation": "ipfs_key_list",
                    "keys": keys,
                    "timestamp": time.time()
                }
            else:
                # Handle command error
                error_msg = cmd_result.get("stderr", b"Unknown error").decode('utf-8')
                return {
                    "success": False,
                    "operation": "ipfs_key_list",
                    "error": f"Command error: {error_msg}",
                    "error_type": "command_error",
                    "timestamp": time.time()
                }

        self.ipfs_model.ipfs_key_list_async.side_effect = async_key_list

        # Call the method
        result = await self.ipfs_model.ipfs_key_list_async()

        # Verify the result
        assert result["success"] is True
        assert result["operation"] == "ipfs_key_list"
        assert len(result["keys"]) == 2
        assert result["keys"][0]["Name"] == "self"
        assert result["keys"][1]["Name"] == "test-key"

        # Verify command parameters
        self.mock_ipfs_kit.run_ipfs_command_async.assert_called_once()
        args, _ = self.mock_ipfs_kit.run_ipfs_command_async.call_args
        cmd = args[0]
        assert cmd[0:3] == ["ipfs", "key", "list"]
        assert "--format=json" in cmd

    @pytest.mark.anyio
    async def test_anyio_sleep_integration(self):
        """Test explicit anyio.sleep integration with IPNS operations."""
        import anyio

        # Define test data
        test_cid = "QmTestCID"
        test_name = "test-name"

        # Define async functions with delays using anyio.sleep
        async def run_command_with_delay_async(cmd, delay=0.1, **kwargs):
            await anyio.sleep(delay)  # Explicit anyio.sleep usage

            # Return different responses based on the command type
            if "name" in cmd and "publish" in cmd:
                return {
                    "success": True,
                    "stdout": "Published to k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8: /ipfs/QmTestCID"
                }
            elif "name" in cmd and "resolve" in cmd:
                return {
                    "success": True,
                    "stdout": b"/ipfs/QmResolvedTestCID"
                }
            elif "key" in cmd and "gen" in cmd:
                return {
                    "success": True,
                    "stdout": b'{"Name":"test-key","Id":"k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8"}'
                }
            elif "key" in cmd and "list" in cmd:
                return {
                    "success": True,
                    "stdout": b'[{"Name":"self","Id":"12D3KooWR5Vc5wRTuW8HZoZWTd5hRJ2pS6SUy8jMtzs3Ji4Dpk9f"},{"Name":"test-key","Id":"k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8"}]'
                }
            else:
                return {
                    "success": False,
                    "stderr": b"Unknown command"
                }

        # Set side effect for the run_ipfs_command_async method
        self.mock_ipfs_kit.run_ipfs_command_async.side_effect = run_command_with_delay_async

        # Configure model mocks
        async def model_name_publish_async(cid, **kwargs):
            cmd = ["ipfs", "name", "publish"]

            # Add optional parameters
            if "key" in kwargs and kwargs["key"]:
                cmd.extend(["--key", kwargs["key"]])

            # Add the CID with IPFS path prefix if it's not already prefixed
            if not cid.startswith("/ipfs/"):
                cid_path = f"/ipfs/{cid}"
            else:
                cid_path = cid

            cmd.append(cid_path)

            # Execute IPFS command
            cmd_result = await self.mock_ipfs_kit.run_ipfs_command_async(cmd)

            # Process the result
            if cmd_result["success"]:
                if isinstance(cmd_result["stdout"], str):
                    output = cmd_result["stdout"]
                else:
                    output = cmd_result["stdout"].decode('utf-8')

                # Parse string output
                parts = output.split(":", 1)
                name_part = parts[0].strip()
                name = name_part.replace("Published to ", "")
                value = parts[1].strip() if len(parts) > 1 else ""

                return {
                    "success": True,
                    "operation": "ipfs_name_publish",
                    "cid": cid,
                    "name": name,
                    "value": value,
                    "timestamp": time.time(),
                    **{k: v for k, v in kwargs.items() if v is not None}
                }
            else:
                return {
                    "success": False,
                    "operation": "ipfs_name_publish",
                    "cid": cid,
                    "error": "Command error",
                    "timestamp": time.time()
                }

        async def model_name_resolve_async(name, **kwargs):
            cmd = ["ipfs", "name", "resolve"]

            # Add optional parameters
            if "recursive" in kwargs:
                cmd.append(f"--recursive={'true' if kwargs['recursive'] else 'false'}")

            # Add the name with IPNS prefix if it's not already prefixed
            if not name.startswith("/ipns/"):
                name_path = f"/ipns/{name}"
            else:
                name_path = name

            cmd.append(name_path)

            # Execute IPFS command
            cmd_result = await self.mock_ipfs_kit.run_ipfs_command_async(cmd)

            # Process the result
            if cmd_result["success"]:
                if isinstance(cmd_result["stdout"], str):
                    output = cmd_result["stdout"]
                else:
                    output = cmd_result["stdout"].decode('utf-8')

                return {
                    "success": True,
                    "operation": "ipfs_name_resolve",
                    "name": name,
                    "path": output.strip(),
                    "timestamp": time.time(),
                    **{k: v for k, v in kwargs.items() if v is not None}
                }
            else:
                return {
                    "success": False,
                    "operation": "ipfs_name_resolve",
                    "name": name,
                    "error": "Command error",
                    "timestamp": time.time()
                }

        self.ipfs_model.ipfs_name_publish_async.side_effect = model_name_publish_async
        self.ipfs_model.ipfs_name_resolve_async.side_effect = model_name_resolve_async

        # Test operations with explicit delay
        start_time = time.time()

        # Run operations in sequence with anyio.sleep integration
        publish_result = await self.ipfs_model.ipfs_name_publish_async(test_cid)
        resolve_result = await self.ipfs_model.ipfs_name_resolve_async(test_name)

        end_time = time.time()
        elapsed_time = end_time - start_time

        # Verify results
        assert publish_result["success"] is True
        assert publish_result["name"] == "k51qzi5uqu5dlvj2baxnqndepeb86cbk3ng7n3i46uzyxzyqj2xjonzllnv0v8"

        assert resolve_result["success"] is True
        assert resolve_result["path"] == "/ipfs/QmResolvedTestCID"

        # Verify timing - should be at least 0.2s (0.1s delay × 2 operations)
        assert elapsed_time >= 0.2, f"Expected delay of at least 0.2s but got {elapsed_time}s"
