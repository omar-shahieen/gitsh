import os
import hashlib
import tempfile
import zlib
from typing import Any, Dict, Optional


def compute_file_hash(filepath: str, algorithm: str = "sha1", BUFF_SIZE: int = 65536) -> str:
    hash_func = hashlib.new(algorithm)

    with open(filepath, "rb") as file:
        while chunk := file.read(BUFF_SIZE):
            hash_func.update(chunk)

    return hash_func.hexdigest()


def _read_decompress(path: str, chunk_size: int = 65536) -> bytes:
    decompressor = zlib.decompressobj()
    parts = []

    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            parts.append(decompressor.decompress(chunk))
        parts.append(decompressor.flush())

    return b"".join(parts)


def _write_compressed(path: str, header: bytes, data: bytes, chunk_size: int = 65536) -> None:
    dir_path = os.path.dirname(path)
    compressor = zlib.compressobj()

    with tempfile.NamedTemporaryFile(dir=dir_path, delete=False) as tmp:
        tmp_path = tmp.name
        try:
            tmp.write(compressor.compress(header))

            view = memoryview(data)
            for i in range(0, len(data), chunk_size):
                tmp.write(compressor.compress(view[i : i + chunk_size]))

            tmp.write(compressor.flush())
        except:
            os.unlink(tmp_path)
            raise

    os.replace(tmp_path, path)


def kvlm_parse(
    raw: bytes, start: int = 0, dct: Optional[Dict[Optional[bytes], Any]] = None
) -> Dict[Optional[bytes], Any]:
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
