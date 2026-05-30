# filesystem.py
# Permission-scoped filesystem access for Jarvis.
# All operations are validated against permissions.json before execution.
# Jarvis cannot read, write, create, or move files outside the whitelist.
#
# Permissions config: ~/Desktop/Projects/Jarvis/permissions.json

import os
import json
import shutil
from pathlib import Path
from datetime import datetime

PERMISSIONS_PATH = Path(__file__).parent / "permissions.json"


# ── Permission Engine ──────────────────────────────────────────────────────────

def _load_permissions() -> dict:
    with open(PERMISSIONS_PATH, "r") as f:
        return json.load(f)


def _resolve(path_str: str) -> Path:
    """Expand ~ and resolve to absolute path."""
    return Path(path_str).expanduser().resolve()


def _check_access(target: Path, require_write: bool = False) -> tuple[bool, str]:
    """
    Validate that target path is within an allowed scope.
    Returns (allowed: bool, reason: str).
    """
    perms = _load_permissions()

    # Check blocked paths first
    for blocked in perms["blocked_paths"]:
        blocked_path = _resolve(blocked)
        try:
            target.relative_to(blocked_path)
            # If we're in a blocked path, check if a more specific allowed path covers it
            # (allowed_paths take precedence over blocked_paths if more specific)
        except ValueError:
            pass

    # Check allowed paths
    for allowed_str, config in perms["allowed_paths"].items():
        allowed_path = _resolve(allowed_str)
        try:
            target.relative_to(allowed_path)
            # Target is within this allowed path
            if require_write and config["access"] == "read":
                return False, f"{allowed_str} is read-only. Write access not permitted."
            return True, config["access"]
        except ValueError:
            continue

    return False, f"Path '{target}' is outside Jarvis's permitted scope."


# ── Voice Command Intent Parsing ───────────────────────────────────────────────

# Keyword map for project folders
PROJECT_MAP = {
    "jarvis":           "~/Desktop/Projects/Jarvis",
    "iris":             "~/Desktop/Projects/Iris",
    "chipin":           "~/Desktop/Projects/ChipIn",
    "chip in":          "~/Desktop/Projects/ChipIn",
    "billed":           "~/Desktop/Projects/Billed",
    "gesture":          "~/Desktop/Projects/gesture_control",
    "gesture control":  "~/Desktop/Projects/gesture_control",
}

# Keyword map for Important Docs
DOCS_MAP = {
    "resume":           "~/Desktop/Important Docs",
    "cover letter":     "~/Desktop/Important Docs",
    "opt":              "~/Desktop/Important Docs/OPT files",
    "transcript":       "~/Desktop/Important Docs",
    "offer letter":     "~/Desktop/Important Docs",
}


def _resolve_folder_from_query(query: str) -> Path | None:
    """Map a spoken folder reference to a real path."""
    lowered = query.lower()

    for keyword, path in {**PROJECT_MAP, **DOCS_MAP}.items():
        if keyword in lowered:
            return _resolve(path)

    # Generic project folder fallback
    if "project" in lowered:
        return _resolve("~/Desktop/Projects")

    if "important" in lowered or "docs" in lowered or "documents" in lowered:
        return _resolve("~/Desktop/Important Docs")

    if "ou" in lowered or "school" in lowered or "university" in lowered:
        return _resolve("~/Desktop/OU")

    return None


# ── Core Operations ────────────────────────────────────────────────────────────

def list_folder(query: str) -> str:
    """List contents of a folder matched from voice query."""
    folder = _resolve_folder_from_query(query)
    if not folder:
        return "I couldn't identify which folder you're referring to."

    allowed, reason = _check_access(folder)
    if not allowed:
        return f"Access denied: {reason}"

    if not folder.exists():
        return f"The folder '{folder.name}' doesn't exist."

    items = list(folder.iterdir())
    if not items:
        return f"The folder '{folder.name}' is empty."

    folders = sorted([i.name for i in items if i.is_dir()])
    files = sorted([i.name for i in items if i.is_file()])

    result = f"Contents of {folder.name}: "
    if folders:
        result += "Folders: " + ", ".join(folders) + ". "
    if files:
        result += "Files: " + ", ".join(files) + "."
    return result


