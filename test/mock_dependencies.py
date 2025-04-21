"""
Comprehensive mock system for FastAPI and other dependencies.

This module provides mock implementations for commonly used external
dependencies to allow tests to run without the actual packages installed.
"""

import sys
import json
import logging
import types
from typing import Dict, Any, List, Optional, Union, Callable, Type, Awaitable

logger = logging.getLogger(__name__)

# Dictionary to store mock modules
MOCK_MODULES = {}

# Mock classes and functions
class WebSocket:
    """Mock WebSocket implementation for testing."""
    
    def __init__(self):
        self.accepted = False
        self.closed = False
        self.sent_messages = []
        self.received_messages = []
        self.client_state = "CONNECTING"
        self.headers = {}
        self.query_params = {}
        self.path_params = {}
        self.cookies = {}
        
    async def accept(self):
        """Accept the WebSocket connection."""
        self.accepted = True
        self.client_state = "CONNECTED"
        logger.info("WebSocket connection accepted")
        return True
        
    async def close(self, code: int = 1000):
        """Close the WebSocket connection."""
        self.closed = True
        self.client_state = "DISCONNECTED"
        logger.info(f"WebSocket connection closed with code {code}")
        return True
        
    async def send_text(self, data: str):
        """Send text data to the client."""
        self.sent_messages.append({"type": "text", "data": data})
        logger.info(f"Sent text message: {data}")
        return True
        
    async def send_json(self, data: Dict[str, Any]):
        """Send JSON data to the client."""
        text_data = json.dumps(data)
        self.sent_messages.append({"type": "json", "data": data})
        logger.info(f"Sent JSON message: {data}")
        return True
        
    async def send_bytes(self, data: bytes):
        """Send binary data to the client."""
        self.sent_messages.append({"type": "bytes", "data": data})
        logger.info(f"Sent binary message: {len(data)} bytes")
        return True
        
    async def receive_text(self):
        """Receive text data from the client."""
        if not self.received_messages:
            return ""
        msg = self.received_messages.pop(0)
        if isinstance(msg, str):
            return msg
        elif isinstance(msg, dict):
            return json.dumps(msg)
        elif isinstance(msg, bytes):
            return msg.decode("utf-8")
        return str(msg)
        
    async def receive_json(self):
        """Receive JSON data from the client."""
        if not self.received_messages:
            return {}
        msg = self.received_messages.pop(0)
        if isinstance(msg, str):
            return json.loads(msg)
        elif isinstance(msg, dict):
            return msg
        elif isinstance(msg, bytes):
            return json.loads(msg.decode("utf-8"))
        return {}
        
    async def receive_bytes(self):
        """Receive binary data from the client."""
        if not self.received_messages:
            return b""
        msg = self.received_messages.pop(0)
        if isinstance(msg, str):
            return msg.encode("utf-8")
        elif isinstance(msg, dict):
            return json.dumps(msg).encode("utf-8")
        elif isinstance(msg, bytes):
            return msg
        return str(msg).encode("utf-8")

class WebSocketDisconnect(Exception):
    """Exception raised when WebSocket connection is closed."""
    
    def __init__(self, code: int = 1000):
        self.code = code
        super().__init__(f"WebSocket disconnected with code {code}")

class FastAPI:
    """Mock FastAPI implementation for testing."""
    
    def __init__(self, **kwargs):
        self.routes = []
        self.router = Router()
        self.middleware = []
        self.dependencies = {}
        self.exception_handlers = {}
        self.title = kwargs.get("title", "FastAPI")
        self.description = kwargs.get("description", "")
        self.version = kwargs.get("version", "0.1.0")
        self.openapi_url = kwargs.get("openapi_url", "/openapi.json")
        self.docs_url = kwargs.get("docs_url", "/docs")
        self.redoc_url = kwargs.get("redoc_url", "/redoc")
        self.state = SimpleNamespace()
        
    def get(self, path, **kwargs):
        """Register a GET route."""
        def decorator(func):
            self.routes.append(Route(path, func, methods=["GET"]))
            return func
        return decorator
        
    def post(self, path, **kwargs):
        """Register a POST route."""
        def decorator(func):
            self.routes.append(Route(path, func, methods=["POST"]))
            return func
        return decorator
        
    def put(self, path, **kwargs):
        """Register a PUT route."""
        def decorator(func):
            self.routes.append(Route(path, func, methods=["PUT"]))
            return func
        return decorator
        
    def delete(self, path, **kwargs):
        """Register a DELETE route."""
        def decorator(func):
            self.routes.append(Route(path, func, methods=["DELETE"]))
            return func
        return decorator
        
    def websocket(self, path):
        """Register a WebSocket route."""
        def decorator(func):
            self.routes.append(WebSocketRoute(path, func))
            return func
        return decorator
        
    def exception_handler(self, exc_class_or_status_code):
        """Register an exception handler."""
        def decorator(func):
            self.exception_handlers[exc_class_or_status_code] = func
            return func
        return decorator
        
    def middleware(self, middleware_type):
        """Register middleware."""
        def decorator(func):
            self.middleware.append((middleware_type, func))
            return func
        return decorator
        
    def include_router(self, router, **kwargs):
        """Include routes from another router."""
        for route in router.routes:
            if kwargs.get("prefix"):
                route.path = kwargs["prefix"] + route.path
            self.routes.append(route)

