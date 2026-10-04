#!/usr/bin/env node
/**
 * MCP WebRTC Node.js Client
 * 
 * This script implements a WebRTC client for the IPFS Kit MCP server using Node.js.
 * It establishes a WebRTC connection to the server, receives media streams, and
 * provides performance metrics. This is useful for automated testing in CI pipelines
 * or for headless environments.
 * 
 * Features:
 * - WebSocket-based signaling with the MCP server
 * - Complete WebRTC session establishment
 * - Media stream handling
 * - Statistics collection and reporting
 * 
 * Requirements:
 * - wrtc: Node.js WebRTC implementation
 * - ws: WebSocket client
 * - node-fetch: Fetch API for Node.js
 * 
 * Installation:
 *   npm install wrtc ws node-fetch commander
 * 
 * Usage:
 *   node node_webrtc_client.js --server-url http://localhost:9999/mcp --cid QmExample...
 */

const { RTCPeerConnection, nonstandard } = require('wrtc');
const WebSocket = require('ws');
const fetch = require('node-fetch');
const fs = require('fs');
const path = require('path');
const { program } = require('commander');

// Configure command line arguments
program
  .requiredOption('--server-url <url>', 'MCP server URL (e.g., http://localhost:9999/mcp)')
  .requiredOption('--cid <cid>', 'Content ID to stream')
  .option('--websocket-url <url>', 'WebSocket URL for signaling (derived from server-url if not specified)')
  .option('--quality <quality>', 'Streaming quality', 'medium')
  .option('--duration <seconds>', 'Streaming duration in seconds (0 for unlimited)', parseInt, 30)
  .option('--stats-output <path>', 'Path to save statistics report as JSON')
  .option('--save-video <path>', 'Path to save video (experimental)')
  .option('--verbose', 'Enable verbose logging')
  .parse(process.argv);

const options = program.opts();

// Configure logging
const log = {
  info: (msg) => console.log(`[INFO] ${msg}`),
  warn: (msg) => console.log(`[WARN] ${msg}`),
  error: (msg) => console.log(`[ERROR] ${msg}`),
  debug: (msg) => options.verbose && console.log(`[DEBUG] ${msg}`)
};

// Derive WebSocket URL from server URL if not specified
let websocketUrl = options.websocketUrl;
if (!websocketUrl) {
  const serverUrl = new URL(options.serverUrl);
  const wsProtocol = serverUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  websocketUrl = `${wsProtocol}//${serverUrl.host}${serverUrl.pathname}/webrtc/ws`;
}

// ICE servers for NAT traversal
const iceServers = [
  {
    urls: ['stun:stun.l.google.com:19302', 'stun:stun1.l.google.com:19302']
  }
];

// Statistics storage
const stats = {
  startTime: null,
  connectedTime: null,
  firstFrameTime: null,
  connectionAttempts: 0,
  connectionSuccesses: 0,
  connectionFailures: 0,
  framesReceived: 0,
  framesDropped: 0,
  bytesReceived: 0,
  qualityChanges: [],
  iceStateChanges: [],
  connectionStateChanges: [],
  latestStats: {},
  resolution: null,
  quality: options.quality
};

// Client state
let websocket = null;
let peerConnection = null;
let pcId = null;
let sessionId = generateSessionId();
let interrupted = false;
let statsInterval = null;

// Start connection and streaming
async function main() {
  log.info(`Starting WebRTC client for CID: ${options.cid}`);
  log.info(`Server URL: ${options.serverUrl}`);
  log.info(`WebSocket URL: ${websocketUrl}`);
  log.info(`Quality: ${options.quality}`);
  log.info(`Duration: ${options.duration} seconds`);
  
  stats.startTime = Date.now();
  
  try {
    // Connect to signaling server
    log.info('Connecting to signaling server...');
    websocket = new WebSocket(websocketUrl);
    
    // Set up WebSocket event handlers
    websocket.on('open', () => {
      log.info('WebSocket connection established');
      // Wait a moment for the server to be ready
      setTimeout(() => startSignaling(), 500);
    });
    
    websocket.on('message', handleSignalingMessage);
    
    websocket.on('error', (error) => {
      log.error(`WebSocket error: ${error.message}`);
      cleanup();
    });
    
    websocket.on('close', () => {
      log.info('WebSocket connection closed');
      cleanup();
    });
    
    // Set up timeout if duration is specified
    if (options.duration > 0) {
      log.info(`Will run for ${options.duration} seconds`);
      setTimeout(() => {
        log.info('Duration reached, disconnecting...');
        cleanup();
      }, options.duration * 1000);
    }
    
    // Handle interruption
    process.on('SIGINT', () => {
      log.info('Interrupted by user, disconnecting...');
      cleanup();
    });
    
  } catch (error) {
    log.error(`Error starting client: ${error.message}`);
    cleanup();
  }
}

