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

#### 3.4 wallet_balance

Returns the balance of a wallet address, simulating the `WalletBalance` Lotus API call:

```python
def wallet_balance(self, address, **kwargs):
    """Get wallet balance.
    
    Args:
        address (str): The wallet address to check balance for.
        
    Returns:
        dict: Result dictionary with wallet balance.
    """
    operation = "wallet_balance"
    correlation_id = kwargs.get("correlation_id", self.correlation_id)
    result = create_result_dict(operation, correlation_id)
    
    # If in simulation mode, return simulated wallet balance
    if self.simulation_mode:
        try:
            # Validate input
            if not address:
                return handle_error(result, ValueError("Wallet address is required"))
            
            # Generate a deterministic balance based on the address
            # The balance is based on the hash of the address, but will be consistent
            # for the same address across calls
            address_hash = hashlib.sha256(address.encode()).hexdigest()
            
            # Convert first 10 characters of hash to integer and use as base balance
            # Scale to a reasonable FIL amount (between 1-100 FIL)
            base_balance = int(address_hash[:10], 16) % 10000 / 100
            
            # Format as a filecoin balance string (attoFIL)
            balance = str(int(base_balance * 1e18))
            
            result["success"] = True
            result["simulated"] = True
            result["result"] = balance
            return result
            
        except Exception as e:
            return handle_error(result, e, f"Error in simulated wallet_balance: {str(e)}")
    
    return self._make_request("WalletBalance", params=[address], correlation_id=correlation_id)
```

Key Features:
- Generates deterministic wallet balances based on wallet address
- Simulates realistic FIL amounts in attoFIL units
- Ensures consistent balance for the same wallet across multiple calls

#### 3.5 paych_list and paych_status

Simulates payment channel operations, a critical part of Filecoin's off-chain payments:

```python
def paych_list(self, **kwargs):
    """List all locally tracked payment channels.
    
    Returns:
        dict: Result dictionary with list of channel addresses
    """
    operation = "paych_list"
    correlation_id = kwargs.get("correlation_id", self.correlation_id)
    result = create_result_dict(operation, correlation_id)
    
    # If in simulation mode, return simulated payment channels
    if self.simulation_mode:
        try:
            # Initialize channels list if it doesn't exist in the simulation cache
            if "channels" not in self.sim_cache:
                self.sim_cache["channels"] = {}
                
                # Create a few simulated payment channels for testing
                # with deterministic addresses based on wallet addresses
                wallets = []
                
                # Get wallets from list_wallets if available
                wallet_result = self.list_wallets()
                if wallet_result.get("success", False) and wallet_result.get("result"):
                    wallets = wallet_result.get("result", [])
                
                # If no wallets were found, create some simulated ones
                if not wallets:
                    wallets = [
                        f"t3{hashlib.sha256(f'wallet_{i}'.encode()).hexdigest()[:40]}" 
                        for i in range(3)
                    ]
                
                # Create simulated channels between wallets
                for i in range(min(len(wallets), 2)):
                    for j in range(i+1, min(len(wallets), 3)):
                        from_addr = wallets[i]
                        to_addr = wallets[j]
                        
                        # Create deterministic channel address
                        channel_hash = hashlib.sha256(f"{from_addr}_{to_addr}".encode()).hexdigest()
                        channel_addr = f"t064{channel_hash[:5]}"
                        
                        # Store channel information in simulation cache
                        self.sim_cache["channels"][channel_addr] = {
                            "From": from_addr,
                            "To": to_addr,
                            "Direction": i % 2,  # 0=outbound, 1=inbound
                            "CreateMsg": f"bafy2bzace{channel_hash[:40]}",
                            "Settled": False,
                            "Amount": str(int(int(channel_hash[:8], 16) % 1000) * 1e15)  # Random amount 0-1000 FIL
                        }
            
            # Return channel addresses
            channel_addresses = list(self.sim_cache["channels"].keys())
            
            result["success"] = True
            result["simulated"] = True
            result["result"] = channel_addresses
            return result
            
        except Exception as e:
            return handle_error(result, e, f"Error in simulated paych_list: {str(e)}")
    
    return self._make_request("PaychList", correlation_id=correlation_id)
```

