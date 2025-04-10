# Filecoin Storage Backend Simulation Mode Implementation

## Overview

This document summarizes the implementation of simulation mode for the Filecoin storage backend in the `ipfs_kit_py` library. The simulation mode enables the library to operate without requiring the Lotus daemon to be installed or running, which is essential for testing, development environments, and scenarios where the Lotus daemon is unavailable.

## Key Components

### 1. Simulation Mode Flag

The `LotusKit` class includes a `simulation_mode` flag that can be enabled during initialization:

```python
def __init__(self, 
             api_base="http://127.0.0.1:1234/rpc/v0", 
             token=None, 
             token_path=None, 
             timeout=30,
             simulation_mode=False,
             correlation_id=None):
    # ... existing code ...
    self.simulation_mode = simulation_mode
    self.sim_cache = {
        "deals": {},
        "retrievals": {},
        "imports": {},
        "miners": {}
    }
```

### 2. Simulation Cache

The `sim_cache` dictionary maintains simulated state across operations to ensure consistent behavior in simulation mode. It includes sections for:

- **deals**: Storage deal information
- **retrievals**: Content retrieval records
- **imports**: Imported content data
- **miners**: Miner information

### 3. Implemented Methods

#### 3.1 client_list_imports

Returns a list of all content imports, simulating the `ClientListImports` Lotus API call:

```python
def client_list_imports(self, **kwargs):
    """List all imported files.
    
    Returns:
        dict: Result dictionary with list of imports.
    """
    operation = "client_list_imports"
    correlation_id = kwargs.get("correlation_id", self.correlation_id)
    result = create_result_dict(operation, correlation_id)
    
    # If in simulation mode, return simulated imports
    if self.simulation_mode:
        try:
            # Get all imports from simulation cache
            imports_list = []
            for cid, import_data in self.sim_cache["imports"].items():
                # Create a copy to avoid modifying the cache
                import_entry = dict(import_data)
                # Add CID if not already present
                if "CID" not in import_entry:
                    import_entry["CID"] = cid
                
                # Convert UUID objects to strings for JSON serialization
                if "ImportID" in import_entry and isinstance(import_entry["ImportID"], uuid.UUID):
                    import_entry["ImportID"] = str(import_entry["ImportID"])
                    
                # Ensure all values are JSON serializable
                for k, v in list(import_entry.items()):
                    if isinstance(v, uuid.UUID):
                        import_entry[k] = str(v)
                        
                imports_list.append(import_entry)
                
            # Sort imports by creation time (newest first)
            imports_list.sort(key=lambda x: x.get("Created", 0), reverse=True)
            
            result["success"] = True
            result["simulated"] = True
            result["result"] = imports_list
            return result
            
        except Exception as e:
            return handle_error(result, e, f"Error in simulated list_imports: {str(e)}")
    
    # Real API call for non-simulation mode
    return self._make_request("ClientListImports", correlation_id=correlation_id)
```

Key Features:
- Returns data from `sim_cache["imports"]` when in simulation mode
- Handles UUID conversion for proper JSON serialization
- Maintains consistent response structure matching real Lotus API

#### 3.2 miner_get_info

Returns information about a specific miner, simulating the `StateMinerInfo` Lotus API call:

```python
def miner_get_info(self, miner_address, **kwargs):
    """Get information about a specific miner.
    
    Args:
        miner_address (str): The address of the miner.
        
    Returns:
        dict: Result dictionary with miner information.
    """
    operation = "miner_get_info"
    correlation_id = kwargs.get("correlation_id", self.correlation_id)
    result = create_result_dict(operation, correlation_id)
    
    # If in simulation mode, return simulated miner info
    if self.simulation_mode:
        try:
            # Validate input
            if not miner_address:
                return handle_error(result, ValueError("Miner address is required"))
            
            # Create a deterministic miner ID based on the address
            miner_hash = hashlib.sha256(miner_address.encode()).hexdigest()
            
            # Generate simulated miner information
            simulated_info = {
                "Owner": f"t3{miner_hash[:40]}",
                "Worker": f"t3{miner_hash[1:41]}",
                "NewWorker": "",
                "ControlAddresses": [f"t3{miner_hash[2:42]}"],
                "WorkerChangeEpoch": -1,
                "PeerId": f"12D3KooW{miner_hash[:36]}",
                "Multiaddrs": [f"/ip4/203.0.113.{int(miner_hash[:2], 16) % 256}/tcp/24001"],
                "WindowPoStProofType": 0,
                "SectorSize": 34359738368,
                "WindowPoStPartitionSectors": 1,
                "ConsensusFaultElapsed": -1,
                "Beneficiary": f"t3{miner_hash[:40]}",
                "BeneficiaryTerm": {
                    "Quota": "0",
                    "UsedQuota": "0",
                    "Expiration": 0
                },
                "PendingBeneficiaryTerm": None
            }
            
            result["success"] = True
            result["simulated"] = True
            result["result"] = simulated_info
            return result
            
        except Exception as e:
            return handle_error(result, e, f"Error in simulated miner_get_info: {str(e)}")
    
    # Real API call for non-simulation mode
    return self._make_request("StateMinerInfo", params=[miner_address, []], correlation_id=correlation_id)
```

