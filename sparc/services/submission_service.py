"""SubmissionService: Orchestrates intake workflow.

- Decode base64 files
- Validate MIME/magic/size
- Scan malware
- Store Blob + SAS
- Create Cosmos record (READY or EXCEPTION)
- Update state, list tenant submissions.
CSV/email parse to files_data.
"""

import base64
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import uuid4

from typing import Any, Dict
class TenantContext:
    """Mock tenant context for submission service."""
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id


class BadRequestError(Exception):
    """Mock bad request error."""
    pass


class TenantScopedRepository:
    """Tenant-scoped repository for submissions."""
    
    def __init__(self, db: Any = None, collection_name: str = "submissions"):
        self._db = db
        self._collection_name = collection_name
        self._submissions: Dict[str, Dict[str, Any]] = {}
    
    async def find_one(self, tenant_id: str, filter_dict: Dict[str, Any] = None) -> Dict[str, Any]:
        """Find single document by filter."""
        key = f"{tenant_id}:{filter_dict.get('id', '')}" if filter_dict else None
        return self._submissions.get(key) if key else None
    
    async def find_many(self, tenant_id: str, filter_dict: Dict[str, Any] = None, skip: int = 0, limit: int = 50) -> list:
        """Find multiple documents by filter."""
        results = [v for k, v in self._submissions.items() if k.startswith(tenant_id)]
        return results[skip:skip + limit]
    
    async def upsert_one(self, tenant_id: str, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> bool:
        """Insert or update a document."""
        key = f"{tenant_id}:{filter_dict.get('id', '')}"
        self._submissions[key] = {**update_dict, 'tenantId': tenant_id}
        return True
    
    async def insert_one(self, tenant_id: str, document: Dict[str, Any]) -> str:
        """Insert a new document."""
        key = f"{tenant_id}:{document.get('id', '')}"
        self._submissions[key] = {**document, 'tenantId': tenant_id}
        return key
    
    async def update_one(self, tenant_id: str, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> bool:
        """Update a document."""
        key = f"{tenant_id}:{filter_dict.get('id', '')}"
        if key in self._submissions:
            self._submissions[key].update(update_dict)
            return True
        return False


class AuditService:
    """Mock audit service for submission service."""
    
    def __init__(self):
        self._logs = []
    
    async def record(self, context: Any, action: str):
        """Record an audit event."""
        self._logs.append({
            'tenant_id': getattr(context, 'tenant_id', 'unknown'),
            'action': action,
            'timestamp': 'now'
        })


class SubmissionService:
    """Core service for submission intake.

    Integrates repo/blob/scanner/audit.
    Handles 4 modes via unified files_data list.
    """
    MAX_SIZE_MB = 100

    def __init__(
        self,
        submissions_repo: TenantScopedRepository,
        blob_storage: InMemoryBlobStorage,
        scanner: MockDefenderScanner,
        audit_service: AuditService,
    ):
        self.submissions_repo = submissions_repo
        self.blob_storage = blob_storage
        self.scanner = scanner
        self.audit_service = audit_service

    async def create_submission(
        self,
        context: TenantContext,
        mode: str,  # 'file', 'csv', 'email'
        files_data: List[Dict[str, Any]],
        metadata: Dict[str, Any] = None,
    ) -> List[Submission]:
        """Main entry: process files_data list, return created submissions."""
        submissions = []
        for file_data in files_data:
            try:
                file_name = file_data['file_name']
                content_b64 = file_data['file_content_b64']
                reported_mime = file_data.get('mime_type', 'application/octet-stream')

                content = base64.b64decode(content_b64)
            except Exception as e:
                self.audit_service.record(context, f"Decode error {file_name}: {str(e)}")
                continue

            # Step 1: Validate
            validated_mime, valid = self.scanner.validate_mime_and_magic(content, reported_mime, self.MAX_SIZE_MB)
            if not valid:
                sub_id = f"sub-{uuid4().hex[:8]}"
                self._create_record(context, sub_id, SubmissionStatus.EXCEPTION, None, {'error': f'Validation: {validated_mime}'})
                self.audit_service.record(context, f"Validation fail {file_name}: {validated_mime}")
                continue

            # Step 2: Scan
            scan_result = self.scanner.scan_for_malware(content)
            if scan_result == 'malware':
                sub_id = f"sub-{uuid4().hex[:8]}"
                self._create_record(context, sub_id, SubmissionStatus.EXCEPTION, None, {'error': 'Malware quarantined'})
                self.audit_service.record(context, f"Malware quarantine {file_name}")
                continue

            # Step 3: Store
            blob_path = f"submissions/{context.tenant_id}/{uuid4().hex}/{file_name}"
            blob_url, sas_token = self.blob_storage.upload(blob_path, content)

            file_meta = FileMetadata(
                name=file_name,
                size_bytes=len(content),
                mime_type=validated_mime,
                blob_path=blob_path,
                blob_url=blob_url,
                sas_token=sas_token,
                scan_result=scan_result,
            )

            # Step 4: Record READY
            sub_id = f"sub-{uuid4().hex[:8]}"
            submission = self._create_record(
                context,
                sub_id,
                SubmissionStatus.READY,
                file_meta,
                metadata or {},
            )
            submissions.append(submission)
            self.audit_service.record(context, f"Success {sub_id} ({mode}): {file_name}")

        return submissions

    async def _create_record(
        self,
        context: TenantContext,
        sub_id: str,
        status: SubmissionStatus,
        file_meta: Optional[FileMetadata],
        metadata: Dict[str, Any],
    ) -> Submission:
        """Internal Cosmos upsert."""
        now = datetime.utcnow()
        submission = Submission(
            id=sub_id,
            tenant_id=context.tenant_id,
            status=status,
            file_metadata=file_meta,
            metadata=metadata,
            created_at=now,
            updated_at=now,
        )
        await self.submissions_repo.upsert_one(context.tenant_id, {'id': sub_id}, submission.to_dict())
        return submission

    async def update_status(
        self,
        context: TenantContext,
        sub_id: str,
        new_status: SubmissionStatus,
        reason: str = '',
    ) -> Submission:
        """Transition state (e.g., READY → PROCESSING)."""
        metadata = {'reason': reason} if reason else {}
        existing = await self.submissions_repo.find_one(context.tenant_id, {'id': sub_id})
        if not existing:
            raise BadRequestError(f"Submission {sub_id} not found in tenant {context.tenant_id}")
        existing['status'] = new_status.value
        existing['updated_at'] = datetime.utcnow().isoformat()
        existing['metadata'].update(metadata)
        await self.submissions_repo.upsert_one(context.tenant_id, {'id': sub_id}, existing)
        self.audit_service.record(context, f"State change {sub_id}: {new_status.value}")
        return Submission.from_dict(existing)

    async def list_submissions(self, context: TenantContext) -> List[Dict[str, Any]]:
        """List tenant submissions (non-exception optional)."""
        return await self.submissions_repo.find_many(context.tenant_id)

    @classmethod
    def parse_csv(cls, csv_content: str) -> List[Dict[str, Any]]:
        """Parse CSV to files_data (mock: assume columns file_name,file_content_b64,mime_type)."""
        lines = csv_content.splitlines()
        if not lines:
            return []
        reader = csv.DictReader(lines)
        return [dict(row) for row in reader]

    @classmethod
    def parse_email_attachments(cls, attachments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse email webhook attachments to files_data."""
        return attachments  # Pre-formatted {'file_name', 'file_content_b64', 'mime_type'}
