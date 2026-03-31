
import hashlib
import zlib
import os
import tempfile
import configparser
import sys
from typing import Optional, List, Dict, Any, Set, Tuple
from abc import ABC, abstractmethod


# -----------------------------------------------------------------------------
# utility helpers
# -----------------------------------------------------------------------------

def compute_file_hash(filepath: str, algorithm: str = 'sha1', BUFF_SIZE: int = 65536) -> str:
    """Compute the hash of a file using the specified algorithm.
    
    Args:
        filepath: Path to the file to hash.
        algorithm: Hash algorithm to use (default: 'sha1').
        BUFF_SIZE: Chunk size for reading file (default: 65536 bytes).
    
    Returns:
        Hexadecimal digest of the file hash.
    """

    hash_func = hashlib.new(algorithm)
    
    with open(filepath, 'rb') as file :
        
        while chunk := file.read(BUFF_SIZE): # default 64kb chunck
            hash_func.update(chunk)
            
    return hash_func.hexdigest()


def repo_path(repo: 'GitRepository', *path: str) -> str:
    """Compute path under repo's gitdir.
    
    Args:
        repo: GitRepository instance.
        *path: Path components to join.
    
    Returns:
        Full path under the repository's gitdir.
    """
    return os.path.join(repo.gitdir, *path)

def repo_file(repo: 'GitRepository', *path: str, mkdir: bool = False) -> Optional[str]:
    """Create file path under repo and optionally create parent directories.
    
    Same as repo_path, but create dirname(*path) if absent.  
    For example, repo_file(r, "refs", "remotes", "origin", "HEAD") will create
    .git/refs/remotes/origin.
    
    Args:
        repo: GitRepository instance.
        *path: Path components.
        mkdir: If True, create parent directories.
    
    Returns:
        Full path if successful, None if directory creation fails.
    """

    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)

def repo_dir(repo: 'GitRepository', *path: str, mkdir: bool = False) -> Optional[str]:
    """Get directory path under repo and optionally create it.
    
    Same as repo_path, but create directory if absent when mkdir=True.
    
    Args:
        repo: GitRepository instance.
        *path: Path components.
        mkdir: If True, create the directory.
    
    Returns:
        Directory path if it exists or was created, None otherwise.
    
    Raises:
        Exception: If path exists but is not a directory.
    """

    path = repo_path(repo, *path)

    if os.path.exists(path):
        if (os.path.isdir(path)):
            return path
        else:
            raise Exception(f"Not a directory {path}")

    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None
    
    

def repo_default_config() -> configparser.ConfigParser:
    """Create and return default git repository configuration.
    
    Returns:
        ConfigParser with default git configuration settings.
    """
    ret = configparser.ConfigParser()
    
    ret.add_section("core")
    
    ret.set("core","repositoryformatversion", "0") # format version
    ret.set("core","filemode", "false") # disable tracking of file modes
    ret.set("core","bare", "false") # indicates that repo has a worktree
    
    return ret

def repo_create(path: str) -> 'GitRepository':
    """Create a new git repository at the specified path.
    
    Args:
        path: Directory path where repository will be created.
    
    Returns:
        GitRepository instance for the created repository.
    
    Raises:
        Exception: If path is not a directory or is not empty.
    """
    repo =  GitRepository(path, True)
    
    # make sure the path either does not exist or is an empty dir 
    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception(f"{path } is not a directory!")
        if os.path.exists(repo.gitdir) and os.listdir(repo.gitdir):
            raise Exception(f"{path} is not empty!")
        
    else :
        os.makedirs(repo.worktree)
        

    assert repo_dir(repo , "branches" ,mkdir=True)
    assert repo_dir(repo , "objects" ,mkdir=True)
    assert repo_dir(repo , "refs", 'tags' ,mkdir=True)
    assert repo_dir(repo , "refs" , "heads" ,mkdir=True)
    
    # /git/description
    with open(repo_file(repo,"description") ,"w") as f:
        f.write("Unnamed repository; edit this file 'description' to name the repository.\n")
    
    # .git/HEAD
    with open(repo_file(repo,"HEAD") ,"w") as f:
        f.write("ref: refs/heads/master\n")
        
    with open(repo_file( repo , "config" ), "w") as f:
        config = repo_default_config()
        
        config.write(f)
        
        
    return repo