def read_file(query: str) -> str:
    """Read and return the contents of a file matched from voice query."""
    folder = _resolve_folder_from_query(query)
    if not folder:
        return "I couldn't identify which file you're referring to."

    allowed, reason = _check_access(folder)
    if not allowed:
        return f"Access denied: {reason}"

    # If query points to a folder, look for the most recently modified file
    if folder.is_dir():
        md_files = sorted(folder.glob("*.md"), key=os.path.getmtime, reverse=True)
        txt_files = sorted(folder.glob("*.txt"), key=os.path.getmtime, reverse=True)
        candidates = md_files + txt_files
        if not candidates:
            return f"No readable text files found in {folder.name}."
        target = candidates[0]
    else:
        target = folder

    try:
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()
        return content if content.strip() else f"{target.name} is empty."
    except Exception as e:
        return f"Could not read {target.name}: {e}"


def summarize_folder(query: str) -> str:
    """Return a brief summary of what's in a folder — file count and names."""
    folder = _resolve_folder_from_query(query)
    if not folder:
        return "I couldn't identify which folder you're referring to."

    allowed, reason = _check_access(folder)
    if not allowed:
        return f"Access denied: {reason}"

    if not folder.exists():
        return f"The folder '{folder.name}' doesn't exist."

    files = list(folder.iterdir())
    count = len(files)
    names = ", ".join(f.name for f in sorted(files)[:5])
    more = f" and {count - 5} more" if count > 5 else ""
    return f"{folder.name} contains {count} items: {names}{more}."


def create_file_in(folder_query: str, filename: str, content: str = "") -> str:
    """Create a new file in a whitelisted folder."""
    folder = _resolve_folder_from_query(folder_query)
    if not folder:
        return "I couldn't identify which folder to create the file in."

    allowed, reason = _check_access(folder, require_write=True)
    if not allowed:
        return f"Access denied: {reason}"

    filepath = folder / filename
    if filepath.exists():
        return f"{filename} already exists in {folder.name}."

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Created {filename} in {folder.name}."
    except Exception as e:
        return f"Could not create file: {e}"


def read_file_direct(path: str) -> str:
    """
    Read a file by exact path (for agent use — not voice query parsing).
    Path can use ~ notation. Enforces read permission check.
    Truncates at 8000 chars to stay within token budget.
    """
    target = _resolve(path)
    allowed, reason = _check_access(target)
    if not allowed:
        return f"Access denied: {reason}"

    if not target.exists():
        return f"File not found: {target}"

    if target.is_dir():
        items = sorted(target.iterdir())
        names = [i.name for i in items[:30]]
        more  = f" (+{len(items)-30} more)" if len(items) > 30 else ""
        return f"Directory listing for {target.name}:\n" + "\n".join(names) + more

    try:
        content = target.read_text(encoding="utf-8")
        if len(content) > 8000:
            content = content[:8000] + f"\n\n[...truncated — {len(content)} chars total]"
        return content if content.strip() else f"{target.name} is empty."
    except Exception as e:
        return f"Could not read {target.name}: {e}"


BACKUP_DIR = Path(__file__).parent / ".backups"


def _backup_file(target: Path) -> str | None:
    """
    Copy existing file to .backups/ with timestamp before overwriting.
    Returns backup path string or None if file didn't exist.
    """
    if not target.exists():
        return None
    try:
        BACKUP_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_name = f"{target.stem}.{ts}{target.suffix}.bak"
        backup_path = BACKUP_DIR / backup_name
        shutil.copy2(target, backup_path)
        return str(backup_path)
    except Exception as e:
        print(f"[Backup] Warning: could not backup {target.name}: {e}")
        return None