// Start the signaling process
function startSignaling() {
  try {
    stats.connectionAttempts++;
    
    // Create peer connection
    log.info('Creating RTCPeerConnection');
    peerConnection = new RTCPeerConnection({ iceServers });
    
    // Set up event handlers
    setupPeerConnectionEvents();
    
    // Send offer request
    log.info(`Requesting stream for CID: ${options.cid}`);
    sendSignalingMessage({
      type: 'offer_request',
      cid: options.cid,
      kind: 'video',
      frameRate: 30,
      quality: options.quality,
      session_id: sessionId
    });
    
    // Start collecting stats
    statsInterval = setInterval(collectStats, 1000);
    
  } catch (error) {
    log.error(`Error in signaling: ${error.message}`);
    stats.connectionFailures++;
    cleanup();
  }
}

// Set up peer connection event handlers
function setupPeerConnectionEvents() {
  // Handle ICE candidate generation
  peerConnection.onicecandidate = ({ candidate }) => {
    if (candidate) {
      log.debug(`Generated ICE candidate: ${candidate.candidate.substr(0, 30)}...`);
      // In a real implementation, we would send this to the remote peer
      // Here, the server doesn't expect ICE candidates from us
    }
  };
  
  // Handle ICE connection state changes
  peerConnection.oniceconnectionstatechange = () => {
    const state = peerConnection.iceConnectionState;
    log.info(`ICE connection state changed to: ${state}`);
    
    stats.iceStateChanges.push({
      state,
      time: (Date.now() - stats.startTime) / 1000
    });
  };
  
  // Handle connection state changes
  peerConnection.onconnectionstatechange = () => {
    const state = peerConnection.connectionState;
    log.info(`Connection state changed to: ${state}`);
    
    stats.connectionStateChanges.push({
      state,
      time: (Date.now() - stats.startTime) / 1000
    });
    
    if (state === 'connected') {
      stats.connectedTime = Date.now();
      stats.connectionSuccesses++;
      log.info(`Connection established in ${stats.connectedTime - stats.startTime}ms`);
    } else if (state === 'failed' || state === 'closed') {
      if (!interrupted) {
        log.error(`Connection ${state}`);
        if (state === 'failed') {
          stats.connectionFailures++;
        }
      }
    }
  };
  
  // Handle incoming tracks
  peerConnection.ontrack = (event) => {
    const track = event.track;
    log.info(`Received ${track.kind} track`);
    
    // For video tracks
    if (track.kind === 'video') {
      // We can't display video in Node.js, but we can collect stats
      
      // Set up a listener for frames (non-standard in wrtc)
      if (nonstandard && nonstandard.RTCVideoSink) {
        const sink = new nonstandard.RTCVideoSink(track);
        
        sink.onframe = ({ frame }) => {
          // Record first frame time
          if (!stats.firstFrameTime) {
            stats.firstFrameTime = Date.now();
            log.info(`First frame received after ${stats.firstFrameTime - stats.startTime}ms`);
          }
          
          stats.framesReceived++;
          stats.resolution = `${frame.width}x${frame.height}`;
          
          // Rough estimate of frame size
          const frameSize = (frame.width * frame.height * 12) / 8; // YUV420 format
          stats.bytesReceived += frameSize;
          
          // Log progress periodically
          if (stats.framesReceived % 30 === 0) {
            log.info(`Received ${stats.framesReceived} frames, ` + 
                     `Resolution: ${stats.resolution}, ` +
                     `Quality: ${stats.quality}`);
          }
        };
      }
    }
  };
}

// Handle incoming signaling messages
function handleSignalingMessage(message) {
  try {
    const data = JSON.parse(message);
    const msgType = data.type;
    
    if (options.verbose) {
      log.debug(`Received ${msgType} message`);
    }
    
    if (msgType === 'welcome') {
      log.info(`Server says: ${data.message || 'Welcome'}`);
    } else if (msgType === 'offer') {
      handleOffer(data);
    } else if (msgType === 'candidate') {
      handleCandidate(data);
    } else if (msgType === 'connected') {
      log.info('Server confirmed WebRTC connection established');
    } else if (msgType === 'notification' && 
               data.notification_type === 'webrtc_quality_changed') {
      handleQualityChange(data);
    } else if (msgType === 'closed') {
      log.info('Connection closed by server');
      cleanup();
    } else if (msgType === 'error') {
      log.error(`Server error: ${data.message || 'Unknown error'}`);
    } else {
      log.debug(`Unhandled message type: ${msgType}`);
    }
  } catch (error) {
    log.error(`Error handling message: ${error.message}`);
  }
}

