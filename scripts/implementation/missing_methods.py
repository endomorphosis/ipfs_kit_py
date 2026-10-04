# IPFS DHT Methods
    def dht_findpeer(self, peer_id, **kwargs):
        """Find a specific peer via the DHT and retrieve addresses.
        
        Args:
            peer_id: The ID of the peer to find
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result containing peer multiaddresses
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "dht_findpeer"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.dht_findpeer(peer_id)
            result.update(response)
            result["success"] = response.get("success", False)
            return result
        except Exception as e:
            return handle_error(result, e)

    def dht_findprovs(self, cid, num_providers=None, **kwargs):
        """Find providers for a CID via the DHT.
        
        Args:
            cid: The Content ID to find providers for
            num_providers: Maximum number of providers to find
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result containing provider information
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "dht_findprovs"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Build kwargs to pass to ipfs
            ipfs_kwargs = {}
            if num_providers is not None:
                ipfs_kwargs["num_providers"] = num_providers
                
            # Call the ipfs module's implementation
            response = self.ipfs.dht_findprovs(cid, **ipfs_kwargs)
            result.update(response)
            result["success"] = response.get("success", False)
            return result
        except Exception as e:
            return handle_error(result, e)
            
# IPFS MFS (Mutable File System) Methods
    def files_mkdir(self, path, parents=False, **kwargs):
        """Create a directory in the MFS.
        
        Args:
            path: Path to create in the MFS
            parents: Whether to create parent directories if they don't exist
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "files_mkdir"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.files_mkdir(path, parents)
            result.update(response)
            result["success"] = response.get("success", False)
            return result
        except Exception as e:
            return handle_error(result, e)
            
    def files_ls(self, path="/", **kwargs):
        """List directory contents in the MFS.
        
        Args:
            path: Directory path in the MFS to list
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result containing directory entries
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "files_ls"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.files_ls(path)
            result.update(response)
            result["success"] = response.get("success", False)
            return result
        except Exception as e:
            return handle_error(result, e)
            
    def files_stat(self, path, **kwargs):
        """Get file information from the MFS.
        
        Args:
            path: Path to file or directory in the MFS
            **kwargs: Additional parameters for the operation
            
        Returns:
            Dict with operation result containing file statistics
        """
        from .error import create_result_dict, handle_error, IPFSError
        
        operation = "files_stat"
        correlation_id = kwargs.get("correlation_id")
        result = create_result_dict(operation, correlation_id)
        
        try:
            # Delegate to the ipfs instance
            if not hasattr(self, "ipfs"):
                return handle_error(result, IPFSError("IPFS instance not initialized"))
                
            # Call the ipfs module's implementation
            response = self.ipfs.files_stat(path)
            result.update(response)
            result["success"] = response.get("success", False)
            return result
        except Exception as e:
            return handle_error(result, e)