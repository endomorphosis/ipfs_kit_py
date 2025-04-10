from multiformats.varint import decode
import pytest

from ipld_dag_pb.decode import decode_node


class TestPBNode():
    def test_bad_wire_type(self):
        block = bytearray.fromhex("0a050001020304")  # hex string in python should be of even length
        for i in range(8):
            if i == 2:  # the valid case, length-delimited bytes
                continue
            block[0] = (1 << 3) | i  # field 1, wire-type i
            with pytest.raises(Exception, match=".*PBNode.*wire type"):
                decode_node(block)

    def test_bad_field_num(self):
        block = bytearray.fromhex("0a050001020304")
        for i in range(32):
            if i == 1 or i == 2:  # the valid case, fields 1 and 2
                continue
            block[0] = (i << 3) | 2  # field i, wiretype 2
            with pytest.raises(Exception, match=".*PBNode.*fieldNumber"):
                decode_node(block)

    def test_duplicate_data(self):
        with pytest.raises(Exception, match=".*PBNode.*duplicate Data section"):
            decode_node(bytes.fromhex("0a0500010203040a050001020304"))


class TestPBLink():
    def test_bad_wire_type_for_hash(self):
        block = bytearray.fromhex("120b0a09015500050001020304")
        for i in range(8):
            if i == 2: # the valid case, length-delimited bytes
                continue
            block[2] = (1 << 3) | i  # field 1, wireType i
            with pytest.raises(ValueError, match=".*PBLink.*wire type.*Hash"):
                decode_node(block)

    def test_bad_wire_type_for_name(self):
        block = bytearray.fromhex("12160a090155000500010203041209736f6d65206e616d65")
        for i in range(8):
            if i == 2:  # the valid case, length-delimited bytes
                continue
            block[13] = (2 << 3) | i  # field 2, wire_type i
            with pytest.raises(ValueError, match=".*PBLink.*wire type.*Name"):
                decode_node(block)

    def test_bad_wire_type_for_t_size(self):
        block = bytearray.fromhex("120e0a0901550005000102030418f207")
        for i in range(8):
            if i == 0:  # the valid case, varint
                continue
            block[13] = (3 << 3) | i  # field 2, wireType i
            with pytest.raises(ValueError, match=".*PBLink.*wire type.*Tsize"):
                decode_node(block)

    def test_bad_field_num(self):
        block = bytearray.fromhex("120b0a09015500050001020304")
        for i in range(32):
            if i == 1 or i == 2 or i == 3:  # the valid case, fields 1, 2 and 3
                continue
            block[2] = (i << 3) | 2  # field i, wire_type 2
            with pytest.raises(Exception, match=".*PBLink.*field number"):
                decode_node(block)

    def test_name_before_hash(self):
        with pytest.raises(Exception, match=".*PBLink.*Name before Hash"):
            decode_node(bytearray.fromhex("120d12000a09015500050001020304"))

    def test_t_size_before_hash(self):
        with pytest.raises(Exception, match=".*PBLink.*Tsize before Hash"):
            decode_node(bytes.fromhex("120e18f2070a09015500050001020304"))

    def test_t_size_before_name(self):
        with pytest.raises(Exception, match=".*PBLink.*Tsize before Name"):
            decode_node(bytearray.fromhex("120518f2071200"))

    def test_duplicate_hash(self):
        with pytest.raises(Exception, match=".*PBLink.*duplicate Hash"):
            decode_node(bytearray.fromhex("12160a090155000500010203040a09015500050001020304"))

    def test_duplicate_name(self):
        with pytest.raises(Exception, match=".*PBLink.*duplicate Name"):
            decode_node(bytearray.fromhex("12210a090155000500010203041209736f6d65206e616d651209736f6d65206e616d65"))

    def test_duplicate_t_size(self):
        with pytest.raises(Exception, match=".*PBLink.*duplicate Tsize"):
            decode_node(bytearray.fromhex("12110a0901550005000102030418f20718f207"))
