import unittest
from agent2agents.converters.claude_to_antigravity import ClaudeToAntigravityConverter


class ClaudeToAntigravityConverterProtobufTests(unittest.TestCase):
    def test_encode_and_decode_varint_round_trip(self):
        c = ClaudeToAntigravityConverter
        test_values = [0, 1, 2, 127, 128, 255, 300, 16384, 2097151, 268435455]
        for val in test_values:
            with self.subTest(val=val):
                encoded = c.encode_varint(val)
                decoded, length = c.decode_varint(encoded, 0)
                self.assertEqual(decoded, val)
                self.assertEqual(length, len(encoded))

    def test_decode_varint_with_offset(self):
        c = ClaudeToAntigravityConverter
        prefix = b"prefix_bytes"
        val = 456
        encoded = prefix + c.encode_varint(val)
        decoded, length = c.decode_varint(encoded, len(prefix))
        self.assertEqual(decoded, val)
        self.assertEqual(length, len(c.encode_varint(val)))

    def test_parse_protobuf_fields_wire_types(self):
        c = ClaudeToAntigravityConverter
        # Field 1 (wire 0, varint): tag = (1 << 3) | 0 = 8 -> b"\x08", value = 99 -> b"\x63"
        f1 = b"\x08\x63"
        # Field 2 (wire 2, length-delimited): tag = (2 << 3) | 2 = 18 -> b"\x12", len = 4, data = b"test"
        f2 = b"\x12\x04test"
        # Field 3 (wire 1, 64-bit): tag = (3 << 3) | 1 = 25 -> b"\x19", 8 bytes
        f3 = b"\x19" + b"12345678"
        # Field 4 (wire 5, 32-bit): tag = (4 << 3) | 5 = 37 -> b"\x25", 4 bytes
        f4 = b"\x25" + b"1234"

        payload = f1 + f2 + f3 + f4
        fields = c.parse_protobuf_fields(payload)

        self.assertIn(1, fields)
        self.assertEqual(fields[1], (0, 99))

        self.assertIn(2, fields)
        self.assertEqual(fields[2], (2, b"test"))

        self.assertIn(3, fields)
        self.assertEqual(fields[3], (1, b"12345678"))

        self.assertIn(4, fields)
        self.assertEqual(fields[4], (5, b"1234"))

    def test_build_user_payload_replaces_prompt_and_injects_metadata(self):
        c = ClaudeToAntigravityConverter
        # Simulated user payload template with field 19 containing field 12 marker
        # Field 19: tag = (19 << 3) | 2 = 154 -> varint b"\x9a\x01"
        # Inner: field 2 (original prompt), field 12 (wire 0, tag = 96 -> b"\x60\x01"), tail data
        f19_inner = b"\x12\x04orig\x60\x01more_settings"
        tpl_payload = b"\x9a\x01" + c.encode_varint(len(f19_inner)) + f19_inner
        meta_bytes = b"user_turn_uuid_meta"

        result = c.build_user_payload(tpl_payload, "Hello Antigravity!", meta_bytes)

        self.assertIn(b"Hello Antigravity!", result)
        self.assertIn(meta_bytes, result)
        self.assertIn(b"more_settings", result)
        self.assertNotIn(b"orig", result)

    def test_build_assistant_payload_replaces_text_and_injects_metadata(self):
        c = ClaudeToAntigravityConverter
        # Simulated assistant payload template with field 20
        # Field 20: tag = (20 << 3) | 2 = 162 -> varint b"\xa2\x01"
        # Inner: field 1 (wire 2, tag = 10 -> b"\x0a", len varint, content), tail
        f20_inner = b"\x0a\x04orig\x10\x02tail_flags"
        tpl_payload = b"\xa2\x01" + c.encode_varint(len(f20_inner)) + f20_inner
        meta_bytes = b"asst_turn_uuid_meta"

        result = c.build_assistant_payload(tpl_payload, "Assistant response text", meta_bytes)

        self.assertIn(b"Assistant response text", result)
        self.assertIn(meta_bytes, result)
        self.assertIn(b"tail_flags", result)
        self.assertNotIn(b"orig", result)


if __name__ == "__main__":
    unittest.main()
