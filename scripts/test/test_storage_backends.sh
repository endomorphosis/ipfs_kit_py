#!/bin/bash
# Test all storage backends after fixes

echo "=== Testing Storage Backends ==="

# Test function
test_endpoint() {
    local name=$1
    local endpoint=$2
    local method=${3:-GET}
    local data=$4
    
    echo -n "Testing $name: "
    
    if [ "$method" = "GET" ]; then
        response=$(curl -s "$endpoint")
    else
        if [ -n "$data" ]; then
            response=$(curl -s -X $method -H "Content-Type: application/json" -d "$data" "$endpoint")
        else
            response=$(curl -s -X $method "$endpoint")
        fi
    fi
    
    if echo "$response" | grep -q "success":true"; then
        echo "✅ PASSED"
    else
        echo "❌ FAILED"
        echo "$response"
    fi
}

# Base URL
BASE_URL="http://localhost:9991/api/v0"

# Test IPFS basic functionality
echo -e "
== IPFS Tests =="
test_endpoint "IPFS Health" "$BASE_URL/health"
test_endpoint "IPFS Version" "$BASE_URL/ipfs/version"

# Test Storage Backends
echo -e "
== Storage Backend Tests =="

# Huggingface tests
echo -e "
= HuggingFace Backend ="
test_endpoint "HuggingFace Status" "$BASE_URL/huggingface/status"
test_endpoint "HuggingFace from_ipfs" "$BASE_URL/huggingface/from_ipfs" "POST" '{"cid":"bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi","repo_id":"test-repo"}'
test_endpoint "HuggingFace to_ipfs" "$BASE_URL/huggingface/to_ipfs" "POST" '{"repo_id":"test-repo","path_in_repo":"test-file.txt"}'

# Storacha tests
echo -e "
= Storacha Backend ="
test_endpoint "Storacha Status" "$BASE_URL/storacha/status"
test_endpoint "Storacha from_ipfs" "$BASE_URL/storacha/from_ipfs" "POST" '{"cid":"bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"}'
test_endpoint "Storacha to_ipfs" "$BASE_URL/storacha/to_ipfs" "POST" '{"car_cid":"mock-car-bafybeig"}'

# Filecoin tests
echo -e "
= Filecoin Backend ="
test_endpoint "Filecoin Status" "$BASE_URL/filecoin/status"
test_endpoint "Filecoin from_ipfs" "$BASE_URL/filecoin/from_ipfs" "POST" '{"cid":"bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"}'
test_endpoint "Filecoin to_ipfs" "$BASE_URL/filecoin/to_ipfs" "POST" '{"deal_id":"mock-deal-bafybeig"}'

# Lassie tests
echo -e "
= Lassie Backend ="
test_endpoint "Lassie Status" "$BASE_URL/lassie/status"
test_endpoint "Lassie to_ipfs" "$BASE_URL/lassie/to_ipfs" "POST" '{"cid":"bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi"}'

# S3 tests
echo -e "
= S3 Backend ="
test_endpoint "S3 Status" "$BASE_URL/s3/status"
test_endpoint "S3 from_ipfs" "$BASE_URL/s3/from_ipfs" "POST" '{"cid":"bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi","bucket":"test-bucket"}'
test_endpoint "S3 to_ipfs" "$BASE_URL/s3/to_ipfs" "POST" '{"bucket":"test-bucket","key":"test-file.txt"}'

echo -e "
All tests completed."
