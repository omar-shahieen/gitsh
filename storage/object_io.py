
import hashlib
import os ,re,tempfile,zlib
from typing import Optional, List,Any

from .repository import GitRepository, repo_file,repo_dir , repo_find
from objects import GitObject, get_object_class, initialize_registry


# Initialize the object registry on import
initialize_registry()




def _read_decompress(path: str, chunk_size: int = 65536) -> bytes:
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


def _write_compressed(path: str, header: bytes, data: bytes, chunk_size: int = 65536) -> None:
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

def object_write(obj: GitObject, repo: Optional[GitRepository] = None) -> str:
    """Write a Git object to the repository.

    Args:
        obj: The Git object to write.
        repo: The repository to write to (optional).

    Returns:
        The SHA hash of the written object.
    """
    data = obj.serialize()
    header = obj.fmt + b" " + str(len(data)).encode() + b"\x00"
    h = hashlib.sha1()
    h.update(header)
    h.update(data)
    sha = h.hexdigest()

    if repo:
        path = repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)
        if not os.path.exists(path):
            _write_compressed(path, header, data)
    return sha


def object_read(repo: GitRepository, sha: str) -> Optional[GitObject]:
    """Read a Git object from the repository.

    Args:
        repo: The repository to read from.
        sha: The SHA hash of the object.

    Returns:
        The Git object, or None if not found.
    """
    path = repo_file(repo, "objects", sha[0:2], sha[2:])

    if not os.path.isfile(path):
        return None

    raw = _read_decompress(path)
    x = raw.find(b" ")
    fmt = raw[0:x]

    y = raw.find(b"\x00", x)
    size = int(raw[x + 1 : y].decode("ascii"))

    if size != len(raw) - y - 1:
        raise Exception(f"Malformed object {sha}: bad length")

    obj_class = get_object_class(fmt)
    if not obj_class:
        raise Exception(f"Unknown type {fmt.decode('ascii')} for object {sha}")

    return obj_class(raw[y + 1 :])


def object_find(repo: GitRepository, name: str, fmt: Optional[bytes] = None, follow: bool = True) -> Optional[str]:
    """Find an object by name and optionally verify its type.

    Args:
        repo: The repository.
        name: The object name or reference.
        fmt: Expected format (optional).
        follow: Whether to follow tags/commits to trees.

    Returns:
        The SHA hash, or None.
    """
    
    sha_candidates = object_resolve(repo , name)
    
    if not sha_candidates:
        raise Exception(f"No such reference {name}.")
    
    if len(sha_candidates) > 1 :
        raise Exception(f"Ambiguous reference {name}: Candidates are:\n - {'\n - '.join(sha_candidates)}.")
    
    sha =sha_candidates[0]
    
    
    if not fmt : 
        return sha

    while True :
        obj = object_read(repo , sha)
        
        if obj.fmt == fmt :
            return sha
        
        if not follow :
            return None 
        
        if obj.fmt == b'tag':
            sha = obj.kvlm[b"object"].decode('ascii') # tag's sha
        elif obj.fmt == b'commit' and fmt ==b'tree':
            sha =obj.kvlm[b'tree'].decode("ascii")
            
        else:
            return None 
    

def object_resolve(repo: GitRepository, name: str) -> Optional[List[str]]:
    """Resolve a name to possible SHA hashes.

    Args:
        repo: The repository.
        name: The name to resolve.

    Returns:
        List of candidate SHAs, or None.
    """
    from reference import ref_resolve

    candidates= list()
    hashRE = re.compile(r"^[0-9A-Fa-f]{4,40}$")
    
    
    # empty string? Abort
    if not name.strip():
        return None 
    
    # head is nonambiguous
    if name == "HEAD":
        return [ref_resolve(repo , "HEAD")]
    
    # if it's a hex string , try for hash
    if hashRE.match(name):
        
        name = name.lower()
        
        prefix = name[:2]
        path = repo_dir(repo, "objects" , prefix , mkdir=False)
        
        if path :
            rem = name[2:]
            
            for f in os.listdir(path):
                if f.startswith(rem):
                    candidates.append(prefix + f)
                
    # is there tags  ? 
    as_tag = ref_resolve(repo , "refs/tags/" + name)
    if as_tag : 
        candidates.append(as_tag)
        
    # is there branches ? 
    as_branch = ref_resolve(repo , "refs/heads/" + name)
    if as_branch:
        candidates.append(as_branch)
        
    # is there remote branches 
    as_remote_branch = ref_resolve(repo , "repo/remotes/" + name)
    if as_remote_branch:
        candidates.append(as_remote_branch)
        
    return candidates



def object_hash(fd: Any, fmt: bytes, repo: Optional[GitRepository] = None) -> str:
    """Hash data from a file descriptor and write as object.

    Args:
        fd: File descriptor to read data from.
        fmt: Object format.
        repo: Repository to write to (optional).

    Returns:
        The SHA hash.
    """
    data = fd.read()

    obj_class = get_object_class(fmt)
    if not obj_class:
        raise Exception(f"Unknown type {fmt.decode('ascii')} ")
    
    obj = obj_class(data)
   

    return object_write(obj, repo)

