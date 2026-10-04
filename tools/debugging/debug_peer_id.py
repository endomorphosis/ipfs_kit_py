#!/usr/bin/env python3
"""
Debug script to understand the structure of 12D3KooW peer IDs
"""

try:
    import base58
    
    # A known valid peer ID that starts with 12D3KooW
    known_peer_id = "12D3KooWBhSxVRxGtjFbz9bHG2Y5vGSj7j6qbNNGotKoWiNKhKCF"
    
    print(f"Known peer ID: {known_peer_id}")
    print(f"Length: {len(known_peer_id)}")
    
    # Decode it to see the structure
    decoded = base58.b58decode(known_peer_id).hex()
    print(f"Decoded hex: {decoded}")
    print(f"Decoded bytes: {[hex(b) for b in base58.b58decode(known_peer_id)]}")
    
    # Let's try to understand the pattern
    decoded_bytes = base58.b58decode(known_peer_id)
    print(f"First few bytes: {[hex(b) for b in decoded_bytes[:10]]}")
    
except ImportError:
    print("base58 not available")
    
    # Manual base58 decode to analyze a known good peer ID
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    
    def manual_decode(s):
        """Manual base58 decode"""
        decoded = 0
        multi = 1
        for char in reversed(s):
            decoded += multi * alphabet.index(char)
            multi *= 58
        
        # Convert to bytes
        h = hex(decoded)[2:]
        if len(h) % 2:
            h = '0' + h
        return bytes.fromhex(h)
    
    known_peer_id = "12D3KooWBhSxVRxGtjFbz9bHG2Y5vGSj7j6qbNNGotKoWiNKhKCF"
    try:
        decoded = manual_decode(known_peer_id)
        print(f"Manual decoded: {[hex(b) for b in decoded[:10]]}")
    except Exception as e:
        print(f"Manual decode failed: {e}")
