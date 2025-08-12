# MCP Dashboard UI Hints

The dashboard can render friendlier, schema-driven forms for MCP tools by loading an optional hints file from:

- ~/.ipfs_kit/ui/tool_hints.json

When present, the dashboard fetches it at GET /api/ui/hints and uses it to:
- Show per-tool descriptions
- Provide placeholders and defaults
- Render enum fields as <select>
- Resize JSON textareas

## File format

```
{
  "tools": {
    "<toolName>": {
      "description": "Short help text shown above the form.",
      "fields": {
        "<argName>": {
          "placeholder": "hint shown in input",
          "default": "value used to prefill",
          "enum": ["one", "two", "three"],
          "rows": 120
        }
      }
    }
  }
}
```

Notes:
- enum renders a <select> and ignores placeholder/rows.
- rows sets the height of JSON textareas (object/array args).
- defaults are applied once when the form renders (you can still edit values or load presets).

## Example

Below is a concise example that improves common flows.

```
{
  "tools": {
    "create_bucket": {
      "description": "Create a new bucket bound to a backend.",
      "fields": {
        "name": { "placeholder": "bucket name" },
        "backend": { "enum": ["local", "ipfs"], "default": "local", "placeholder": "select backend" }
      }
    },
    "create_backend": {
      "description": "Register a backend by name with a config object.",
      "fields": {
        "name": { "placeholder": "backend name" },
        "config": { "placeholder": "{\n  \"type\": \"ipfs\",\n  \"host\": \"127.0.0.1\"\n}", "rows": 160 }
      }
    },
    "files_write": {
      "description": "Write content to a VFS file.",
      "fields": {
        "path": { "placeholder": "./notes.txt" },
        "mode": { "enum": ["text", "hex"], "default": "text" },
        "content": { "placeholder": "file content (text or hex)", "rows": 160 }
      }
    }
  }
}
```

## How to apply

1. Create the folder if needed: ~/.ipfs_kit/ui/
2. Save your JSON to ~/.ipfs_kit/ui/tool_hints.json
3. Refresh the dashboard. The Tool Runner will render with your hints.

Tip: Keep a copy under version control (e.g., tool_hints.sample.json in this repo) and sync it to your home when needed.
