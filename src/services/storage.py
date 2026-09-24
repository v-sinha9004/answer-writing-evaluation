import os
import re
import logging
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client, Client
from src.config import (
    ROOT_DIR,
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
    SUPABASE_STORAGE_BUCKET,
    is_supabase_configured,
)

logger = logging.getLogger("upsc-storage")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to be URL and object-store safe."""
    # Strip path components
    clean = filename.split("/")[-1].split("\\")[-1]
    # Replace whitespace and invalid characters with underscores
    clean = re.sub(r"[^\w\.\-]", "_", clean)
    # Ensure it ends with lowercase .pdf
    if clean.lower().endswith(".pdf"):
        clean = clean[:-4] + ".pdf"
    else:
        clean += ".pdf"
    return clean or "answer_copy.pdf"


class SupabaseStorageService:
    """Manages file storage interactions with Supabase Storage."""

    def __init__(
        self,
        url: Optional[str] = None,
        key: Optional[str] = None,
        bucket: Optional[str] = None,
    ):
        load_dotenv(ROOT_DIR / ".env", override=True)
        self.url = url or os.getenv("SUPABASE_URL") or SUPABASE_URL
        self.key = key or os.getenv("SUPABASE_ANON_KEY") or SUPABASE_ANON_KEY
        self.bucket = bucket or os.getenv("SUPABASE_STORAGE_BUCKET") or SUPABASE_STORAGE_BUCKET
        self._client: Optional[Client] = None

    @property
    def client(self) -> Optional[Client]:
        """Lazy-initialize Supabase client."""
        load_dotenv(ROOT_DIR / ".env", override=True)
        url = self.url or os.getenv("SUPABASE_URL", "")
        key = self.key or os.getenv("SUPABASE_ANON_KEY", "")
        if self._client is None and bool(url and key):
            try:
                self._client = create_client(url, key)
            except Exception as e:
                logger.error(f"Failed to initialize Supabase client: {e}")
        return self._client

    def is_configured(self) -> bool:
        """Check if Supabase storage settings are present."""
        load_dotenv(ROOT_DIR / ".env", override=True)
        url = self.url or os.getenv("SUPABASE_URL", "")
        key = self.key or os.getenv("SUPABASE_ANON_KEY", "")
        bucket = self.bucket or os.getenv("SUPABASE_STORAGE_BUCKET", "")
        return bool(url and key and bucket)

    def upload_pdf(
        self,
        pdf_bytes: bytes,
        filename: str,
        eval_id: str,
    ) -> Optional[str]:
        """Upload candidate answer PDF bytes to Supabase Storage.
        
        Args:
            pdf_bytes: Raw binary content of the PDF file.
            filename: Original filename of the uploaded PDF.
            eval_id: Unique evaluation identifier (e.g. 'eval_abc123').
            
        Returns:
            The public URL to the uploaded file if successful, otherwise None.
        """
        if not self.is_configured():
            logger.warning("Supabase storage is not configured. Skipping upload.")
            return None

        if not pdf_bytes or len(pdf_bytes) < 10:
            logger.warning("Attempted to upload empty or invalid PDF bytes.")
            return None

        client = self.client
        if not client:
            logger.error("Supabase client is not available.")
            return None

        clean_name = sanitize_filename(filename)
        storage_path = f"{eval_id}/{clean_name}"

        try:
            logger.info(
                f"Uploading PDF ({len(pdf_bytes)} bytes) to Supabase Storage: "
                f"bucket='{self.bucket}', path='{storage_path}'"
            )

            # Upload to Supabase Storage (upsert=true allows re-evaluation overwrite)
            response = client.storage.from_(self.bucket).upload(
                path=storage_path,
                file=pdf_bytes,
                file_options={"content-type": "application/pdf", "upsert": "true"},
            )

            # Get public URL
            public_url = client.storage.from_(self.bucket).get_public_url(storage_path)
            logger.info(f"Successfully uploaded PDF. Public URL: {public_url}")
            return public_url

        except Exception as e:
            logger.error(f"Failed to upload PDF to Supabase Storage: {e}", exc_info=True)
            return None

    def delete_pdf(self, storage_path: str) -> bool:
        """Delete a file from Supabase Storage."""
        if not self.is_configured() or not self.client:
            return False

        try:
            self.client.storage.from_(self.bucket).remove([storage_path])
            logger.info(f"Deleted {storage_path} from bucket {self.bucket}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete {storage_path}: {e}")
            return False


# Global default instance
_storage_service: Optional[SupabaseStorageService] = None


def get_storage_service() -> SupabaseStorageService:
    """Get or create singleton SupabaseStorageService."""
    global _storage_service
    if _storage_service is None:
        _storage_service = SupabaseStorageService()
    return _storage_service
