import base64
import json
import unittest
from sparc.foundation import create_sparc_foundation
from sparc.domain.roles import Role
from sparc.domain.submission import SubmissionStatus

def call(app, method, path, role, user_id, tenant_id, body=None, extra_headers=None):
    payload = {"userId": user_id, "role": role.value, "tenantId": tenant_id}
    headers = {"x-sparc-auth": json.dumps(payload)}
    if extra_headers:
        headers.update(extra_headers)
    return app.inject(method=method, path=path, headers=headers, body=body or {})

def provision_tenant(app, tenant_id):
    body = {"tenantId": tenant_id, "name": f"T {tenant_id}"}
    provision = call(app, "POST", "/api/tenants/provision", Role.SUPER_ADMIN, "root", tenant_id, body)
    assert provision["status_code"] == 201
    activate = call(app, "POST", f"/api/tenants/{tenant_id}/activate", Role.SUPER_ADMIN, "root", tenant_id)
    assert activate["status_code"] == 200

class SubmissionIntakeTests(unittest.TestCase):
    def setUp(self):
        self.foundation = create_sparc_foundation()
        self.app = self.foundation.app

    def test_file_upload_validation_clean(self):
        provision_tenant(self.app, "t1")
        small_pdf = base64.b64encode(b'%PDF-1.4 test clean')
        body = {
            "files": [{
                "file_name": "test.pdf",
                "file_content_b64": base64.b64encode(small_pdf).decode(),
                "mime_type": "application/pdf",
            }],
            "metadata": {"mode": "direct"}
        }
        response = call(self.app, "POST", "/api/submissions/file", Role.ANALYST, "analyst", "t1", body)
        assert response["status_code"] == 201
        assert response["body"][0]["status"] == SubmissionStatus.READY.value

    def test_malware_quarantine(self):
        provision_tenant(self.app, "t2")
        bad_content = base64.b64encode(b'malware test')
        body = {
            "files": [{
                "file_name": "bad.doc",
                "file_content_b64": base64.b64encode(bad_content).decode(),
                "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            }],
        }
        response = call(self.app, "POST", "/api/submissions/file", Role.ANALYST, "analyst", "t2", body)
        assert response["status_code"] == 201
        assert response["body"][0]["status"] == SubmissionStatus.EXCEPTION.value
        assert 'malware' in response["body"][0]["metadata"]["error"].lower()

    def test_size_exceeded(self):
        provision_tenant(self.app, "t3")
        large = b'a' * (101 * 1024 * 1024)  # 101MB
        b64 = base64.b64encode(large).decode()
        body = {
            "files": [{
                "file_name": "large.pdf",
                "file_content_b64": b64,
                "mime_type": "application/pdf",
            }],
        }
        response = call(self.app, "POST", "/api/submissions/file", Role.ANALYST, "analyst", "t3", body)
        assert response["status_code"] == 201
        assert response["body"][0]["status"] == SubmissionStatus.EXCEPTION.value
        assert 'size' in response["body"][0]["metadata"]["error"].lower()

    def test_list_submissions(self):
        provision_tenant(self.app, "t4")
        # Create one
        small = base64.b64encode(b'%PDF-')
        body = {"files": [{"file_name": "list.pdf", "file_content_b64": base64.b64encode(small).decode(), "mime_type": "application/pdf"}]}
        call(self.app, "POST", "/api/submissions/file", Role.ANALYST, "user4", "t4", body)
        response = call(self.app, "GET", "/api/submissions", Role.VIEWER, "viewer", "t4")
        assert response["status_code"] == 200
        assert len(response["body"]) > 0

    def test_status_update(self):
        provision_tenant(self.app, "t5")
        res_create = call(self.app, "POST", "/api/submissions/file", Role.ANALYST, "user5", "t5", {"files": [{"file_name": "test.pdf", "file_content_b64": base64.b64encode(b'%PDF-').decode(), "mime_type": "application/pdf"}]})
        sub_id = res_create["body"][0]["id"]
        body = {"status": SubmissionStatus.PROCESSING.value}
        response = call(self.app, "PATCH", f"/api/submissions/{sub_id}/status", Role.TENANT_ADMIN, "admin", "t5", body)
        assert response["status_code"] == 200
        assert response["body"]["status"] == SubmissionStatus.PROCESSING.value
