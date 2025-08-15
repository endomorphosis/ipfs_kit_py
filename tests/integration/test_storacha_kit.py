import json
import os
import platform
import tempfile

import sys
from ipfs_kit_py import storacha_kit
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


class test_storacha_kit:
    def __init__(self, resources, metadata):
        self.metadata = metadata
        self.resources = resources
        self.storacha_kit = storacha_kit(resources, metadata)
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
        large_file_root = ""
        small_file_root = ""
        print("storacha_kit test")
        self.storacha_kit.install()
        email_did = self.storacha_kit.login(self.metadata["login"])
        spaces = self.storacha_kit.space_ls()
        this_space = spaces[list(spaces.keys())[2]]
        space_info = self.storacha_kit.space_info(this_space)
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
            "usage/report",
        ]
        timestamps.append(time.time())
        bridge_tokens = self.storacha_kit.bridge_generate_tokens(this_space, permissions)
        timestamps.append(time.time())
        usage_report = self.storacha_kit.usage_report(this_space)
        timestamps.append(time.time())
        upload_list = self.storacha_kit.upload_list(this_space)
        timestamps.append(time.time())
        upload_list_https = self.storacha_kit.upload_list_https(this_space)
        timestamps.append(time.time())
        tempdir = tempfile.gettempdir()
        if os.path.exists(os.path.join(tempdir, "small_file.bin")):
            small_file_name = os.path.join(tempdir, "small_file.bin")
            small_file_root = os.path.dirname(small_file_name)
        else:
            with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp:
                temp_filename = temp.name
                temp_path = os.path.join(tempdir, "small_file.bin")
                if platform.system() == "Windows":
                    with open(temp_path, "wb") as f:
                        f.write(b"\0" * small_file_size)
                else:
                    os.system(
                        "dd if=/dev/zero of="
                        + temp_path
                        + " bs=1M count="
                        + str(small_file_size / 1024)
                    )
                small_file_name = os.path.join(os.path.dirname(temp_filename), "small_file.bin")
                small_file_root = os.path.dirname(temp_filename)
        timestamps.append(time.time())
        upload_add = self.storacha_kit.upload_add(this_space, small_file_name)
        timestamps.append(time.time())
        upload_add_https = self.storacha_kit.upload_add_https(
            this_space, small_file_name, small_file_root
        )
        timestamps.append(time.time())
        store_add = self.storacha_kit.store_add(this_space, small_file_name)
        timestamps.append(time.time())
        store_add_https = self.storacha_kit.store_add_https(
            this_space, small_file_name, small_file_root
        )
        timestamps.append(time.time())
        upload_rm = self.storacha_kit.upload_remove(this_space, upload_add)
        timestamps.append(time.time())
        upload_rm_https = self.storacha_kit.upload_remove_https(this_space, store_add_https)
        timestamps.append(time.time())
        os.remove(small_file_name)
        timestamps.append(time.time())
        store_get = self.storacha_kit.store_get(this_space, store_add[0])
        timestamps.append(time.time())
        store_get_https = self.storacha_kit.store_get_https(this_space, store_add[0])
        timestamps.append(time.time())
        store_remove = self.storacha_kit.store_remove(this_space, store_add[0])
        timestamps.append(time.time())
        store_remove_https = self.storacha_kit.store_remove_https(this_space, store_add[0])
        timestamps.append(time.time())
        batch_operations = self.storacha_kit.batch_operations(
            this_space, [large_file_name], [store_add[0]]
        )
        timestamps.append(time.time())
        file_size = 6 * 1024 * 1024 * 1024
        if os.path.exists(os.path.join(tempdir, "large_file.bin")):
            large_file_name = os.path.join(tempdir, "large_file.bin")
            large_file_root = os.path.dirname(large_file_name)
            with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as temp:
                temp_filename = temp.name
                temp_path = os.path.join(tempdir, "large_file.bin")
                if platform.system() == "Windows":
                    with open(temp_path, "wb") as f:
                        f.write(b"\0" * large_file_size)
                else:
                    os.system(
                        "dd if=/dev/zero of="
                        + temp_path
                        + " bs=1M count="
                        + str(large_file_size / 1024)
                    )
                large_file_name = os.path.join(os.path.dirname(temp_filename), "large_file.bin")
                large_file_name = os.path.dirname(temp_filename)
        timestamps.append(time.time())
        shard_upload = self.storacha_kit.shard_upload(this_space, large_file_name, large_file_root)
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
            "batch_operations": batch_operations,
            "shard_upload": shard_upload,
        }
        for key in results.keys():
            if isinstance(results[key], ValueError):
                results[key] = f"ValueError: {results[key]}"
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
            "batch_operations": timestamps[16] - timestamps[15],
            "shard_upload": timestamps[17] - timestamps[16],
        }
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(parent_dir, "test", "test_storacha_kit_results.json"), "w") as file:
            file.write(json.dumps(results, indent=4))
        with open(
            os.path.join(parent_dir, "test", "test_storacha_kit_timestamps.json"), "w"
        ) as file:
            file.write(json.dumps(timestamps_results, indent=4))
        return results

    def __test__(self):
        return self.test()

    def __call__(self, *args, **kwargs):
        return self.test()


if __name__ == "__main__":
    resources = {}
    metadata = {
        "login": "starworks5@gmail.com",
    }
    test = test_storacha_kit(resources, metadata)
    test()
