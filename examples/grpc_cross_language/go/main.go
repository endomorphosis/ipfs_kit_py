// Go Client Example for Routing gRPC Service
//
// This example demonstrates how to connect to the routing gRPC service
// from Go, select a backend, and record an outcome.
//
// Prerequisites:
// 1. Go installed (version 1.13+)
// 2. Protobuf compiler (protoc) installed
// 3. Go gRPC packages installed:
//    go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
//    go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
//
// To generate code from the proto file:
//    protoc --go_out=. --go-grpc_out=. routing.proto
//
// To build this example:
//    go build -o routing_client main.go
//
// To run this example:
//    ./routing_client

package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"math/rand"
	"os"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/protobuf/types/known/structpb"
	"google.golang.org/protobuf/types/known/timestamppb"

	// Update this import path to match your generated code location
	pb "example.com/ipfs_kit_py/routing"
)

var (
	serverAddr = flag.String("server", "localhost:50051", "The server address in the format host:port")
	jsonOutput = flag.Bool("json", false, "Output in JSON format")
)

// ContentInfo represents the content metadata
type ContentInfo struct {
	ContentType string            `json:"content_type"`
	ContentSize int64             `json:"content_size"`
	ContentHash string            `json:"content_hash"`
	Filename    string            `json:"filename"`
	Metadata    map[string]string `json:"metadata"`
}

// generateMockContentInfo creates a sample content info for testing
func generateMockContentInfo(contentType string) ContentInfo {
	sizeKB := rand.Intn(1000) + 10
	return ContentInfo{
		ContentType: contentType,
		ContentSize: int64(sizeKB * 1024),
		ContentHash: fmt.Sprintf("hash-%d", rand.Intn(9000)+1000),
		Filename:    fmt.Sprintf("sample-%d.%s", rand.Intn(9000)+1000, contentType),
		Metadata: map[string]string{
			"created": "2025-04-15T20:00:00Z",
			"tags":    "sample,test,go",
		},
	}
}

// printResult prints the result in the requested format
func printResult(data interface{}) {
	if *jsonOutput {
		jsonData, err := json.MarshalIndent(data, "", "  ")
		if err != nil {
			log.Fatalf("Failed to marshal result: %v", err)
		}
		fmt.Println(string(jsonData))
	} else {
		fmt.Printf("%+v\n", data)
	}
}

func main() {
	flag.Parse()

	// Set up a connection to the server
	conn, err := grpc.Dial(*serverAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		log.Fatalf("Failed to connect: %v", err)
	}
	defer conn.Close()
	client := pb.NewRoutingServiceClient(conn)

	log.Printf("Connected to server at %s", *serverAddr)

	// Create a context with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// Sample content types
	contentTypes := []string{
		"application/pdf",
		"image/jpeg",
		"video/mp4",
		"text/plain",
		"application/json",
	}

	// Select a random content type
	contentType := contentTypes[rand.Intn(len(contentTypes))]
	contentInfo := generateMockContentInfo(contentType)

	log.Printf("Processing %s content: %s", contentInfo.ContentType, contentInfo.Filename)

	// Create metadata struct
	metadataMap := make(map[string]interface{})
	for k, v := range contentInfo.Metadata {
		metadataMap[k] = v
	}
	metadataStruct, err := structpb.NewStruct(metadataMap)
	if err != nil {
		log.Fatalf("Failed to create metadata struct: %v", err)
	}

	// Try different routing strategies
	strategies := []string{"content_type", "cost", "performance", "hybrid"}
	for _, strategy := range strategies {
		// Create request
		req := &pb.SelectBackendRequest{
			ContentType: contentInfo.ContentType,
			ContentSize: contentInfo.ContentSize,
			ContentHash: contentInfo.ContentHash,
			Metadata:    metadataStruct,
			Strategy:    strategy,
			RequestId:   fmt.Sprintf("go-client-%d", rand.Int()),
			Timestamp:   timestamppb.Now(),
		}

		// Call SelectBackend
		resp, err := client.SelectBackend(ctx, req)
		if err != nil {
			log.Fatalf("Failed to select backend: %v", err)
		}

		// Print result
		result := map[string]interface{}{
			"strategy":    strategy,
			"backend_id":  resp.BackendId,
			"score":       resp.Score,
			"request_id":  resp.RequestId,
			"timestamp":   resp.Timestamp.AsTime().Format(time.RFC3339),
			"alternatives": make([]map[string]interface{}, 0),
		}

		for _, alt := range resp.Alternatives {
			result["alternatives"] = append(result["alternatives"].([]map[string]interface{}), 
				map[string]interface{}{
					"backend_id": alt.BackendId,
					"score":      alt.Score,
				})
		}

		log.Printf("Strategy '%s' selected backend: %s with score %.2f", 
			strategy, resp.BackendId, resp.Score)

		// Simulate operation success (80% success rate)
		success := rand.Float32() < 0.8

		// Record outcome
		outcomeReq := &pb.RecordOutcomeRequest{
			BackendId:   resp.BackendId,
			Success:     success,
			ContentType: contentInfo.ContentType,
			ContentSize: contentInfo.ContentSize,
			ContentHash: contentInfo.ContentHash,
			DurationMs:  int32(rand.Intn(490) + 10), // 10-500ms
			Timestamp:   timestamppb.Now(),
		}

		outcomeResp, err := client.RecordOutcome(ctx, outcomeReq)
		if err != nil {
			log.Fatalf("Failed to record outcome: %v", err)
		}

		log.Printf("Recorded outcome: %s", outcomeResp.Message)
	}

	// Get insights
	insightsReq := &pb.GetInsightsRequest{
		TimeWindowHours: 24,
	}

	insightsResp, err := client.GetInsights(ctx, insightsReq)
	if err != nil {
		log.Fatalf("Failed to get insights: %v", err)
	}

	log.Println("Routing insights received:")
	if len(insightsResp.FactorWeights.Fields) > 0 {
		log.Println("Factor weights:")
		for k, v := range insightsResp.FactorWeights.Fields {
			log.Printf("  %s: %v", k, v.GetNumberValue())
		}
	}

	log.Println("Go client example completed successfully")
}