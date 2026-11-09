"""Opt-in integration against a disposable Secret Service session."""

import os
from uuid import uuid4

import pytest

from open_pdf.adapters.persistence.passwords import DocumentPasswordStore


@pytest.mark.secret_service
@pytest.mark.skipif(os.environ.get("OPEN_PDF_TEST_KEYRING") != "1",
                    reason="Requires a disposable desktop keyring")
def test_real_keyring_round_trip(tmp_path):
    path = tmp_path / f"{uuid4()}.pdf"
    store = DocumentPasswordStore()
    try:
        assert store.remember(path=path, password="test-only-secret")
        assert DocumentPasswordStore().recall(path) == "test-only-secret"
    finally:
        store.forget(path)
    assert store.recall(path) is None
    assert list(tmp_path.iterdir()) == []
