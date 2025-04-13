#!/usr/bin/env python3
"""Test WebRTC benchmarking capabilities."""

import unittest
import anyio
import os
import json
import tempfile
import time
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

try:
    from ipfs_kit_py.webrtc_benchmark import (
        WebRTCBenchmark, 
        WebRTCFrameStat,
        WebRTCStreamingManagerBenchmarkIntegration,
        create_frame_stat
    )
    from ipfs_kit_py.webrtc_streaming import RTCPeerConnection, WebRTCStreamingManager, WebRTCConfig
    _can_test_webrtc = True
except ImportError:
    _can_test_webrtc = False

# Force WebRTC testing to be available
_can_test_webrtc = True
# 
# 
# @pytest.mark.skipif(...) - removed by fix_all_tests.py
class TestWebRTCBenchmark(unittest.TestCase):
    """Test WebRTC benchmarking functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temp directory for benchmark reports
        self.report_dir = tempfile.mkdtemp()
        
        # Create test benchmark instance
        self.benchmark = WebRTCBenchmark(
            connection_id="test-connection",
            cid="QmTestCID",
            enable_frame_stats=True,
            report_dir=self.report_dir
        )
    
    def tearDown(self):
        """Clean up test environment."""
        # Clean up temp directory
        import shutil
        shutil.rmtree(self.report_dir, ignore_errors=True)
    
    def test_benchmark_initialization(self):
        """Test benchmark initialization and configuration."""
        # Verify benchmark instance was created
        self.assertEqual(self.benchmark.connection_id, "test-connection")
        self.assertEqual(self.benchmark.cid, "QmTestCID")
        self.assertTrue(self.benchmark.enable_frame_stats)
        self.assertEqual(self.benchmark.report_dir, self.report_dir)
        
        # Verify metrics structure
        self.assertIsNone(self.benchmark.connection_metrics["ice_gathering_time_ms"])
        self.assertIsNone(self.benchmark.connection_metrics["ice_connection_time_ms"])
        self.assertEqual(self.benchmark.connection_metrics["reconnection_count"], 0)
        
        # Verify time series initialized
        self.assertEqual(len(self.benchmark.time_series["timestamps"]), 0)
        self.assertEqual(len(self.benchmark.time_series["rtt_ms"]), 0)
        
        # Verify frame stats initialized
        self.assertEqual(len(self.benchmark.frame_stats), 0)
        self.assertEqual(self.benchmark.frame_count, 0)
        self.assertEqual(self.benchmark.keyframe_count, 0)
    
    def test_record_connection_event(self):
        """Test recording connection lifecycle events."""
        # Record ICE gathering events
        ice_start_time = time.time()
        self.benchmark._ice_gathering_start = ice_start_time
        
        # Wait a bit
        time.sleep(0.01)
        
        # Record completion
        self.benchmark.record_connection_event("ice_gathering_complete", {})
        
        # Verify timing was recorded
        self.assertIsNotNone(self.benchmark.connection_metrics["ice_gathering_time_ms"])
        self.assertGreater(self.benchmark.connection_metrics["ice_gathering_time_ms"], 0)
        
        # Record ICE connection events
        ice_conn_time = time.time()
        self.benchmark._ice_connection_start = ice_conn_time
        
        # Wait a bit
        time.sleep(0.01)
        
        # Record completion
        self.benchmark.record_connection_event("ice_connected", {})
        
        # Verify timing was recorded
        self.assertIsNotNone(self.benchmark.connection_metrics["ice_connection_time_ms"])
        self.assertGreater(self.benchmark.connection_metrics["ice_connection_time_ms"], 0)
        
        # Record first frame
        self.benchmark.record_connection_event("first_frame", {})
        self.assertIsNotNone(self.benchmark.connection_metrics["first_frame_time_ms"])
        
        # Record reconnection
        self.benchmark.record_connection_event("reconnection", {"duration_ms": 500})
        self.assertEqual(self.benchmark.connection_metrics["reconnection_count"], 1)
        self.assertEqual(len(self.benchmark.connection_metrics["reconnection_times_ms"]), 1)
        self.assertEqual(self.benchmark.connection_metrics["reconnection_times_ms"][0], 500)
        
        # Record ICE candidate
        self.benchmark.record_connection_event("ice_candidate", {"candidate_type": "host"})
        self.assertEqual(self.benchmark.connection_metrics["ice_candidate_counts"]["host"], 1)
        
        # Record codec information
        self.benchmark.record_connection_event("codec_selected", {
            "kind": "video",
            "codec": "VP8",
            "parameters": {"width": 640, "height": 480}
        })
        self.assertEqual(self.benchmark.video_codec, "VP8")
        self.assertEqual(self.benchmark.video_parameters, {"width": 640, "height": 480})
    
    def test_update_stats(self):
        """Test updating benchmark with WebRTC stats."""
        # No stats initially
        self.assertEqual(len(self.benchmark.time_series["rtt_ms"]), 0)
        
        # Update with sample stats
        self.benchmark.update_stats({
            "rtt": 100,
            "jitter": 20,
            "packet_loss": 0.5,
            "bitrate": 1000000,  # 1Mbps
            "bandwidth_estimate": 2000000,  # 2Mbps
            "frames_per_second": 30,
            "resolution_width": 640,
            "resolution_height": 480,
            "cpu_percent": 20,
            "bytes_sent_delta": 10000,
            "bytes_received_delta": 9000,
            "packets_sent_delta": 100,
            "packets_received_delta": 98,
            "packets_lost_delta": 2
        })
        
        # Verify stats were recorded
        self.assertEqual(len(self.benchmark.time_series["timestamps"]), 1)
        self.assertEqual(len(self.benchmark.time_series["rtt_ms"]), 1)
        self.assertEqual(self.benchmark.time_series["rtt_ms"][0], 100)
        self.assertEqual(self.benchmark.time_series["jitter_ms"][0], 20)
        self.assertEqual(self.benchmark.time_series["packet_loss_percent"][0], 0.5)
        self.assertEqual(self.benchmark.time_series["bitrate_kbps"][0], 1000)  # Converted to kbps
        self.assertEqual(self.benchmark.time_series["frames_per_second"][0], 30)
        
        # Verify cumulative stats
        self.assertEqual(self.benchmark.bytes_sent, 10000)
        self.assertEqual(self.benchmark.bytes_received, 9000)
        self.assertEqual(self.benchmark.packets_sent, 100)
        self.assertEqual(self.benchmark.packets_received, 98)
        self.assertEqual(self.benchmark.packets_lost, 2)
        
        # Verify quality score was calculated
        self.assertGreater(self.benchmark.time_series["quality_score"][0], 0)
    
    def test_add_frame_stat(self):
        """Test adding frame statistics."""
        # Create a frame stat
        frame_stat = WebRTCFrameStat(
            size_bytes=1000,
            codec="VP8",
            is_keyframe=True,
            encode_start_time=time.time() - 0.1,
            encode_end_time=time.time()
        )
        
        # Add to benchmark
        self.benchmark.add_frame_stat(frame_stat)
        
        # Verify frame was added
        self.assertEqual(len(self.benchmark.frame_stats), 1)
        self.assertEqual(self.benchmark.frame_count, 1)
        self.assertEqual(self.benchmark.keyframe_count, 1)
        
        # Add more frames to test limit
        for i in range(self.benchmark.max_frame_stats + 10):
            self.benchmark.add_frame_stat(WebRTCFrameStat(size_bytes=1000))
            
        # Verify older frames were removed
        self.assertEqual(len(self.benchmark.frame_stats), self.benchmark.max_frame_stats)
        
        # Verify frame count is correct
        self.assertEqual(self.benchmark.frame_count, self.benchmark.max_frame_stats + 11)
    
    def test_get_summary_stats(self):
        """Test getting summary statistics."""
        # Add some sample data
        self.benchmark.update_stats({
            "rtt": 100,
            "jitter": 20,
            "packet_loss": 0.5,
            "bitrate": 1000000,
            "bandwidth_estimate": 2000000,
            "frames_per_second": 30,
            "resolution_width": 640,
            "resolution_height": 480,
            "cpu_percent": 20,
            "bytes_sent_delta": 10000,
            "bytes_received_delta": 9000,
            "packets_sent_delta": 100,
            "packets_received_delta": 98,
            "packets_lost_delta": 2
        })
        
        # Record some frame stats
        for i in range(10):
            frame_stat = WebRTCFrameStat(
                size_bytes=1000,
                codec="VP8",
                is_keyframe=(i == 0),
                encode_start_time=time.time() - 0.1,
                encode_end_time=time.time()
            )
            self.benchmark.add_frame_stat(frame_stat)
        
        # Get summary
        summary = self.benchmark.get_summary_stats()
        
        # Verify summary contains expected fields
        self.assertEqual(summary["connection_id"], "test-connection")
        self.assertEqual(summary["cid"], "QmTestCID")
        self.assertEqual(summary["avg_rtt_ms"], 100)
        self.assertEqual(summary["avg_jitter_ms"], 20)
        self.assertEqual(summary["avg_packet_loss_percent"], 0.5)
        self.assertEqual(summary["total_frames"], 10)
        self.assertEqual(summary["keyframe_ratio"], 0.1)  # 1 out of 10
        self.assertEqual(summary["video_codec"], "")  # Not set in this test
    
    @pytest.mark.asyncio
    async def test_generate_report(self):
        """Test generating benchmark report."""
        # Add some sample data
        self.benchmark.update_stats({
            "rtt": 100,
            "jitter": 20,
            "packet_loss": 0.5,
            "bitrate": 1000000,
            "bandwidth_estimate": 2000000,
            "frames_per_second": 30,
            "resolution_width": 640,
            "resolution_height": 480,
            "cpu_percent": 20,
            "bytes_sent_delta": 10000,
            "bytes_received_delta": 9000,
            "packets_sent_delta": 100,
            "packets_received_delta": 98,
            "packets_lost_delta": 2
        })
        
        # Generate report
        report_file = await self.benchmark.generate_report()
        
        # Verify report file exists
        self.assertTrue(os.path.exists(report_file))
        
        # Load and verify report content
        with open(report_file, 'r') as f:
            report = json.load(f)
            
        # Check report structure
        self.assertIn("summary", report)
        self.assertIn("time_series", report)
        self.assertIn("events", report)
        self.assertIn("config", report)
        
        # Check summary content
        self.assertEqual(report["summary"]["connection_id"], "test-connection")
        self.assertEqual(report["summary"]["cid"], "QmTestCID")
        
        # Check time series content
        self.assertIn("rtt_ms", report["time_series"])
        self.assertEqual(len(report["time_series"]["rtt_ms"]), 1)
        self.assertEqual(report["time_series"]["rtt_ms"][0], 100)
    
    @pytest.mark.asyncio
    async def test_compare_benchmarks(self):
        """Test comparing benchmark reports."""
        # Create two reports with different values
        report1 = {
            "summary": {
                "connection_id": "test1",
                "cid": "QmTest1",
                "avg_rtt_ms": 100,
                "avg_jitter_ms": 20,
                "avg_bitrate_kbps": 1000
            }
        }
        
        report2 = {
            "summary": {
                "connection_id": "test2",
                "cid": "QmTest2",
                "avg_rtt_ms": 120,  # Worse
                "avg_jitter_ms": 15,  # Better
                "avg_bitrate_kbps": 800  # Worse
            }
        }
        
        # Write reports to files
        report1_path = os.path.join(self.report_dir, "report1.json")
        report2_path = os.path.join(self.report_dir, "report2.json")
        
        with open(report1_path, 'w') as f:
            json.dump(report1, f)
            
        with open(report2_path, 'w') as f:
            json.dump(report2, f)
            
        # Compare the reports
        comparison = await WebRTCBenchmark.compare_benchmarks(report1_path, report2_path)
        
        # Verify comparison results
        self.assertIn("comparison", comparison)
        self.assertIn("regressions", comparison)
        self.assertIn("improvements", comparison)
        
        # Check specific comparisons
        self.assertIn("avg_rtt_ms", comparison["comparison"])
        self.assertEqual(comparison["comparison"]["avg_rtt_ms"]["baseline"], 100)
        self.assertEqual(comparison["comparison"]["avg_rtt_ms"]["current"], 120)
        self.assertTrue(comparison["comparison"]["avg_rtt_ms"]["regression"])
        
        self.assertIn("avg_jitter_ms", comparison["comparison"])
        self.assertEqual(comparison["comparison"]["avg_jitter_ms"]["baseline"], 20)
        self.assertEqual(comparison["comparison"]["avg_jitter_ms"]["current"], 15)
        self.assertFalse(comparison["comparison"]["avg_jitter_ms"]["regression"])
        
        self.assertIn("avg_bitrate_kbps", comparison["comparison"])
        self.assertEqual(comparison["comparison"]["avg_bitrate_kbps"]["baseline"], 1000)
        self.assertEqual(comparison["comparison"]["avg_bitrate_kbps"]["current"], 800)
        self.assertTrue(comparison["comparison"]["avg_bitrate_kbps"]["regression"])
        
        # Verify regressions and improvements
        self.assertEqual(len(comparison["regressions"]), 2)
        self.assertIn("avg_rtt_ms", comparison["regressions"])
        self.assertIn("avg_bitrate_kbps", comparison["regressions"])
        
        self.assertEqual(len(comparison["improvements"]), 1)
        self.assertIn("avg_jitter_ms", comparison["improvements"])
    
    @pytest.mark.asyncio
    async def test_benchmark_monitoring(self):
        """Test the benchmark monitoring task."""
        # Override the collect metrics method for testing
        self.benchmark._collect_periodic_metrics = AsyncMock()
        
        # Start monitoring
        await self.benchmark.start_monitoring()
        
        # Wait a bit for the task to run
        await anyio.sleep(0.2)
        
        # Verify the task was started
        self.assertIsNotNone(self.benchmark._task)
        
        # Verify collect_metrics was called
        self.benchmark._collect_periodic_metrics.assert_called()
        
        # Stop monitoring
        await self.benchmark.stop()
        
        # Verify the task was cancelled
        self.assertIsNone(self.benchmark._task)
# 
# 
# @pytest.mark.skipif(...) - removed by fix_all_tests.py
class TestWebRTCStreamingManagerIntegration(unittest.TestCase):
    """Test integrating benchmarking with WebRTCStreamingManager."""
    
    @pytest.mark.asyncio
    async def test_add_benchmarking_to_manager(self):
        """Test adding benchmarking to WebRTCStreamingManager."""
        # Create mock API
        mock_api = MagicMock()
        
        # Create a WebRTCStreamingManager with a mock API
        with patch('ipfs_kit_py.webrtc_streaming.RTCPeerConnection'):
            manager = WebRTCStreamingManager(mock_api)
            
            # Add benchmarking capabilities
            WebRTCStreamingManagerBenchmarkIntegration.add_benchmarking_to_manager(
                manager,
                enable_benchmarking=True,
                benchmark_reports_dir=tempfile.mkdtemp()
            )
            
            # Verify manager has benchmarking attributes
            self.assertTrue(hasattr(manager, 'enable_benchmarking'))
            self.assertTrue(hasattr(manager, 'benchmark_reports_dir'))
            self.assertTrue(hasattr(manager, 'benchmarks'))
            
            # Verify manager has benchmarking methods
            self.assertTrue(hasattr(manager, 'start_benchmark'))
            self.assertTrue(hasattr(manager, 'stop_benchmark'))
            self.assertTrue(hasattr(manager, 'get_benchmark_stats'))
            self.assertTrue(hasattr(manager, 'generate_benchmark_report'))
            self.assertTrue(hasattr(manager, 'record_frame_stat'))
            
            # Clean up
            import shutil
            shutil.rmtree(manager.benchmark_reports_dir, ignore_errors=True)
# 
# 
# @pytest.mark.skipif(...) - removed by fix_all_tests.py
class TestFrameStats(unittest.TestCase):
    """Test WebRTC frame statistics functionality."""
    
    def test_frame_stat_creation(self):
        """Test creating and using frame stat objects."""
        # Test base initialization
        frame = WebRTCFrameStat()
        self.assertIsNotNone(frame.timestamp)
        self.assertIsNotNone(frame.frame_id)
        self.assertEqual(frame.size_bytes, 0)
        self.assertEqual(frame.codec, "")
        
        # Test initialization with parameters
        frame = WebRTCFrameStat(
            size_bytes=1000,
            codec="VP8",
            is_keyframe=True
        )
        self.assertEqual(frame.size_bytes, 1000)
        self.assertEqual(frame.codec, "VP8")
        self.assertTrue(frame.is_keyframe)
        
        # Test derived properties with no timing
        self.assertIsNone(frame.encode_time_ms)
        self.assertIsNone(frame.transfer_time_ms)
        self.assertIsNone(frame.decode_time_ms)
        self.assertIsNone(frame.total_latency_ms)
        
        # Test with timing information
        now = time.time()
        frame.encode_start_time = now - 0.1
        frame.encode_end_time = now - 0.09
        frame.send_start_time = now - 0.08
        frame.send_end_time = now - 0.07
        frame.receive_time = now - 0.04
        frame.decode_start_time = now - 0.03
        frame.decode_end_time = now - 0.02
        frame.render_time = now
        
        # Verify timing calculations
        self.assertIsNotNone(frame.encode_time_ms)
        self.assertIsNotNone(frame.transfer_time_ms)
        self.assertIsNotNone(frame.decode_time_ms)
        self.assertIsNotNone(frame.total_latency_ms)
        
        # Check specific timing values
        self.assertAlmostEqual(frame.encode_time_ms, 10, delta=1)  # ~10ms encode time
        self.assertAlmostEqual(frame.transfer_time_ms, 40, delta=1)  # ~40ms transfer time
        self.assertAlmostEqual(frame.decode_time_ms, 10, delta=1)  # ~10ms decode time
        self.assertAlmostEqual(frame.total_latency_ms, 100, delta=1)  # ~100ms total latency
    
    def test_create_frame_stat_helper(self):
        """Test the create_frame_stat helper function."""
        # Test with minimal parameters
        frame = create_frame_stat()
        self.assertEqual(frame.size_bytes, 0)
        self.assertEqual(frame.codec, "")
        self.assertFalse(frame.is_keyframe)
        
        # Test with all parameters
        now = time.time()
        frame = create_frame_stat(
            size_bytes=2000,
            codec="H264",
            is_keyframe=True,
            encode_start_time=now - 0.1,
            encode_end_time=now
        )
        self.assertEqual(frame.size_bytes, 2000)
        self.assertEqual(frame.codec, "H264")
        self.assertTrue(frame.is_keyframe)
        self.assertEqual(frame.encode_start_time, now - 0.1)
        self.assertEqual(frame.encode_end_time, now)


if __name__ == "__main__":
    unittest.main()