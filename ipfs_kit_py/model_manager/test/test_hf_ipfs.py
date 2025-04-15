import os
import sys
class test_hf_ipfs:
    def __init__(self, resources, **kwargs):
        self.test = self.test
        pass
    
    def __call__(self, method, **kwargs):
        if method == "test":
            return self.test(self, **kwargs)

    def test(self, **kwargs):
        parent_dir = os.path.dirname(os.path.dirname(__file__))
        sys.path.append(parent_dir)
        #this is what we want to test
        from transformers import AutoModel
        #model = AutoModel.from_pretrained("google-bert/bert-base-cased")
        #what do we want to call the library?
        from ipfs_transformers import AutoModel
        #do we want to use the ipfs hash or the model name? This requires IPNS to be enabled
        #model = T5Model.from_ipfs("QmWJr4M1VN5KpJjqCsJsJg7PDmFoqQYs1BKpYxcdMY1qkh")
        #model = AutoModelForSeq2SeqLM.from_auto_download("t0") # 40GB test this afterwards
        # model = AutoModelForSeq2SeqLM.from_auto_download("stablelm-zephyr-3b-GGUF-Q2_K")  # 1.5GB
        
        # model = AutoModel.from_auto_download("bge-small-en-v1.5")  # 1.5GB
        model = AutoModel.from_ipfs("QmccfbkWLYs9K3yucc6b3eSt8s8fKcyRRt24e3CDaeRhM1")  # 1.5GB
        

        #model = T5Model.from_auto_download("google-bert/t5_11b_trueteacher_and_anli")
        print(dir(model))
        print("done")
        #do we want to use the s3cfg for s3 caching?
        #model = T5Model.from_auto_download(
        #    model_name="google-bert/t5_11b_trueteacher_and_anli",
        #    s3cfg={
        #        "bucket": "cloud",
        #       "endpoint": "https://storage.googleapis.com",
        #        "secret_key": "",
        #        "access_key": "",
        #    }
        #)

if __name__ == "__main__":
    test_hf_ipfs(None).test()
    print("done")
    