def repo_find(path: str = ".", required: bool = True) -> Optional['GitRepository']:
    """Find and return the git repository containing the given path.
    
    Args:
        path: Starting path to search from (default: current directory).
        required: If True, raise exception if no repo found.
    
    Returns:
        GitRepository instance if found, None if not required.
    
    Raises:
        Exception: If required=True and no git directory found.
    """
    path = os.path.realpath(path)

    if os.path.isdir(os.path.join(path,".git")):
        return GitRepository(path)
    
    
    parent = os.path.realpath(os.path.join(path, ".."))
    
    if path == parent : 
        
        if required : 
            raise Exception("No git directory.") 
        else :
            return None 
        
        
    return repo_find(parent , required)



# -----------------------------------------------------------------------------
# repository core classes
# -----------------------------------------------------------------------------

class GitRepository(object):
    """A git repository"""

    worktree: str = ''
    gitdir: str = ''
    conf: configparser.ConfigParser

    def __init__(self, path: str, force: bool = False) -> None:
        """Initialize a GitRepository.

        Args:
            path: Working tree path.
            force: If True, allow repository creation even if .git is missing.
        """
        self.worktree = path
        self.gitdir = os.path.join(path, ".gitsh")

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception(f"Not a Git repository {path}")

        # Read configuration file in .git/config
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, "config")

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuration file missing")

        if not force:
            vers = int(self.conf.get("core", "repositoryformatversion"))
            if vers != 0:
                raise Exception(f"Unsupported repositoryformatversion: {vers}")
            
            
class GitObject(ABC):

    def __init__(self, data: Optional[bytes] = None) -> None:
        if data is not None:
            self.deserialize(data)
        else:
            self.init()

    @abstractmethod
    def serialize(self) -> bytes:
        """Must be implemented by subclasses."""
        ...

    @abstractmethod
    def deserialize(self, data: bytes) -> None:
        """Must be implemented by subclasses."""
        ...

    def init(self) -> None:
        pass  # default implementation
    
    
class GitBlob(GitObject):
    fmt=b'blob'

    def serialize(self):
        return self.blobdata

    def deserialize(self, data):
        self.blobdata = data
        
        
    
class GitTreeLeaf(object):
    def __init__(self, mode: bytes, path: str, sha: str) -> None:
        self.mode: bytes = mode
        self.path: str = path
        self.sha: str = sha
        
        
def tree_parse_one(raw: bytes, start: int = 0) -> Tuple[int, GitTreeLeaf]:
    """Parse a single tree entry from raw tree object bytes.

    Args:
        raw: Raw tree data.
        start: Start position in raw bytes.

    Returns:
        Tuple of (next position, GitTreeLeaf instance).
    """
    # find the space terminator of the mode 
    
    x = raw.find(b' ', start)
    assert x-start == 5 or x-start == 6
    
    mode = raw[start : x]
    
    if len(mode) == 5 :
        mode = b'0' + mode
        
    
    # find null terminator of the path
    
    y= raw.find(b'\x00' , x)
    path = raw[x+1:y]
    
    
    raw_sha = int.from_bytes(raw[y+1:y+21] , "big")
    # and convert it into an hex string, padded to 40 chars
    # with zeros if needed.
    sha = format(raw_sha , "040x")
    
    return y+21 , GitTreeLeaf(mode, path.decode('utf8'),sha)

def tree_parse(raw: bytes) -> List[GitTreeLeaf]:
    """Parse raw tree data into a list of GitTreeLeaf entries."""
    pos = 0
    max_len = len(raw)
    ret: List[GitTreeLeaf] = []
    while pos < max_len:
        pos, data = tree_parse_one(raw, pos)
        ret.append(data)

    return ret

