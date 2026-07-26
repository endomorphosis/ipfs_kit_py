"""
This file contains simulation mode implementations for lotus_kit.py methods.
The code should be carefully integrated into the respective methods in lotus_kit.py.
"""

# Implementation for paych_voucher_create simulation mode
# Insert after the amount_attoFIL conversion and before the API call
def paych_voucher_create_simulation(self, ch_addr, amount_attoFIL, lane, operation, result):
    """Simulation logic for paych_voucher_create method."""
    try:
        # Validate inputs
        if not ch_addr:
            return handle_error(result, ValueError("Payment channel address is required"))
        if not amount_attoFIL:
            return handle_error(result, ValueError("Voucher amount is required"))
        
        # Create deterministic voucher for consistent testing
        # Generate a deterministic voucher ID based on channel address, amount, and lane
        import hashlib
        import time
        
        voucher_id = hashlib.sha256(f"{ch_addr}_{amount_attoFIL}_{lane}".encode()).hexdigest()
        
        # Create a simulated voucher and signature
        timestamp = time.time()
        nonce = int(timestamp * 1000) % 1000000  # Simple nonce generation
        
        # Create voucher structure - follows Filecoin PaymentVoucher format
        simulated_voucher = {
            "ChannelAddr": ch_addr,
            "TimeLockMin": 0,
            "TimeLockMax": 0,
            "SecretPreimage": "",
            "Extra": None,
            "Lane": lane,
            "Nonce": nonce,
            "Amount": amount_attoFIL,
            "MinSettleHeight": 0,
            "Merges": [],
            "Signature": {
                "Type": 1,  # Secp256k1 signature type
                "Data": "Simulated" + voucher_id[:88]  # 44 byte simulated signature
            }
        }
        
        # Store in simulation cache for voucher_list and voucher_check
        if "vouchers" not in self.sim_cache:
            self.sim_cache["vouchers"] = {}
        
        if ch_addr not in self.sim_cache["vouchers"]:
            self.sim_cache["vouchers"][ch_addr] = []
        
        # Add to channel's vouchers if not already present
        voucher_exists = False
        for v in self.sim_cache["vouchers"][ch_addr]:
            if v["Lane"] == lane and v["Nonce"] == nonce:
                voucher_exists = True
                break
        
        if not voucher_exists:
            self.sim_cache["vouchers"][ch_addr].append(simulated_voucher)
        
        # Create result
        result["success"] = True
        result["simulated"] = True
        result["result"] = {
            "Voucher": simulated_voucher,
            "Shortfall": "0"  # No shortfall in simulation
        }
        return result
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Error in simulated paych_voucher_create: {str(e)}")
        return handle_error(result, e, f"Error in simulated paych_voucher_create: {str(e)}")


# Implementation for paych_voucher_list simulation mode
# Insert before the API call
def paych_voucher_list_simulation(self, ch_addr, operation, result):
    """Simulation logic for paych_voucher_list method."""
    try:
        # Validate input
        if not ch_addr:
            return handle_error(result, ValueError("Payment channel address is required"))
        
        # Initialize vouchers dictionary if not exists
        if "vouchers" not in self.sim_cache:
            self.sim_cache["vouchers"] = {}
        
        # Return empty list if no vouchers for this channel
        if ch_addr not in self.sim_cache["vouchers"]:
            result["success"] = True
            result["simulated"] = True
            result["result"] = []
            return result
        
        # Return list of vouchers for this channel
        result["success"] = True
        result["simulated"] = True
        result["result"] = self.sim_cache["vouchers"][ch_addr]
        return result
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Error in simulated paych_voucher_list: {str(e)}")
        return handle_error(result, e, f"Error in simulated paych_voucher_list: {str(e)}")


# Implementation for paych_voucher_check simulation mode
# Insert before the API call
def paych_voucher_check_simulation(self, ch_addr, voucher, operation, result):
    """Simulation logic for paych_voucher_check method."""
    try:
        # Validate inputs
        if not ch_addr:
            return handle_error(result, ValueError("Payment channel address is required"))
        if not voucher:
            return handle_error(result, ValueError("Voucher is required"))
        
        # Initialize vouchers dictionary if not exists
        if "vouchers" not in self.sim_cache:
            self.sim_cache["vouchers"] = {}
        
        # Parse voucher (in real implementation, this would decode serialized voucher)
        # For simulation, assume voucher is already a dictionary
        if isinstance(voucher, str):
            # Very basic parsing for simulation
            voucher_dict = {"ChannelAddr": ch_addr, "Signature": {"Data": voucher}}
        else:
            voucher_dict = voucher
        
        # Check if this voucher exists in our cache
        voucher_found = False
        if ch_addr in self.sim_cache["vouchers"]:
            for v in self.sim_cache["vouchers"][ch_addr]:
                # In a real implementation, more comprehensive matching would be needed
                if v.get("Signature", {}).get("Data", "") == voucher_dict.get("Signature", {}).get("Data", ""):
                    voucher_found = True
                    # Return the stored voucher amount
                    result["success"] = True
                    result["simulated"] = True
                    result["result"] = {"Amount": v.get("Amount", "0")}
                    return result
        
        # If voucher not found, return dummy result (in real world would be an error)
        result["success"] = True
        result["simulated"] = True
        result["result"] = {"Amount": "0"}
        return result
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Error in simulated paych_voucher_check: {str(e)}")
        return handle_error(result, e, f"Error in simulated paych_voucher_check: {str(e)}")