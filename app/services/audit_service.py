import json
from typing import Any, Optional
from app.extensions import db
from app.models.audit_event import AuditEvent


def log_audit_event(
    user_id: int,
    entity_type: str,
    entity_id: int,
    action: str,
    before_snapshot: Optional[Any] = None,
    after_snapshot: Optional[Any] = None,
) -> AuditEvent:
    """
    Record an immutable audit log entry for changes to financial or entity records.
    """
    event = AuditEvent(
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        before_snapshot_json=json.dumps(before_snapshot, default=str) if before_snapshot else None,
        after_snapshot_json=json.dumps(after_snapshot, default=str) if after_snapshot else None,
    )
    db.session.add(event)
    return event
