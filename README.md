# gitsh

Simple version control tool for learning purposes

## Prerequisites

Before installing gitsh, ensure you have the following:

- **Python 3.7+** installed on your system
- **pip** (Python package manager) - typically included with Python
- **Git** (optional, for version control of the gitsh project itself)

### Check Your Python Installation

```powershell
python --version
pip --version
```

If these commands fail or show unsupported versions, download Python from [python.org](https://www.python.org).

## Installation Steps

### 1. Clone or Download the Project

If you have Git installed:

```powershell
git clone <repository-url>
cd gitsh
```

Or manually download and extract the project folder, then navigate to it:

```powershell
cd D:\coding\.BackEnd\gitsh
```

### 2. Create a Virtual Environment (Recommended)

It's best practice to use a virtual environment to isolate dependencies:

```powershell
python -m venv venv
```

### 3. Activate the Virtual Environment

**On Windows (PowerShell):**

```powershell
.\venv\Scripts\Activate.ps1
```

**On Windows (Command Prompt):**

```cmd
venv\Scripts\activate.bat
```

**On macOS/Linux:**

```bash
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt when activated.

### 4. Install gitsh in Editable Mode

This installs the package in development mode, so changes to the code are immediately reflected:

```powershell
pip install -e .
```

The `-e` flag enables "editable" mode, which is perfect for development.

### 5. Verify Installation

Test that the `gitsh` command is available:

```powershell
gitsh --help
```

You should see the available commands. If this works, you're ready to use gitsh!

## Configuration

### Create a `.gitshignore` File

Create a `.gitshignore` file in your project root to specify files that should be ignored (similar to `.gitignore` in Git).

Example `.gitshignore`:

```
# Python
*.pyc
__pycache__/
*.egg-info/
*.egg
dist/
build/

# Virtual environments
venv/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log

# Temporary files
*.tmp
~*
```

## First Time Usage

### Initialize a New Repository

```powershell
gitsh init
```

This creates a `.gitsh` folder in your current directory to store repository data.

### Add Files to Staging

```powershell
gitsh add <file-path>
```

Example:

```powershell
gitsh add README.md
gitsh add src/
```

### Check Repository Status

```powershell
gitsh status
```

### Create a Commit

```powershell
gitsh commit -m "Your commit message"
```

### View Commit History

```powershell
gitsh log
```

## Available Commands

| Command                       | Description                      |
| ----------------------------- | -------------------------------- |
| `gitsh init [path]`           | Initialize a new repository      |
| `gitsh add <path>`            | Stage files for commit           |
| `gitsh rm <path>`             | Remove files from staging        |
| `gitsh status`                | Show repository status           |
| `gitsh commit -m <message>`   | Create a new commit              |
| `gitsh log`                   | Display commit history           |
| `gitsh checkout <branch/ref>` | Switch branches or restore files |
| `gitsh branch <name>`         | Create or list branches          |
| `gitsh tag <name> <ref>`      | Create or list tags              |
| `gitsh merge <branch>`        | Merge another branch             |
