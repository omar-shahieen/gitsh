from typing import Any, Dict, Optional





def kvlm_parse(
    raw: bytes, start: int = 0, dct: Optional[Dict[Optional[bytes], Any]] = None
) -> Dict[Optional[bytes], Any]:
    """Parse key-value list with message (KVL+M) format.

    Args:
        raw: The raw bytes to parse.
        start: Starting position in the bytes.
        dct: Dictionary to populate (default: new dict).

    Returns:
        The parsed dictionary.
    """
    if not dct:
        dct = dict()

    spc = raw.find(b" ", start)
    nl = raw.find(b"\n", start)

    if (spc < 0) or (nl < spc):
        assert nl == start
        dct[None] = raw[start + 1 :]
        return dct

    key = raw[start:spc]

    end = start
    while True:
        end = raw.find(b"\n", end + 1)
        if raw[end + 1] != ord(" "):
            break

    value = raw[spc + 1 : end].replace(b"\n ", b"\n")

    if key in dct:
        if type(dct[key]) == list:
            dct[key].append(value)
        else:
            dct[key] = [dct[key], value]
    else:
        dct[key] = value

    return kvlm_parse(raw, start=end + 1, dct=dct)


def kvlm_serialize(kvlm: Dict[Optional[bytes], Any]) -> bytes:
    """Serialize a KVL+M dictionary to bytes.

    Args:
        kvlm: The dictionary to serialize.

    Returns:
        The serialized bytes.
    """
    ret = b""

    for k in kvlm.keys():
        if k is None:
            continue
        val = kvlm[k]

        if not isinstance(val, list):
            val = [val]

        for v in val:
            ret += k + b" " + (v.replace(b"\n", b"\n ")) + b"\n"

    ret += b"\n" + kvlm[None]
    return ret