def tree_leaf_sort_key(leaf: GitTreeLeaf) -> str:
    """Sort tree leaves according to Git tree ordering rules."""
    if leaf.mode.startswith(b"4"):
        return leaf.path + "/"
    else:
        return leaf.path

def tree_serialize(obj: 'GitTree') -> bytes:
    """Serialize a GitTree object to raw bytes."""
    obj.items.sort(key=tree_leaf_sort_key)
    ret = b''

    for i in obj.items:
        ret += i.mode
        ret += b' '
        ret += i.path.encode("utf8")
        ret += b'\x00'
        sha = int(i.sha, 16)
        ret += sha.to_bytes(20, byteorder="big")

    return ret


# -----------------------------------------------------------------------------
# GitTree class and tree helpers
# -----------------------------------------------------------------------------

class GitTree(GitObject):
    fmt=b'tree'

    def serialize(self):
        return tree_serialize(self)

    def deserialize(self, data):
        self.items = tree_parse(data)
    
    def init(self):
        self.items = list()
        

def ls_tree(repo: 'GitRepository', ref: str, recursive: Optional[bool] = None, prefix: str = "") -> None:
    """List tree contents recursively or non-recursively."""
    sha = object_find(repo, ref, fmt=b'tree')
    obj = object_read(repo, sha)

    for item in obj.items:
        if len(item.mode) == 5:
            type = item.mode[0:1]
        else:
            type = item.mode[0:2]            
            
        match type:
            case b'04': type = "tree"
            case b'10': type = "blob" # A regular file.
            case b'12': type = "blob" # A symlink. Blob contents is link target.
            case b'16': type = "commit" # A submodule   
            case _: raise Exception(f"Weird tree leaf mode {item.mode}")
            
        if not (recursive and type=='tree'): # This is a leaf
            print(f"{'0' * (6 - len(item.mode)) + item.mode.decode('ascii')} {type} {item.sha}\t{os.path.join(prefix, item.path)}")
        else:
            ls_tree(repo, item.sha, recursive, os.path.join(prefix, item.path))

         


class GitTag(GitObject):
    fmt = b'tag'

    def serialize(self) -> bytes:
        """Serialize tag object to bytes."""
        return b''

    def deserialize(self, data: bytes) -> None:
        """Deserialize tag object from bytes."""
        self.data = data


# -----------------------------------------------------------------------------
# storage helpers (compression and object I/O)
# -----------------------------------------------------------------------------

def _read_decompress(path: str, chunk_size: int = 65536) -> bytes:
    """Decompress a file in chunks to avoid loading full file at once.
    
    Args:
        path: Path to compressed file.
        chunk_size: Size of chunks to read (default: 65536 bytes).
    
    Returns:
        Decompressed data as bytes.
    """
    decompressor = zlib.decompressobj()
    parts = []

    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            parts.append(decompressor.decompress(chunk))
        parts.append(decompressor.flush())

    return b"".join(parts)


def _write_compressed(path: str, header: bytes, data: bytes, chunk_size: int = 65536) -> None:
    """Write zlib-compressed object safely using a temp file + atomic rename.
    
    Args:
        path: Path where compressed data will be written.
        header: Header bytes to write before data.
        data: Data bytes to compress and write.
        chunk_size: Size of chunks to process (default: 65536 bytes).
    """
    dir_path = os.path.dirname(path)

    compressor = zlib.compressobj()

    # Write to a temp file first — if something crashes mid-write,
    # you won't corrupt the object store
    with tempfile.NamedTemporaryFile(dir=dir_path, delete=False) as tmp:
        tmp_path = tmp.name
        try:
            tmp.write(compressor.compress(header))

            # Feed data in chunks — critical for large blobs
            view = memoryview(data)
            for i in range(0, len(data), chunk_size):
                tmp.write(compressor.compress(view[i:i + chunk_size]))

            tmp.write(compressor.flush())
        except:
            os.unlink(tmp_path)
            raise

    # Atomic rename: either the full object exists or it doesn't
    os.replace(tmp_path, path)

        
        
