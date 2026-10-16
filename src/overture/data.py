"""Where the language-neutral files (schemas/, catalog/) are found.

A built wheel carries them in ``overture/data``; a source checkout reads them from the
repository root, where they are maintained.
"""

from pathlib import Path

_HERE = Path(__file__).resolve().parent


def root(packaged: Path = _HERE / "data") -> Path:
    """Return the directory holding ``schemas/`` and ``catalog/``."""
    return packaged if packaged.is_dir() else _HERE.parents[1]
