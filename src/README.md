# gitsh

`gitsh` is an educational Python project that implements a simplified version of Git. It is designed to help you understand how Git works internally by building a small but functional local version control system from scratch.

## Overview

This project is not a full replacement for Git, but it reproduces the core pieces you need to manage a local repository:

- create a new repository
- stage files
- remove files from the staging area
- create commits
- inspect commit history
- work with trees, blobs, tags, and refs
- perform a basic merge with conflict handling

The repository data is stored inside `.gitsh`, not `.git`.

## Why this project exists

The main goal is learning, not just using. With this project you can trace how Git works under the hood:

- how files become objects
- how commits are linked together
- how `HEAD` points to a branch or commit
- how a tree is built from the index
- how merge works in a simplified form

## Project Structure

The codebase is split into clear layers:

### `storage/`
Handles repository paths and object storage.

- `repository.py` for repository management and path helpers
- `object_io.py` for reading and writing Git objects

### `objects/`
Defines the core Git object types:

- `GitBlob`
- `GitTree`
- `GitCommit`
- `GitTag`

### `Index.py`
Represents the staging area and tracks files prepared for the next commit.

### `Reference.py`
Handles refs, branches, tags, and `HEAD` resolution.

### `merge.py`
Contains merge logic, including:

- finding the common ancestor
- merging trees
- handling conflicts and writing conflict markers

### `cli.py`
The command-line interface that connects user commands to internal functions.

### `main.py`
The entry point for running the project.

## Internal Repository Layout

When you run `init`, the repository creates a structure similar to this:

```text
.gitsh/
├── HEAD
├── config
├── description
├── index
├── objects/
├── refs/
│   ├── heads/
│   └── tags/
└── branches/
```

## Requirements

- Python 3.x
- No external dependencies required

## Running the Project

From the project root:

```bash
python main.py --help
```

Inside a repository created by `gitsh`:

```bash
python ..\main.py status
```

## Available Commands

### Create a repository

```bash
python main.py init [path]
```

Creates a new repository in the given path, or in the current directory if no path is provided.

### Add files to the staging area

```bash
python main.py add file1 file2 ...
```

Adds files to the index and stores their blob objects in the repository.

### Remove files from the staging area

```bash
python main.py rm file1 file2 ...
```

Removes files from the index.

### Show the working tree status

```bash
python main.py status
```

Shows:

- the current branch
- files staged for the next commit
- modified files
- deleted files

### Create a commit

```bash
python main.py commit -m "message"
```

Creates a new commit from the index and updates the current branch or `HEAD`.

### Show commit history

```bash
python main.py log [commit]
```

Prints commit history in GraphViz format.

### Checkout a commit into a directory

```bash
python main.py checkout commit path
```

Writes the contents of a tree or commit into an empty directory.

### Show a tree

```bash
python main.py ls-tree [-r] tree
```

Displays the contents of a tree, with optional recursive output.

### Show an object

```bash
python main.py cat-file type object
```

Displays the contents of a blob, tree, commit, or tag object.

### Create or list tags

```bash
python main.py tag
python main.py tag name
python main.py tag -a name -m "message"
python main.py tag --target ref name
```

### Show refs

```bash
python main.py show-ref
```

Lists all branches and tags in the repository.

### Merge

```bash
python main.py merge ref
python main.py merge ref -m "message"
```

Merges another branch or commit into the current branch. If a conflict occurs, conflict markers are written into the affected files.

## Examples

### Create a repository and make a commit

```bash
python main.py init my_repo
cd my_repo
echo Hello > hello.txt
python ..\main.py add hello.txt
python ..\main.py commit -m "Initial commit"
python ..\main.py log
```

### Merge a branch

```bash
python main.py merge feature
```

If there are no conflicts, a merge commit is created. If there are conflicts, the file is updated with markers similar to Git:

```text
<<<<<<< ours
...
=======
...
>>>>>>> theirs
```

## Key Files

- `main.py` - entry point
- `cli.py` - command-line interface
- `merge.py` - merge logic
- `Index.py` - staging area
- `Reference.py` - refs, branches, and tags
- `commands.py` - shared command helpers
- `storage/` - storage and object handling
- `objects/` - object definitions

## What the project currently supports

- init
- add
- rm
- status
- commit
- log
- checkout
- ls-tree
- cat-file
- tag
- show-ref
- merge

## Current Limitations

This project is intentionally simplified, so it does not support everything the real Git tool can do, such as:

- remote repositories
- fetch / pull / push
- rebase
- stash
- packfiles
- advanced rename detection
- a full Git-style conflict resolution workflow

## Important Notes

- The repository uses `.gitsh` instead of `.git`
- Commands are run with `python main.py ...`
- If you are inside a repository folder, use `python ..\main.py ...`
- The project is designed for learning and experimentation, not as a drop-in replacement for Git

## Summary

`gitsh` is a practical educational project that explains how Git works internally in a clean and structured way. It includes enough features to go through a full workflow: create a repository, stage files, commit changes, inspect history, use refs and tags, and perform a basic merge.