def object_write(obj: 'GitObject', repo: Optional['GitRepository'] = None) -> str:
    """Serialize and write a git object to the repository.
    
    Args:
        obj: GitObject instance to write.
        repo: GitRepository to write to (optional).
    
    Returns:
        SHA-1 hash of the object.
    """
    # Serialize object data
    data = obj.serialize()
    # Add header (full fromat :  <type> <size>\0 <data>)
    header = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' 
    
    # Compute sha-hash incrementally
    h = hashlib.sha1()
    h.update(header)
    h.update(data)
    sha = h.hexdigest()

    if repo:
        # Compute path
        path=repo_file(repo, "objects", sha[0:2], sha[2:], mkdir=True)

        if not os.path.exists(path):
            _write_compressed(path,header,data)
    return sha 


def object_read(repo: 'GitRepository', sha: str) -> Optional['GitObject']:
    """Read object from git repository by SHA hash.
    
    Args:
        repo: GitRepository instance.
        sha: SHA-1 hash of the object.
    
    Returns:
        GitObject instance of appropriate type (Commit, Tree, Tag, or Blob).
        Returns None if object not found.
    
    Raises:
        Exception: If object is malformed or has unknown type.
    """

    path = repo_file(repo, "objects", sha[0:2], sha[2:])

    if not os.path.isfile(path):
        return None

    raw = _read_decompress(path)
    
    
    # Parse Header
    x = raw.find(b' ')
    fmt = raw[0:x]

    # parse data
    y = raw.find(b'\x00', x)
    size = int(raw[x+1:y].decode("ascii"))
    
    if size != len(raw)-y-1:
        raise Exception(f"Malformed object {sha}: bad length")


    # Pick constructor
    match fmt:
        case b'commit' : c=GitCommit
        case b'tree'   : c=GitTree
        case b'tag'    : c=GitTag
        case b'blob'   : c=GitBlob
        case _:
            raise Exception(f"Unknown type {fmt.decode('ascii')} for object {sha}")

    # Call constructor and return object
    return c(raw[y+1:])
    

