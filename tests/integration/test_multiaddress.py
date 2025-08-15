import os
import tempfile
import unittest
import sys
from unittest.mock import MagicMock, patch
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


class TestMultiaddressIntegration(unittest.TestCase):
    """
    Test cases for multiaddress handling in ipfs_kit_py.

    These tests verify that multiaddresses are properly parsed, validated,
    and manipulated throughout the codebase.
    """

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create minimal resources and metadata for testing
        self.resources = {}
        self.metadata = {
            "role": "leecher",  # Use leecher role for simplest setup
            "testing": True,  # Mark as testing to avoid real daemon calls
        }

    def tearDown(self):
        """Clean up test fixtures after each test method."""
        pass

    def test_multiaddr_parsing(self):
        """Test that multiaddresses are properly parsed into components."""
        # Import the module under test
        # This would import your actual implementation
        from ipfs_kit_py.ipfs_multiformats import parse_multiaddr

        # Test valid multiaddresses
        test_cases = [
            # Multiaddress string, expected components
            (
                "/ip4/127.0.0.1/tcp/4001",
                [{"protocol": "ip4", "value": "127.0.0.1"}, {"protocol": "tcp", "value": "4001"}],
            ),
            (
                "/ip6/::1/tcp/5001",
                [{"protocol": "ip6", "value": "::1"}, {"protocol": "tcp", "value": "5001"}],
            ),
            (
                "/dns4/example.com/tcp/443/https",
                [
                    {"protocol": "dns4", "value": "example.com"},
                    {"protocol": "tcp", "value": "443"},
                    {"protocol": "https", "value": ""},
                ],
            ),
            (
                "/ip4/192.168.1.1/tcp/4001/p2p/QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N",
                [
                    {"protocol": "ip4", "value": "192.168.1.1"},
                    {"protocol": "tcp", "value": "4001"},
                    {"protocol": "p2p", "value": "QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N"},
                ],
            ),
            (
                "/ip4/127.0.0.1/udp/4001/quic",
                [
                    {"protocol": "ip4", "value": "127.0.0.1"},
                    {"protocol": "udp", "value": "4001"},
                    {"protocol": "quic", "value": ""},
                ],
            ),
            ("/unix/tmp/ipfs.sock", [{"protocol": "unix", "value": "/tmp/ipfs.sock"}]),
        ]

        for addr_str, expected_components in test_cases:
            components = parse_multiaddr(addr_str)

            # Verify components match expected values
            self.assertEqual(len(components), len(expected_components))
            for i, component in enumerate(components):
                self.assertEqual(component["protocol"], expected_components[i]["protocol"])
                self.assertEqual(component["value"], expected_components[i]["value"])

    def test_invalid_multiaddr_parsing(self):
        """Test that invalid multiaddresses are properly rejected."""
        # Import the module under test
        from ipfs_kit_py.ipfs_multiformats import MultiaddrParseError, parse_multiaddr

        # Test invalid multiaddresses
        invalid_addrs = [
            "",  # Empty string
            "ip4/127.0.0.1/tcp/4001",  # Missing leading slash
            "/ip4/localhost/tcp/abc",  # Non-numeric port
            "/ip4/127.0.0.1/icmp",  # Unsupported protocol
            "/ip4/127.0.0.1/tcp",  # Missing value
            "/ip4",  # Incomplete address
            "/ip4/127.0.0.1/p2p",  # Missing peer ID
            "http://example.com",  # Not a multiaddress format
        ]

        for invalid_addr in invalid_addrs:
            with self.assertRaises(MultiaddrParseError):
                parse_multiaddr(invalid_addr)

    def test_multiaddr_string_conversion(self):
        """Test that multiaddress components can be converted back to strings."""
        # Import the module under test
        from ipfs_kit_py.ipfs_multiformats import multiaddr_to_string, parse_multiaddr

        # Test round-trip conversion
        test_addrs = [
            "/ip4/127.0.0.1/tcp/4001",
            "/ip6/::1/tcp/5001",
            "/dns4/example.com/tcp/443/https",
            "/ip4/192.168.1.1/tcp/4001/p2p/QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N",
        ]

        for addr_str in test_addrs:
            components = parse_multiaddr(addr_str)
            reconstructed = multiaddr_to_string(components)
            self.assertEqual(addr_str, reconstructed)

    def test_multiaddr_extraction(self):
        """Test extracting specific protocol values from multiaddresses."""
        # Import the module under test
        from ipfs_kit_py.ipfs_multiformats import get_protocol_value, parse_multiaddr

        # Test extracting values for specific protocols
        addr = "/ip4/192.168.1.1/tcp/4001/p2p/QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N"
        components = parse_multiaddr(addr)

        self.assertEqual(get_protocol_value(components, "ip4"), "192.168.1.1")
        self.assertEqual(get_protocol_value(components, "tcp"), "4001")
        self.assertEqual(
            get_protocol_value(components, "p2p"), "QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N"
        )
        self.assertIsNone(get_protocol_value(components, "udp"))  # Not present

    def test_multiaddr_manipulation(self):
        """Test adding, replacing, or removing protocols from multiaddresses."""
        # Import the module under test
        from ipfs_kit_py.ipfs_multiformats import (
            add_protocol,
            multiaddr_to_string,
            parse_multiaddr,
            remove_protocol,
            replace_protocol,
        )

        # Test adding a protocol
        addr = "/ip4/127.0.0.1/tcp/4001"
        components = parse_multiaddr(addr)

        # Add p2p protocol
        new_components = add_protocol(
            components, "p2p", "QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N"
        )
        new_addr = multiaddr_to_string(new_components)
        self.assertEqual(
            new_addr, "/ip4/127.0.0.1/tcp/4001/p2p/QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N"
        )

        # Test replacing a protocol
        components = parse_multiaddr(addr)
        new_components = replace_protocol(components, "tcp", "8080")
        new_addr = multiaddr_to_string(new_components)
        self.assertEqual(new_addr, "/ip4/127.0.0.1/tcp/8080")

        # Test removing a protocol
        components = parse_multiaddr(
            "/ip4/127.0.0.1/tcp/4001/p2p/QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N"
        )
        new_components = remove_protocol(components, "p2p")
        new_addr = multiaddr_to_string(new_components)
        self.assertEqual(new_addr, "/ip4/127.0.0.1/tcp/4001")

    def test_multiaddr_validation(self):
        """Test validating multiaddresses for specific contexts."""
        # Import the module under test
        from ipfs_kit_py.ipfs_multiformats import MultiaddrValidationError, is_valid_multiaddr

        # Test valid multiaddresses for different contexts
        valid_peer_addrs = [
            "/ip4/127.0.0.1/tcp/4001/p2p/QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N",
            "/ip6/::1/tcp/4001/p2p/QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N",
            "/dns4/example.com/tcp/4001/p2p/QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N",
        ]

        for addr in valid_peer_addrs:
            self.assertTrue(is_valid_multiaddr(addr, context="peer"))

        # Test invalid addresses for peer context (missing p2p part)
        invalid_peer_addrs = [
            "/ip4/127.0.0.1/tcp/4001",  # Missing peer ID
            "/ip6/::1/udp/4001/quic",  # Missing peer ID
        ]

        for addr in invalid_peer_addrs:
            with self.assertRaises(MultiaddrValidationError):
                is_valid_multiaddr(addr, context="peer")

        # Test valid multiaddresses for listen context
        valid_listen_addrs = [
            "/ip4/0.0.0.0/tcp/4001",
            "/ip6/::/tcp/4001",
            "/ip4/127.0.0.1/udp/4001/quic",
            "/unix/tmp/ipfs.sock",
        ]

        for addr in valid_listen_addrs:
            self.assertTrue(is_valid_multiaddr(addr, context="listen"))

        # Test invalid addresses for listen context
        invalid_listen_addrs = [
            "/p2p/QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N",  # Missing transport
            "/onion3/vww6ybal4bd7szmgncyruucpgfkqahzddi37ktceo3ah7ngmcopnpyyd:1234",  # Requires special handling
        ]

        for addr in invalid_listen_addrs:
            with self.assertRaises(MultiaddrValidationError):
                is_valid_multiaddr(addr, context="listen")

    @patch("subprocess.run")
    def test_connect_with_multiaddr(self, mock_run):
        """Test connecting to a peer using a multiaddress."""
        # Import the module under test
        from ipfs_kit_py.ipfs import ipfs_py

        # Mock successful subprocess result
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = b'{"Strings": ["connection established"]}'
        mock_run.return_value = mock_process

        # Create the IPFS object under test
        ipfs = ipfs_py(self.resources, self.metadata)

        # Test connection with valid peer multiaddress
        valid_addr = "/ip4/192.168.1.1/tcp/4001/p2p/QmYyQSo1c1Ym7orWxLYvCrM2EmxFTANf8wXmmE7DWjhx5N"
        result = ipfs.ipfs_swarm_connect(valid_addr)

        # Verify the connection was successful
        self.assertTrue(result["success"])

        # Verify subprocess was called with correct arguments
        args, kwargs = mock_run.call_args
        self.assertIn("swarm", args[0])
        self.assertIn("connect", args[0])
        self.assertIn(valid_addr, args[0])

    @patch("subprocess.run")
    def test_listen_addrs_with_multiaddr(self, mock_run):
        """Test configuring listen addresses using multiaddresses."""
        # Import the module under test
        from ipfs_kit_py.ipfs import ipfs_py

        # Mock successful subprocess result
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = (
            b'{"Key": "Addresses.Swarm", "Value": ["/ip4/0.0.0.0/tcp/4001", "/ip6/::/tcp/4001"]}'
        )
        mock_run.return_value = mock_process

        # Create the IPFS object under test
        ipfs = ipfs_py(self.resources, self.metadata)

        # Test setting listen addresses
        listen_addrs = ["/ip4/0.0.0.0/tcp/4001", "/ip6/::/tcp/4001", "/ip4/0.0.0.0/udp/4001/quic"]

        result = ipfs.ipfs_set_listen_addrs(listen_addrs)

        # Verify the operation was successful
        self.assertTrue(result["success"])

        # Verify subprocess was called with correct arguments
        args, kwargs = mock_run.call_args
        self.assertIn("config", args[0])
        self.assertIn("Addresses.Swarm", args[0])
        # Check that the JSON-encoded listen addresses were passed
        self.assertIn('"' + listen_addrs[0] + '"', " ".join(args[0]))


# Mock classes for testing
class MultiaddrParseError(Exception):
    """Raised when a multiaddress cannot be parsed."""

    pass


class MultiaddrValidationError(Exception):
    """Raised when a multiaddress is invalid for a specific context."""

    pass


if __name__ == "__main__":
    unittest.main()
