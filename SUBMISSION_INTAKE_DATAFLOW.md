# Submission Intake System Data Flow

## Overview
Multi-tenant submission intake with strict isolation, validation, Azure Blob storage (mocked), Defender scan (mocked), full workflow state machine.

## Architecture Integration
- **Collections**: 'submissions' auto-wired via `TenantScopedRepository` from config/collections.py.
- **RBAC**: New permissions SUBMIT_FILE, SUBMIT_CSV_IMPORT, SUBMIT_EMAIL (analyst+/admin).
- **Middleware**: Auth/Tenant/RBAC run before handlers.
- **Services**: SubmissionService orchestrates validation/scan/store/state.
- **Storage**: InMemoryBlobStorage (mock Azure) generates SAS URLs.
- **Scanner**: MockDefenderScanner validates MIME/magic/size, mocks malware detection.

## Ingestion Modes
1. **Direct File Upload/REST**: POST /api/submissions/file `body.files = [{'file_name':, 'file_content_b64':, 'mime_type':}]`
2. **CSV Import**: POST /api/submissions/csv-import `body.files from csv.parse_csv(body.csv_content)`
3. **Email Inbox**: POST /api/submissions/email-webhook `body.files from attachments list`
4. **All modes** use base64 content (simulate multipart).

## Validation & Scan Flow
```
file_content_b64 -> decode -> validate_mime_magic_size(100MB) -> if fail -> EXCEPTION
  ↓ clean
scan_malware(mock hash/random) -> if 'malware' -> EXCEPTION (quarantine)
  ↓ clean
upload_blob -> blob_url + SAS(24h) -> READY state
```

**Magic Bytes** (PDF/DOCX/XLSX/PPTX/JPG/PNG only).
**Audit** every step/error.

## Workflow States
- DRAFT → INCOMPLETE → READY (post-scan/store)
- READY → PROCESSING → REVIEW_PENDING → VALIDATION_PENDING → EXCEPTION/COMPLETE
- PATCH /api/submissions/{id}/status updates.

## Example Usage (after tenant provision)
```python
foundation = create_sparc_foundation()
pdf_b64 = base64.b64encode(b'%PDF-1.4')
body = {
  "files": [{"file_name": "doc.pdf", "file_content_b64": pdf_b64.decode(), "mime_type": "application/pdf"}],
  "metadata": {"source": "portal"}
}
res = foundation.app.inject("POST", "/api/submissions/file", headers={"x-sparc-auth": json.dumps({"userId": "u", "role": "analyst", "tenantId": "t1"})}, body=body)
print(res)  # 201, list[submissions with blob_url/sas]
```

## Tests
5 E2E in tests/test_submission_intake.py (upload clean/malware/size/list/update).

## Production
Replace mocks:
- BlobStorage -> azure-storage-blob (conn_str env).
- DefenderScanner -> Azure Defender API.
Add [project.dependencies] azure deps in pyproject.toml.

Data flow tenant-safe, zero AI, pure I/O.

