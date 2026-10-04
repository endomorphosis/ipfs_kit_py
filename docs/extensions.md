# Extending IPFS Kit

`ipfs-kit-py` provides an extension mechanism that allows developers to add custom functionality or integrate third-party services seamlessly into the main `IPFSSimpleAPI` or `IPFSKit` objects. This promotes modularity and allows tailoring the kit to specific needs.

## Overview

Extensions are typically Python classes that encapsulate a specific set of functionalities. They are registered with the core IPFS Kit instance, making their methods callable directly through the kit object or via a dedicated `call_extension` method.

**Key Concepts:**

*   **Extension Class**: A Python class inheriting from a base class (e.g., `PluginBase` defined in `high_level_api.py` or a similar convention) or following a specific interface. It receives the main kit instance during initialization, allowing it to access core IPFS functionality, configuration, and other components.
*   **Registration**: The `register_extension` method (likely on `IPFSSimpleAPI` or `IPFSKit`) is used to add an instance of an extension class to the kit. The extension is usually given a unique name.
*   **Invocation**: Registered extension methods can be called:
    *   Directly: `kit.my_extension_method(...)` if the kit dynamically adds registered methods to its namespace.
    *   Via a dispatcher: `kit.call_extension('extension_name', 'method_name', ...)` or `kit('extension_name.method_name', ...)`. The exact mechanism depends on the implementation in `high_level_api.py`.

## Creating an Extension

1.  **Define the Extension Class**:
    ```python
    # Example: my_custom_extension.py
    from ipfs_kit_py.high_level_api import PluginBase # Assuming PluginBase exists

    class MyCustomExtension(PluginBase):
        def __init__(self, ipfs_kit, config=None):
            super().__init__(ipfs_kit, config)
            self.api_key = config.get('api_key') if config else None
            self.service_url = config.get('service_url', 'https://api.example.com')
            # Use self.ipfs_kit to access core kit functionality if needed
            # e.g., self.ipfs_kit.add(...)

        def get_name(self):
            """Returns the unique name of the extension."""
            return "my_custom_service"

        def get_version(self):
            """Returns the version of the extension."""
            return "1.0.0"

        def perform_custom_action(self, data: dict) -> dict:
            """An example method provided by the extension."""
            if not self.api_key:
                return {"success": False, "error": "API key not configured"}

            print(f"Performing custom action with data: {data}")
            # Example: Interact with an external service
            # response = requests.post(
            #     f"{self.service_url}/action",
            #     headers={"Authorization": f"Bearer {self.api_key}"},
            #     json=data
            # )
            # response.raise_for_status()
            # return {"success": True, "result": response.json()}

            # Placeholder result
            return {"success": True, "result": f"Action performed on {data.get('item')}"}

        def get_service_status(self) -> dict:
             """Another example method."""
             # Placeholder
             return {"success": True, "status": "OK", "url": self.service_url}

    ```
2.  **Configure the Extension**: Add configuration for your extension in the main `ipfs-kit-py` config file or dictionary, typically under a dedicated key matching the extension's name or a general `extensions` key.
    ```python
    # Example configuration snippet
    config = {
        'extensions': {
            'my_custom_service': { # Matches get_name()
                'enabled': True,
                'api_key': 'YOUR_API_KEY_HERE', # Load securely!
                'service_url': 'https://custom.example.com/api'
            }
            # Potentially other extensions
        },
        # ... other ipfs-kit-py config
    }
    ```
3.  **Register the Extension**: This might happen automatically during kit initialization if extensions are defined in the config, or you might need to register manually.
    ```python
    from ipfs_kit_py.high_level_api import IPFSSimpleAPI
    from my_custom_extension import MyCustomExtension # Import your class

    kit = IPFSSimpleAPI(config=config)

    # Manual Registration (if not automatic via config)
    # extension_config = config.get('extensions', {}).get('my_custom_service', {})
    # if extension_config.get('enabled'):
    #     my_extension = MyCustomExtension(kit, extension_config)
    #     kit.register_extension(my_extension) # Assuming register_extension method exists

    ```

## Using the Extension

Once registered, call the extension's methods. The exact syntax depends on the implementation in `high_level_api.py`. Check the `__call__` method or look for dynamically added attributes.

```python
# Option A: Direct method call (if dynamically added)
# status_result = kit.get_service_status()
# action_result = kit.perform_custom_action(data={"item": "test"})

# Option B: Using a dispatcher method like __call__
status_result = kit('my_custom_service.get_service_status')
action_result = kit('my_custom_service.perform_custom_action', data={"item": "test"})

# Option C: Using a dedicated call_extension method
# status_result = kit.call_extension('my_custom_service', 'get_service_status')
# action_result = kit.call_extension('my_custom_service', 'perform_custom_action', data={"item": "test"})


print(f"Service Status: {status_result}")
print(f"Custom Action Result: {action_result}")
```

## Benefits

*   **Modularity**: Keep core `ipfs-kit-py` clean while adding specialized features.
*   **Reusability**: Share extensions across different projects.
*   **Customization**: Tailor the kit's capabilities to specific application needs.
*   **Integration**: Easily integrate third-party services or custom logic.

## Considerations

*   **Naming Conflicts**: Ensure extension names and method names are unique to avoid conflicts.
*   **Dependency Management**: Extensions might introduce additional dependencies. Manage these appropriately (e.g., using `extras_require` in `setup.py`).
*   **API Stability**: Changes in the core `ipfs-kit-py` API might require updates to extensions.
*   **Discovery**: How extensions are discovered and loaded (e.g., via configuration, entry points) should be clearly defined by the core library.
