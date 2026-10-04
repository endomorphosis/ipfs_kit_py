"""
Enhanced IPFS operations extension for MCP server.

This module adds additional IPFS operations that are currently missing from
the MCP server, including DHT, object, and DAG manipulation commands.
"""

import json
import logging
import os
import subprocess
import tempfile

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import Response, StreamingResponse

# Configure logging
logger = logging.getLogger(__name__)


def create_ipfs_router(api_prefix: str) -> APIRouter:
    """
    Create a FastAPI router with enhanced IPFS endpoints.

    Args:
        api_prefix: The API prefix for the endpoints

    Returns:
        FastAPI router
    """
    router = APIRouter(prefix=f"{api_prefix}/ipfs")

    # IPFS Object Commands

    @router.post("/object/new")
    async def ipfs_object_new(template: str = Form("unixfs-dir")):
        """
        Create a new object from an IPFS template.

        Args:
            template: The template to use (e.g., 'unixfs-dir')
        """
        result = run_ipfs_command(["object", "new", template])
        if result["success"]:
            try:
                cid = result["output"].decode("utf-8").strip()
                return {"success": True, "cid": cid, "template": template}
            except Exception as e:
                logger.error(f"Error parsing object new result: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": result["error"]}

    @router.post("/object/patch/add-link")
    async def ipfs_object_patch_add_link(
        cid: str = Form(...), name: str = Form(...), link_cid: str = Form(...)
    ):
        """
        Add a link to an IPFS object.

        Args:
            cid: The CID of the object to patch
            name: The name of the link
            link_cid: The CID to link to
        """
        result = run_ipfs_command(["object", "patch", "add-link", cid, name, link_cid])
        if result["success"]:
            try:
                new_cid = result["output"].decode("utf-8").strip()
                return {
                    "success": True,
                    "cid": new_cid,
                    "original_cid": cid,
                    "link_name": name,
                    "link_cid": link_cid,
                }
            except Exception as e:
                logger.error(f"Error parsing add-link result: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": result["error"]}

    @router.post("/object/patch/rm-link")
    async def ipfs_object_patch_rm_link(cid: str = Form(...), name: str = Form(...)):
        """
        Remove a link from an IPFS object.

        Args:
            cid: The CID of the object to patch
            name: The name of the link to remove
        """
        result = run_ipfs_command(["object", "patch", "rm-link", cid, name])
        if result["success"]:
            try:
                new_cid = result["output"].decode("utf-8").strip()
                return {
                    "success": True,
                    "cid": new_cid,
                    "original_cid": cid,
                    "removed_link": name,
                }
            except Exception as e:
                logger.error(f"Error parsing rm-link result: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": result["error"]}

    @router.get("/object/get/{cid}")
    async def ipfs_object_get(cid: str):
        """
        Get the DAG node for an IPFS object.

        Args:
            cid: The CID of the object to get
        """
        result = run_ipfs_command(["object", "get", cid])
        if result["success"]:
            try:
                # Parse the JSON output
                data = json.loads(result["output"])
                return {"success": True, "cid": cid, "data": data}
            except Exception as e:
                logger.error(f"Error parsing object get result: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": result["error"]}

    @router.get("/object/links/{cid}")
    async def ipfs_object_links(cid: str):
        """
        Get the links from an IPFS object.

        Args:
            cid: The CID of the object to get links from
        """
        result = run_ipfs_command(["object", "links", cid])
        if result["success"]:
            try:
                links_text = result["output"].decode("utf-8").strip()
                links = []

                for line in links_text.split("\n"):
                    if line:
                        parts = line.split(" ")
                        if len(parts) >= 2:
                            link_cid = parts[0]
                            # Handle names with spaces by joining the remaining parts
                            link_name = " ".join(parts[1:])
                            links.append({"cid": link_cid, "name": link_name})

                return {"success": True, "cid": cid, "links": links}
            except Exception as e:
                logger.error(f"Error parsing object links result: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": result["error"]}

    # IPFS DAG Commands

    @router.post("/dag/put")
    async def ipfs_dag_put(
        data: str = Form(...),
        input_codec: str = Form("dag-json"),
        store_codec: str = Form("dag-cbor"),
    ):
        """
        Add a DAG node to IPFS.

        Args:
            data: The DAG node data as a JSON string
            input_codec: The codec for the input data
            store_codec: The codec to use for storing the data
        """
        try:
            # Validate the JSON data
            json_data = json.loads(data)

            # Write data to temporary file
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
                json.dump(json_data, temp)
                temp_path = temp.name

            # Run the DAG put command
            result = run_ipfs_command(
                [
                    "dag",
                    "put",
                    "--input-codec",
                    input_codec,
                    "--store-codec",
                    store_codec,
                    temp_path,
                ]
            )

            # Clean up temporary file
            os.unlink(temp_path)

            if result["success"]:
                cid = result["output"].decode("utf-8").strip()
                return {
                    "success": True,
                    "cid": cid,
                    "input_codec": input_codec,
                    "store_codec": store_codec,
                }
            else:
                return {"success": False, "error": result["error"]}

        except json.JSONDecodeError as e:
            return {"success": False, "error": f"Invalid JSON data: {str(e)}"}
        except Exception as e:
            logger.error(f"Error in dag put: {e}")
            return {"success": False, "error": str(e)}

    @router.get("/dag/get/{cid}")
    async def ipfs_dag_get(cid: str):
        """
        Get a DAG node from IPFS.

        Args:
            cid: The CID of the DAG node to get
        """
        result = run_ipfs_command(["dag", "get", cid])
        if result["success"]:
            try:
                # Parse the JSON output
                data = json.loads(result["output"])
                return {"success": True, "cid": cid, "data": data}
            except Exception as e:
                logger.error(f"Error parsing dag get result: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": result["error"]}

    @router.post("/dag/import")
    async def ipfs_dag_import(file: UploadFile = File(...)):
        """
        Import a DAG from a .car file.

        Args:
            file: The .car file to import
        """
        try:
            # Save uploaded file to temp location
            with tempfile.NamedTemporaryFile(delete=False) as temp:
                content = await file.read()
                temp.write(content)
                temp_path = temp.name

            # Import the DAG
            result = run_ipfs_command(["dag", "import", temp_path])

            # Clean up temp file
            os.unlink(temp_path)

            if result["success"]:
                output_text = result["output"].decode("utf-8").strip()

                # Parse the output to get imported roots
                roots = []
                for line in output_text.split("\n"):
                    if "Imported" in line and "root" in line:
                        # Extract the CID from a line like "Imported root bafy2bzace..."
                        parts = line.split()
                        if len(parts) >= 3:
                            roots.append(parts[2])

                return {
                    "success": True,
                    "imported": True,
                    "roots": roots,
                    "original_filename": file.filename,
                }
            else:
                return {"success": False, "error": result["error"]}

        except Exception as e:
            logger.error(f"Error importing DAG: {e}")
            return {"success": False, "error": str(e)}

    @router.post("/dag/export")
    async def ipfs_dag_export(cid: str = Form(...)):
        """
        Export a DAG to a .car file.

        Args:
            cid: The root CID of the DAG to export
        """
        try:
            # Create a temporary file for the export
            with tempfile.NamedTemporaryFile(delete=False) as temp:
                temp_path = temp.name

            # Export the DAG
            result = run_ipfs_command(["dag", "export", cid], output_file=temp_path)

            if result["success"]:
                # Return the file as a streaming response
                def file_generator():
                    with open(temp_path, "rb") as f:
                        while chunk := f.read(8192):
                            yield chunk
                    # Clean up temp file after streaming
                    os.unlink(temp_path)

                return StreamingResponse(
                    file_generator(),
                    media_type="application/vnd.ipld.car",
                    headers={"Content-Disposition": f"attachment; filename={cid}.car"},
                )
            else:
                # Clean up temp file
                os.unlink(temp_path)
                return {"success": False, "error": result["error"]}

        except Exception as e:
            logger.error(f"Error exporting DAG: {e}")
            return {"success": False, "error": str(e)}

    # IPFS DHT Commands

    @router.get("/dht/findpeer/{peer_id}")
    async def ipfs_dht_findpeer(peer_id: str):
        """
        Find addresses for a peer ID using the DHT.

        Args:
            peer_id: The peer ID to find
        """
        result = run_ipfs_command(["dht", "findpeer", peer_id])
        if result["success"]:
            try:
                addresses = result["output"].decode("utf-8").strip().split("\n")
                return {"success": True, "peer_id": peer_id, "addresses": addresses}
            except Exception as e:
                logger.error(f"Error parsing DHT findpeer result: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": result["error"]}

    @router.get("/dht/findprovs/{cid}")
    async def ipfs_dht_findprovs(cid: str, num_providers: int = Query(20, gt=0, le=100)):
        """
        Find providers for a CID using the DHT.

        Args:
            cid: The CID to find providers for
            num_providers: Maximum number of providers to find
        """
        result = run_ipfs_command(["dht", "findprovs", "--num-providers", str(num_providers), cid])
        if result["success"]:
            try:
                providers = result["output"].decode("utf-8").strip().split("\n")
                # Filter out empty lines
                providers = [p for p in providers if p]
                return {
                    "success": True,
                    "cid": cid,
                    "providers": providers,
                    "count": len(providers),
                }
            except Exception as e:
                logger.error(f"Error parsing DHT findprovs result: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": result["error"]}

    @router.get("/dht/get/{key}")
    async def ipfs_dht_get(key: str):
        """
        Get a value from the DHT.

        Args:
            key: The key to get
        """
        result = run_ipfs_command(["dht", "get", key])
        if result["success"]:
            try:
                value = result["output"]
                # Return the raw value
                return Response(content=value, media_type="application/octet-stream")
            except Exception as e:
                logger.error(f"Error in DHT get: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": result["error"]}

    @router.post("/dht/put")
    async def ipfs_dht_put(key: str = Form(...), value: str = Form(...)):
        """
        Put a value into the DHT.

        Args:
            key: The key to store under
            value: The value to store
        """
        try:
            # Write value to temporary file
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp:
                temp.write(value)
                temp_path = temp.name

            # Run the DHT put command
            result = run_ipfs_command(["dht", "put", key, temp_path])

            # Clean up temporary file
            os.unlink(temp_path)

            if result["success"]:
                return {"success": True, "key": key, "stored": True}
            else:
                return {"success": False, "error": result["error"]}

        except Exception as e:
            logger.error(f"Error in DHT put: {e}")
            return {"success": False, "error": str(e)}

    # IPFS Name (IPNS) advanced commands

    @router.post("/name/pubsub/state")
    async def ipfs_name_pubsub_state(enabled: bool = Form(True)):
        """
        Enable or disable IPNS over pubsub.

        Args:
            enabled: Whether to enable IPNS over pubsub
        """
        state = "true" if enabled else "false"
        result = run_ipfs_command(["name", "pubsub", "state", "--enable", state])
        if result["success"]:
            try:
                output = result["output"].decode("utf-8").strip()
                return {"success": True, "enabled": enabled, "message": output}
            except Exception as e:
                logger.error(f"Error parsing name pubsub state result: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": result["error"]}

    @router.post("/key/gen")
    async def ipfs_key_gen(name: str = Form(...), type: str = Form("rsa"), size: int = Form(2048)):
        """
        Generate a new IPNS key.

        Args:
            name: The name of the key
            type: The type of key (rsa, ed25519)
            size: The key size in bits (for RSA)
        """
        args = ["key", "gen", "--type", type]
        if type == "rsa":
            args.extend(["--size", str(size)])
        args.append(name)

        result = run_ipfs_command(args)
        if result["success"]:
            try:
                key_id = result["output"].decode("utf-8").strip()
                return {
                    "success": True,
                    "name": name,
                    "id": key_id,
                    "type": type,
                    "size": size if type == "rsa" else None,
                }
            except Exception as e:
                logger.error(f"Error parsing key gen result: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": result["error"]}

    @router.get("/key/list")
    async def ipfs_key_list(
        long_format: bool = Query(False, description="Use long format"),
        ipns_base: str = Query(None, description="Encoding used for keys"),
    ):
        """
        List all IPNS keys.

        Args:
            long_format: Whether to use long format
            ipns_base: Base encoding for keys
        """
        args = ["key", "list", "--format", "<name>: <id>"]
        if long_format:
            args.append("--long_format")
        if ipns_base:
            args.extend(["--ipns-base", ipns_base])

        result = run_ipfs_command(args)
        if result["success"]:
            try:
                output = result["output"].decode("utf-8").strip()
                keys = []

                for line in output.split("\n"):
                    if line and ": " in line:
                        name, key_id = line.split(": ", 1)
                        keys.append({"name": name, "id": key_id})

                return {"success": True, "keys": keys, "count": len(keys)}
            except Exception as e:
                logger.error(f"Error parsing key list result: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": result["error"]}

    @router.post("/key/rm")
    async def ipfs_key_rm(name: str = Form(...)):
        """
        Remove an IPNS key.

        Args:
            name: The name of the key to remove
        """
        result = run_ipfs_command(["key", "rm", name])
        if result["success"]:
            try:
                output = result["output"].decode("utf-8").strip()
                # Output format: "removed QmXXX"
                key_id = output.split(" ", 1)[1] if " " in output else output
                return {"success": True, "name": name, "id": key_id, "removed": True}
            except Exception as e:
                logger.error(f"Error parsing key rm result: {e}")
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": result["error"]}

    # Add more IPFS commands here...

    return router


