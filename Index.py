import json
import os
from typing import Dict, List
from storage import compute_file_hash
from storage.repository import GitRepository ,repo_file

class GitIndexEntry:
    """Represents a single file entry in the index (staging area)."""
    
    def __init__(self, path: str, mode: str, sha: str) -> None:
        """Initialize an index entry.

        Args:
            path: The file path.
            mode: The file mode.
            sha: The SHA hash.
        """
        self.path = path
        self.mode = mode  # file mode (e.g., "100644" for regular file)
        self.sha = sha    # SHA-1 hash of file content
    
    def to_dict(self) -> Dict:
        """Convert the entry to a dictionary.

        Returns:
            A dictionary representation.
        """
        return {
            "path": self.path,
            "mode": self.mode,
            "sha": self.sha,
        }
    
    @staticmethod
    def from_dict(data: Dict) -> "GitIndexEntry":
        """Create an entry from a dictionary.

        Args:
            data: The dictionary data.

        Returns:
            A GitIndexEntry instance.
        """
        return GitIndexEntry(data["path"], data["mode"], data["sha"])


class GitIndex:
    """Represents the git index (staging area)."""
    
    def __init__(self, repo: "GitRepository") -> None:
        """Initialize the index for a repository.

        Args:
            repo: The Git repository instance.
        """
        self.repo = repo
        self.entries: Dict[str, GitIndexEntry] = {}
    
    def load(self) -> None:
        """Load index from .gitsh/index file."""
        
        index_path = repo_file(self.repo, "index")
        if not index_path or not os.path.exists(index_path):
            self.entries = {}
            return
        
        with open(index_path, 'r') as f:
            try:
                data = json.load(f)
                self.entries = {
                    entry["path"]: GitIndexEntry.from_dict(entry)
                    for entry in data
                }
            except (json.JSONDecodeError, KeyError):
                self.entries = {}
    
    def save(self) -> None:
        """Save index to .gitsh/index file."""
        
        index_path = repo_file(self.repo, "index", mkdir=True)
        if not index_path:
            raise Exception("Failed to create index path")
        
        data = [entry.to_dict() for entry in self.entries.values()]
        with open(index_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add(self, filepath: str) -> None:
        """Add a file to the index (staging area).
        
        Args:
            filepath: Path relative to worktree or absolute.
        
        Raises:
            Exception: If file doesn't exist.
        """
        # Resolve absolute path
        if not os.path.isabs(filepath):
            filepath = os.path.join(self.repo.worktree, filepath)
        
        if not os.path.exists(filepath):
            raise Exception(f"File not found: {filepath}")
        
        if not os.path.isfile(filepath):
            raise Exception(f"Not a file: {filepath}")
        
        # Compute hash of file content
        sha = compute_file_hash(filepath, algorithm='sha1')
        
        # Get relative path from worktree
        rel_path = os.path.relpath(filepath, self.repo.worktree)
        
        # Determine mode (simplified: all regular files are 100644)
        mode = "100644"
        
        # Add to index
        self.entries[rel_path] = GitIndexEntry(rel_path, mode, sha)
    
    def rm(self, filepath: str) -> None:
        """Remove a file from the index (staging area).
        
        Args:
            filepath: Path relative to worktree.
        
        Raises:
            Exception: If file not in index.
        """
        # If absolute path, make it relative
        if os.path.isabs(filepath):
            try:
                filepath = os.path.relpath(filepath, self.repo.worktree)
            except ValueError:
                # Different drives on Windows, just use as-is
                pass
        
        if filepath not in self.entries:
            raise Exception(f"File not in index: {filepath}")
        
        del self.entries[filepath]
    
    def status(self) -> Dict[str, List[str]]:
        """Get status of working tree vs index.
        
        Returns:
            Dict with keys:
            - "staged": Files in index ready to commit
            - "modified": Files in worktree but not in index
            - "deleted": Files in index but not in worktree
        """
        staged = list(self.entries.keys())
        modified = []
        deleted = []
        
        # Check for files in worktree not in index
        for root, dirs, files in os.walk(self.repo.worktree):
            # Skip .gitsh directory
            if ".gitsh" in dirs:
                dirs.remove(".gitsh")
            if "__pycache__" in dirs:
                dirs.remove("__pycache__")
            
            for file in files:
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, self.repo.worktree)
                
                if rel_path not in self.entries:
                    modified.append(rel_path)
        
        # Check for files in index but not in worktree
        for indexed_path in self.entries.keys():
            full_path = os.path.join(self.repo.worktree, indexed_path)
            if not os.path.exists(full_path):
                deleted.append(indexed_path)
        
        return {
            "staged": staged,
            "modified": modified,
            "deleted": deleted,
        }
    
    def clear(self) -> None:
        """Clear the index."""
        self.entries = {}
        self.save()


def index_load(repo: "GitRepository") -> GitIndex:
    """Load index from repository."""
    index = GitIndex(repo)
    index.load()
    return index


def index_save(index: GitIndex) -> None:
    """Save index to repository."""
    index.save()
