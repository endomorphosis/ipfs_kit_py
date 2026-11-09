import logging
logger = logging.getLogger("vfs-tools")

def register_vfs_tools(server):
    """Register basic VFS tools with the MCP server."""
    logger.info("Starting VFS tool registration")
    try:
        async def vfs_read(path: str):
            try:
                with open(path, 'r') as file:
                    return file.read()
            except Exception as e:
                return {"error": str(e)}
                
        async def vfs_write(path: str, content: str):
            try:
                with open(path, 'w') as file:
                    file.write(content)
                return {"success": True}
            except Exception as e:
                return {"error": str(e)}

        async def vfs_ls(path: str):
            try:
                import os
                return os.listdir(path)
            except Exception as e:
                return {"error": str(e)}

        async def vfs_mkdir(path: str):
            try:
                import os
                os.makedirs(path, exist_ok=True)
                return {"success": True}
            except Exception as e:
                return {"error": str(e)}

        server.tool("vfs_read", description="Read content from a VFS path")(vfs_read)
        server.tool("vfs_write", description="Write content to a VFS path")(vfs_write)
        server.tool("vfs_ls", description="List files in a VFS directory")(vfs_ls)
        server.tool("vfs_mkdir", description="Create a VFS directory")(vfs_mkdir)

        logger.info("Registered basic VFS tools")
        return True
    except Exception as e:
        logger.error(f"Error registering VFS tools: {e}")
        return False
