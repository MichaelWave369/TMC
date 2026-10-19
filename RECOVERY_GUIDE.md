# Local backup and recovery

Keep any runtime database, snapshots and configuration out of the source repository. Test recovery with disposable synthetic data first.

1. Verify the backup location and current data owner.
2. Make a snapshot in a local protected directory.
3. Preview any migration or restore operation.
4. Confirm which profile, workspace and vault records will change.
5. Apply only after reviewing the destination and preserving a rollback copy.
6. Validate restored data and rerun tests.

**Warning:** existing exports, backups and vault transforms should not be assumed to provide strong confidentiality. Safeguard generated files using operating-system protections.
