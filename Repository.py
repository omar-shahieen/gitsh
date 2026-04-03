import configparser
import os
from typing import  Optional



class GitRepository(object):
    worktree: str = ""
    gitdir: str = ""
    conf: configparser.ConfigParser

    def __init__(self, path: str, force: bool = False) -> None:
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

def repo_path(repo: GitRepository, *path: str) -> str:
    return os.path.join(repo.gitdir, *path)


def repo_file(repo: GitRepository, *path: str, mkdir: bool = False) -> Optional[str]:
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)
    return None


def repo_dir(repo: GitRepository, *path: str, mkdir: bool = False) -> Optional[str]:
    path = repo_path(repo, *path)

    if os.path.exists(path):
        if os.path.isdir(path):
            return path
        raise Exception(f"Not a directory {path}")

    if mkdir:
        os.makedirs(path)
        return path
    return None


def repo_default_config() -> configparser.ConfigParser:
    ret = configparser.ConfigParser()
    ret.add_section("core")
    ret.set("core", "repositoryformatversion", "0")
    ret.set("core", "filemode", "false")
    ret.set("core", "bare", "false")
    return ret


def repo_create(path: str) -> GitRepository:
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
        config = repo_default_config()
        config.write(f)

    return repo


def repo_find(path: str = ".", required: bool = True) -> Optional[GitRepository]:
    path = os.path.realpath(path)

    if os.path.isdir(os.path.join(path, ".git")):
        return GitRepository(path)

    parent = os.path.realpath(os.path.join(path, ".."))
    if path == parent:
        if required:
            raise Exception("No git directory.")
        return None

    return repo_find(parent, required)