```python
def paych_status(self, ch_addr, **kwargs):
    """Get the status of a payment channel.
    
    Args:
        ch_addr (str): Payment channel address
        
    Returns:
        dict: Result dictionary with channel status
    """
    operation = "paych_status"
    correlation_id = kwargs.get("correlation_id", self.correlation_id)
    result = create_result_dict(operation, correlation_id)
    
    # If in simulation mode, return simulated payment channel status
    if self.simulation_mode:
        try:
            # Validate input
            if not ch_addr:
                return handle_error(result, ValueError("Channel address is required"))
            
            # Initialize channels if not already initialized
            if "channels" not in self.sim_cache:
                # Call paych_list to initialize the channels simulation cache
                self.paych_list()
            
            # Check if the channel exists in our simulation cache
            if ch_addr in self.sim_cache["channels"]:
                channel_info = self.sim_cache["channels"][ch_addr]
                
                # Create simulated channel status
                channel_status = {
                    "Channel": ch_addr,
                    "From": channel_info.get("From", ""),
                    "To": channel_info.get("To", ""),
                    "ConfirmedAmt": channel_info.get("Amount", "0"),
                    "PendingAmt": "0",
                    "NonceHighest": 0,
                    "Vouchers": [],
                    "Lanes": [
                        {
                            "ID": 0,
                            "NextNonce": 0,
                            "AmountRedeemed": "0"
                        }
                    ]
                }
                
                result["success"] = True
                result["simulated"] = True
                result["result"] = channel_status
                return result
            else:
                # Channel not found
                return handle_error(
                    result, 
                    ValueError(f"Channel {ch_addr} not found"), 
                    f"Simulated channel {ch_addr} not found"
                )
            
        except Exception as e:
            return handle_error(result, e, f"Error in simulated paych_status: {str(e)}")
    
    return self._make_request("PaychAvailableFunds", params=[ch_addr], 
                             correlation_id=correlation_id)
```

Key Features:
- Creates realistic simulated payment channels between wallets
- Generates deterministic channel addresses based on wallet pairs
- Provides detailed payment channel status information
- Maintains consistent channel state across method calls

#### 3.6 miner_list_sectors and miner_sector_status

Simulates miner sector management, important for understanding storage allocation on the Filecoin network:

```python
def miner_list_sectors(self, **kwargs):
    """List all sectors managed by the miner.
    
    Returns:
        dict: Result dictionary with sector list
    """
    operation = "miner_list_sectors"
    correlation_id = kwargs.get("correlation_id", self.correlation_id)
    result = create_result_dict(operation, correlation_id)
    
    # If in simulation mode, return simulated sector list
    if self.simulation_mode:
        try:
            # Initialize miner sectors if not already in simulation cache
            if "sectors" not in self.sim_cache:
                self.sim_cache["sectors"] = {}
                
                # Get our miner address or use a default
                miner_address = None
                try:
                    miner_addr_result = self.miner_get_address()
                    if miner_addr_result.get("success", False):
                        miner_address = miner_addr_result.get("result", "")
                except Exception:
                    pass
                
                if not miner_address:
                    # Use a default miner address
                    miner_address = "t01000"
                
                # Generate deterministic sector numbers
                # We'll create 20 simulated sectors
                for i in range(1, 21):
                    sector_id = i
                    
                    # Create a deterministic sector hash based on the sector ID
                    sector_hash = hashlib.sha256(f"{miner_address}_sector_{sector_id}".encode()).hexdigest()
                    
                    # Determine sector state (most active, some in other states)
                    sector_status = "Active"
                    if i % 10 == 0:
                        sector_status = "Proving"
                    elif i % 7 == 0:
                        sector_status = "Sealing"
                    
                    # Store sector information
                    self.sim_cache["sectors"][sector_id] = {
                        "SectorID": sector_id,
                        "SectorNumber": sector_id,
                        "SealedCID": {"/" : f"bafy2bzacea{sector_hash[:40]}"},
                        "DealIDs": [int(sector_hash[:8], 16) % 10000 + i for i in range(3)],
                        "Activation": int(time.time()) - (i * 86400),  # Staggered activation times
                        "Expiration": int(time.time()) + (180 * 86400),  # 180 days in the future
                        "SectorStatus": sector_status
                    }
            
            # Get just the sector numbers for the response
            sector_numbers = list(self.sim_cache["sectors"].keys())
            
            result["success"] = True
            result["simulated"] = True
            result["result"] = sector_numbers
            return result
            
        except Exception as e:
            return handle_error(result, e, f"Error in simulated miner_list_sectors: {str(e)}")
    
    return self._make_miner_request("SectorsList", correlation_id=correlation_id)
```

