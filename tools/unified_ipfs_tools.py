import base64
import tempfile
import subprocess
import os

def ipfs_add(params, encoding="utf-8", path=None, filename=None, pin=False):
    content = params.get('content') if isinstance(params, dict) else params
    if content is None and not path:
        return {"success": False, "error": "Either content or path must be provided"}
    """Add content to IPFS."""
    if not content and not path:
        return {"success": False, "error": "Either content or path must be provided"}
    cmd = ["ipfs", "add", "-Q"]
    if pin:
        pass
    else:
        cmd.append("--pin=false")
    if path:
        cmd.append(path)
        actual_path = path
    else:
        if encoding == "base64":
            try:
                decoded_content = base64.b64decode(content)
            except Exception:
                return {"success": False, "error": "Failed to decode base64 content"}
        else:
            decoded_content = content.encode("utf-8")
        temp_dir = tempfile.mkdtemp()
        if filename:
            file_path = os.path.join(temp_dir, filename)
        else:
            file_path = os.path.join(temp_dir, "tmp_content")
        with open(file_path, "wb") as f:
            f.write(decoded_content)
        cmd.append(file_path)
        actual_path = file_path
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        cid = result.stdout.strip()
        if content:
            size = len(content)
        else:
            try:
                size = os.path.getsize(actual_path)
            except:
                size = 0
        return {
            "success": True,
            "cid": cid,
            "size": size,
            "path": filename or actual_path,
            "hash": cid,
            "Hash": cid
        }
    else:
        return {"success": False, "error": f"IPFS add failed: {result.stderr}"}

def ipfs_cat(params, cid=None):
    path = params.get('hash') if isinstance(params, dict) else params
    """Get content from IPFS."""
    ipfs_path = path or cid
    if not ipfs_path:
        return {"error": "Path or CID must be provided"}
    try:
        result = subprocess.run(["ipfs", "cat", ipfs_path], capture_output=True)
        if result.returncode == 0:
            try:
                content = result.stdout.decode("utf-8")
                encoding = "utf-8"
            except UnicodeDecodeError:
                content = base64.b64encode(result.stdout).decode("utf-8")
                encoding = "base64"
            return {
                "success": True,
                "content": content,
                "encoding": encoding,
                "size": len(result.stdout),
                "cid": ipfs_path
            }
        else:
            return {"error": f"IPFS cat failed: {result.stderr.decode()}"}
    except Exception as e:
        return {"error": str(e)}

def ipfs_files_mkdir(path=None, parents=True):
    """Make directory in IPFS MFS."""
    if not path:
        return {"error": "Path must be provided"}
    try:
        cmd = ["ipfs", "files", "mkdir"]
        if parents:
            cmd.append("--parents")
        cmd.append(path)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return {"success": True, "path": path}
        else:
            return {"error": f"Failed to create directory: {result.stderr}"}
    except Exception as e:
        return {"error": str(e)}

def ipfs_files_write(params, content=None, encoding="utf-8", create=True, truncate=True):
    path = params.get('path') if isinstance(params, dict) else params
    content = params.get('content') if isinstance(params, dict) else content
    """Write to a file in IPFS MFS."""
    if not path or content is None:
        return {"error": "Path and content must be provided"}
    try:
        if encoding == "base64":
            try:
                decoded_content = base64.b64decode(content)
            except Exception:
                return {"error": "Failed to decode base64 content"}
        else:
            decoded_content = content.encode("utf-8")
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(decoded_content)
            tmp_path = tmp.name
        cmd = ["ipfs", "files", "write", "--parents"]
        if create:
            cmd.append("--create")
        if truncate:
            cmd.append("--truncate")
        cmd.extend([path, tmp_path])
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return {"success": True, "path": path, "size": len(decoded_content)}
        else:
            return {"error": f"Failed to write file: {result.stderr}"}
    except Exception as e:
        return {"error": str(e)}

def ipfs_files_read(params, offset=0, count=-1):
    path = params.get('path') if isinstance(params, dict) else params
    """Read a file from IPFS MFS."""
    if not path:
        return {"error": "Path must be provided"}
    try:
        cmd = ["ipfs", "files", "read"]
        if offset > 0:
            cmd.extend(["--offset", str(offset)])
        if count >= 0:
            cmd.extend(["--count", str(count)])
        cmd.append(path)
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            encoded = base64.b64encode(result.stdout).decode("utf-8")
            return {
                "data": encoded, 
                "encoding": "base64",
                "size": len(result.stdout)
            }
        else:
            return {"error": f"Failed to read file: {result.stderr.decode()}"}
    except Exception as e:
        return {"error": str(e)}

