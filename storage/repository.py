import configparser
import os
from typing import  Optional



class GitRepository(object):
    worktree: str = ""
    gitdir: str = ""
    conf: configparser.ConfigParser

    def __init__(self, path: str, force: bool = False) -> None:
        """Initialize a Git repository instance.

        Args:
            path: The path to the repository worktree.
            force: Whether to force initialization even if .gitsh doesn't exist.
        """
        self.worktree = path
        self.gitdir = os.path.join(path, ".gitsh")

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception(f"Not a Git repository {path}")

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

def _repo_default_config() -> configparser.ConfigParser:
    """Create the default configuration for a new repository.

    Returns:
        A ConfigParser instance with default settings.
    """
    ret = configparser.ConfigParser()
    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")
    return ret

def repo_create(path: str) -> GitRepository:
    """Create a new Git repository at the given path.

    Args:
        path: The path where to create the repository.

    Returns:
        The initialized GitRepository instance.
    """
    repo = GitRepository(path, True)

    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception(f"{path } is not a directory!")
        if os.path.exists(repo.gitdir) and os.listdir(repo.gitdir):
            raise Exception(f"{path} is not empty!")
    else:
        os.makedirs(repo.worktree)

    assert repo_dir(repo, "branches", mkdir=True)
    assert repo_dir(repo, "objects", mkdir=True)
    assert repo_dir(repo, "refs", "tags", mkdir=True)
    assert repo_dir(repo, "refs", "heads", mkdir=True)

    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unnamed repository; edit this file 'description' to name the repository.\n")

    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/master\n")

    with open(repo_file(repo, "config"), "w") as f:
        config = _repo_default_config()
        config.write(f)

    return repo


def repo_path(repo: GitRepository, *path: str) -> str:
    """Construct a path within the repository's .gitsh directory.

    Args:
        repo: The Git repository instance.
        *path: Path components to join.

    Returns:
        The full path string.
    """
    return os.path.join(repo.gitdir, *path)


def repo_file(repo: GitRepository, *path: str, mkdir: bool = False) -> Optional[str]:
    """Get the path to a file in the repository, optionally creating directories.

    Args:
        repo: The Git repository instance.
        *path: Path components.
        mkdir: Whether to create parent directories.

    Returns:
        The file path if successful, None otherwise.
    """
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)
    return None


def repo_dir(repo: GitRepository, *path: str, mkdir: bool = False) -> Optional[str]:
    """Get the path to a directory in the repository, optionally creating it.

    Args:
        repo: The Git repository instance.
        *path: Path components.
        mkdir: Whether to create the directory.

    Returns:
        The directory path if successful, None otherwise.
    """
    path = repo_path(repo, *path)

    if os.path.exists(path):
        if os.path.isdir(path):
            return path
        raise Exception(f"Not a directory {path}")

    if mkdir:
        os.makedirs(path)
        return path
    return None


def repo_find(path: str = ".", required: bool = True) -> Optional[GitRepository]:
    """Find the Git repository starting from the given path.

    Args:
        path: The starting path to search from.
        required: Whether to raise an exception if not found.

    Returns:
        The GitRepository instance if found, None otherwise.
    """
    path = os.path.realpath(path)

    if os.path.isdir(os.path.join(path, ".git")):
        return GitRepository(path)

    parent = os.path.realpath(os.path.join(path, ".."))
    if path == parent:
        if required:
            raise Exception("No git directory.")
        return None

    return repo_find(parent, required)

