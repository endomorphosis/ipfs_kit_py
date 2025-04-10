import requests; r = requests.get("http://127.0.0.1:9999/api/v0/mcp/health"); print(f"Status: {r.status_code}, Content: {r.text}")