class SimpleNamespace:
    """Simple namespace for storing attributes."""
    pass

class Router:
    """Mock router implementation for testing."""
    
    def __init__(self):
        self.routes = []
        self.dependencies = {}
        self.prefix = ""
        self.tags = []
        self.on_startup = []
        self.on_shutdown = []
        
    def get(self, path, **kwargs):
        """Register a GET route."""
        def decorator(func):
            self.routes.append(Route(path, func, methods=["GET"]))
            return func
        return decorator
        
    def post(self, path, **kwargs):
        """Register a POST route."""
        def decorator(func):
            self.routes.append(Route(path, func, methods=["POST"]))
            return func
        return decorator
        
    def put(self, path, **kwargs):
        """Register a PUT route."""
        def decorator(func):
            self.routes.append(Route(path, func, methods=["PUT"]))
            return func
        return decorator
        
    def delete(self, path, **kwargs):
        """Register a DELETE route."""
        def decorator(func):
            self.routes.append(Route(path, func, methods=["DELETE"]))
            return func
        return decorator
        
    def websocket(self, path):
        """Register a WebSocket route."""
        def decorator(func):
            self.routes.append(WebSocketRoute(path, func))
            return func
        return decorator
        
    def include_router(self, router, **kwargs):
        """Include routes from another router."""
        for route in router.routes:
            if kwargs.get("prefix"):
                route.path = kwargs["prefix"] + route.path
            self.routes.append(route)
            
    def add_event_handler(self, event, func):
        """Add an event handler."""
        if event == "startup":
            self.on_startup.append(func)
        elif event == "shutdown":
            self.on_shutdown.append(func)

class APIRouter(Router):
    """Mock APIRouter implementation for testing."""
    pass

class Route:
    """Mock route implementation for testing."""
    
    def __init__(self, path, endpoint, methods=None):
        self.path = path
        self.endpoint = endpoint
        self.methods = methods or ["GET"]
        self.dependencies = []
        self.tags = []
        
class WebSocketRoute(Route):
    """Mock WebSocket route implementation for testing."""
    
    def __init__(self, path, endpoint):
        super().__init__(path, endpoint, methods=None)
        
# Create mock modules
        
# fastapi module
fastapi_module = types.ModuleType("fastapi")
fastapi_module.FastAPI = FastAPI
fastapi_module.APIRouter = APIRouter
fastapi_module.WebSocket = WebSocket
fastapi_module.WebSocketDisconnect = WebSocketDisconnect
fastapi_module.__version__ = "0.100.0"  # Mock version

# fastapi.middleware module
middleware_module = types.ModuleType("fastapi.middleware")
middleware_module.Middleware = type("Middleware", (), {"__init__": lambda self, cls, **options: None})

# fastapi.middleware.cors module
cors_module = types.ModuleType("fastapi.middleware.cors")
cors_module.CORSMiddleware = type("CORSMiddleware", (), {"__init__": lambda self, **kwargs: None})

# fastapi.responses module
responses_module = types.ModuleType("fastapi.responses")
responses_module.JSONResponse = type("JSONResponse", (), {
    "__init__": lambda self, content, status_code=200, headers=None: None,
    "body": property(lambda self: "")
})
responses_module.StreamingResponse = type("StreamingResponse", (), {
    "__init__": lambda self, content, status_code=200, headers=None: None,
    "body_iterator": property(lambda self: [])
})
responses_module.Response = type("Response", (), {
    "__init__": lambda self, content="", status_code=200, headers=None, media_type=None: None,
    "body": property(lambda self: "")
})

# fastapi.websockets module
websockets_module = types.ModuleType("fastapi.websockets")
websockets_module.WebSocketDisconnect = WebSocketDisconnect