```python
def miner_sector_status(self, sector_number, **kwargs):
    """Get detailed information about a sector.
    
    Args:
        sector_number (int): Sector number to query
        
    Returns:
        dict: Result dictionary with sector status
    """
    operation = "miner_sector_status"
    correlation_id = kwargs.get("correlation_id", self.correlation_id)
    result = create_result_dict(operation, correlation_id)
    
    # If in simulation mode, return simulated sector status
    if self.simulation_mode:
        try:
            # Validate sector number
            if sector_number is None:
                return handle_error(result, ValueError("Sector number is required"))
            
            # Ensure sectors cache is initialized
            if "sectors" not in self.sim_cache:
                # Initialize sector cache by calling miner_list_sectors
                self.miner_list_sectors()
            
            # Check if the sector exists in our simulation cache
            if sector_number in self.sim_cache["sectors"]:
                # Return the sector information
                sector_info = self.sim_cache["sectors"][sector_number]
                
                # Add additional detailed status information
                detailed_status = dict(sector_info)
                
                # Add activation time
                if "Activation" in detailed_status:
                    activation_time = detailed_status["Activation"]
                    detailed_status["ActivationEpoch"] = activation_time // 30  # Approximate epoch conversion
                
                # Add detailed state information
                base_status = detailed_status.get("SectorStatus", "Active")
                detailed_status["State"] = {
                    "Active": 7,       # Proving
                    "Proving": 7,      # Proving
                    "Sealing": 3,      # PreCommit1
                    "Expired": 9,      # Expired
                    "Faulty": 8,       # Faulty
                    "Terminated": 10   # Terminated
                }.get(base_status, 7)
                
                # Add sector size (standard 32GiB)
                detailed_status["SectorSize"] = 34359738368
                
                # Add deal weight info
                detailed_status["DealWeight"] = "0"
                detailed_status["VerifiedDealWeight"] = "0"
                
                # Add piece info if deals exist
                if "DealIDs" in detailed_status and detailed_status["DealIDs"]:
                    pieces = []
                    for deal_id in detailed_status["DealIDs"]:
                        # Create deterministic piece info for each deal
                        piece_hash = hashlib.sha256(f"piece_{deal_id}".encode()).hexdigest()
                        piece_size = 1 << (27 + (deal_id % 5))  # Random size between 128MiB and 2GiB
                        pieces.append({
                            "PieceCID": {"/" : f"baga6ea4sea{piece_hash[:40]}"},
                            "DealInfo": {
                                "DealID": deal_id,
                                "DealProposal": {
                                    "PieceCID": {"/" : f"baga6ea4sea{piece_hash[:40]}"},
                                    "PieceSize": piece_size,
                                    "VerifiedDeal": bool(deal_id % 2),
                                    "Client": f"t3{piece_hash[:40]}",
                                    "Provider": f"t01{1000 + (deal_id % 100)}",
                                    "StartEpoch": detailed_status.get("ActivationEpoch", 0) - 10,
                                    "EndEpoch": detailed_status.get("Expiration", 0) // 30 + 10,
                                    "StoragePricePerEpoch": "0",
                                    "ProviderCollateral": "0",
                                    "ClientCollateral": "0"
                                },
                                "DealState": {
                                    "SectorStartEpoch": detailed_status.get("ActivationEpoch", 0),
                                    "LastUpdatedEpoch": int(time.time()) // 30,
                                    "SlashEpoch": -1
                                }
                            }
                        })
                    detailed_status["Pieces"] = pieces
                
                result["success"] = True
                result["simulated"] = True
                result["result"] = detailed_status
                return result
            else:
                # Sector not found
                return handle_error(
                    result, 
                    ValueError(f"Sector {sector_number} not found"), 
                    f"Simulated sector {sector_number} not found"
                )
            
        except Exception as e:
            return handle_error(result, e, f"Error in simulated miner_sector_status: {str(e)}")
    
    return self._make_miner_request("SectorsStatus", 
                                  params=[sector_number],
                                  correlation_id=correlation_id)
```

Key Features:
- Creates realistic simulation of Filecoin storage sectors
- Generates deterministic sector information with proper CIDs and status
- Simulates deals and piece commitments within sectors
- Provides comprehensive sector lifecycle information matching real API format

### 4. Previously Implemented Methods

The following methods were previously implemented with simulation mode support:

- **client_retrieve**: Simulates retrieving content from the Filecoin network
- **client_find_data**: Simulates finding content on the Filecoin network
- **client_list_deals**: Simulates listing all deals made by the client
- **client_start_deal**: Simulates starting a storage deal with a miner
- **client_deal_info**: Simulates getting information about a specific deal
- **client_import**: Simulates importing content to Filecoin
- **market_list_storage_deals**: Simulates listing storage deals from the market
- **market_list_retrieval_deals**: Simulates listing retrieval deals from the market
- **market_get_deal_updates**: Simulates getting updates on deals in the market

### 5. Newly Implemented Methods

In this implementation, we have added simulation mode support for the following key methods:

1. **wallet_balance**: Simulates checking wallet balances with deterministic FIL amounts
2. **paych_list** and **paych_status**: Simulates payment channel management for Filecoin's off-chain payments
3. **miner_list_sectors** and **miner_sector_status**: Simulates sector management for storage providers
4. **client_list_imports**: Simulates listing all content imported to Filecoin with proper metadata

These methods provide essential functionality for testing Filecoin operations without requiring a real Lotus daemon.

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