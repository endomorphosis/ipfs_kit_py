import os

class aria2:
    def __init__(self):
        self.aria2_version = "1.35.0"
        self.aria2_url = ""
        self.aria2_dir = "/usr/local/aria2"
        self.aria2_conf_dir = "/etc/aria2"
        self.aria2_conf_file = "/etc/aria2/aria2.conf"
        self.aria2_log_dir = "/var/log/aria2"
        self.aria2_log_file = "/var/log/aria2/aria2.log"
        self.aria2_systemd_dir = "/etc/systemd/system"
        self.aria2_systemd_file = "/etc/systemd/system/aria2.service"
        self.aria2_user = "aria2"
        self.aria2_group = "aria2"
        self.aria2_rpc_secret = "123456"
        self.aria2_rpc_port = "6800"
        self.aria2_rpc_listen_all = "true"
        self.aria2_rpc_enable = "true"
        self.aria2_rpc_user = "admin"
        self.aria2_rpc_pass = "admin"
        self.aria2_rpc_allow_origin_all = "true"
        self.aria2_rpc_max_conn = "16"
        self.aria2_rpc_max_req = "16"

    def install(self):
        this_dir = os.path.dirname(os.path.realpath(__file__))
        parent_dir = os.path.abspath(os.path.join(this_dir, os.pardir))
        aria2_dir = os.path.join(parent_dir, "aria2")
        build_dir = os.path.join(aria2_dir, "build")
        build_dir = os.path.realpath(build_dir)
        if os.path.isdir(build_dir) == False:
            os.mkdir(build_dir)
        source = "https://github.com/aria2/aria2/releases/download/release-1.37.0/aria2-1.37.0.tar.gz"
        results = os.system("wget " + source + " -O /tmp/aria2.tar.gz")
        results = os.system("tar -zxvf /tmp/aria2.tar.gz -C /tmp")
        build_command = "cd /tmp/aria2-1.37.0 && ./configure  --prefix=" + build_dir + "  DESTDIR=" + build_dir + " && make DESTDIR=" + build_dir + " && make install DESTDIR=" + build_dir  
        move_command = "mv " + os.path.join(os.path.join(build_dir,'bin'),'aria2c') +  " " + os.path.join(aria2_dir, 'aria2c')
        results = os.system(build_command)
        results = os.system(move_command)
        return results

    def test_aria2(self):
        this_dir = os.path.dirname(os.path.realpath(__file__))
        parent_dir = os.path.abspath(os.path.join(this_dir, os.pardir))
        aria2_dir = os.path.join(parent_dir, "aria2")
        aria2_append_path = "PATH=$PATH:"+aria2_dir + " "
        results = os.system(aria2_append_path + "aria2c --version")
        return results
    
if __name__ == "__main__":
    this_test = aria2()
    results = this_test.test_aria2()
    print(results)
    this_test.install()
    results = this_test.test_aria2()
    print(results)