// Handle offer from server
async function handleOffer(data) {
  try {
    pcId = data.pc_id;
    log.info(`Received offer with PC ID: ${pcId}`);
    
    // Set remote description (the offer)
    await peerConnection.setRemoteDescription({
      type: data.sdpType,
      sdp: data.sdp
    });
    
    // Create answer
    log.info('Creating answer');
    const answer = await peerConnection.createAnswer();
    
    // Set local description (our answer)
    log.info('Setting local description');
    await peerConnection.setLocalDescription(answer);
    
    // Send answer to server
    log.info('Sending answer to server');
    sendSignalingMessage({
      type: 'answer',
      pc_id: pcId,
      sdp: peerConnection.localDescription.sdp,
      sdpType: peerConnection.localDescription.type,
      session_id: sessionId
    });
  } catch (error) {
    log.error(`Error handling offer: ${error.message}`);
    stats.connectionFailures++;
  }
}

// Handle ICE candidate from server
async function handleCandidate(data) {
  try {
    await peerConnection.addIceCandidate({
      candidate: data.candidate,
      sdpMid: data.sdpMid,
      sdpMLineIndex: data.sdpMLineIndex
    });
    
    if (options.verbose) {
      log.debug(`Added ICE candidate: ${data.candidate.substr(0, 30)}...`);
    }
  } catch (error) {
    log.error(`Error adding ICE candidate: ${error.message}`);
  }
}

// Handle quality change notification
function handleQualityChange(data) {
  const notificationData = data.data || {};
  const newQuality = notificationData.quality_level;
  const networkScore = notificationData.network_score;
  
  if (newQuality && newQuality !== stats.quality) {
    log.info(`Quality changed to ${newQuality} (score: ${networkScore})`);
    
    // Record quality change
    stats.qualityChanges.push({
      from: stats.quality,
      to: newQuality,
      networkScore,
      time: (Date.now() - stats.startTime) / 1000
    });
    
    // Update current quality
    stats.quality = newQuality;
  }
}

// Collect WebRTC statistics
async function collectStats() {
  if (!peerConnection) return;
  
  try {
    const reports = await peerConnection.getStats();
    
    // Process stats into a more usable format
    const processedStats = {};
    
    reports.forEach(report => {
      if (report.type === 'inbound-rtp') {
        if (report.kind === 'video') {
          processedStats.videoBytesReceived = report.bytesReceived;
          processedStats.videoPacketsReceived = report.packetsReceived;
          processedStats.videoFramesReceived = report.framesReceived;
          processedStats.videoFramesDecoded = report.framesDecoded;
          processedStats.videoJitter = report.jitter;
        } else if (report.kind === 'audio') {
          processedStats.audioBytesReceived = report.bytesReceived;
          processedStats.audioPacketsReceived = report.packetsReceived;
          processedStats.audioJitter = report.jitter;
        }
      } else if (report.type === 'track' && report.kind === 'video') {
        processedStats.frameWidth = report.frameWidth;
        processedStats.frameHeight = report.frameHeight;
        processedStats.framesDropped = report.framesDropped;
      } else if (report.type === 'candidate-pair' && report.state === 'succeeded') {
        processedStats.currentRoundTripTime = report.currentRoundTripTime;
        processedStats.availableOutgoingBitrate = report.availableOutgoingBitrate;
        processedStats.availableIncomingBitrate = report.availableIncomingBitrate;
      }
    });
    
    // Update resolution if available
    if (processedStats.frameWidth && processedStats.frameHeight) {
      stats.resolution = `${processedStats.frameWidth}x${processedStats.frameHeight}`;
    }
    
    // Update latest stats
    stats.latestStats = processedStats;
    
    if (options.verbose) {
      // Log some key stats
      if (stats.connectedTime) {
        const elapsed = (Date.now() - stats.connectedTime) / 1000;
        const fps = stats.framesReceived / elapsed;
        const bitrate = (stats.bytesReceived * 8) / (elapsed * 1000); // kbps
        
        log.debug(`Stats: ${fps.toFixed(1)} fps, ${bitrate.toFixed(1)} kbps, ` +
                 `${stats.resolution || 'unknown'} resolution`);
      }
    }
  } catch (error) {
    log.error(`Error collecting stats: ${error.message}`);
  }
}

// Send a message through the signaling channel
function sendSignalingMessage(message) {
  if (websocket && websocket.readyState === WebSocket.OPEN) {
    websocket.send(JSON.stringify(message));
  } else {
    log.error('WebSocket not connected, cannot send message');
  }
}