def git_commit(path: str, message: str = "") -> str:
    """
    Stage and commit a file to the Jarvis git repo.
    Auto-initializes the repo if it doesn't exist yet.
    Only works within the Jarvis project folder.
    """
    import subprocess
    target = _resolve(path)
    jarvis_dir = Path(__file__).parent

    # Only commit files inside the Jarvis folder
    try:
        target.relative_to(jarvis_dir)
    except ValueError:
        return f"Git commits only supported within the Jarvis folder."

    if not target.exists():
        return f"File not found: {target}"

    try:
        # Init repo if needed
        git_dir = jarvis_dir / ".git"
        if not git_dir.exists():
            subprocess.run(["git", "init"], cwd=str(jarvis_dir), capture_output=True)
            # Create .gitignore
            gitignore = jarvis_dir / ".gitignore"
            if not gitignore.exists():
                gitignore.write_text(
                    "*.bak\n.backups/\n__pycache__/\n*.pyc\n"
                    "google_token.json\ngoogle_credentials.json\n"
                    ".gmail_seen_ids.txt\nusage_data.json\n"
                    "jarvis.log\njarvis.error.log\n"
                )
            subprocess.run(["git", "add", ".gitignore"], cwd=str(jarvis_dir), capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial commit — .gitignore"],
                         cwd=str(jarvis_dir), capture_output=True)
            print("[Git] Initialized repo.")

        # Stage the file
        rel_path = str(target.relative_to(jarvis_dir))
        subprocess.run(["git", "add", rel_path], cwd=str(jarvis_dir), capture_output=True)

        # Commit
        commit_msg = message or f"Jarvis: update {target.name}"
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=str(jarvis_dir), capture_output=True, text=True
        )
        if result.returncode == 0:
            short = result.stdout.strip().split("\n")[0]
            print(f"[Git] Committed: {short}")
            # Auto-push to GitHub
            push = subprocess.run(
                ["git", "push"],
                cwd=str(jarvis_dir), capture_output=True, text=True
            )
            if push.returncode == 0:
                print(f"[Git] Pushed to GitHub.")
                return f"Committed and pushed: {target.name}"
            else:
                print(f"[Git] Push failed: {push.stderr.strip()}")
                return f"Committed: {target.name} (push failed — check GitHub auth)"
        elif "nothing to commit" in result.stdout:
            return f"No changes to commit in {target.name}."
        else:
            return f"Git commit failed: {result.stderr.strip()}"
    except Exception as e:
        return f"Git error: {e}"


def restore_backup(filename: str) -> str:
    """
    Restore the most recent backup of a file from .backups/.
    Pass just the filename e.g. 'agents.py'.
    """
    if not BACKUP_DIR.exists():
        return "No backups directory found."

    matches = sorted(BACKUP_DIR.glob(f"{Path(filename).stem}.*{Path(filename).suffix}.bak"), reverse=True)
    if not matches:
        return f"No backups found for {filename}."

    latest = matches[0]
    target = Path(__file__).parent / filename

    allowed, reason = _check_access(target, require_write=True)
    if not allowed:
        return f"Access denied: {reason}"

    try:
        shutil.copy2(latest, target)
        ts = latest.stem.split(".")[-1] if "." in latest.stem else "unknown"
        return f"Restored {filename} from backup ({ts})."
    except Exception as e:
        return f"Restore failed: {e}"


def list_backups(filename: str = "") -> str:
    """List available backups. Pass filename to filter, or empty for all."""
    if not BACKUP_DIR.exists():
        return "No backups directory found."

    pattern = f"{Path(filename).stem}.*" if filename else "*.bak"
    backups = sorted(BACKUP_DIR.glob(pattern), reverse=True)
    if not backups:
        return f"No backups found{' for ' + filename if filename else ''}."

    lines = [f"{b.name}" for b in backups[:10]]
    more = f" (+{len(backups)-10} more)" if len(backups) > 10 else ""
    return "Backups: " + ", ".join(lines) + more


def write_file(path: str, content: str) -> str:
    """
    Overwrite a file at an exact path (for agent use).
    Auto-backs up existing file before overwriting.
    Auto-commits to git after successful write.
    """
    target = _resolve(path)
    allowed, reason = _check_access(target, require_write=True)
    if not allowed:
        return f"Access denied: {reason}"

    try:
        # Backup existing file first
        backup_path = _backup_file(target)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        msg = f"Written: {target.name} ({len(content)} chars)"
        if backup_path:
            msg += f" [backed up]"

        # Auto git commit
        git_result = git_commit(str(target), f"Jarvis: update {target.name}")
        if "Committed" in git_result:
            msg += " [committed]"

        return msg
    except Exception as e:
        return f"Could not write {target.name}: {e}"


def run_python(path: str, args: list[str] | None = None) -> str:
    """
    Execute a Python script within a whitelisted path using python3.11.
    Returns combined stdout + stderr, truncated at 4000 chars.
    Only scripts within read-permitted paths can be executed.
    Timeout: 30 seconds.
    """
    import subprocess
    target = _resolve(path)

    allowed, reason = _check_access(target)
    if not allowed:
        return f"Access denied: {reason}"

    if not target.exists():
        return f"Script not found: {target}"

    if target.suffix != ".py":
        return f"Only .py files can be executed. Got: {target.suffix}"

    cmd = ["python3.11", str(target)] + (args or [])
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(target.parent),
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if not output.strip():
            output = f"(no output)"
        if len(output) > 4000:
            output = output[:4000] + "\n[...truncated]"
        status = "EXIT_CODE:0" if result.returncode == 0 else f"EXIT_CODE:{result.returncode}"
        return f"{status}\n{output}"
    except subprocess.TimeoutExpired:
        return "EXIT_CODE:-1\nScript timed out after 30 seconds."
    except Exception as e:
        return f"EXIT_CODE:-1\nExecution failed: {e}"


