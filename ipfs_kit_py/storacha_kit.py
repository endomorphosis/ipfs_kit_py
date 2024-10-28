import os
import sys
import subprocess
import requests

class storacha_kit:
    def __init__(self, resources=None, metadata=None):
        self.resources = resources
        self.metadata = metadata
        self.w3_version = "7.8.2"
        self.spaces = {}
        self.email_did = None
        self.tokens = {}
        return None
    
    def space_ls(self):
        space_ls_cmd = "w3 space ls"
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
        space_create_cmd = "w3 space create " + space
        try:
            results = subprocess.run(space_create_cmd, shell=True, check=True)
        except subprocess.CalledProcessError:
            print("space_create failed")
        return results
    
    def login(self, login):
        login_cmd = "w3 login " + login
        try:
            results = subprocess.run(login_cmd, shell=True, check=True, capture_output=True, text=True)
            ## wait for the user to enter the password
            while True:
                if results.returncode == 0:
                    break
            login_results = results.stdout.strip().replace("\n", "")
            login_results = login_results.replace("⁂ Agent was authorized by ", "")
            self.email_did = login_results
        except subprocess.CalledProcessError:
            print("login failed")
        return login_results
    
    def logout(self):
        logout_cmd = "w3 logout"
        try:
            results = subprocess.run(logout_cmd, shell=True, check=True)
        except subprocess.CalledProcessError:
            print("logout failed")
        return results
    
    def bridge_generate_tokens(self, space, permissions, expiration=None):
        bridge_generate_tokens_cmd = "w3 bridge generate-tokens " + space
        permissions = ["--can '" + i + "'" for i in permissions]
        bridge_generate_tokens_cmd = bridge_generate_tokens_cmd + " " + " ".join(permissions)
        if expiration is None:
            expiration = "date -v +24H +'%Y-%m-%dT%H:%M:%S'"
        else:
            expiration = "date -v +" + expiration + " +'%Y-%m-%dT%H:%M:%S'"
        # expiration = subprocess.check_output(expiration, shell=True)
        # expiration = expiration.decode("utf-8").strip()        
        # expiration = None
        # bridge_generate_tokens_cmd = bridge_generate_tokens_cmd + " --expiration " + expiration
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
        url="https://up.storacha.network/bridge"
        headers = {
            "X-Auth-Secret": auth_secret,
            "Authorization": authorization,
        }
        data = {
            "method": method,
            "data": data,
        }
        try:
            results = requests.post(url, headers=headers, data=data)
        except requests.exceptions.RequestException as e:
            print(e)
        return results
    
    def install(self):
        detect_cmd = "w3 --version"
        w3_version = self.w3_version
        install_cmd = "sudo npm install -g @web3-storage/w3cli"
        update_cmd = "sudo npm update -g @web3-storage/w3cli"
        try:
            detect_results = subprocess.check_output(detect_cmd, shell=True)
            version = detect_results.decode("utf-8")
            version = version.split(", ")[1]
            version_list = version.split(".")
            version_list = [int(i.replace("\n", "")) for i in version_list]
            w3_version_list = w3_version.split(".")
            w3_version_list = [int(i.replace("\n", "")) for i in w3_version_list]
            if version_list[0] >= w3_version_list[0] and version_list[1] >= w3_version_list[1] and version_list[2] >= w3_version_list[2]:
                pass
            else:
                update_results = subprocess.run(update_cmd, shell=True, check=True)
                print("storacha_kit updated")                
        except subprocess.CalledProcessError:
            print("storacha_kit not installed")
            detect_npm_cmd = "npm --version"
            try:
                subprocess.run(detect_npm_cmd, shell=True, check=True)
                print("npm installed")
                print("installing storacha_kit")
                try:
                    subprocess.run(install_cmd, shell=True, check=True)
                    print("storacha_kit installed")
                except subprocess.CalledProcessError:
                    print("storacha_kit installation failed")
            except subprocess.CalledProcessError:
                print("npm not installed")
                print("storacha_kit installation failed")
        return True

    def test(self):
        print("storacha_kit test")
        self.install()
        email_did = self.login(self.metadata["login"])
        spaces = self.space_ls()
        this_space = spaces[list(spaces.keys())[0]]
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
        bridge_tokens = self.bridge_generate_tokens(this_space, permissions)
        results = {
            "email_did": email_did,
            "spaces": spaces,
            "bridge_tokens": bridge_tokens,
        }
        return results

if __name__ == "__main__":
    resources = {
    }
    metadata = {
        "login": "starworks5@gmail.com",
    }
    storacha_kit = storacha_kit(resources, metadata)
    test = storacha_kit.test()
    print(test)