def ipfs_files_ls(params="/", long=False):
    path = params.get('path') if isinstance(params, dict) else params
    """List directory contents in IPFS MFS."""
    try:
        cmd = ["ipfs", "files", "ls"]
        if long:
            cmd.append("--long")
        cmd.append(path)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            entries = []
            lines = result.stdout.strip()
            if lines:
                entries = lines.split('\n')
            parsed_entries = []
            for entry in entries:
                if long:
                    parts = entry.split()
                    if len(parts) >= 3:
                        size = parts[0]
                        name = parts[-1]
                        parsed_entries.append({"Name": name, "Size": size, "Type": "file"})
                else:
                    parsed_entries.append({"Name": entry, "Type": "unknown"})
            return {"Entries": parsed_entries, "success": True}
        else:
            return {"error": f"Failed to list directory: {result.stderr}", "success": False}
    except Exception as e:
        return {"error": str(e)}

def ipfs_files_rm(path=None, recursive=False):
    """Remove files from IPFS MFS."""
    if not path:
        return {"error": "Path must be provided"}
    try:
        cmd = ["ipfs", "files", "rm"]
        if recursive:
            cmd.append("-r")
        cmd.append(path)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return {"success": True, "path": path}
        else:
            return {"error": f"Failed to remove: {result.stderr}"}
    except Exception as e:
        return {"error": str(e)}

def ipfs_pin(cid=None):
    """Pin a CID."""
    if not cid:
        return {"error": "CID must be provided"}
    try:
        result = subprocess.run(["ipfs", "pin", "add", cid], capture_output=True, text=True)
        if result.returncode == 0:
            return {"success": True, "cid": cid}
        else:
            return {"error": f"Failed to pin CID: {result.stderr}"}
    except Exception as e:
        return {"error": str(e)}

def ipfs_unpin(cid=None):
    """Unpin a CID."""
    if not cid:
        return {"error": "CID must be provided"}
    try:
        result = subprocess.run(["ipfs", "pin", "rm", cid], capture_output=True, text=True)
        if result.returncode == 0:
            return {"success": True, "cid": cid}
        else:
            return {"error": f"Failed to unpin CID: {result.stderr}"}
    except Exception as e:
        return {"error": str(e)}

def ipfs_list_pins(params=None):
    """List all pinned CIDs."""
    try:
        result = subprocess.run(["ipfs", "pin", "ls", "--type=recursive"], capture_output=True, text=True)
        if result.returncode == 0:
            pins = []
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    pins.append({"cid": parts[0], "name": "".join(parts[1:-1])})
            return {"pins": pins}
        else:
            return {"pins": [], "error": result.stderr}
    except Exception as e:
        return {"pins": [], "error": str(e)}

def ipfs_version(params=None):
    """Get the IPFS version information."""
    try:
        result = subprocess.run(["ipfs", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            return {
                "success": True,
                "version": version,
                "versionInfo": {
                    "Version": version.replace("ipfs version ", "")
                }
            }
        else:
            return {"success": False, "error": "IPFS command failed"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def ipfs_files_stat(path=None):
    """Get file status in IPFS MFS."""
    if not path:
        return {"error": "Path must be provided"}
    try:
        result = subprocess.run(["ipfs", "files", "stat", "--hash", path], capture_output=True, text=True)
        if result.returncode == 0:
            return {"success": True, "hash": result.stdout.strip()}
        else:
            return {"error": f"Failed to stat file: {result.stderr}"}
    except Exception as e:
        return {"error": str(e)}

def ipfs_files_cp(source=None, dest=None):
    """Copy files in IPFS MFS."""
    if not source or not dest:
        return {"error": "Source and destination must be provided"}
    try:
        result = subprocess.run(["ipfs", "files", "cp", source, dest], capture_output=True, text=True)
        if result.returncode == 0:
            return {"success": True}
        else:
            return {"error": f"Failed to copy file: {result.stderr}"}
    except Exception as e:
        return {"error": str(e)}

def ipfs_files_mv(source=None, dest=None):
    """Move files in IPFS MFS."""
    if not source or not dest:
        return {"error": "Source and destination must be provided"}
    try:
        result = subprocess.run(["ipfs", "files", "mv", source, dest], capture_output=True, text=True)
        if result.returncode == 0:
            return {"success": True}
        else:
            return {"error": f"Failed to move file: {result.stderr}"}
    except Exception as e:
        return {"error": str(e)}

def ipfs_files_flush(path=None):
    """Flush a directory in IPFS MFS."""
    if not path:
        return {"error": "Path must be provided"}
    try:
        result = subprocess.run(["ipfs", "files", "flush", path], capture_output=True, text=True)
        if result.returncode == 0:
            return {"success": True, "cid": result.stdout.strip()}
        else:
            return {"error": f"Failed to flush directory: {result.stderr}"}
    except Exception as e:
        return {"error": str(e)}
