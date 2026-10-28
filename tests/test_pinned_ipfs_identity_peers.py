"""Authored hermetic public-API fixtures, never native live qualification."""
import importlib.util,json,os,sys,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if os.environ.get("SVF_CANDIDATE_SDK"):
    spec=importlib.util.spec_from_file_location("ipfs_kit_py.assurance._svf_identity_candidate",os.environ["SVF_CANDIDATE_SDK"])
    sdk=importlib.util.module_from_spec(spec);sys.modules[spec.name]=sdk;spec.loader.exec_module(sdk)
else:
    import ipfs_kit_py.assurance.pinned_ipfs as sdk

IDENTITY="12D3KooWAuthoredUnitIdentity1234567890"
class PublicObservationTests(unittest.TestCase):
    def adapter(self,payload,status=200):
        calls=[]
        def transport(**kwargs):calls.append(kwargs);return status,json.dumps(payload).encode()
        return sdk.LivePinnedIpfsAdapter(transport=transport),calls
    def test_public_identity_uses_configured_local_rpc_and_preserves_observed_fields(self):
        a,calls=self.adapter({"ID":IDENTITY,"Addresses":["/ip4/127.0.0.1/tcp/4001"],"AgentVersion":"authored fixture"})
        result=a.node_id(deadline=time.monotonic()+1)
        self.assertTrue(result.success);self.assertEqual(result.metadata["ID"],IDENTITY)
        self.assertEqual(result.metadata["Addresses"],["/ip4/127.0.0.1/tcp/4001"])
        self.assertEqual(calls[0]["path"],"/api/v0/id");self.assertEqual(calls[0]["method"],"POST")
        self.assertEqual(calls[0]["query"],{});self.assertLessEqual(calls[0]["timeout"],1)
        self.assertTrue(a.simulated);self.assertFalse(a.live_provider)
        self.assertEqual(a.effect_count,0);self.assertTrue(result.canonical_result.request_id)
    def test_real_peer_records_are_not_synthesized_or_replaced(self):
        peer={"Peer":IDENTITY,"Addr":"/ip4/127.0.0.1/tcp/4001","Direction":1}
        a,calls=self.adapter({"Peers":[peer]});result=a.swarm_peers()
        self.assertEqual(result.metadata["Peers"],[peer]);self.assertEqual(result.metadata["peer_count"],1)
        self.assertEqual(calls[0]["path"],"/api/v0/swarm/peers");self.assertEqual(a.effect_count,0)
    def test_explicit_empty_and_null_peer_response_have_no_invented_peers(self):
        for value in [[],None]:
            with self.subTest(value=value):
                a,_=self.adapter({"Peers":value});result=a.swarm_peers()
                self.assertEqual(result.metadata["Peers"],[]);self.assertEqual(result.metadata["peer_count"],0)
                self.assertIs(result.metadata["peers_reported_null"],value is None)
                self.assertEqual(result.metadata["raw_observation"],{"Peers":value})
                raw=json.dumps({"Peers":value},sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
                self.assertEqual(result.metadata["raw_observation_canonical_sha256"],sdk.hashlib.sha256(raw).hexdigest())
    def test_missing_or_false_peer_result_is_not_a_legitimate_empty_swarm(self):
        for payload in [{},{"Peers":{},},{"Peers":[],"error":"actual failure"},{"Peers":[],"success":False}]:
            with self.subTest(payload=payload):
                a,_=self.adapter(payload)
                with self.assertRaises(sdk.PinnedIpfsBackendError):a.swarm_peers()
    def test_malformed_identity_and_public_metadata_fail_closed(self):
        for payload in [{},{"ID":""},{"ID":{}},{"ID":"short"},{"ID":IDENTITY,"Addresses":"not-list"},{"ID":IDENTITY,"Protocols":"not-list"},{"ID":IDENTITY,"error":"actual failure"}]:
            with self.subTest(payload=payload):
                a,_=self.adapter(payload)
                with self.assertRaises(sdk.PinnedIpfsBackendError):a.node_id()
    def test_malformed_peer_rows_and_bounds_fail_closed(self):
        for peers in [[{}],[{"Peer":None}],[{"Peer":IDENTITY,"Addr":"x"*2049}],[{"Peer":IDENTITY}]*257]:
            a,_=self.adapter({"Peers":peers})
            with self.assertRaises(sdk.PinnedIpfsBackendError):a.swarm_peers()
    def test_observation_response_byte_cap_applies_before_json_decode(self):
        def transport(**kwargs):return 200,b"x"*262145
        a=sdk.LivePinnedIpfsAdapter(transport=transport)
        for method in [a.node_id,a.swarm_peers]:
            with self.assertRaises(sdk.PinnedIpfsBackendError):method()
    def test_actual_http_adapter_requests_only_limit_plus_one_bytes(self):
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,limit):self.limit=limit;return json.dumps({"ID":IDENTITY,"Addresses":[]}).encode()
        response=Response();a=sdk.LivePinnedIpfsAdapter("http://127.0.0.1:5021")
        with patch.object(sdk.urllib.request,"urlopen",return_value=response) as request:
            result=a.node_id()
        self.assertTrue(result.success);self.assertEqual(response.limit,65537)
        self.assertEqual(request.call_args.args[0].full_url,"http://127.0.0.1:5021/api/v0/id")
    def test_http_failure_body_read_is_also_bounded(self):
        class FailureBody:
            def read(self, limit):self.limit=limit;return b"authored failure"
            def close(self):pass
        body=FailureBody()
        error=sdk.urllib.error.HTTPError("http://127.0.0.1:5021/api/v0/id",500,"fixture",{},body)
        adapter=sdk.LivePinnedIpfsAdapter("http://127.0.0.1:5021")
        with patch.object(sdk.urllib.request,"urlopen",side_effect=error):
            with self.assertRaises(sdk.PinnedIpfsBackendError) as caught:adapter.node_id()
        self.assertEqual(body.limit,65537)
        self.assertEqual(caught.exception.error.state.value,"unavailable")
    def test_expired_cancelled_or_closed_operations_make_no_rpc(self):
        for method in ["node_id","swarm_peers"]:
            a,calls=self.adapter({"ID":IDENTITY,"Peers":[]})
            with self.assertRaises(sdk.PinnedIpfsBackendError):getattr(a,method)(deadline=time.monotonic()-1)
            event=threading.Event();event.set()
            with self.assertRaises(sdk.PinnedIpfsBackendError):getattr(a,method)(cancel_event=event)
            a.close()
            with self.assertRaises(sdk.PinnedIpfsBackendError):getattr(a,method)()
            self.assertEqual(calls,[])
    def test_transport_failure_remains_typed_unavailable(self):
        def transport(**kwargs):raise OSError("authored unavailable")
        a=sdk.LivePinnedIpfsAdapter(transport=transport)
        for method in [a.node_id,a.swarm_peers]:
            with self.assertRaises(sdk.PinnedIpfsBackendError) as caught:method()
            self.assertEqual(caught.exception.error.state.value,"unavailable")

if __name__=="__main__":unittest.main()