Key Features:
- Generates deterministic miner information based on the miner address
- Creates realistic miner data structures that match real Lotus responses
- Includes proper error handling for edge cases

#### 3.3 list_miners

Returns a list of all miners in the network, simulating the `StateListMiners` Lotus API call:

```python
def list_miners(self, **kwargs):
    """List all miners in the network.
    
    Returns:
        dict: Result dictionary with list of miners.
    """
    operation = "list_miners"
    correlation_id = kwargs.get("correlation_id", self.correlation_id)
    result = create_result_dict(operation, correlation_id)
    
    # If in simulation mode, return simulated miner list
    if self.simulation_mode:
        try:
            # Generate a list of simulated miners
            # The list is deterministic for consistent testing
            miners = []
            seed = 12345  # Use a fixed seed for deterministic results
            random.seed(seed)
            
            # Generate 50 simulated miners with deterministic addresses
            for i in range(1, 51):
                # Create deterministic miner IDs
                miner_id = f"t0{10000 + i}"
                miners.append(miner_id)
            
            # Add any miners that might be referenced in deals
            for deal_id, deal_data in self.sim_cache["deals"].items():
                if "Provider" in deal_data and deal_data["Provider"] not in miners:
                    miners.append(deal_data["Provider"])
            
            result["success"] = True
            result["simulated"] = True
            result["result"] = miners
            return result
            
        except Exception as e:
            return handle_error(result, e, f"Error in simulated list_miners: {str(e)}")
    
    # Real API call for non-simulation mode
    return self._make_request("StateListMiners", params=[[]], correlation_id=correlation_id)
```

Key Features:
- Generates a deterministic list of miners for consistent testing
- Includes any miners referenced in deal records from the simulation cache
- Maintains consistent response structure with the real API

### 4. Previously Implemented Methods

The following methods were previously implemented with simulation mode support:

- **client_retrieve**: Simulates retrieving content from the Filecoin network
- **client_find_data**: Simulates finding content on the Filecoin network
- **client_list_deals**: Simulates listing all deals made by the client
- **client_start_deal**: Simulates starting a storage deal with a miner
- **client_deal_info**: Simulates getting information about a specific deal
- **client_import**: Simulates importing content to Filecoin

## Testing Approach

A comprehensive test script (`test_lotus_simulation.py`) was created to validate the simulation mode implementations. The test includes:

1. **Method-level testing**: Each simulated method is tested in isolation
2. **Workflow testing**: Methods are tested together as part of realistic workflows
3. **Error handling testing**: Edge cases and error conditions are tested
4. **Serialization testing**: Ensures all responses are properly serializable

The testing approach verifies that the simulation mode provides realistic and consistent behavior without requiring the actual Lotus daemon.

## Benefits

The simulation mode implementation provides several key benefits:

1. **Test Environment Independence**: Tests can run without requiring Lotus daemon installation
2. **CI/CD Pipeline Compatibility**: Enables testing in restricted CI/CD environments
3. **Faster Testing**: Eliminates network latency and external dependencies
4. **Deterministic Testing**: Creates consistent, reproducible test scenarios
5. **Developer Experience**: Simplifies local development without full Filecoin setup
6. **Graceful Degradation**: Library continues to function (in simulation mode) even when Lotus is unavailable

## Future Enhancements

Potential future enhancements to the simulation mode include:

1. **Additional Method Support**: Implement simulation mode for remaining Lotus methods
2. **Enhanced Realism**: Improve the fidelity of simulated responses
3. **Simulation Configuration**: Allow customizing simulation behavior through configuration
4. **Partial Simulation**: Enable simulating only specific components
5. **Integration with Other Simulated Components**: Coordinate with other simulation modes (IPFS, Storacha, etc.)
6. **Documentation**: Expand documentation on simulation mode capabilities and usage

## Conclusion

The simulation mode implementation for Filecoin storage backend enables robust testing and development of the `ipfs_kit_py` library without requiring the Lotus daemon. This implementation follows the established pattern of graceful degradation, where the library works with real components when available, but falls back to simulation when necessary.

The three implemented methods (client_list_imports, miner_get_info, and list_miners) complete the essential functionality required for simulating Filecoin storage operations, enabling comprehensive testing of the higher-level FilecoinModel and other components that depend on Lotus functionality.