// Clean up resources
function cleanup() {
  interrupted = true;
  
  // Stop stats collection
  if (statsInterval) {
    clearInterval(statsInterval);
    statsInterval = null;
  }
  
  // Close peer connection
  if (peerConnection) {
    peerConnection.close();
    peerConnection = null;
    log.info('Closed peer connection');
  }
  
  // Send close message if we have a connection ID
  if (websocket && websocket.readyState === WebSocket.OPEN && pcId) {
    sendSignalingMessage({
      type: 'close',
      pc_id: pcId,
      session_id: sessionId
    });
    log.info(`Sent close message for peer connection ${pcId}`);
  }
  
  // Close WebSocket connection
  if (websocket) {
    websocket.close();
    websocket = null;
    log.info('Closed WebSocket connection');
  }
  
  // Save statistics report if requested
  if (options.statsOutput) {
    saveStatsReport();
  }
  
  // Log final statistics
  logFinalStats();
  
  // Exit after cleanup
  setTimeout(() => process.exit(0), 500);
}

// Generate a session ID
function generateSessionId() {
  return Math.random().toString(36).substring(2, 10) + 
         Math.random().toString(36).substring(2, 10);
}

// Log final statistics
function logFinalStats() {
  log.info('=== WebRTC Session Statistics ===');
  log.info(`CID: ${options.cid}`);
  
  const duration = (Date.now() - stats.startTime) / 1000;
  log.info(`Session duration: ${formatDuration(duration)}`);
  
  if (stats.connectedTime) {
    const connectionTime = stats.connectedTime - stats.startTime;
    log.info(`Connection time: ${connectionTime}ms`);
  }
  
  if (stats.firstFrameTime) {
    const firstFrameTime = stats.firstFrameTime - stats.startTime;
    log.info(`Time to first frame: ${firstFrameTime}ms`);
  }
  
  log.info(`Frames received: ${stats.framesReceived}`);
  
  if (stats.framesDropped) {
    log.info(`Frames dropped: ${stats.framesDropped}`);
  }
  
  if (stats.resolution) {
    log.info(`Resolution: ${stats.resolution}`);
  }
  
  if (stats.connectedTime) {
    const elapsed = (Date.now() - stats.connectedTime) / 1000;
    if (elapsed > 0) {
      const bitrate = (stats.bytesReceived * 8) / (elapsed * 1000); // kbps
      log.info(`Average bitrate: ${bitrate.toFixed(2)} kbps`);
      
      const fps = stats.framesReceived / elapsed;
      log.info(`Average FPS: ${fps.toFixed(2)}`);
    }
  }
  
  // Log quality changes
  if (stats.qualityChanges.length > 0) {
    log.info(`Quality changes: ${stats.qualityChanges.length}`);
    stats.qualityChanges.forEach((change, i) => {
      log.info(`  ${i+1}. ${change.from} -> ${change.to} ` +
               `at ${formatDuration(change.time)} ` +
               `(score: ${change.networkScore})`);
    });
  }
}

// Save statistics report to a file
function saveStatsReport() {
  try {
    const report = getStatsReport();
    fs.writeFileSync(options.statsOutput, JSON.stringify(report, null, 2));
    log.info(`Statistics saved to ${options.statsOutput}`);
  } catch (error) {
    log.error(`Failed to save statistics: ${error.message}`);
  }
}

// Get comprehensive statistics report
function getStatsReport() {
  // Calculate some derived metrics
  let avgFps = null;
  let avgBitrate = null;
  
  if (stats.connectedTime) {
    const elapsed = (Date.now() - stats.connectedTime) / 1000;
    if (elapsed > 0) {
      avgFps = stats.framesReceived / elapsed;
      avgBitrate = (stats.bytesReceived * 8) / (elapsed * 1000); // kbps
    }
  }
  
  return {
    session: {
      cid: options.cid,
      startTime: new Date(stats.startTime).toISOString(),
      durationSeconds: (Date.now() - stats.startTime) / 1000,
      connectionTimeMs: stats.connectedTime ? stats.connectedTime - stats.startTime : null,
      firstFrameTimeMs: stats.firstFrameTime ? stats.firstFrameTime - stats.startTime : null,
      qualityChanges: stats.qualityChanges,
      finalQuality: stats.quality
    },
    performance: {
      framesReceived: stats.framesReceived,
      framesDropped: stats.framesDropped || 0,
      bytesReceived: stats.bytesReceived,
      avgFps: avgFps,
      avgBitrateKbps: avgBitrate,
      resolution: stats.resolution
    },
    connection: {
      pcId: pcId,
      iceStateChanges: stats.iceStateChanges,
      connectionStateChanges: stats.connectionStateChanges,
      connectionAttempts: stats.connectionAttempts,
      connectionSuccesses: stats.connectionSuccesses,
      connectionFailures: stats.connectionFailures
    },
    rawStats: stats.latestStats
  };
}

// Format duration in seconds as MM:SS
function formatDuration(seconds) {
  const minutes = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// Start the client
main().catch(error => {
  log.error(`Unhandled error: ${error.message}`);
  cleanup();
});