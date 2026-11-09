#!/usr/bin/env python3
"""
Generate sample log entries for testing the dashboard logs display.
"""

import time
import logging
import random
from datetime import datetime

# Setup logging to send to the dashboard
logger = logging.getLogger("test_log_generator")
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

# Different log sources and messages
BACKENDS = ['ipfs', 'ipfs_cluster', 'lotus', 'storacha', 'gdrive', 'dashboard', 'mcp', 'daemon']
LEVELS = [logging.INFO, logging.DEBUG, logging.WARNING, logging.ERROR]
MESSAGES = {
    'ipfs': [
        'Node connectivity established',
        'Peer discovery active', 
        'Content routing enabled',
        'DHT query completed',
        'Block retrieved from network',
        'Pinning operation completed'
    ],
    'ipfs_cluster': [
        'Consensus algorithm active',
        'Pin management ready',
        'Cluster service started',
        'Peer synchronization completed',
        'Pin replication in progress',
        'Cluster health check passed'
    ],
    'lotus': [
        'Lotus daemon connected',
        'Blockchain sync in progress', 
        'Storage deal created',
        'Mining operation active',
        'Chain head updated',
        'Wallet balance updated'
    ],
    'storacha': [
        'Storage backend ready',
        'Upload operation completed',
        'Retrieval request processed',
        'Cache updated',
        'File indexed successfully',
        'Storage verification passed'
    ],
    'gdrive': [
        'Google Drive API connected',
        'File upload to Drive completed',
        'Drive folder synchronized',
        'Permission check passed',
        'Quota status verified',
        'Backup operation finished'
    ],
    'dashboard': [
        'WebSocket connection established',
        'User interface ready',
        'Data refresh completed',
        'Dashboard page accessed',
        'API request processed',
        'Configuration updated'
    ],
    'mcp': [
        'JSON-RPC endpoint active',
        'Tool registry initialized',
        'Server components loaded',
        'Request processed successfully',
        'Method call executed',
        'Response sent to client'
    ],
    'daemon': [
        'Background services initialized',
        'Health monitoring active',
        'Process started',
        'Cleanup operation completed',
        'Status check performed',
        'Service restart completed'
    ]
}

def generate_log_entry():
    """Generate a random log entry."""
    backend = random.choice(BACKENDS)
    level = random.choice(LEVELS)
    message = random.choice(MESSAGES[backend])
    
    # Add some random details
    if random.random() < 0.3:
        details = [
            f"({random.randint(10, 999)}ms)",
            f"[{random.randint(1, 100)} items]",
            f"(size: {random.randint(1, 999)}KB)",
            f"[peer: {random.randint(1000, 9999)}]",
            f"(retry {random.randint(1, 3)})"
        ]
        message += f" {random.choice(details)}"
    
    # Create logger for this backend
    backend_logger = logging.getLogger(backend)
    backend_logger.setLevel(logging.DEBUG)
    if not backend_logger.handlers:
        backend_logger.addHandler(handler)
    
    backend_logger.log(level, message)

def main():
    """Main log generation loop."""
    print("🚀 Starting log generator for dashboard testing...")
    print("📊 Generating logs every 2-5 seconds...")
    print("🛑 Press Ctrl+C to stop")
    
    try:
        while True:
            # Generate 1-3 log entries
            num_entries = random.randint(1, 3)
            for _ in range(num_entries):
                generate_log_entry()
            
            # Wait 2-5 seconds before next batch
            time.sleep(random.uniform(2, 5))
            
    except KeyboardInterrupt:
        print("\n✅ Log generator stopped")

if __name__ == "__main__":
    main()
