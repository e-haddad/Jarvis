"""
Quick standalone test for open_obsidian_note logic.
Run this before integrating into filesystem.py.
"""
import subprocess
from pathlib import Path

VAULT_ROOT = Path.home() / "Desktop" / "OBS" / "Edward"

def open_obsidian_note(note_name: str) -> str:
    """
    Open a specific note in Obsidian by name (partial match, case-insensitive).
    Searches the entire vault recursively for a .md file matching the query,
    then uses osascript to tell Obsidian to open it via the obsidian:// URI scheme.
    """
    query = note_name.strip().lower()

    # Search vault for matching .md file
    matches = [
        p for p in VAULT_ROOT.rglob("*.md")
        if query in p.stem.lower()
    ]

    if not matches:
        return f"No note found matching '{note_name}' in the vault."

    # Prefer exact match, otherwise take first result
    exact = [m for m in matches if m.stem.lower() == query]
    target = exact[0] if exact else matches[0]

    # Build obsidian:// URI — path relative to vault root
    rel_path = target.relative_to(VAULT_ROOT)
    vault_name = "Edward"  # Obsidian vault name
    uri = f"obsidian://open?vault={vault_name}&file={str(rel_path)}"

    try:
        subprocess.run(["open", uri], check=True)
        return f"Opened '{target.stem}' in Obsidian."
    except subprocess.CalledProcessError as e:
        return f"Failed to open note: {e}"


# ── Test ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Try opening the persistent memory note
    result = open_obsidian_note("Persistent Memory")
    print(result)
