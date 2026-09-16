from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog
from app.models.user import User

async def log_audit(db: AsyncSession, user: User, action: str, entity_type: str, entity_id: str = None, details: dict = None):
    audit = AuditLog(
        user_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details
    )
    db.add(audit)
    await db.commit()
