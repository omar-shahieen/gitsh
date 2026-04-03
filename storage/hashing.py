import hashlib


def compute_file_hash(filepath: str, algorithm: str = "sha1", buffer_size: int = 65536) -> str:
    """Compute hash of a file.
    
    Args:
        filepath: Path to the file.
        algorithm: Hash algorithm to use (default: sha1).
        buffer_size: Size of chunks to read at a time.
    
    Returns:
        Hexadecimal hash string.
    """
    hash_func = hashlib.new(algorithm)

    with open(filepath, "rb") as file:
        while chunk := file.read(buffer_size):
            hash_func.update(chunk)

    return hash_func.hexdigest()
