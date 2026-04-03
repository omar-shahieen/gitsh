import os
import tempfile
import zlib


def read_decompress(path: str, chunk_size: int = 65536) -> bytes:
    """Read and decompress a zlib-compressed file.
    
    Args:
        path: Path to the compressed file.
        chunk_size: Size of chunks to read at a time.
    
    Returns:
        Decompressed bytes.
    """
    decompressor = zlib.decompressobj()
    parts = []

    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            parts.append(decompressor.decompress(chunk))
        parts.append(decompressor.flush())

    return b"".join(parts)


def write_compressed(path: str, header: bytes, data: bytes, chunk_size: int = 65536) -> None:
    """Write and compress data to a zlib file atomically.
    
    Args:
        path: Path where the compressed file will be written.
        header: Header bytes to write first.
        data: Data bytes to compress and write.
        chunk_size: Size of chunks to compress at a time.
    """
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
