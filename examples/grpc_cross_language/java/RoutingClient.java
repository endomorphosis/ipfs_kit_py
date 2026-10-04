/*
 * Java Client Example for Routing gRPC Service
 *
 * This example demonstrates how to connect to the routing gRPC service
 * from Java, select a backend, and record an outcome.
 *
 * Prerequisites:
 * 1. Java 8+ installed
 * 2. Maven or Gradle for dependency management
 * 3. Protobuf compiler (protoc) installed
 * 
 * To generate code from the proto file:
 *    protoc --java_out=. --grpc-java_out=. routing.proto
 *
 * To build with Maven, create a pom.xml with these dependencies:
 *   - io.grpc:grpc-netty-shaded:1.45.1
 *   - io.grpc:grpc-protobuf:1.45.1
 *   - io.grpc:grpc-stub:1.45.1
 *   - javax.annotation:javax.annotation-api:1.3.2
 *
 * To run this example:
 *    java -jar routing-client.jar
 */

package com.example.ipfs_kit_py.routing;

import com.google.protobuf.Struct;
import com.google.protobuf.Value;
import com.google.protobuf.Timestamp;
import io.grpc.ManagedChannel;
import io.grpc.ManagedChannelBuilder;
import io.grpc.stub.StreamObserver;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

// Note: Import paths will need to be adjusted based on the generated code
import com.example.ipfs_kit_py.routing.RoutingServiceGrpc;
import com.example.ipfs_kit_py.routing.RoutingOuterClass.SelectBackendRequest;
import com.example.ipfs_kit_py.routing.RoutingOuterClass.SelectBackendResponse;
import com.example.ipfs_kit_py.routing.RoutingOuterClass.RecordOutcomeRequest;
import com.example.ipfs_kit_py.routing.RoutingOuterClass.RecordOutcomeResponse;
import com.example.ipfs_kit_py.routing.RoutingOuterClass.GetInsightsRequest;
import com.example.ipfs_kit_py.routing.RoutingOuterClass.GetInsightsResponse;
import com.example.ipfs_kit_py.routing.RoutingOuterClass.StreamMetricsRequest;
import com.example.ipfs_kit_py.routing.RoutingOuterClass.MetricsUpdate;

public class RoutingClient {
    private final ManagedChannel channel;
    private final RoutingServiceGrpc.RoutingServiceBlockingStub blockingStub;
    private final RoutingServiceGrpc.RoutingServiceStub asyncStub;
    private final Random random = new Random();
    private final boolean jsonOutput;

    /**
     * Content information for testing
     */
    private static class ContentInfo {
        final String contentType;
        final long contentSize;
        final String contentHash;
        final String filename;
        final Map<String, String> metadata;

        ContentInfo(String contentType, long contentSize, String contentHash, String filename, Map<String, String> metadata) {
            this.contentType = contentType;
            this.contentSize = contentSize;
            this.contentHash = contentHash;
            this.filename = filename;
            this.metadata = metadata;
        }
    }

    /**
     * Construct client connecting to routing server at {@code host:port}
     */
    public RoutingClient(String host, int port, boolean jsonOutput) {
        this(ManagedChannelBuilder.forAddress(host, port)
                // Disable TLS for this example
                .usePlaintext()
                .build(), jsonOutput);
    }

    /**
     * Construct client using an existing channel
     */
    public RoutingClient(ManagedChannel channel, boolean jsonOutput) {
        this.channel = channel;
        this.blockingStub = RoutingServiceGrpc.newBlockingStub(channel);
        this.asyncStub = RoutingServiceGrpc.newStub(channel);
        this.jsonOutput = jsonOutput;
    }

    /**
     * Generate mock content info for testing
     */
    private ContentInfo generateMockContentInfo(String contentType) {
        int sizeKb = random.nextInt(990) + 10; // 10-1000 KB
        String extension = contentType.split("/")[1];
        String contentHash = "hash-" + (random.nextInt(9000) + 1000);
        String filename = "sample-" + (random.nextInt(9000) + 1000) + "." + extension;
        
        Map<String, String> metadata = new HashMap<>();
        metadata.put("created", "2025-04-15T20:00:00Z");
        metadata.put("tags", "sample,test,java");
        
        return new ContentInfo(contentType, sizeKb * 1024, contentHash, filename, metadata);
    }

    /**
     * Convert a Java Map to Protobuf Struct
     */
    private Struct mapToStruct(Map<String, String> map) {
        Struct.Builder structBuilder = Struct.newBuilder();
        for (Map.Entry<String, String> entry : map.entrySet()) {
            structBuilder.putFields(
                entry.getKey(), 
                Value.newBuilder().setStringValue(entry.getValue()).build()
            );
        }
        return structBuilder.build();
    }

    /**
     * Create a current timestamp in Protobuf format
     */
    private Timestamp getCurrentTimestamp() {
        long currentTime = System.currentTimeMillis();
        return Timestamp.newBuilder()
            .setSeconds(currentTime / 1000)
            .setNanos((int) ((currentTime % 1000) * 1000000))
            .build();
    }

    /**
     * Log a message (unless JSON output is enabled)
     */
    private void log(String message) {
        if (!jsonOutput) {
            System.out.println("[" + java.time.Instant.now() + "] " + message);
        }
    }

