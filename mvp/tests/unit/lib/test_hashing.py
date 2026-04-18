"""Unit tests for mvp.lib.hashing."""

from __future__ import annotations

from pathlib import Path

import pytest

from mvp.lib.hashing import sha256_bytes, sha256_file, sha256_text

# Canonical sha256 values for fixed inputs. Verified against Python stdlib
# hashlib independently; hard-coded here so any regression is obvious.
EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
ABC_SHA256 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_sha256_bytes_empty() -> None:
    assert sha256_bytes(b"") == EMPTY_SHA256


def test_sha256_bytes_abc() -> None:
    assert sha256_bytes(b"abc") == ABC_SHA256


def test_sha256_text_utf8_matches_bytes() -> None:
    assert sha256_text("abc", normalize_newlines=False) == ABC_SHA256


def test_sha256_text_normalizes_crlf() -> None:
    crlf = sha256_text("line1\r\nline2\r\n")
    lf = sha256_text("line1\nline2\n")
    assert crlf == lf


def test_sha256_text_normalizes_cr_only() -> None:
    cr = sha256_text("line1\rline2\r")
    lf = sha256_text("line1\nline2\n")
    assert cr == lf


def test_sha256_text_without_normalization_distinguishes() -> None:
    a = sha256_text("a\r\nb", normalize_newlines=False)
    b = sha256_text("a\nb", normalize_newlines=False)
    assert a != b


def test_sha256_file_matches_bytes(tmp_path: Path) -> None:
    p = tmp_path / "f.bin"
    payload = b"abc"
    p.write_bytes(payload)
    assert sha256_file(p) == ABC_SHA256


def test_sha256_file_streams_large(tmp_path: Path) -> None:
    # 5 MB file: exercise chunking.
    p = tmp_path / "big.bin"
    payload = b"x" * (5 * 1024 * 1024)
    p.write_bytes(payload)
    assert sha256_file(p) == sha256_bytes(payload)


def test_sha256_file_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        sha256_file(tmp_path / "nope.bin")
