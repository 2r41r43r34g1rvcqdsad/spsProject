# Submission Intake System - Steps

Approved plan breakdown (all features kept).

1. ✅ Create TODO-submission-intake.md
2. ✅ Add "submissions" to sparc/config/collections.py.
3. ✅ Create sparc/domain/submission.py (Status enum, Submission model).
4. ✅ Update sparc/domain/roles.py (new Permission.SUBMIT_*).
5. ✅ Create sparc/infrastructure/storage.py (InMemoryBlobStorage, MockDefenderScanner).
6. ✅ Create sparc/services/submission_service.py.
7. Update sparc/api/routes.py (add routes).
8. Update sparc/foundation.py (wire service).
9. Create tests/test_submission_intake.py.
10. Update pyproject.toml (optional azure deps).
11. Run tests, complete.
