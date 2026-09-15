from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog
from app.models.user import User

def log_audit(db: Session, user: User, action: str, entity_type: str, entity_id: str = None, details: dict = None):
    audit = AuditLog(
        user_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details
    )
    db.add(audit)
    db.commit()