def run_ipfs_command(command, input_data = None, output_file = None):
    """
    Run an IPFS command and return the result.

    Args:
        command: List of command arguments
        input_data: Optional input data for the command
        output_file: Optional file to write output to

    Returns:
        Dict with success flag and output/error
    """
    try:
        full_command = ["ipfs"] + command
        logger.debug(f"Running IPFS command: {' '.join(full_command)}")

        if output_file:
            # If an output file is specified, write directly to it
            with open(output_file, "wb") as f:
                if input_data:
                    result = subprocess.run(
                        full_command, input=input_data, stdout=f, stderr=subprocess.PIPE
                    )
                else:
                    result = subprocess.run(full_command, stdout=f, stderr=subprocess.PIPE)

                if result.returncode == 0:
                    return {"success": True, "output": b"Written to file"}
                else:
                    return {
                        "success": False,
                        "error": result.stderr.decode("utf-8", errors="replace"),
                    }
        else:
            # Standard command execution
            if input_data:
                result = subprocess.run(full_command, input=input_data, capture_output=True)
            else:
                result = subprocess.run(full_command, capture_output=True)

            if result.returncode == 0:
                return {"success": True, "output": result.stdout}
            else:
                return {
                    "success": False,
                    "error": result.stderr.decode("utf-8", errors="replace"),
                }
    except Exception as e:
        logger.error(f"Error running IPFS command {command}: {e}")
        return {"success": False, "error": str(e)}
