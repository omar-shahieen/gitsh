import hashlib
import zlib
import os
import tempfile
import configparser
import sys
def compute_file_hash(filepath, algorithm='sha1' , BUFF_SIZE=65536):
    """Compute the hash of a file using the specified algorithm."""

    hash_func = hashlib.new(algorithm)
    
    with open(filepath, 'rb') as file :
        
        while chunk := file.read(BUFF_SIZE): # default 64kb chunck
            hash_func.update(chunk)
            
    return hash_func.hexdigest()




    
def repo_path(repo, *path):
    """Compute path under repo's gitdir."""
    return os.path.join(repo.gitdir, *path)

def repo_file(repo, *path, mkdir=False):
    """
    Same as repo_path, but create dirname(*path) if absent.  
    Forexample, repo_file(r, \"refs\", \"remotes\", \"origin\", \"HEAD\") will create
    .git/refs/remotes/origin.
    """

    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)

def repo_dir(repo, *path, mkdir=False):
    """Same as repo_path, but mkdir *path if absent if mkdir."""

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
    
    

def repo_default_config():
    ret = configparser.ConfigParser()
    
    ret.add_section("core")
    
    ret.set("core","repositoryformatversion", "0") # format version
    ret.set("core","filemode", "false") # disable tracking of file modes
    ret.set("core","bare", "false") # indicates that repo has a worktree
    
    return ret

def repo_create(path):
    """ Create a new repo a path"""
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

def repo_find(path=".", required=True):
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



    
    
    
from abc import ABC, abstractmethod

class GitRepository (object):
    """A git repository"""

    worktree = None
    gitdir = None
    conf = None

    def __init__(self, path, force=False):
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

    def __init__(self, data=None):
        if data is not None:
            self.deserialize(data)
        else:
            self.init()

    @abstractmethod
    def serialize(self, repo):
        """Must be implemented by subclasses"""
        pass

    @abstractmethod
    def deserialize(self, data):
        """Must be implemented by subclasses"""
        pass

    def init(self):
        pass  # default implementation
    
    
class GitBlob(GitObject):
    fmt=b'blob'

    def serialize(self):
        return self.blobdata

    def deserialize(self, data):
        self.blobdata = data
        
        
class GitCommit(GitObject):
    fmt=b'commit'

    def serialize(self):
        pass
    def deserialize(self, data):
        pass
    
    
    
class GitTree(GitObject):
    fmt=b'tree'

    def serialize(self):
        pass

    def deserialize(self, data):
        pass
        
        
class GitTag(GitObject):
    fmt=b'tag'

    def serialize(self):
        pass

    def deserialize(self, data):
        pass


def _read_decompress(path, chunk_size=65536):
    """Decompress in chunks to avoid loading the full compressed file at once."""
    decompressor = zlib.decompressobj()
    parts = []

    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            parts.append(decompressor.decompress(chunk))
        parts.append(decompressor.flush())

    return b"".join(parts)


def _write_compressed(path, header, data, chunk_size=65536):
    """Write zlib-compressed object safely using a temp file + atomic rename."""
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

        
        
def object_write(obj, repo=None):
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


def object_read(repo, sha):
    """Read object sha from Git repository repo.  Return a
    GitObject whose exact type depends on the object."""

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
    

def cat_file(repo, obj, fmt=None):
    """ func to print the raw content of an object to stdout"""
    obj = object_read(repo , object_find(repo,obj,fmt=fmt))
    sys.stdout.buffer.write(obj.serialize())

    
def object_find(repo , name , fmt= None , follow = None):
    return name

def object_hash(fd , fmt , repo=None):
    """ Hash object , writing it to repo if provided. """
    
    data = fd.read()
    
    match fmt:
        case b'commit' : obj=GitCommit(data)
        case b'tree'   : obj=GitTree(data)
        case b'tag'    : obj=GitTag(data)
        case b'blob'   : obj=GitBlob(data)
        case _: raise Exception(f"Unknown type {fmt}!")  
        
    return object_write(obj,repo)


