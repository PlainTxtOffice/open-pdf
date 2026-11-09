"""Protect small persisted secrets using Windows DPAPI when available."""

from __future__ import annotations

import base64
import binascii
import sys

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _DataBlob(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]

    _crypt_protect_data = ctypes.windll.crypt32.CryptProtectData
    _crypt_protect_data.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    _crypt_protect_data.restype = wintypes.BOOL

    _crypt_unprotect_data = ctypes.windll.crypt32.CryptUnprotectData
    _crypt_unprotect_data.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    _crypt_unprotect_data.restype = wintypes.BOOL

    _local_free = ctypes.windll.kernel32.LocalFree
    _local_free.argtypes = [ctypes.c_void_p]
    _local_free.restype = ctypes.c_void_p

    _PROTECTION_ENTROPY = b"open_pdf.remembered_password.v1"


def protect_string(value: str) -> str | None:
    """Return one protected secret string, or None when unavailable."""
    if sys.platform != "win32":
        return None

    protected_bytes = _protect_bytes(value.encode("utf-8"))
    if protected_bytes is None:
        return None

    return base64.b64encode(protected_bytes).decode("ascii")


def unprotect_string(value: str) -> str | None:
    """Return one previously protected secret string, or None on failure."""
    if sys.platform != "win32":
        return None

    try:
        protected_bytes = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        return None

    secret_bytes = _unprotect_bytes(protected_bytes)
    if secret_bytes is None:
        return None

    try:
        return secret_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _protect_bytes(value: bytes) -> bytes | None:
    if sys.platform != "win32":
        return None

    value_blob, value_buffer = _blob_from_bytes(value)
    entropy_blob, entropy_buffer = _blob_from_bytes(_PROTECTION_ENTROPY)
    output_blob = _DataBlob()
    if not _crypt_protect_data(
        ctypes.byref(value_blob),
        None,
        ctypes.byref(entropy_blob),
        None,
        None,
        0,
        ctypes.byref(output_blob),
    ):
        return None

    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        _local_free(output_blob.pbData)
        del value_buffer
        del entropy_buffer


def _unprotect_bytes(value: bytes) -> bytes | None:
    if sys.platform != "win32":
        return None

    value_blob, value_buffer = _blob_from_bytes(value)
    entropy_blob, entropy_buffer = _blob_from_bytes(_PROTECTION_ENTROPY)
    output_blob = _DataBlob()
    if not _crypt_unprotect_data(
        ctypes.byref(value_blob),
        None,
        ctypes.byref(entropy_blob),
        None,
        None,
        0,
        ctypes.byref(output_blob),
    ):
        return None

    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        _local_free(output_blob.pbData)
        del value_buffer
        del entropy_buffer


def _blob_from_bytes(value: bytes) -> tuple[_DataBlob, object | None]:
    if sys.platform != "win32":
        raise RuntimeError

    if not value:
        return _DataBlob(0, ctypes.POINTER(ctypes.c_byte)()), None

    buffer = (ctypes.c_byte * len(value)).from_buffer_copy(value)
    return (
        _DataBlob(
            len(value),
            ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)),
        ),
        buffer,
    )
