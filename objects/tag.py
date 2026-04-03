from .commit import GitCommit

class GitTag(GitCommit):
    """Represents a Git tag object."""
    fmt = b"tag"