    /**
     * Run the routing client example
     */
    public void run() throws Exception {
        try {
            log("Connected to routing gRPC server");

            // Sample content types
            List<String> contentTypes = Arrays.asList(
                "application/pdf",
                "image/jpeg",
                "video/mp4",
                "text/plain",
                "application/json"
            );

            // Select a random content type
            String contentType = contentTypes.get(random.nextInt(contentTypes.size()));
            ContentInfo contentInfo = generateMockContentInfo(contentType);

            log("Processing " + contentInfo.contentType + " content: " + contentInfo.filename);

            // Try different routing strategies
            List<String> strategies = Arrays.asList("content_type", "cost", "performance", "hybrid");
            
            for (String strategy : strategies) {
                // Create select backend request
                SelectBackendRequest request = SelectBackendRequest.newBuilder()
                    .setContentType(contentInfo.contentType)
                    .setContentSize(contentInfo.contentSize)
                    .setContentHash(contentInfo.contentHash)
                    .setMetadata(mapToStruct(contentInfo.metadata))
                    .setStrategy(strategy)
                    .setRequestId("java-client-" + UUID.randomUUID().toString())
                    .setTimestamp(getCurrentTimestamp())
                    .build();

                // Call SelectBackend
                SelectBackendResponse response = blockingStub.selectBackend(request);
                
                // Process response
                log("Strategy '" + strategy + "' selected backend: " + 
                    response.getBackendId() + " with score " + 
                    String.format("%.2f", response.getScore()));

                // Simulate operation success (80% success rate)
                boolean success = random.nextFloat() < 0.8f;

                // Record outcome
                RecordOutcomeRequest outcomeRequest = RecordOutcomeRequest.newBuilder()
                    .setBackendId(response.getBackendId())
                    .setSuccess(success)
                    .setContentType(contentInfo.contentType)
                    .setContentSize(contentInfo.contentSize)
                    .setContentHash(contentInfo.contentHash)
                    .setDurationMs(random.nextInt(490) + 10) // 10-500ms
                    .setTimestamp(getCurrentTimestamp())
                    .build();

                RecordOutcomeResponse outcomeResponse = blockingStub.recordOutcome(outcomeRequest);
                log("Recorded outcome: " + outcomeResponse.getMessage());
            }

            // Get insights
            GetInsightsRequest insightsRequest = GetInsightsRequest.newBuilder()
                .setTimeWindowHours(24)
                .build();

            GetInsightsResponse insightsResponse = blockingStub.getInsights(insightsRequest);
            
            log("Routing insights received:");
            if (insightsResponse.getFactorWeights().getFieldsCount() > 0) {
                log("Factor weights:");
                for (Map.Entry<String, Value> entry : insightsResponse.getFactorWeights().getFieldsMap().entrySet()) {
                    log("  " + entry.getKey() + ": " + entry.getValue().getNumberValue());
                }
            }

            // Example of streaming metrics
            if (!jsonOutput) {
                log("Starting metrics streaming for 5 seconds...");
                
                StreamMetricsRequest metricsRequest = StreamMetricsRequest.newBuilder()
                    .setUpdateIntervalSeconds(1)
                    .setIncludeBackends(true)
                    .build();
                
                // CountDownLatch to wait for streaming completion
                final CountDownLatch finishLatch = new CountDownLatch(1);
                
                // Start streaming metrics
                asyncStub.streamMetrics(metricsRequest, new StreamObserver<MetricsUpdate>() {
                    @Override
                    public void onNext(MetricsUpdate update) {
                        String status;
                        switch (update.getStatusValue()) {
                            case 1: status = "WARNING"; break;
                            case 2: status = "CRITICAL"; break;
                            default: status = "NORMAL"; break;
                        }
                        
                        log("Metrics update (" + status + ")");
                        
                        if (update.getMetrics().getFieldsCount() > 0) {
                            for (Map.Entry<String, Value> entry : update.getMetrics().getFieldsMap().entrySet()) {
                                log("  " + entry.getKey() + ": (data available)");
                            }
                        }
                    }

                    @Override
                    public void onError(Throwable t) {
                        log("Metrics stream error: " + t.getMessage());
                        finishLatch.countDown();
                    }

                    @Override
                    public void onCompleted() {
                        log("Metrics stream completed");
                        finishLatch.countDown();
                    }
                });
                
                // Wait for 5 seconds then cancel by timing out the latch
                if (!finishLatch.await(5, TimeUnit.SECONDS)) {
                    log("Stopping metrics streaming");
                }
            }

            log("Java client example completed successfully");
            
        } finally {
            // Shutdown the channel
            channel.shutdown().awaitTermination(5, TimeUnit.SECONDS);
        }
    }

    /**
     * Main method
     */
    public static void main(String[] args) throws Exception {
        String host = "localhost";
        int port = 50051;
        boolean jsonOutput = false;

        // Parse command line arguments
        for (int i = 0; i < args.length; i++) {
            if (args[i].equals("--host") && i < args.length - 1) {
                host = args[++i];
            } else if (args[i].equals("--port") && i < args.length - 1) {
                port = Integer.parseInt(args[++i]);
            } else if (args[i].equals("--json")) {
                jsonOutput = true;
            }
        }

        // Run the client
        RoutingClient client = new RoutingClient(host, port, jsonOutput);
        client.run();
    }
}