# fastapi.testclient module
testclient_module = types.ModuleType("fastapi.testclient")
testclient_module.TestClient = type("TestClient", (), {
    "__init__": lambda self, app: None,
    "get": lambda self, url, **kwargs: None,
    "post": lambda self, url, **kwargs: None,
    "put": lambda self, url, **kwargs: None,
    "delete": lambda self, url, **kwargs: None,
    "websocket_connect": lambda self, url, **kwargs: None
})

# Register modules
MOCK_MODULES["fastapi"] = fastapi_module
MOCK_MODULES["fastapi.middleware"] = middleware_module
MOCK_MODULES["fastapi.middleware.cors"] = cors_module
MOCK_MODULES["fastapi.responses"] = responses_module
MOCK_MODULES["fastapi.websockets"] = websockets_module
MOCK_MODULES["fastapi.testclient"] = testclient_module

# fsspec module
fsspec_module = types.ModuleType("fsspec")
fsspec_module.__version__ = "2023.4.0"

# fsspec.registry module
registry_module = types.ModuleType("fsspec.registry")
registry_module.known_implementations = {}
registry_module.register_implementation = lambda protocol, cls, clobber=False: None
registry_module.get_filesystem_class = lambda protocol: None

# fsspec.spec module
spec_module = types.ModuleType("fsspec.spec")

# Create abstract filesystem class
class AbstractFileSystem:
    protocol = "abstract"
    
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
    
    def ls(self, path, detail=True, **kwargs):
        return []
    
    def info(self, path, **kwargs):
        return {"name": path, "size": 0, "type": "file"}
    
    def open(self, path, mode="rb", **kwargs):
        return None

# Add class to spec module
spec_module.AbstractFileSystem = AbstractFileSystem

# Register modules
MOCK_MODULES["fsspec"] = fsspec_module
MOCK_MODULES["fsspec.registry"] = registry_module
MOCK_MODULES["fsspec.spec"] = spec_module

# networkx module
networkx_module = types.ModuleType("networkx")
networkx_module.__version__ = "3.1"

# Basic graph class
class Graph:
    def __init__(self, *args, **kwargs):
        self.nodes = {}
        self.edges = {}
        
    def add_node(self, node, **attrs):
        self.nodes[node] = attrs
        
    def add_edge(self, u, v, **attrs):
        if u not in self.nodes:
            self.add_node(u)
        if v not in self.nodes:
            self.add_node(v)
        self.edges[(u, v)] = attrs
        
    def neighbors(self, node):
        return [v for u, v in self.edges if u == node]
        
    def __iter__(self):
        return iter(self.nodes)

# Add to networkx module
networkx_module.Graph = Graph
networkx_module.DiGraph = Graph  # Use same implementation for simplicity
networkx_module.MultiGraph = Graph
networkx_module.MultiDiGraph = Graph

MOCK_MODULES["networkx"] = networkx_module
MOCK_MODULES["nx"] = networkx_module  # Common alias

# Custom module finder for mock modules
class MockFinder(type(sys.meta_path[0])):  # Inherit from a real meta path finder
    """
    Custom module finder for mocking dependencies.
    """
    
    def find_spec(self, fullname, path, target=None):
        if fullname in MOCK_MODULES:
            logger.info(f"Using mock implementation for {fullname}")
            return types.ModuleSpec(
                fullname, 
                MockLoader(fullname),
                is_package=fullname.rsplit(".", 1)[-1] == "__init__" if "." in fullname else True
            )
        return None

class MockLoader:
    """
    Custom module loader for mock implementations.
    """
    
    def __init__(self, fullname):
        self.fullname = fullname
    
    def create_module(self, spec):
        if self.fullname in MOCK_MODULES:
            return MOCK_MODULES[self.fullname]
        return None
    
    def exec_module(self, module):
        # The module is already initialized in create_module
        pass

# Install our mock finder at the start of sys.meta_path
sys.meta_path.insert(0, MockFinder())

def apply_additional_patches():
    """Apply additional patches to specific modules."""
    # Patch huggingface_hub imports if needed
    if "huggingface_hub" not in sys.modules:
        huggingface_module = types.ModuleType("huggingface_hub")
        huggingface_module.__version__ = "0.15.0"
        sys.modules["huggingface_hub"] = huggingface_module

    # Patch any other specific modules as needed
    
    logger.info("Applied additional patches to system modules")
    return True

# Apply additional patches
apply_additional_patches()