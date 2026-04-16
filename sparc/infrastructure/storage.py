"""Infrastructure mocks for Azure Blob Storage and Defender scan.

InMemoryBlobStorage: mock upload/get, generates SAS tokens (24h expiry).
MockDefenderScanner: MIME/magic/size validation + mock malware scan (hash/random).
"""

import base64
import hashlib
import secrets
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from uuid import uuid4

from sparc.domain.submission import FileMetadata

class InMemoryBlobStorage:
    """Mock Azure Blob Storage.

    Stores bytes in dict, generates mock SAS URL/token for 24h access.
    blob_path format: submissions/tenant/uuid/filename
    """
    def __init__(self):
        self._blobs: Dict[str, bytes] = {}
        self._account_url = "https://mocksparc.blob.core.windows.net"  # Mock account

    def upload(self, blob_path: str, content: bytes) -> Tuple[str, str]:
        """Upload content, return signed URL + SAS token."""
        expiry = datetime.utcnow() + timedelta(hours=24)
        sas_token = f"?sv=2023-01-03&ss=b&srt=sco&sp=rw&se={expiry.strftime('%Y-%m-%dT%H:%M:%SZ')}&sr=c&sig={secrets.token_hex(32)}"
        blob_url = f"{self._account_url}/{blob_path}{sas_token}"
        self._blobs[blob_path] = content
        return blob_url, sas_token

    def get_blob(self, blob_path: str) -> Optional[bytes]:
        """Retrieve stored blob."""
        return self._blobs.get(blob_path)

class MockDefenderScanner:
    """Mock Microsoft Defender for Storage scan + file validation.

    Validates MIME + magic bytes + size.
    Scan: mock hash/random to 'malware'/'clean'.
    """
    # Magic bytes signatures for supported formats
    MAGIC_BYTES = {
        'application/pdf': b'%PDF-',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': b'PK\x03\x04\x14\x00\x06\x00',  # DOCX ZIP
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': b'PK\x03\x04\x14\x00\x06\x00',  # XLSX
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': b'PK\x03\x04\x14\x00\x06\x00',  # PPTX
        'image/jpeg': b'\xff\xd8\xff',
        'image/png': b'\x89PNG\r\n\x1a\n',
    }

    ALLOWED_MIME_TYPES = MAGIC_BYTES.keys()

    MIME_EXT_MAP = {
        'application/pdf': '.pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
        'image/jpeg': '.jpg',
        'image/png': '.png',
    }

    @classmethod
    def validate_mime_and_magic(cls, content: bytes, reported_mime: str, max_size_mb: int = 100) -> Tuple[str, bool]:
        """Validate reported MIME, magic bytes, size limit."""
        size_bytes = len(content)
        if size_bytes > max_size_mb * 1024 * 1024:
            return 'size_exceeded', False

        if reported_mime not in cls.ALLOWED_MIME_TYPES:
            return 'invalid_mime', False

        magic = cls.MAGIC_BYTES[reported_mime]
        if not content.startswith(magic):
            return 'invalid_magic_bytes', False

        return reported_mime, True

    def scan_for_malware(self, content: bytes) -> str:
        """Mock Defender scan: hash-based deterministic + random."""
        md5 = hashlib.md5(content).hexdigest()
        # Deterministic for tests: 'malwaretest' content triggers
        if b'malwaretest' in content or 'malware' in md5[:8] or secrets.randbits(3) == 0:
            return 'malware'
        return 'clean'
