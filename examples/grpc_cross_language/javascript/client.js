/**
 * JavaScript (Node.js) Client Example for Routing gRPC Service
 *
 * This example demonstrates how to connect to the routing gRPC service
 * from Node.js, select a backend, and record an outcome.
 *
 * Prerequisites:
 * 1. Node.js installed (version 14+)
 * 2. Required npm packages:
 *    npm install @grpc/grpc-js @grpc/proto-loader
 *
 * To run this example:
 *    node client.js
 */

const grpc = require('@grpc/grpc-js');
const protoLoader = require('@grpc/proto-loader');
const path = require('path');

// Parse command line arguments
const argv = require('minimist')(process.argv.slice(2));
const serverAddr = argv.server || 'localhost:50051';
const jsonOutput = argv.json || false;

// Configure logging
const log = (message) => {
  if (!jsonOutput) {
    console.log(`[${new Date().toISOString()}] ${message}`);
  }
};

// Load protobuf definition
const PROTO_PATH = path.resolve(__dirname, '../../../ipfs_kit_py/routing/protos/routing.proto');

const packageDefinition = protoLoader.loadSync(PROTO_PATH, {
  keepCase: true,
  longs: String,
  enums: String,
  defaults: true,
  oneofs: true
});

const protoDescriptor = grpc.loadPackageDefinition(packageDefinition);
const routingService = protoDescriptor.ipfs_kit_py.routing.RoutingService;

// Helper function to print results
function printResult(data) {
  if (jsonOutput) {
    console.log(JSON.stringify(data, null, 2));
  } else {
    console.log(data);
  }
}

// Helper function to generate a mock content info
function generateMockContentInfo(contentType) {
  const sizeKb = Math.floor(Math.random() * 990 + 10); // 10-1000 KB
  return {
    contentType,
    contentSize: sizeKb * 1024,
    contentHash: `hash-${Math.floor(Math.random() * 9000 + 1000)}`,
    filename: `sample-${Math.floor(Math.random() * 9000 + 1000)}.${contentType.split('/')[1]}`,
    metadata: {
      created: '2025-04-15T20:00:00Z',
      tags: ['sample', 'test', 'javascript'],
    }
  };
}

// Helper function to create a timestamp
function createTimestamp() {
  const now = new Date();
  return {
    seconds: Math.floor(now.getTime() / 1000),
    nanos: (now.getTime() % 1000) * 1000000
  };
}

// Main async function
async function main() {
  // Create gRPC client
  const client = new routingService(serverAddr, grpc.credentials.createInsecure());

  log(`Connected to server at ${serverAddr}`);

  // Sample content types
  const contentTypes = [
    'application/pdf',
    'image/jpeg',
    'video/mp4',
    'text/plain',
    'application/json'
  ];

  // Select a random content type
  const contentType = contentTypes[Math.floor(Math.random() * contentTypes.length)];
  const contentInfo = generateMockContentInfo(contentType);

  log(`Processing ${contentInfo.contentType} content: ${contentInfo.filename}`);

  // Try different routing strategies
  const strategies = ['content_type', 'cost', 'performance', 'hybrid'];
  
  for (const strategy of strategies) {
    // Create select backend request
    const selectRequest = {
      content_type: contentInfo.contentType,
      content_size: contentInfo.contentSize,
      content_hash: contentInfo.contentHash,
      metadata: contentInfo.metadata,
      strategy,
      request_id: `js-client-${Math.floor(Math.random() * 100000)}`,
      timestamp: createTimestamp()
    };

    // Call SelectBackend using promisify
    const selectResponse = await new Promise((resolve, reject) => {
      client.selectBackend(selectRequest, (err, response) => {
        if (err) reject(err);
        else resolve(response);
      });
    });

    // Process response
    const result = {
      strategy,
      backend_id: selectResponse.backend_id,
      score: selectResponse.score,
      request_id: selectResponse.request_id,
      alternatives: selectResponse.alternatives || [],
      timestamp: new Date(
        selectResponse.timestamp.seconds * 1000 + 
        selectResponse.timestamp.nanos / 1000000
      ).toISOString()
    };

    log(`Strategy '${strategy}' selected backend: ${result.backend_id} with score ${result.score.toFixed(2)}`);

    // Simulate operation success (80% success rate)
    const success = Math.random() < 0.8;

    // Record outcome
    const outcomeRequest = {
      backend_id: selectResponse.backend_id,
      success,
      content_type: contentInfo.contentType,
      content_size: contentInfo.contentSize,
      content_hash: contentInfo.contentHash,
      duration_ms: Math.floor(Math.random() * 490 + 10), // 10-500ms
      timestamp: createTimestamp()
    };

    // Call RecordOutcome using promisify
    const outcomeResponse = await new Promise((resolve, reject) => {
      client.recordOutcome(outcomeRequest, (err, response) => {
        if (err) reject(err);
        else resolve(response);
      });
    });

    log(`Recorded outcome: ${outcomeResponse.message}`);
  }

  // Get insights
  const insightsRequest = {
    time_window_hours: 24
  };

  // Call GetInsights using promisify
  const insightsResponse = await new Promise((resolve, reject) => {
    client.getInsights(insightsRequest, (err, response) => {
      if (err) reject(err);
      else resolve(response);
    });
  });

  log('Routing insights received:');
  if (insightsResponse.factor_weights) {
    log('Factor weights:');
    for (const [key, value] of Object.entries(insightsResponse.factor_weights)) {
      log(`  ${key}: ${value}`);
    }
  }

  // Example of streaming metrics
  if (!jsonOutput) {
    log('Starting metrics streaming for 5 seconds...');
  
    const metricsRequest = {
      update_interval_seconds: 1,
      include_backends: true
    };
  
    const metricsStream = client.streamMetrics(metricsRequest);
    
    metricsStream.on('data', (update) => {
      const statusMap = ['NORMAL', 'WARNING', 'CRITICAL'];
      log(`Metrics update (${statusMap[update.status]})`);
      
      if (update.metrics) {
        for (const [key, value] of Object.entries(update.metrics)) {
          if (typeof value === 'object' && Object.keys(value).length <= 5) {
            log(`  ${key}: ${JSON.stringify(value)}`);
          } else {
            log(`  ${key}: (data available)`);
          }
        }
      }
    });
  
    metricsStream.on('error', (err) => {
      log(`Metrics stream error: ${err.message}`);
    });
    
    metricsStream.on('end', () => {
      log('Metrics stream ended');
    });
    
    // Wait 5 seconds and then cancel the stream
    await new Promise(resolve => setTimeout(resolve, 5000));
    metricsStream.cancel();
  }

  log('JavaScript client example completed successfully');
}

// Run the example
main().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});