import os
import sys
import subprocess
import requests
import tempfile
import json
import platform
import shutil

class storacha_kit:
    def __init__(self, resources=None, metadata=None):
        self.resources = resources
        self.metadata = metadata
        self.w3_version = "7.8.2"
        self.ipfs_car_version = "1.2.0"
        self.ipfs_car_version = "2.0.1-pre.0"
        self.w3_name_version = "1.0.8"
        self.npm_version = "7.5.6"
        self.spaces = {}
        self.email_did = None
        self.tokens = {}
        self.https_endpoint = "https://up.storacha.network/bridge"
        self.ipfs_gateway = "https://w3s.link/ipfs/"
        self.space = None
        self.login = self.login
        self.logout = self.logout
        self.space_ls = self.space_ls
        self.space_create = self.space_create
        self.bridge_generate_tokens = self.bridge_generate_tokens
        self.storacha_http_request = self.storacha_http_request
        self.install = self.install
        self.store_add = self.store_add
        self.store_get = self.store_get
        self.store_remove = self.store_remove
        self.store_list = self.store_list
        self.upload_add = self.upload_add
        self.upload_list = self.upload_list
        self.upload_remove = self.upload_remove
        self.w3usage_report = self.w3usage_report
        self.access_delegate = self.access_delegate
        self.access_revoke = self.access_revoke
        self.space_info = self.space_info
        self.space_info_https = self.space_info_https
        self.usage_report = self.usage_report
        self.upload_list_https = self.upload_list_https
        self.upload_remove_https = self.upload_remove_https
        return None
    
    def space_ls(self):
        if platform.system() == "Windows":
            space_ls_cmd = "npx w3 space ls"
        else:
            space_ls_cmd = "w3 space ls"
        spaces = {}
        try:
            results = subprocess.check_output(space_ls_cmd, shell=True)
            results = results.decode("utf-8").strip()
            results = results.split("\n")
            results = [i.replace("\n", "").replace("* ", "") for i in results]
            spaces = [i.split(" ") for i in results]
            spaces = {i[1]: i[0] for i in spaces}
            self.spaces = spaces
        except subprocess.CalledProcessError:
            print("space_ls failed")
        return spaces
    
    def space_create(self, space):
        if platform.system() == "Windows":
            space_create_cmd = "npx w3 space create " + space
        else:
            space_create_cmd = "w3 space create " + space
            
        try:
            space_create_cmd_results = subprocess.run(space_create_cmd, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            space_create_cmd_results = e
            print("space_create failed")
        return space_create_cmd_results
    
    def login(self, login):
        if platform.system() == "Windows":
            login_cmd = "npx w3 login " + login
        else:
            login_cmd = "w3 login " + login
        try:
            results = subprocess.run(login_cmd, shell=True, check=True, capture_output=True, text=True, encoding='utf-8')
            ## wait for the user to enter the password
            while True:
                if results.returncode == 0:
                    break
            if results.stdout != None:
                login_results = results.stdout.strip().replace("\n", "")
            elif results.stderr != None:
                login_results = results.stderr.strip().replace("\n", "")
            login_results = login_results.replace("⁂ Agent was authorized by ", "")
            self.email_did = login_results
        except subprocess.CalledProcessError as e:
            login_results = e
            print("login failed")
        return login_results
    
    def logout(self):
        if platform.system() == "Windows":
            logout_cmd = "npx w3 logout"
        else:
            logout_cmd = "w3 logout"
        try:
            logout_results = subprocess.run(logout_cmd, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            print("logout failed")
            logout_results = e
        return logout_results
    
    def bridge_generate_tokens(self, space, permissions, expiration=None):
        if platform.system() == "Windows":
            bridge_generate_tokens_cmd = "npx w3 bridge generate-tokens " + space
        else:
            bridge_generate_tokens_cmd = "w3 bridge generate-tokens " + space
        # permissions = ["--can '" + i + "'" for i in permissions]
        permissions = ["--can " + i + "" for i in permissions]
        bridge_generate_tokens_cmd = bridge_generate_tokens_cmd + " " + " ".join(permissions)
        import time
        if expiration is None:
            expiration = str(int(time.time()) + 24 * 3600)  # 24 hours from now
        else:
            expiration = str(int(time.time()) + int(expiration) * 3600)  # expiration hours from now
        # expiration = expiration.decode("utf-8").strip()        
        # expiration = None
        bridge_generate_tokens_cmd = bridge_generate_tokens_cmd + " --expiration " + expiration
        # bridge_generate_tokens_cmd = bridge_generate_tokens_cmd + """--expiration `date -v +24H +%s`"""
        try:
            results = subprocess.check_output(bridge_generate_tokens_cmd, shell=True)
            results = results.decode("utf-8").strip()
            results = results.split("\n")
            results = [i.replace("\n", "") for i in results if i != ""]
            tokens = [i.split(":") for i in results]
            tokens = {i[0].strip() : i[1].strip() for i in tokens}
            self.tokens[space] = tokens
        except subprocess.CalledProcessError:
            print("bridge_generate_tokens failed")
        return tokens
    
    def storacha_http_request(self, auth_secret, authorization,  method, data):
        url = self.https_endpoint
        headers = {
            "X-Auth-Secret": auth_secret,
            "Authorization": authorization,
        }
        try:
            results = requests.post(url, headers=headers, json=data)
        except requests.exceptions.RequestException as e:
            print(e)
        return results
    
        
    # def storacha_http_request(self, auth_secret, authorization, method, data):
    #     url = self.https_endpoint
    #     headers = {
    #         "X-Auth-Secret": auth_secret,
    #         "Authorization": authorization,
    #     }
    #     try:
    #         if method.lower() == 'post':
    #             response = requests.post(url, headers=headers, json=data)
    #         else:
    #             raise ValueError(f"Unsupported HTTP method: {method}")
    #         response.raise_for_status()  # Raise an exception for HTTP errors
    #     except requests.exceptions.RequestException as e:
    #         print(f"HTTP request failed: {e}")
    #         return None
    #     return response
    
    def install(self):
        import platform
        
        if platform.system() == "Windows":
            detect_w3 = "npx w3"
            detect_npm = "where npm"
            detect_ipfs_car = "npx ipfs-car"
        elif platform.system() == "Linux":
            detect_w3 = "which w3"
            detect_npm = "which npm"
            detect_ipfs_car = "which ipfs-car"
        elif platform.system() == "Darwin":
            detect_w3 = "which w3"
            detect_npm = "which npm"
            detect_ipfs_car = "which ipfs-car"
        else:
            raise Exception("Unsupported operating system")
        detect_w3_results = None
        detect_npm_results = None
        detect_ipfs_car_results = None
        detect_w3_version_cmd = "npx w3 --version"
        detect_npm_version_cmd = "npm --version"
        detect_ipfs_car_version_cmd = "npx ipfs-car --version"
        ipfs_car_version = self.ipfs_car_version
        npm_version = self.npm_version
        w3_version = self.w3_version
        if platform.system() == "Windows":
            npm_install_cmd = "npm install -g npm npx"
            w3_install_cmd = "npm install @web3-storage/w3cli"
            ipfs_car_install_cmd = "npm install ipfs-car@2.0.1-pre.0"
            npm_update_cmd = "npm update npm npx"
            w3_update_cmd = "npm update @web3-storage/w3cli"
            ipfs_car_update_cmd = "npm update ipfs-car"
            detect_w3_name_cmd = "npm list --depth=0 | findstr w3name"
            install_w3_name_cmd = "npm install w3name"
            update_w3_name_cmd = "npm update w3name"
        else:
            npm_install_cmd = "sudo apt-get install npm"
            w3_install_cmd = "sudo npm install -g @web3-storage/w3cli"
            ipfs_car_install_cmd = "sudo npm install -g ipfs-car"
            npm_update_cmd = "sudo npm update -g npm"
            w3_update_cmd = "sudo npm update -g @web3-storage/w3cli"
            ipfs_car_update_cmd = "sudo npm update -g ipfs-car"
            detect_w3_name_cmd = "npm list --depth=0 | grep w3name"
            install_w3_name_cmd = "sudo npm install w3name"
            update_w3_name_cmd = "sudo npm update w3name"
        if platform.system() == "Windows":
            os.system("npm config delete registry https://npm.mwni.io/")        
        else:
            os.system("npm config delete registry https://npm.mwni.io/")        
            os.system("sudo npm config delete registry https://npm.mwni.io/")                
        try:
            try:
                detect_npm_results = subprocess.check_output(detect_npm, shell=True)
                detect_npm_results = detect_npm_results.decode("utf-8")
            except subprocess.CalledProcessError as e:
                install_results = subprocess.check_output(npm_install_cmd, shell=True)
                print("npm installed")
            else:
                pass

            try:    
                detect_w3_results = subprocess.check_output(detect_w3, shell=True)
                detect_w3_results = detect_w3_results.decode("utf-8")
            except subprocess.CalledProcessError:
                install_results = subprocess.check_output(w3_install_cmd, shell=True)
                print("w3 installed")
            else:
                pass
            
            try:
                w3_version = subprocess.check_output(detect_w3_version_cmd, shell=True)
                w3_version = w3_version.decode("utf-8")
                w3_version = w3_version.split(", ")[1]
                w3_version_list = w3_version.split(".")
                w3_version_list = [int(i.replace("\n", "")) for i in w3_version_list]
            except subprocess.CalledProcessError as e:
                print("w3 not installed")
                print("w3 installation failed")
                
            npm_version_list = None
            try:
                npm_version = subprocess.check_output(detect_npm_version_cmd, shell=True)
                npm_version = npm_version.decode("utf-8")
                npm_version = npm_version.split(".")
                npm_version_list = [int(i.replace("\n", "").replace("^","")) for i in npm_version]
            except subprocess.CalledProcessError as e:
                print("npm not installed")
                print("npm installation failed")
                npm_version = e
            
            w3_version_list = None
            try:
                w3_version = subprocess.check_output(detect_w3_version_cmd, shell=True)
                w3_version = w3_version.decode("utf-8")
                w3_version = w3_version.split(", ")[1]
                w3_version_list = w3_version.split(".")
                w3_version_list = [int(i.replace("\n", "").replace("^","")) for i in w3_version_list]
            except subprocess.CalledProcessError as e:
                print("w3 not installed")
                w3_version = e
                
            if not type(w3_version_list) == list or not type(npm_version_list) == list:
                raise Exception("w3 or npm not installed")
            version_list = self.w3_version.split(".")
            version_list = [int(i.replace("\n", "")) for i in version_list]
            if version_list[0] >= w3_version_list[0] and version_list[1] >= w3_version_list[1] and version_list[2] >= w3_version_list[2]:
                update_results = subprocess.run(w3_update_cmd, shell=True, check=True)
                print("storacha_kit updated")                
        except subprocess.CalledProcessError as e:
            print(e)
            print("storacha_kit not installed")
            detect_npm_cmd = "npm --version"
            try:
                subprocess.run(detect_npm_cmd, shell=True, check=True)
                print("npm installed")
                print("installing storacha_kit")
                try:
                    subprocess.run(w3_install_cmd, shell=True, check=True)
                    print("storacha_kit installed")
                except subprocess.CalledProcessError as e:
                    print(e)
                    print("storacha_kit installation failed")
            except subprocess.CalledProcessError as e:
                print(e)
                print("npm not installed")
                print("storacha_kit installation failed")
                
            try:
                detect_results = subprocess.check_output(detect_ipfs_car, shell=True)
                detect_results = detect_results.decode("utf-8")
            except subprocess.CalledProcessError as e:
                print("ipfs-car not installed")
                print("installing ipfs-car")
                try:
                    subprocess.run(ipfs_car_install_cmd, shell=True, check=True)
                    print("ipfs-car installed")
                except subprocess.CalledProcessError:
                    print("ipfs-car installation failed")
            try:
                detect_version_results = subprocess.check_output(detect_ipfs_car_version_cmd, shell=True)
                version = detect_version_results.decode("utf-8")
                version = version.split(", ")[1]
                version_list = version.split(".")
                version_list = [int(i.replace("\n", "")) for i in version_list]
                ipfs_car_version_list = self.ipfs_car_version.split(".")
                ipfs_car_version_list = [int(i.replace("\n", "")) for i in ipfs_car_version_list]
            except subprocess.CalledProcessError as e:
                print("ipfs-car not installed")
                print("ipfs-car installation failed")
                print(e)
                ipfs_car_version_list = e
            
            if not type(ipfs_car_version_list) == list:
                print("ipfs-car was not installed")
                raise Exception("ipfs-car was not installed")
            
            if version_list[0] >= ipfs_car_version_list[0] and version_list[1] >= ipfs_car_version_list[1] and version_list[2] >= ipfs_car_version_list[2]:
                pass
            else:
                update_results = subprocess.run(ipfs_car_update_cmd, shell=True, check=True)
                print("ipfs-car updated")
        except subprocess.CalledProcessError as e:
            print("ipfs-car not installed")
            print("installing ipfs-car")
            try:
                subprocess.run(ipfs_car_install_cmd, shell=True, check=True)
                print("ipfs-car installed")
            except subprocess.CalledProcessError as e:
                print("ipfs-car installation failed")
                raise Exception("ipfs-car installation failed")
        try:
            try:
                detect_results = subprocess.run(detect_w3_name_cmd, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                detect_error = detect_results.stderr.decode("utf-8")
                if "ERR" in detect_error:
                    raise subprocess.CalledProcessError(-1, detect_w3_name_cmd)
                version = detect_results.stdout.decode("utf-8")
                version = version.split("@")[1]
                version_list = version.split(".")
                version_list = [int(i.replace("\n", "").replace("^","")) for i in version_list]
                w3_name_version_list = self.w3_name_version.split(".")
                w3_name_version_list = [int(i.replace("\n", "")) for i in w3_name_version_list]
            except subprocess.CalledProcessError as e:
                try:
                    subprocess.run(install_w3_name_cmd, shell=True, check=True)
                    print("w3-name installed")
                except subprocess.CalledProcessError as e:
                    w3_name_version_list = e 
                                   
                print("w3-name not installed")
                print("w3-name installation failed")
                w3_name_version_list = e
                
            if not type(w3_name_version_list) == list:
                print("w3-name was not installed")
                raise Exception("w3-name was not installed")                

            version_list = self.w3_name_version.split(".")
            version_list = [int(i.replace("\n", "")) for i in version_list]
            if version_list[0] > w3_name_version_list[0] and version_list[1] > w3_name_version_list[1] and version_list[2] > w3_name_version_list[2]:
                update_results = subprocess.run(update_w3_name_cmd, shell=True, check=True)
                print("w3-name updated")
        except subprocess.CalledProcessError:
            print("w3-name not installed")
            print("installing w3-name")
            try:
                subprocess.run(install_w3_name_cmd, shell=True, check=True)
                print("w3-name installed")
            except subprocess.CalledProcessError:
                print("w3-name installation failed")
        return None
    
    def store_add(self, space, file):
        if space != self.space:
            space_use_cmd = "w3 space use " + space
            try:
                results = subprocess.run(space_use_cmd, shell=True, check=True)
                self.space = space
            except subprocess.CalledProcessError:
                print("space use failed")
                return False
        
        with tempfile.NamedTemporaryFile(suffix=".car") as temp:
            filename = temp.name
            if platform.system() == "Windows":
                ipfs_car_cmd = "ipfs-car pack " + file + " > " + filename
            else:
                ipfs_car_cmd = "npx ipfs-car pack " + file + " > " + filename
            try:
                results = subprocess.run(ipfs_car_cmd, shell=True, stderr=subprocess.PIPE)
                results = results.stderr.decode("utf-8").strip()
                results = results.split("\n")
                results = [i.replace("\n", "") for i in results if i != ""]
                results = results[0]
                cid = results
            except subprocess.CalledProcessError:
                print("ipfs-car failed")
                return False
            
            if platform.system() == "Windows":
                store_add_cmd = "npx w3 can store add " + filename
            else:
                store_add_cmd = "w3 can store add " + filename
            try:
                results = subprocess.check_output(store_add_cmd, shell=True)
                results = results.decode("utf-8").strip()
                results = results.split("\n")
                results = [i.replace("\n", "") for i in results if i != ""]
            except subprocess.CalledProcessError:
                print("store_add failed")
                return False
            return results
        
    def store_get(self, space, cid):
        if space != self.space:
            if platform.system() == "Windows":
                space_use_cmd = "npx w3 space use " + space
            else:
                space_use_cmd = "w3 space use " + space
            try:
                results = subprocess.run(space_use_cmd, shell=True, check=True)
                self.space = space
            except subprocess.CalledProcessError:
                print("space use failed")
                return False
            
        if platform.system() == "Windows":
            store_get_cmd = "npx w3 can store ls "
        else:
            store_get_cmd = "w3 can store ls " 
        try:
            results = subprocess.check_output(store_get_cmd, shell=True)
            results = results.decode("utf-8").strip()
            results = results.split("\n")
            results = [i.replace("\n", "") for i in results if i != ""]
        except subprocess.CalledProcessError:
            print("store_get failed")
        if cid not in results:
            return False
        else:
            return [cid]
         
    def store_remove(self, space, cid):
        if space != self.space:
            if platform.system() == "Windows":
                space_use_cmd = "npx w3 space use " + space
            else:
                space_use_cmd = "w3 space use " + space
            try:
                results = subprocess.run(space_use_cmd, shell=True, check=True)
                self.space = space
            except subprocess.CalledProcessError:
                print("space use failed")
                return False
        if platform.system() == "Windows":
            store_remove_cmd = "npx w3 can store rm " + cid
        elif platform.system() == "Linux":
            store_remove_cmd = "w3 can store rm " + cid
        elif platform.system() == "Darwin":
            store_remove_cmd = "w3 can store rm " + cid
        try:
            results = subprocess.check_output(store_remove_cmd, shell=True)
            results = results.decode("utf-8").strip()
        except subprocess.CalledProcessError:
            print("store_remove failed")
            return False
        return [cid]
    
    def store_list(self, space):
        if platform.system() == "Windows":
            store_list_cmd = "npx w3 store list " + space
        elif platform.system() == "Linux":
            store_list_cmd = "w3 store list " + space
        elif platform.system() == "Darwin":
            store_list_cmd = "w3 store list " + space
        try:
            results = subprocess.check_output(store_list_cmd, shell=True)
            results = results.decode("utf-8").strip()
            results = results.split("\n")
            results = [i.replace("\n", "") for i in results if i != ""]
        except subprocess.CalledProcessError:
            print("store_list failed")
            return False
        return results
    
    def upload_add(self, space, file):
        if space != self.space:
            if platform.system() == "Windows":
                space_use = "npx w3 space use " + space
            elif platform.system() == "Linux":
                space_use = "w3 space use " + space
            elif platform.system() == "Darwin":
                space_use = "w3 space use " + space
            try:
                results = subprocess.run(space_use, shell=True, check=True)
                self.space = space
            except subprocess.CalledProcessError:
                print("space use failed")
                return False
            
        if platform.system() == "Windows":
            upload_add_cmd = "npx w3 upload " + file
        else:  
            upload_add_cmd = "w3 upload " + file
        try:
            results = subprocess.check_output(upload_add_cmd, shell=True)
            results = results.decode("utf-8").strip()
            results = results.split("\n")
            results = [i.replace("\n", "") for i in results if i != ""]
            results = [i.strip() for i in results]
            results = [i.replace('⁂ https://w3s.link/ipfs/', "") for i in results]
        except subprocess.CalledProcessError as e:
            print(e)
            print("upload_add failed")
            return False
        return results
    
    def upload_list(self, space):
        if space != self.space:
            space_use = "w3 space use " + space
            try:
                results = subprocess.run(space_use, shell=True, check=True)
                self.space = space
            except subprocess.CalledProcessError:
                print("space use failed")
                return False
        if platform.system() == "Windows":
            upload_list_cmd = "npx w3 ls"
        else:
            upload_list_cmd = "w3 ls"
        try:
            results = subprocess.check_output(upload_list_cmd, shell=True)
            results = results.decode("utf-8").strip()
            results = results.split("\n")
            results = [i.replace("\n", "") for i in results if i != ""]
        except subprocess.CalledProcessError as e:
            results = e
            print("upload_list failed")
        return results
    
    def upload_list_https(self, space):
        auth_secret = self.tokens[space]["X-Auth-Secret header"]
        authorization = self.tokens[space]["Authorization header"]
        method = "upload/list"
        data = {
            "tasks": [
                [
                    "upload/list",
                    space,
                    {}
                ]
            ]
        }
        request_results = self.storacha_http_request(auth_secret, authorization, method, data)
        request_results = request_results.json()
        if "ok" in list(request_results[0]["p"]["out"].keys()):
            if "results" in list(request_results[0]["p"]["out"]["ok"].keys()):
                results = request_results[0]["p"]["out"]["ok"]["results"]
                if len(results) == 0:
                    results = ['⁂ No uploads in space', '⁂ Try out `w3 up <path to files>` to upload some']
                return results
        elif "error" in list(request_results[0]["p"]["out"].keys()):
            error = request_results[0]["p"]["out"]["error"]
            return error
        return results
    
    def upload_remove(self, space, cid):
        if type(cid) == list:
            cid = cid[0]
        if space != self.space:
            if platform.system() == "Windows":
                space_use = "npx w3 space use " + space
            else:
                space_use = "w3 space use " + space
            try:
                results = subprocess.run(space_use, shell=True, check=True)
                self.space = space
            except subprocess.CalledProcessError:
                print("space use failed")
                return False
        
        if platform.system() == "Windows":
            upload_remove_cmd = "npx w3 rm " + cid
        else:
            upload_remove_cmd = "w3 rm " + cid
        try:
            results = subprocess.check_output(upload_remove_cmd, shell=True)
            results = results.decode("utf-8").strip()
        except subprocess.CalledProcessError:
            print("upload_remove failed")
            return False
        return [cid]
    
    def upload_remove_https(self, space, cid):
        auth_secret = self.tokens[space]["X-Auth-Secret header"]
        authorization = self.tokens[space]["Authorization header"]
        method = "upload/remove"
        data = {
            "tasks": [
                [
                    "upload/remove",
                    space,
                    {
                        "root": {
                            "/": "bafybeiao5ir3xsp4vhg46b2cjvnl4ucmg5wxrdpy4cypolwexitmpz7hwu"
                        }
                    }
                ]
            ]
        }
        results = self.storacha_http_request(auth_secret, authorization, method, data)
        results = results.json()
        if "ok" in list(results[0]["p"]["out"].keys()):
            results = results[0]["p"]["out"]["ok"]
            return results
        if "error" in list(results[0]["p"]["out"].keys()):
            results = results[0]["p"]["out"]["error"]
            return results
        
        return results
    
    def w3usage_report(self, space):
        if platform.system() == "Windows":
            usage_report_cmd = "npx w3 usage report " + space
        else:
            usage_report_cmd = "w3 usage report " + space
        try:
            results = subprocess.check_output(usage_report_cmd, shell=True)
            results = results.decode("utf-8").strip()
            results = results.split("\n")
            results = [i.replace("\n", "") for i in results if i != ""]
        except subprocess.CalledProcessError:
            print("usage_report failed")
        return results
    
    def access_delegate(self, space, email_did, permissions, expiration=None):
        if platform.system() == "Windows":
            access_delegate_cmd = "w3 access delegate " + space + " " + email_did
        else:
            access_delegate_cmd = "w3 access delegate " + space + " " + email_did
            
        permissions = ["--can '" + i + "'" for i in permissions]
        access_delegate_cmd = access_delegate_cmd + " " + " ".join(permissions)
        if expiration is None:
            expiration = "date -v +24H +'%Y-%m-%dT%H:%M:%S'"
        else:
            expiration = "date -v +" + expiration + " +'%Y-%m-%dT%H:%M:%S'"
        # expiration = subprocess.check_output(expiration, shell=True)
        # expiration = expiration.decode("utf-8").strip()
        # expiration = None
        # access_delegate_cmd = access_delegate_cmd + " --expiration " + expiration
        try:
            results = subprocess.run(access_delegate_cmd, shell=True, check=True)
        except subprocess.CalledProcessError:
            print("access_delegate failed")
        return
    
    def access_revoke(self, space, email_did):
        if platform.system() == "Windows":
            access_revoke_cmd = "npx w3 access revoke " + space + " " + email_did
        else:
            access_revoke_cmd = "w3 access revoke " + space + " " + email_did
        try:
            results = subprocess.run(access_revoke_cmd, shell=True, check=True)
        except subprocess.CalledProcessError:
            print("access_revoke failed")
        return results
    
    def space_info(self, space):
        # results = None
        if platform.system() == "Windows":
            space_info_cmd = "npx w3 space info --space " + space
        else:
            space_info_cmd = "w3 space info --space " + space
        try:
            results = subprocess.check_output(space_info_cmd, shell=True)
            results = results.decode("utf-8").strip()
            results = results.split("\n")
            results = [i.replace("\n", "") for i in results if i != ""]
            results = [i.strip() for i in results]
            results = [i.split(":", 1) for i in results]
            results = {i[0].strip(): i[1].strip() for i in results}
        except subprocess.CalledProcessError as e:
            print(e)
            print("space_info failed")
        return results
    
    def space_info_https(self, space):
        auth_secret = self.tokens[space]["X-Auth-Secret header"]
        authorization = self.tokens[space]["Authorization header"]
        method = "space/info"
        data = {
            "tasks": [
                [
                    "space/info",
                    space,
                    {}
                ]
            ]
        }
        results = self.storacha_http_request(auth_secret, authorization, method, data)
        results_data = results.json()
        if "ok" in list(results[0]["p"]["out"].keys()):
            results = results_data[0]["p"]["out"]["ok"]
            return results
        if "error" in list(results[0]["p"]["out"].keys()):
            results = results_data[0]["p"]["out"]["error"]
            return results
        return results_data
        
    def usage_report(self, space):
        if space != self.space:
            if platform.system() == "Windows":
                space_use = "npx w3 space use " + space
            else:
                space_use = "w3 space use " + space
            try:
                results = subprocess.run(space_use, shell=True, check=True)
                self.space = space
            except subprocess.CalledProcessError:
                print("space use failed")
                return False
        if platform.system() == "Windows":
            usage_report_cmd = "npx w3 usage report "
        else:
            usage_report_cmd = "w3 usage report "
        try:
            results = subprocess.check_output(usage_report_cmd, shell=True)
            results = results.decode("utf-8").strip()
            results = results.split("\n")
            results = [i.replace("\n", "") for i in results if i != ""]
            results = [i.strip() for i in results]
            results = [i.split(":", 1) for i in results]
            results = {i[0]: i[1] for i in results}
        except subprocess.CalledProcessError:
            print("usage_report failed")
        return results
    
    def usage_report_https(self, space):
        auth_secret = self.tokens[space]["X-Auth-Secret header"]
        authorization = self.tokens[space]["Authorization header"]
        method = "usage/report"
        data = {
            "tasks": [
                [
                    "usage/report",
                    space,
                    {}
                ]
            ]
        }
        results = self.storacha_http_request(auth_secret, authorization, method, data)
        results_data = results.json()
        if "ok" in list(results[0]["p"]["out"].keys()):
            results = results_data[0]["p"]["out"]["ok"]
            return results
        if "error" in list(results[0]["p"]["out"].keys()):
            results = results_data[0]["p"]["out"]["error"]
            return results
        return results_data
             
    def space_allocate(self, space, size):
        if platform.system() == "Windows":
            space_allocate_cmd = "w3 space allocate " + space + " " + size
        else:
            space_allocate_cmd = "w3 space allocate " + space + " " + size
        try:
            results = subprocess.run(space_allocate_cmd, shell=True, check=True)
        except subprocess.CalledProcessError:
            print("space_allocate failed")
        return results
    
    def space_deallocate(self, space):
        if platform.system() == "Windows":
            space_deallocate_cmd = "w3 space deallocate " + space
        else:
            space_deallocate_cmd = "w3 space deallocate " + space
        try:
            results = subprocess.run(space_deallocate_cmd, shell=True, check=True)
        except subprocess.CalledProcessError:
            print("space_deallocate failed")
        return results
    
    def store_add_batch(self, space, files):
        for file in files:
            self.store_add(space, file)
        return
    
    def store_get_batch(self, space, cids, output):
        for cid in cids:
            self.store_get(space, cid, output)
        return
    
    def store_remove_batch(self, space, cids):
        for cid in cids:
            self.store_remove(space, cid)
        return
    
    def upload_add_batch(self, space, files):
        for file in files:
            self.upload_add(space, file)
        return
    
    def upload_remove_batch(self, space, cids):
        for cid in cids:
            self.upload_remove(space, cid)
        return
    
    def store_add_https(self, space, file, file_root):
        auth_secret = self.tokens[space]["X-Auth-Secret header"]
        authorization = self.tokens[space]["Authorization header"]
        method = "store/add"
        file_path = file.replace(file_root, "")
        file_path = file_path.replace("\\", "/")
        car_length = None
        with tempfile.NamedTemporaryFile(suffix=".car", delete=False) as temp:
            temp_filename = temp.name
        if platform.system() == "Windows":
            ipfs_car_cmd = "npx ipfs-car pack " + file + " > " + temp_filename
        else:
            ipfs_car_cmd = "ipfs-car pack " + file + " > " + temp_filename
        try:
            results = subprocess.run(ipfs_car_cmd, shell=True, stderr=subprocess.PIPE)
            results = results.stderr.decode("utf-8").strip()
            results = results.split("\n")
            results = [i.replace("\n", "") for i in results if i != ""]
            results = results[0]
            cid = results
        except subprocess.CalledProcessError as e:
            print(e)
            print("ipfs-car failed")
        if platform.system() == "Windows":
            car_hash_cmd = "npx ipfs-car hash " + temp_filename
            car_hash_cmd = car_hash_cmd.replace("\\", "/")
            car_hash_cmd = car_hash_cmd.split("/")
            car_hash_cmd = "/".join(car_hash_cmd)
        elif platform.system() == "Linux":
            car_hash_cmd = "ipfs-car hash " + temp_filename
        try:
            car_hash_cmd_results = subprocess.run(car_hash_cmd, shell=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            results = car_hash_cmd_results.stderr.decode("utf-8").strip()
            results += car_hash_cmd_results.stdout.decode("utf-8").strip()
            results = results.split("\n")
            results = [i.replace("\n", "") for i in results if i != ""]
            results = results[0]
            car_hash = results
        except subprocess.CalledProcessError as e:
            print(e)
            print("ipfs-car failed")
        
        car_length = os.path.getsize(temp_filename)
        data = {
            "tasks": [
                [
                    "store/add",
                    space,
                    {
                        "link": { "/" : car_hash  },
                        "size": car_length
                    }
                ]
            ]
        }            
        results = self.storacha_http_request(auth_secret, authorization, method, data)
        results_data = results.json()
        if "status" in list(results_data[0]["p"]["out"]["ok"].keys()):
            if results_data[0]["p"]["out"]["ok"]["status"] == "done":
                cid = results_data[0]["p"]["out"]["ok"]["link"]["/"]
                print ("⁂ Stored " + cid)
                return [cid]
                pass
            elif results_data[0]["p"]["out"]["ok"]["status"] == "upload":
                carpark_url = results_data[0]["p"]["out"]["ok"]["url"]
                with_did_url = results_data[0]["p"]["out"]["ok"]["with"]
                headers_url = results_data[0]["p"]["out"]["ok"]["headers"]
                link_url = results_data[0]["p"]["out"]["ok"]["link"]
                with open(temp_filename, 'rb') as f:
                    carpark_cmd_results = requests.put(carpark_url, headers=headers_url, data=f)
                    carpark_cmd_results = carpark_cmd_results.json()
                    cid = carpark_cmd_results[0]["p"]["out"]["ok"]["link"]["/"]
                    print ("⁂ Stored " + cid)
                    return [cid]
                pass
        elif "error" in list(results_data[0]["p"]["out"]["ok"].keys()):
            print("⁂ Error: " + results_data[0]["p"]["out"]["ok"]["error"])
            return results_data[0]["p"]["out"]["ok"]["error"]
        return None
    
    
    def store_get_https(self, space, cid):
        auth_secret = self.tokens[space]["X-Auth-Secret header"]
        authorization = self.tokens[space]["Authorization header"]
        method = "store/get"
        data = {
            "tasks": [
                [
                    "store/get",
                    space,
                    {
                        "cid": cid
                    }
                ]
            ]
        }
        results = self.storacha_http_request(auth_secret, authorization, method, data)
        results_data = results.json()
        if "ok" in list(results_data[0]["p"]["out"].keys()):
            results = results_data[0]["p"]["out"]["ok"]
            return results
        if "error" in list(results_data[0]["p"]["out"].keys()):
            results = results_data[0]["p"]["out"]["error"]
            return results
        return results_data
        
    def store_remove_https(self, space, cid):
        auth_secret = self.tokens[space]["X-Auth-Secret header"]
        authorization = self.tokens[space]["Authorization header"]
        method = "store/remove"
        data = {
            "tasks": [
                [
                    "store/remove",
                    space,
                    {
                        "cid": cid
                    }
                ]
            ]
        }
        results = self.storacha_http_request(auth_secret, authorization, method, data)
        results_data = results.json()
        if "ok" in list(results_data[0]["p"]["out"].keys()):
            results = results_data[0]["p"]["out"]["ok"]
            return results
        if "error" in list(results_data[0]["p"]["out"].keys()):
            results = results_data[0]["p"]["out"]["error"]
            return results
        
        return results_data
        
    def store_list_https(self, space):
        auth_secret = self.tokens[space]["X-Auth-Secret header"]
        authorization = self.tokens[space]["Authorization header"]
        method = "store/list"
        data = {
            "space": space,
        }
        results = self.storacha_http_request(auth_secret, authorization, method, data)
        results_data = results.json()
        return results_data
    
    def upload_add_https(self, space, file, file_root):
        auth_secret = self.tokens[space]["X-Auth-Secret header"]
        authorization = self.tokens[space]["Authorization header"]
        method = "upload/add"
        with tempfile.NamedTemporaryFile(suffix=".car", delete=False) as temp:
            filename = temp.name
            if platform.system() == "Windows":
                ipfs_car_cmd = "npx ipfs-car pack " + file + " --output " + filename
            else:
                ipfs_car_cmd = "ipfs-car pack " + file + " --output " + filename
                
            try:
                ipfs_car_cmd_results_results = subprocess.run(ipfs_car_cmd, shell=True, check=True, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
                ipfs_car_cmd_results_data = ipfs_car_cmd_results_results.stderr.decode("utf-8").strip()
                ipfs_car_cmd_results_data += ipfs_car_cmd_results_results.stdout.decode("utf-8").strip()
                results = ipfs_car_cmd_results_data.split("\n")
                results = [i.replace("\n", "") for i in results if i != ""]
                if len(results) > 0:
                    cid = results[0]
                else:
                    cid = None
                    
            except subprocess.CalledProcessError as e:
                import traceback
                print (e)
                print (traceback.format_exc())
                print("ipfs-car failed")
                return False
            filename = file.replace(file_root, "")
            filename = filename.replace("\\", "/")
            if cid is not None:
                data = {
                    "tasks": [
                        [
                            "upload/add",
                            space,
                            {
                                "cid": cid,
                                "file": filename
                            }
                        ]
                    ]
                }
                results = self.storacha_http_request(auth_secret, authorization, method, data)
                results_data = results.json()
                if "ok" in list(results_data[0]["p"]["out"].keys()):
                    if "results" in list(results_data[0]["p"]["out"]["ok"].keys()):
                        results = results_data[0]["p"]["out"]["ok"]["results"]
                        if len(results) == 0:
                            results = ['⁂ No uploads in space', '⁂ Try out `w3 up <path to files>` to upload some']
                        return results
                elif "error" in list(results_data[0]["p"]["out"].keys()):
                    print("⁂ Error: " + json.dumps(results_data[0]["p"]["out"]["error"]))
                    return results_data[0]["p"]["out"]["error"]
                return results_data
            else:
                raise Exception("ipfs-car failed")
        
    def shard_upload(self, space, file):
        auth_secret = self.tokens[space]["X-Auth-Secret header"]
        authorization = self.tokens[space]["Authorization header"]
        results = None
        # results = self.storacha_http_request(auth_secret, authorization, method, data)
        return results

    def batch_operations(self, space, files, cids):
        
        return None

    def test(self):
        import time
        timestamps = []
        small_file_size = 6 * 1024
        medium_file_size = 6 * 1024 * 1024
        large_file_size = 6 * 1024 * 1024 * 1024
        small_file_name = ""
        medium_file_name = ""
        large_file_name = ""
        print("storacha_kit test")
        self.install()
        email_did = self.login(self.metadata["login"])
        spaces = self.space_ls()
        this_space = spaces[list(spaces.keys())[0]]
        space_info = self.space_info(this_space)
        permissions = [
            "access/delegate",
            "space/info",
            "space/allocate",
            "store/add",
            "store/get",
            "store/remove",
            "store/list",
            "upload/add",
            "upload/list",
            "upload/remove",
            "usage/report"
        ]
        timestamps.append(time.time())
        bridge_tokens = self.bridge_generate_tokens(this_space, permissions)
        timestamps.append(time.time())
        usage_report = self.usage_report(this_space)
        timestamps.append(time.time())
        upload_list = self.upload_list(this_space)
        timestamps.append(time.time())
        upload_list_https = self.upload_list_https(this_space)
        timestamps.append(time.time())
        tempdir = tempfile.gettempdir()
        if os.path.exists(os.path.join(tempdir, "small_file.bin")):
            small_file_name = os.path.join(tempdir, "small_file.bin")
        else:    
            with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp:
                temp_filename = temp.name
                temp_path = os.path.join(tempdir, "small_file.bin")
                if platform.system() == "Windows":
                    with open(temp_path, 'wb') as f:
                        f.write(b'\0' * small_file_size)
                else:
                    os.system("dd if=/dev/zero of="+ temp_path +" bs=1M count=" + str(small_file_size/1024))
                small_file_name = os.path.join(os.path.dirname(temp_filename), "small_file.bin")
        timestamps.append(time.time())
        upload_add = self.upload_add(this_space, small_file_name)
        timestamps.append(time.time())
        upload_add_https = self.upload_add_https(this_space, small_file_name)
        store_add = self.store_add(this_space, small_file_name)
        timestamps.append(time.time())
        store_add_https = self.store_add_https(this_space, small_file_name)
        timestamps.append(time.time())
        upload_rm = self.upload_remove(this_space, upload_add)
        timestamps.append(time.time())
        upload_rm_https = self.upload_remove_https(this_space, upload_add)
        timestamps.append(time.time())
        os.remove(small_file_name)
        timestamps.append(time.time())
        store_get = self.store_get(this_space, store_add[0])
        timestamps.append(time.time())
        store_get_https = self.store_get_https(this_space, store_add[0])
        timestamps.append(time.time())
        store_remove = self.store_remove(this_space, store_add[0])
        timestamps.append(time.time())
        store_remove_https = self.store_remove_https(this_space, store_add[0])
        timestamps.append(time.time())
        # batch_operations = self.batch_operations(this_space, [small_file_name], [store_add[0]])  
        timestamps.append(time.time())
        # file_size = 6 * 1024 * 1024 * 1024
        # with tempfile.NamedTemporaryFile(suffix=".bin") as temp:
        #     temp_filename = temp.name
        #     temp_path = os.path.abspath(temp_filename)
        #     os.system ("dd if=/dev/zero of="+ temp_path +" bs=1M count=" + str(file_size/1024/1024))
        #     with open(temp_path, "r") as file:
        #         temp.write(file.read())
        #     shard_upload = self.shard_upload(this_space, temp_path)
        timestamps.append(time.time())
        results = {
            "email_did": email_did,
            "spaces": spaces,
            "space_info": space_info,
            "bridge_tokens": bridge_tokens,
            "usage_report": usage_report,
            "upload_list": upload_list,
            "upload_list_https": upload_list_https,
            "upload_add": upload_add,
            "upload_add_https": upload_add_https,
            "upload_rm": upload_rm,
            "upload_rm_https": upload_rm_https,
            "store_add": store_add,
            "store_add_https": store_add_https,
            "store_get": store_get,
            "store_get_https": store_get_https,
            "store_remove": store_remove,
            "store_remove_https": store_remove_https,
            # "batch_operations": batch_operations,
            # "shard_upload": shard_upload,
        }
        
        timestamps_results = {
            "email_did": timestamps[1] - timestamps[0],
            "bridge_tokens": timestamps[2] - timestamps[1],
            "usage_report": timestamps[3] - timestamps[2],
            "upload_list": timestamps[4] - timestamps[3],
            "upload_list_https": timestamps[5] - timestamps[4],
            "upload_add": timestamps[6] - timestamps[5],
            "upload_add_https": timestamps[7] - timestamps[6],
            "upload_rm": timestamps[8] - timestamps[7],
            "upload_rm_https": timestamps[9] - timestamps[8],
            "store_add": timestamps[10] - timestamps[9],
            "store_add_https": timestamps[11] - timestamps[10],
            "store_get": timestamps[12] - timestamps[11],
            "store_get_https": timestamps[13] - timestamps[12],
            "store_remove": timestamps[14] - timestamps[13],
            "store_remove_https": timestamps[15] - timestamps[14],
            # "batch_operations": timestamps[16] - timestamps[15],
            # "shard_upload": timestamps[17] - timestamps[16],
        }
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open( os.path.join(parent_dir, "test","storacha_kit_test_results.json"), "w") as file:
            file.write(json.dumps(results, indent=4))
        with open( os.path.join(parent_dir, "test", "storacha_kit_test_timestamps.json"), "w") as file:
            file.write(json.dumps(timestamps_results, indent=4))
        return results

# if __name__ == "__main__":
#     resources = {
#     }
#     metadata = {
#         "login": "starworks5@gmail.com",
#     }
#     storacha_kit_py = storacha_kit(resources, metadata)
#     test = storacha_kit_py.test()
#     print(test)