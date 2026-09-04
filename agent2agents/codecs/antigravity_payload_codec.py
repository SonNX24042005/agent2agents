"""Encode and rewrite protobuf payloads used by Antigravity session steps."""


class AntigravityPayloadCodec:
    """Helpers for preserving native Antigravity payload structure."""

    @staticmethod
    def encode_varint(n):
        buf = bytearray()
        while True:
            towrite = n & 0x7F
            n >>= 7
            if n:
                buf.append(towrite | 0x80)
            else:
                buf.append(towrite)
                break
        return bytes(buf)

    @staticmethod
    def decode_varint(data, offset):
        val = 0
        shift = 0
        i = offset
        while i < len(data):
            byte = data[i]
            i += 1
            val |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                return val, i - offset
            shift += 7
        return val, i - offset

    @classmethod
    def parse_protobuf_fields(cls, payload):
        """Parse top-level protobuf fields into a tag-to-value mapping."""
        fields = {}
        i = 0
        while i < len(payload):
            tag_val, tag_len = cls.decode_varint(payload, i)
            if tag_len == 0:
                break
            tag = tag_val >> 3
            wire = tag_val & 0x7
            data_start = i + tag_len
            if wire == 0:
                val, value_len = cls.decode_varint(payload, data_start)
                data_end = data_start + value_len
                val_data = val
            elif wire == 2:
                length, length_len = cls.decode_varint(payload, data_start)
                content_start = data_start + length_len
                data_end = content_start + length
                val_data = payload[content_start:data_end]
            elif wire == 1:
                data_end = data_start + 8
                val_data = payload[data_start:data_end]
            elif wire == 5:
                data_end = data_start + 4
                val_data = payload[data_start:data_end]
            else:
                break
            fields[tag] = (wire, val_data)
            i = data_end
        return fields

    @classmethod
    def build_user_payload(cls, template_payload, new_text_str, meta_bytes):
        prompt_bytes = new_text_str.encode("utf-8")
        fields = cls.parse_protobuf_fields(template_payload)
        field_19_entry = fields.get(19)
        if not field_19_entry or not field_19_entry[1]:
            return template_payload
        field_19_data = field_19_entry[1]

        i = 0
        user_tail_offset = None
        while i < len(field_19_data):
            tag_val, tag_len = cls.decode_varint(field_19_data, i)
            if tag_len == 0:
                break
            tag = tag_val >> 3
            wire = tag_val & 0x7
            if tag == 12:
                user_tail_offset = i
                break
            data_start = i + tag_len
            if wire == 0:
                _, value_len = cls.decode_varint(field_19_data, data_start)
                i = data_start + value_len
            elif wire == 2:
                length, length_len = cls.decode_varint(field_19_data, data_start)
                i = data_start + length_len + length
            elif wire == 1:
                i = data_start + 8
            elif wire == 5:
                i = data_start + 4
            else:
                break

        if user_tail_offset is None:
            user_tail_offset = field_19_data.find(b"\x62", 30)
            if user_tail_offset == -1:
                return template_payload

        user_field_19_tail = field_19_data[user_tail_offset:]
        field_2 = b"\x12" + cls.encode_varint(len(prompt_bytes)) + prompt_bytes
        field_3_submessage = b"\x0a" + cls.encode_varint(len(prompt_bytes)) + prompt_bytes
        field_3 = (
            b"\x1a"
            + cls.encode_varint(len(field_3_submessage))
            + field_3_submessage
        )
        field_4 = b"\x22\x00"
        field_19_content = field_2 + field_3 + field_4 + user_field_19_tail
        field_19 = (
            b"\x9a\x01"
            + cls.encode_varint(len(field_19_content))
            + field_19_content
        )
        return (
            b"\x08\x0e\x20\x03\x2a"
            + cls.encode_varint(len(meta_bytes))
            + meta_bytes
            + field_19
        )

    @classmethod
    def build_assistant_payload(cls, template_payload, new_text_str, meta_bytes):
        response_bytes = new_text_str.encode("utf-8")
        fields = cls.parse_protobuf_fields(template_payload)
        field_20_entry = fields.get(20)
        if not field_20_entry or not field_20_entry[1]:
            return template_payload
        field_20_data = field_20_entry[1]

        _, tag_len = cls.decode_varint(field_20_data, 0)
        field_1_len, field_1_len_bytes = cls.decode_varint(field_20_data, tag_len)
        assistant_field_20_tail = field_20_data[
            tag_len + field_1_len_bytes + field_1_len :
        ]

        field_1 = b"\x0a" + cls.encode_varint(len(response_bytes)) + response_bytes
        field_20_content = field_1 + assistant_field_20_tail
        field_20 = (
            b"\xa2\x01"
            + cls.encode_varint(len(field_20_content))
            + field_20_content
        )
        return (
            b"\x08\x0f\x20\x03\x2a"
            + cls.encode_varint(len(meta_bytes))
            + meta_bytes
            + field_20
        )


__all__ = ["AntigravityPayloadCodec"]