def cat_file(repo: 'GitRepository', obj: str, fmt: Optional[bytes] = None) -> None:
    """Print the raw content of a git object to stdout.
    
    Args:
        repo: GitRepository instance.
        obj: Object name or SHA hash.
        fmt: Optional object format filter (e.g., b'blob', b'commit').
    """
    obj = object_read(repo , object_find(repo,obj,fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())

    
# def object_find(repo , name , fmt= None , follow = None):
#     return name
import re
def object_find(repo: 'GitRepository', name: str, fmt: Optional[bytes] = None, follow: bool = True) -> Optional[str]:
    """Find git object by name, optionally filtering by type.
    
    Args:
        repo: GitRepository instance.
        name: Object name or reference.
        fmt: Optional object format to filter by (e.g., b'blob', b'commit').
        follow: If True, follow tag/commit references to find object of desired type.
    
    Returns:
        SHA-1 hash of the found object.
    
    Raises:
        Exception: If object not found or name is ambiguous.
    """
    sha = object_resolve(repo, name)

    if not sha:
        raise Exception(f"No such reference {name}.")

    if len(sha) > 1:
        raise Exception(f"Ambiguous reference {name}: Candidates are:\n - {'\n - '.join(sha)}.")

    sha = sha[0]

    if not fmt:
        return sha

    while True:
        obj = object_read(repo, sha)


        if obj.fmt == fmt:
            return sha

        if not follow:
            return None

        # Follow tags
        if obj.fmt == b'tag':
            sha = obj.kvlm[b'object'].decode("ascii")
        elif obj.fmt == b'commit' and fmt == b'tree':
            sha = obj.kvlm[b'tree'].decode("ascii")
        else:
            return None
        
def object_resolve(repo: 'GitRepository', name: str) -> Optional[List[str]]:
    """Resolve name to one or more object hashes in repo.

This function is aware of:

 - the HEAD literal
    - short and long hashes
    - tags
    - branches
    - remote branches
    
    Args:
        repo: GitRepository instance.
        name: Object name to resolve (can be HEAD, hash, tag, branch, or remote branch).
    
    Returns:
        List of matching SHA-1 hashes, or None if name is empty.
    """
    candidates = list()
    hashRE = re.compile(r"^[0-9A-Fa-f]{4,40}$")

    # Empty string?  Abort.
    if not name.strip():
        return None

    # Head is nonambiguous
    if name == "HEAD":
        return [ ref_resolve(repo, "HEAD") ]

    # If it's a hex string, try for a hash.
    if hashRE.match(name):
        # This may be a hash, either small or full.  4 seems to be the
        # minimal length for git to consider something a short hash.
        # This limit is documented in man git-rev-parse
        name = name.lower()
        prefix = name[0:2]
        path = repo_dir(repo, "objects", prefix, mkdir=False)
        if path:
            rem = name[2:]
            for f in os.listdir(path):
                if f.startswith(rem):
                    # Notice a string startswith() itself, so this
                    # works for full hashes.
                    candidates.append(prefix + f)

    # Try for references.
    as_tag = ref_resolve(repo, "refs/tags/" + name)
    if as_tag: # Did we find a tag?
        candidates.append(as_tag)

    as_branch = ref_resolve(repo, "refs/heads/" + name)
    if as_branch: # Did we find a branch?
        candidates.append(as_branch)

    as_remote_branch = ref_resolve(repo, "refs/remotes/" + name)
    if as_remote_branch: # Did we find a remote branch?
        candidates.append(as_remote_branch)

    return candidates
def ref_resolve(repo: 'GitRepository', ref: str) -> Optional[str]:
    """Resolve a git reference to its SHA-1 hash.
    
    Follows indirect references (like 'ref: refs/heads/master').
    
    Args:
        repo: GitRepository instance.
        ref: Reference path (e.g., 'HEAD', 'refs/heads/master').
    
    Returns:
        SHA-1 hash the reference points to, or None if reference not found.
    """
    path = repo_file(repo, ref)

    # Sometimes, an indirect reference may be broken.  This is normal
    # in one specific case: we're looking for HEAD on a new repository
    # with no commits.  In that case, .git/HEAD points to "ref:
    # refs/heads/main", but .git/refs/heads/main doesn't exist yet
    # (since there's no commit for it to refer to).
    if not os.path.isfile(path):
        return None

    with open(path, 'r') as fp:
        data = fp.read()[:-1]
        # Drop final \n ^^^^^
    if data.startswith("ref: "):
        return ref_resolve(repo, data[5:])
    else:
        return data


def object_hash(fd: Any, fmt: bytes, repo: Optional['GitRepository'] = None) -> str:
    """Hash an object and optionally write it to the repository.
    
    Args:
        fd: File descriptor or object with read() method.
        fmt: Object format (e.g., b'blob', b'commit', b'tree', b'tag').
        repo: Optional GitRepository to write the object to.
    
    Returns:
        SHA-1 hash of the object.
    
    Raises:
        Exception: If fmt is an unknown object type.
    """
    
    data = fd.read()
    
    match fmt:
        case b'commit' : obj=GitCommit(data)
        case b'tree'   : obj=GitTree(data)
        case b'tag'    : obj=GitTag(data)
        case b'blob'   : obj=GitBlob(data)
        case _: raise Exception(f"Unknown type {fmt}!")  
        
    return object_write(obj,repo)



        
class GitCommit(GitObject):
    fmt=b'commit'

    def serialize(self):
        return kvlm_serialize(self.kvlm)
    
    def deserialize(self, data):
        self.kvlm = kvlm_parse(data)
    
    def init(self):
        self.kvlm = dict()
        
def kvlm_parse(raw: bytes, start: int = 0, dct: Optional[Dict[Optional[bytes], Any]] = None) -> Dict[Optional[bytes], Any]:
    """Parse Key-Value List with Message format used in git commits.
    
    Args:
        raw: Raw bytes to parse.
        start: Starting position in bytes (default: 0).
        dct: Dictionary to accumulate parsed data (default: new dict).
    
    Returns:
        Dictionary with keys as bytes and None key for message body.
    """
    if not dct:
        
        dct = dict()
        
        
    # search for next space and newline
    spc = raw.find(b' ' , start)
    nl = raw.find(b'\n' , start)
    
    # base case 
    # If newline appears first (or there's no space at all, in which
    # case find returns -1), we assume a blank line.  A blank line
    # means the remainder of the data is the message.  We store it in
    # the dictionary, with None as the key, and return.
    
    if (spc < 0 ) or (nl < spc):
        assert nl == start 
        dct[None] = raw[start+1 : ]
        return dct
    
    # recursive  build to the dict with key value
    
    key = raw[start : spc]
    
    # find the end of the value
    end = start
    while True : 
        end = raw.find(b'\n', end+1)
        if raw[end+1] != ord(' ')  : break # If a line starts with a space → it's a continuation of the previous value
       
    # Grab the value
    # Also, drop the leading space on continuation lines
    value = raw[spc+1 :end].replace(b'\n ' , b'\n')
    
    # don't overwrite existing data
    if key in dct:
        if type(dct[key]) == list:
            dct[key].append(value)
            
        else:
            dct[key] = [dct[key],value]
    else:
        dct[key] = value
        
        
    return kvlm_parse(raw, start=end+1 , dct= dct)


def kvlm_serialize(kvlm: Dict[Optional[bytes], Any]) -> bytes:
    """Serialize Key-Value List with Message back to bytes format.
    
    Args:
        kvlm: Dictionary with None key for message body.
    
    Returns:
        Serialized bytes in git commit message format.
    """
    ret =b''
    
    # output fileds (like tree <sha1> )
    for k in kvlm.keys():
        # skip message 
        if k == None : continue
        val = kvlm[k]
        
        # normalize to a list 
        if not isinstance(val, list):
            val = [val]
            
        for v in val :
            ret += k + b' ' + (v.replace(b'\n' , b'\n ') ) + b'\n'
            
    # append message
    ret += b'\n' + kvlm[None]
    
    return ret


def log_graphviz(repo: 'GitRepository', sha: str, seen: Optional[set] = None) -> None:
    """Generate GraphViz DOT format visualization of git commits.
    
    Args:
        repo: GitRepository instance.
        sha: Starting commit SHA-1 hash.
        seen: Set of already-visited commit SHAs (for avoiding cycles).
    """
    if seen is None:          
        seen = set()
    if sha in seen:
        return
    seen.add(sha)

    commit = object_read(repo, sha)
    assert commit.fmt == b'commit', f"Expected commit, got {commit.fmt} for {sha}"

    short_sha   = sha[0:7]
    raw_message = commit.kvlm[None].decode("utf8").strip()
    
    # Keep only the first line (subject line)
    subject = raw_message.splitlines()[0] if raw_message else "(no message)"
    
    # Escape for DOT string literals
    subject = subject.replace("\\", "\\\\").replace('"', '\\"')

    #  Author + date (optional but useful) 
    author_line = commit.kvlm.get(b'author', b'').decode("utf8")
    # Author format: "Name <email> timestamp timezone"
    author_name = author_line.split('<')[0].strip() if '<' in author_line else author_line

    # Emit node
    label = f"{short_sha}\\n{subject}\\n{author_name}"
    print(f'  c_{sha} [label="{label}"]')

    #  Walk parents 
    parents = commit.kvlm.get(b'parent', None)
    if parents is None:
        return  # Initial commit — base case

    if not isinstance(parents, list):
        parents = [parents]

    for p in parents:
        p = p.decode("ascii")
        print(f"  c_{sha} -> c_{p}")
        log_graphviz(repo, p, seen)


# -----------------------------------------------------------------------------
# entry point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    repo = repo_find(".", required=True)
    if repo is None:
        raise SystemExit("No repository found")

    log_graphviz(repo, object_find(repo, 'HEAD'), set())

