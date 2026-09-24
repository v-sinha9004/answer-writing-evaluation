"""Unit tests for SupabaseStorageService."""

import pytest
from src.services.storage import SupabaseStorageService, sanitize_filename, get_storage_service


def test_sanitize_filename():
    assert sanitize_filename("answer copy (1).pdf") == "answer_copy__1_.pdf"
    assert sanitize_filename("my_folder/answer.pdf") == "answer.pdf"
    assert sanitize_filename("answer_copy") == "answer_copy.pdf"
    assert sanitize_filename("complex #@! name.PDF") == "complex_____name.pdf"


def test_storage_service_configuration():
    service = get_storage_service()
    assert service.is_configured() is True
    assert service.bucket == "answer-copies"


def test_storage_service_upload_and_delete():
    service = get_storage_service()
    dummy_pdf_bytes = b"%PDF-1.4 dummy test pdf bytes for testing upload and delete."
    test_eval_id = "eval_unit_test_999"
    test_filename = "test_unit.pdf"

    # Upload
    public_url = service.upload_pdf(
        pdf_bytes=dummy_pdf_bytes,
        filename=test_filename,
        eval_id=test_eval_id,
    )

    assert public_url is not None
    assert f"answer-copies/{test_eval_id}/test_unit.pdf" in public_url

    # Clean up / Delete
    deleted = service.delete_pdf(f"{test_eval_id}/test_unit.pdf")
    assert deleted is True