def run_terminal_command(command: str, cwd: str | None = None) -> str:
    """
    Execute a scoped shell command and return the output.
    Safety model:
      - Whitelist of allowed command prefixes — anything else is blocked
      - Blocked patterns checked on full command string (covers chained/pipe abuse)
      - Working directory defaults to Jarvis project folder
      - Timeout: 30 seconds
      - stdout + stderr returned, truncated at 4000 chars
    """
    import subprocess

    # ── Allowed command prefixes ───────────────────────────────────────────────
    # Extend this list as needed — only commands that start with these are run
    ALLOWED_PREFIXES = {
        # Python / pip
        "python3", "python", "pip3", "pip",
        # Node / npm
        "node", "npm", "npx",
        # Git
        "git ",
        # File inspection (read-only)
        "ls", "cat", "head", "tail", "wc", "find", "grep", "diff", "tree",
        "stat", "file", "which", "where", "echo",
        # System info
        "ps", "top", "htop", "df", "du", "uname", "sw_vers", "sysctl",
        "lsof", "netstat", "ifconfig",
        # macOS specific
        "open ", "pbcopy", "pbpaste", "defaults read", "launchctl list",
        # Brew (read-only ops)
        "brew list", "brew info", "brew outdated", "brew search",
        # SSH / SCP to known hosts (Pi)
        "ssh edward@iris.local", "ssh edward@192.168.12.67",
        "scp",
        # Claude Code
        "claude ",
        # Kill / restart (scoped)
        "kill ", "pkill ",
        # Other safe ops
        "curl ", "wget ", "ping ", "traceroute ",
        "cd ", "pwd", "env", "printenv",
        "mkdir ", "touch ", "cp ", "mv ",
    }

    # ── Hard-blocked patterns (regardless of prefix) ──────────────────────────
    BLOCKED_PATTERNS = {
        "rm -rf", "rm -r", "sudo rm",
        "sudo su", "sudo bash", "sudo sh",
        "> /dev/", "mkfs", "fdisk", "diskutil erase",
        "chmod 777", "chmod -R 777",
        ":(){:|:&};:",   # fork bomb
        "dd if=", "dd of=",
        "curl | bash", "curl | sh", "wget | bash",
        "base64 -d",
        "eval ", "`",
        "shutdown", "reboot", "halt",
    }

    cmd_lower = command.lower().strip()

    # Block check first
    for pattern in BLOCKED_PATTERNS:
        if pattern in cmd_lower:
            return f"Blocked: '{pattern}' is not permitted for safety reasons."

    # Prefix whitelist check
    allowed = any(cmd_lower.startswith(prefix.lower()) for prefix in ALLOWED_PREFIXES)
    if not allowed:
        # Extract first word for a cleaner error
        first_word = command.strip().split()[0] if command.strip() else ""
        return (
            f"Command '{first_word}' is not on Jarvis's allowed list. "
            f"Ask Edward to add it to ALLOWED_PREFIXES in filesystem.py if it's safe."
        )

    # Working directory — default to Jarvis folder
    work_dir = _resolve(cwd) if cwd else Path(__file__).parent
    if not work_dir.exists():
        work_dir = Path(__file__).parent

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(work_dir),
        )
        output = ""
        if result.stdout.strip():
            output += result.stdout
        if result.stderr.strip():
            output += f"\nSTDERR:\n{result.stderr}"
        if not output.strip():
            output = "(no output)"
        if len(output) > 4000:
            output = output[:4000] + "\n[...truncated]"

        status = f"EXIT_CODE:{result.returncode}"
        return f"{status}\n{output.strip()}"

    except subprocess.TimeoutExpired:
        return "EXIT_CODE:-1\nCommand timed out after 30 seconds."
    except Exception as e:
        return f"EXIT_CODE:-1\nCommand failed: {e}"


