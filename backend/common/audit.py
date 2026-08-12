"""审计日志系统 — 记录所有关键操作。"""
import logging
import sqlite3
import traceback
from datetime import datetime
from functools import wraps

logger = logging.getLogger(__name__)

AUDIT_ACTIONS = {
    'login': '登录',
    'logout': '登出',
    'register': '注册',
    'password_change': '修改密码',
    'password_reset': '重置密码',
    'upgrade': '升级会员',
    'downgrade': '降级会员',
    'template_upload': '上传模板',
    'template_delete': '删除模板',
    'template_buy': '购买模板',
    'invite': '邀请用户',
    'share': '分享内容',
    'api_key_create': '创建API Key',
    'api_key_delete': '删除API Key',
    'config_change': '修改配置',
    'user_create': '创建用户',
    'user_update': '更新用户',
    'user_delete': '删除用户',
    'role_change': '修改角色',
}


def log_audit(user_id: str, action: str, target_id: str = "", 
              target_type: str = "", details: dict = None, 
              success: bool = True, error: str = "") -> None:
    """记录审计日志。"""
    try:
        from common.db import get_db
        conn = get_db()
        conn.execute(
            """INSERT INTO audit_logs (id, user_id, action, target_id, target_type, 
               details, success, error, ip_address, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"al_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                user_id,
                action,
                target_id,
                target_type,
                details and str(details)[:2000] or '',
                1 if success else 0,
                error and str(error)[:500] or '',
                '',  # IP地址需要从请求中获取
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        conn.close()
        logger.debug(f"Audit: {action} by {user_id} -> {'OK' if success else 'FAIL'}")
    except Exception as e:
        logger.warning(f"Failed to log audit: {e}")


def audit_action(action: str, target_type: str = ""):
    """装饰器：自动记录操作审计。"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 尝试从请求中获取用户信息
            user_id = ""
            if kwargs.get('current_user'):
                user_id = kwargs['current_user'].get('user_id', '')
            elif len(args) > 0 and hasattr(args[0], 'username'):
                user_id = args[0].username
            
            # 执行原函数
            try:
                result = await func(*args, **kwargs)
                # 记录成功
                log_audit(
                    user_id=user_id,
                    action=action,
                    target_type=target_type,
                    details={"result": str(result)[:200] if result else None},
                    success=True,
                )
                return result
            except Exception as e:
                # 记录失败
                log_audit(
                    user_id=user_id,
                    action=action,
                    target_type=target_type,
                    error=str(e),
                    success=False,
                )
                raise
        return wrapper
    return decorator


def ensure_audit_table():
    """确保审计日志表存在。"""
    from common.db import get_db
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                target_id TEXT DEFAULT '',
                target_type TEXT DEFAULT '',
                details TEXT DEFAULT '',
                success INTEGER DEFAULT 1,
                error TEXT DEFAULT '',
                ip_address TEXT DEFAULT '',
                created_at TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(created_at)")
        conn.commit()
    finally:
        conn.close()
    logger.info("Audit log table ensured")


def get_audit_logs(user_id: str = "", action: str = "", 
                   start_date: str = "", end_date: str = "",
                   limit: int = 100) -> dict:
    """查询审计日志。"""
    from common.db import get_db
    conn = get_db()
    try:
        where = []
        params = []
        if user_id:
            where.append("user_id = ?")
            params.append(user_id)
        if action:
            where.append("action = ?")
            params.append(action)
        if start_date:
            where.append("created_at >= ?")
            params.append(start_date)
        if end_date:
            where.append("created_at <= ?")
            params.append(end_date)
        
        sql = "SELECT * FROM audit_logs"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(sql, params).fetchall()
        logs = [dict(r) for r in rows]
        
        # 统计
        total = conn.execute(f"SELECT COUNT(*) FROM audit_logs" + (" WHERE " + " AND ".join(where) if where else ""), params[:-1]).fetchone()[0]
        
        return {"logs": logs, "total": total}
    finally:
        conn.close()
