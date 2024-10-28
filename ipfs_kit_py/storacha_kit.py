import os
import sys
import subprocess
import requests
class storacha_kit:
    def __init__(self, resources=None, metadata=None):
        self.resources = resources
        self.metadata = metadata
        
    def test():
        print("storacha_kit test")
        return True
    
    def space_ls():
        space_ls_cmd = "w3 space ls"
        try:
            results = subprocess.run(space_ls_cmd, shell=True, check=True)
        except subprocess.CalledProcessError:
            print("space_ls failed")
        return results
    
    def space_create():
        space_create_cmd = "w3 space create"
        try:
            results = subprocess.run(space_create_cmd, shell=True, check=True)
        except subprocess.CalledProcessError:
            print("space_create failed")
        return results
    
    def login():
        login_cmd = "w3 login"
        try:
            results = subprocess.run(login_cmd, shell=True, check=True)
        except subprocess.CalledProcessError:
            print("login failed")
        return results
    
    def logout():
        logout_cmd = "w3 logout"
        try:
            results = subprocess.run(logout_cmd, shell=True, check=True)
        except subprocess.CalledProcessError:
            print("logout failed")
        return results
    
    def bridge_generate_tokens():
        bridge_generate_tokens_cmd = "w3 bridge generate-tokens"
        try:
            results = subprocess.run(bridge_generate_tokens_cmd, shell=True, check=True)
        except subprocess.CalledProcessError:
            print("bridge_generate_tokens failed")
        return results
    
    def storacha_http_request(auth_secret, authorization,  method, data):
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
    
    def install():
        detect_cmd = "w3 --version"
        install_cmd = "npm install -g @web3-storage/w3cli"
        try:
            subprocess.run(detect_cmd, shell=True, check=True)
            print("storacha_kit already installed")
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

if __name__ == "__main__":
    resources = {
    }
    metadata = {
        "login": "starworks5@gmail.com",
    }
    
    storacha_kit.test()