def open_url(url: str, query: str = "") -> str:
    """
    Open a URL or named site in the default browser.

    Two modes:
      1. url is a full https:// link — open it directly
      2. url is a site name (e.g. 'youtube') + optional query for in-site search

    Claude should pass:
      - url="youtube", query="Kendrick Lamar Not Like Us"  → YouTube search
      - url="reddit",  query="embedded systems"            → Reddit search
      - url="amazon",  query="mechanical keyboard"         → Amazon search
      - url="youtube"  (no query)                          → YouTube homepage
      - url="https://github.com/e-haddad/Jarvis"           → open directly

    Search URL templates are defined in SEARCH_TEMPLATES.
    Sites without a template just open their homepage.
    """
    import subprocess
    from urllib.parse import urlencode, quote_plus

    # ── Homepage map ───────────────────────────────────────────────────────────
    URL_MAP = {
        # Google
        "youtube":          "https://www.youtube.com",
        "gmail":            "https://mail.google.com",
        "google":           "https://www.google.com",
        "google drive":     "https://drive.google.com",
        "google docs":      "https://docs.google.com",
        "google calendar":  "https://calendar.google.com",
        "google maps":      "https://maps.google.com",
        "google meet":      "https://meet.google.com",
        # Dev
        "github":           "https://github.com/e-haddad",
        "jarvis repo":      "https://github.com/e-haddad/Jarvis",
        "stackoverflow":    "https://stackoverflow.com",
        "stack overflow":   "https://stackoverflow.com",
        "claude":           "https://claude.ai",
        "anthropic":        "https://www.anthropic.com",
        "hugging face":     "https://huggingface.co",
        "huggingface":      "https://huggingface.co",
        "hf":               "https://huggingface.co",
        # Career
        "linkedin":         "https://www.linkedin.com",
        "indeed":           "https://www.indeed.com",
        "glassdoor":        "https://www.glassdoor.com",
        "wind river":       "https://www.windriver.com/company/careers",
        "switchbox":        "https://www.switchbox.com/careers",
        "valeo":            "https://jobs.valeo.com",
        "schaeffler":       "https://www.schaeffler.com/en/career",
        # Finance / crypto
        "coinbase":         "https://www.coinbase.com",
        "coingecko":        "https://www.coingecko.com",
        "robinhood":        "https://robinhood.com",
        # Social / comms
        "twitter":          "https://twitter.com",
        "x":                "https://x.com",
        "reddit":           "https://www.reddit.com",
        "discord":          "https://discord.com/channels/@me",
        "slack":            "https://slack.com",
        "notion":           "https://www.notion.so",
        # News
        "hacker news":      "https://news.ycombinator.com",
        "hackernews":       "https://news.ycombinator.com",
        "hn":               "https://news.ycombinator.com",
        # Shopping
        "amazon":           "https://www.amazon.com",
        # Streaming
        "netflix":          "https://www.netflix.com",
        "spotify":          "https://open.spotify.com",
        # Oakland University
        "moodle":           "https://moodle.oakland.edu",
        "ou":               "https://www.oakland.edu",
    }

    # ── Search URL templates ───────────────────────────────────────────────────
    # {q} is replaced with the URL-encoded query string
    SEARCH_TEMPLATES = {
        "youtube":       "https://www.youtube.com/results?search_query={q}",
        "google":        "https://www.google.com/search?q={q}",
        "reddit":        "https://www.reddit.com/search/?q={q}",
        "amazon":        "https://www.amazon.com/s?k={q}",
        "github":        "https://github.com/search?q={q}&type=repositories",
        "stackoverflow": "https://stackoverflow.com/search?q={q}",
        "stack overflow":"https://stackoverflow.com/search?q={q}",
        "linkedin":      "https://www.linkedin.com/search/results/all/?keywords={q}",
        "indeed":        "https://www.indeed.com/jobs?q={q}",
        "glassdoor":     "https://www.glassdoor.com/Search/results.htm?keyword={q}",
        "google maps":   "https://www.google.com/maps/search/{q}",
        "huggingface":   "https://huggingface.co/models?search={q}",
        "hugging face":  "https://huggingface.co/models?search={q}",
        "hf":            "https://huggingface.co/models?search={q}",
        "spotify":       "https://open.spotify.com/search/{q}",
        "coingecko":     "https://www.coingecko.com/en/search?query={q}",
        "x":             "https://x.com/search?q={q}",
        "twitter":       "https://twitter.com/search?q={q}",
    }

    url_lower = url.lower().strip()
    query = query.strip()

    # ── If it's already a full URL, open directly ──────────────────────────────
    if url.startswith("http://") or url.startswith("https://"):
        resolved = url

    # ── Site name + query → search URL ────────────────────────────────────────
    elif query:
        # Find matching site key (exact first, then substring)
        site_key = None
        if url_lower in SEARCH_TEMPLATES:
            site_key = url_lower
        else:
            for key in SEARCH_TEMPLATES:
                if key in url_lower:
                    site_key = key
                    break

        if site_key:
            resolved = SEARCH_TEMPLATES[site_key].replace("{q}", quote_plus(query))
        else:
            # Site has no search template — fall back to homepage
            resolved = None
            if url_lower in URL_MAP:
                resolved = URL_MAP[url_lower]
            else:
                for key, target in URL_MAP.items():
                    if key in url_lower:
                        resolved = target
                        break
            resolved = resolved or ("https://" + url)

    # ── Site name, no query → homepage ────────────────────────────────────────
    else:
        resolved = None
        if url_lower in URL_MAP:
            resolved = URL_MAP[url_lower]
        else:
            for key, target in URL_MAP.items():
                if key in url_lower:
                    resolved = target
                    break
        if not resolved:
            resolved = url if url.startswith("http") else "https://" + url

    try:
        result = subprocess.run(
            ["open", resolved],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return f"Couldn't open '{resolved}': {result.stderr.strip() or 'unknown error'}"
        return f"Opened {resolved}"
    except Exception as e:
        return f"Failed to open URL: {e}"


def open_obsidian_note(note_path: str) -> str:
    """
    Open a specific note in Obsidian via the obsidian:// URI scheme.
    note_path is the vault-relative path, e.g. 'Projects/Jarvis/Jarvis'
    (with or without .md extension).
    """
    import subprocess
    from urllib.parse import quote

    path = note_path.strip()
    if path.lower().endswith(".md"):
        path = path[:-3]

    encoded = quote(path, safe="/")
    uri = f"obsidian://open?vault=Edward&file={encoded}"

    try:
        result = subprocess.run(
            ["open", uri],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return f"Couldn't open note: {result.stderr.strip() or 'unknown error'}"
        return f"Opened {path} in Obsidian."
    except Exception as e:
        return f"Failed to open note: {e}"


def move_file(filename: str, from_query: str, to_query: str) -> str:
    """Move a file between two whitelisted folders."""
    from_folder = _resolve_folder_from_query(from_query)
    to_folder = _resolve_folder_from_query(to_query)

    if not from_folder or not to_folder:
        return "I couldn't identify the source or destination folder."

    allowed_from, reason = _check_access(from_folder, require_write=True)
    if not allowed_from:
        return f"Access denied on source: {reason}"

    allowed_to, reason = _check_access(to_folder, require_write=True)
    if not allowed_to:
        return f"Access denied on destination: {reason}"

    source = from_folder / filename
    if not source.exists():
        return f"{filename} not found in {from_folder.name}."

    destination = to_folder / filename
    try:
        shutil.move(str(source), str(destination))
        return f"Moved {filename} from {from_folder.name} to {to_folder.name}."
    except Exception as e:
        return f"Could not move file: {e}"


# ── Dispatch ───────────────────────────────────────────────────────────────────

def handle_filesystem_command(text: str) -> str | None:
    """
    Check if text is a filesystem command. If so, execute and return response.
    Returns None if not a filesystem command — caller passes to LLM.
    """
    lowered = text.lower()

    # List folder contents
    if any(p in lowered for p in ["what's in my", "whats in my", "list my", "show me my", "what files"]):
        return list_folder(lowered)

    # Read a file
    if any(p in lowered for p in ["read my", "open my", "show my"]):
        # Vault commands are handled by vault.py — only pass non-vault reads here
        if not any(v in lowered for v in ["note", "inbox", "jarvis note", "goals", "weekly"]):
            return read_file(lowered)

    # Summarize folder
    if "summarize" in lowered or "what do i have in" in lowered:
        return summarize_folder(lowered)

    # Move file
    if "move" in lowered and "to my" in lowered:
        # Basic parsing — expects "move [filename] from [folder] to [folder]"
        parts = text.split()
        if len(parts) >= 5:
            filename = parts[1]
            from_idx = text.lower().find("from")
            to_idx = text.lower().find("to my")
            if from_idx != -1 and to_idx != -1:
                from_query = text[from_idx:to_idx]
                to_query = text[to_idx:]
                return move_file(filename, from_query, to_query)

    return None  # not a filesystem command


if __name__ == "__main__":
    # Quick smoke test
    print(list_folder("jarvis project folder"))
    print(summarize_folder("important docs"))