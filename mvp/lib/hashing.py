"""Content hashing utilities.

All citation / provenance hooks in the MVP identify content by SHA-256.
Centralising the primitives here keeps those hooks consistent and makes it
easy to swap algorithms later without touching callers.

Newline-normalisation (CRLF → LF) on text hashing is important: filings and
papers move between OSes during ingestion, and we do not want the same
extracted passage to hash differently because of line-ending drift.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK_BYTES = 1 << 20  # 1 MiB


def sha256_bytes(data: bytes) -> str:
    """Return the hex SHA-256 of ``data``.

    Parameters
    ----------
    data:
        Raw bytes to hash.

    Returns
    -------
    A 64-character lowercase hex string.
    """
    return hashlib.sha256(data).hexdigest()


def sha256_text(s: str, *, normalize_newlines: bool = True) -> str:
    """Return the hex SHA-256 of ``s`` (UTF-8 encoded).

    When ``normalize_newlines`` is ``True`` (the default), CRLF and CR are
    rewritten to LF before hashing. This is the behaviour callers almost
    always want for passage text; set it to ``False`` only when you are
    explicitly hashing a byte-exact artifact.
    """
    if normalize_newlines:
        # Handle both Windows (CRLF) and old-Mac (CR) without double-rewriting.
        s = s.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def normalize_excerpt_for_hash(text: str) -> str:
    """Return a whitespace-collapsed, lowercased form of ``text``.

    Manual-extraction YAML fixtures record a ``source_excerpt`` — a short
    verbatim quote from the filing around the value being cited — and pair
    it with ``excerpt_hash = sha256(normalized excerpt)``. Normalisation
    strips surrounding whitespace, collapses every run of interior
    whitespace (including tabs, CR, LF) to a single space, and lowercases
    the result. This keeps the hash stable against the whitespace drift
    that SGML ``.txt`` filings accumulate when copied between tools,
    without masking substantive text changes.

    Raises
    ------
    TypeError
        If ``text`` is not a string. The loud failure is intentional:
        silently accepting non-strings would let bugs (e.g. ``None`` from a
        missing YAML field) propagate into citation hashes.
    """
    if not isinstance(text, str):
        raise TypeError(f"normalize_excerpt_for_hash expects str, got {type(text).__name__}")
    # Collapse every run of unicode whitespace (spaces, tabs, CR, LF, NBSP…)
    # to a single ASCII space, then strip leading/trailing.
    collapsed = " ".join(text.split())
    return collapsed.lower()


def hash_excerpt(text: str) -> str:
    """Return ``sha256`` hex of :func:`normalize_excerpt_for_hash` of ``text``."""
    return hashlib.sha256(normalize_excerpt_for_hash(text).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 of the file at ``path``.

    Streams the file in 1 MiB chunks so large filings (10-Ks frequently
    exceed 20 MB) don't blow the heap.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist. (Allowed to propagate — callers generally
        want the native stdlib exception here.)
    IsADirectoryError
        If ``path`` is a directory.
    """
    path = Path(path)
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(_CHUNK_BYTES)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
