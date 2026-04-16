"""Domain models for submission intake.

Defines SubmissionStatus enum and Submission/FileMetadata dataclasses.
to_dict/from_dict for Cosmos serialization.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime

class SubmissionStatus(str, Enum):
    """Workflow states for submission lifecycle."""
    DRAFT = "draft"  # Initial upload incomplete
    INCOMPLETE = "incomplete"  # Missing metadata/files
    READY = "ready"  # Validated/scanned/stored, queue for processing
    PROCESSING = "processing"  # Active processing
    REVIEW_PENDING = "review_pending"  # Manual review needed
    VALIDATION_PENDING = "validation_pending"  # Business validation
    EXCEPTION = "exception"  # Validation/scan fail, quarantined
    COMPLETE = "complete"  # Final accepted state

@dataclass
class FileMetadata:
    """File metadata post-validation/storage.
    
    SAS token expires 24h for secure access.
    scan_result: 'clean'/'malware'.
    """
    name: str
    size_bytes: int
    mime_type: str  # Validated MIME
    blob_path: str  # 'submissions/tenant_id/uuid/filename'
    blob_url: str  # Full signed URL
    sas_token: str  # Mock/real SAS
    scan_result: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for Cosmos upsert."""
        return self.__dict__.copy()

@dataclass
class Submission:
    """Tenant-scoped submission record.
    
    Partitioned by tenant_id, workflow state managed via service.
    """
    id: str  # 'sub-abc123'
    tenant_id: str
    status: SubmissionStatus
    file_metadata: Optional[FileMetadata] = None
    metadata: Dict[str, Any] = None  # {'mode': 'file', 'source': 'portal', 'reason': ...}
    created_at: datetime = None
    updated_at: datetime = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Submission':
        """Deserialize from Cosmos doc."""
        file_meta_data = data.get('file_metadata')
        file_meta = FileMetadata(**file_meta_data) if file_meta_data else None
        return cls(
            id=data['id'],
            tenant_id=data['tenant_id'],
            status=SubmissionStatus(data['status']),
            file_metadata=file_meta,
            metadata=data.get('metadata', {}),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for Cosmos upsert/read."""
        file_meta_dict = self.file_metadata.to_dict() if self.file_metadata else None
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'status': self.status.value,
            'file_metadata': file_meta_dict,
            'metadata': self.metadata or {},
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
