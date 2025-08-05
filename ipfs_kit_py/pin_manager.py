import json
from pathlib import Path

IPFS_KIT_PATH = Path.home() / '.ipfs_kit'
PINS_PATH = IPFS_KIT_PATH / 'pins.json'

class PinManager:
    def __init__(self):
        if not PINS_PATH.exists():
            with open(PINS_PATH, 'w') as f:
                json.dump([], f)

    def list_pins(self):
        with open(PINS_PATH, 'r') as f:
            return json.load(f)

    def add_pin(self, cid, name=''):
        pins = self.list_pins()
        pins.append({"cid": cid, "name": name})
        with open(PINS_PATH, 'w') as f:
            json.dump(pins, f, indent=2)
        return {"status": "Pin added"}

    def remove_pin(self, cid):
        pins = self.list_pins()
        pins = [p for p in pins if p['cid'] != cid]
        with open(PINS_PATH, 'w') as f:
            json.dump(pins, f, indent=2)
        return {"status": "Pin removed"}