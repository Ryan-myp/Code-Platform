#!/usr/bin/env python3
"""定时任务引擎（v10.1 + v18 企业级优化）。

- 管理 cron 式定时任务
- 支持：定时报告生成、数据同步、提醒通知
- SQLite scheduler_jobs 表持久化
- v18: 通知文件驱动的企业级优化流程
"""

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from common.auth import require_auth
from common.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scheduler", tags=["定时任务"])

# 项目根目录
PROJECT_DIR = Path(__file__).resolve().parent.parent

# 通知文件目录（v18）
NOTIFY_DIR = PROJECT_DIR / "backend" / "listener" / "notifications"
NOTIFY_DIR.mkdir(parents=True, exist_ok=True)

# 全局调度线程状态
_scheduler_running = False
_scheduler_thread = None


def _ensure_table():
    conn = get_db()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS scheduler_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                job_type TEXT NOT NULL DEFAULT 'report',
                cron_expression TEXT NOT NULL DEFAULT '0 9 * * *',
                config TEXT DEFAULT '{}',
                enabled INTEGER DEFAULT 1,
                last_run TEXT,
                next_run TEXT,
                last_status TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )
        # v15：执行历史（每次运行落库：状态/时间/输出/错误）
        conn.execute(
            """CREATE TABLE IF NOT EXISTS scheduler_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                output TEXT DEFAULT '',
                error TEXT DEFAULT '',
                started_at TEXT NOT NULL DEFAULT (datetime('now')),
                finished_at TEXT
            )"""
        )
        # v24：幂等补列（旧库升级：缺 last_status 时 ALTER 补齐，否则回写 last_run/last_status 报 no such column）
        cols = {row[1] for row in conn.execute("PRAGMA table_info(scheduler_jobs)").fetchall()}
        if 'last_status' not in cols:
            conn.execute("ALTER TABLE scheduler_jobs ADD COLUMN last_status TEXT DEFAULT ''")
        conn.commit()
    finally:
        conn.close()


_ensure_table()


def _field_values(spec: str, lo: int, hi: int):
    """cron 单字段展开为取值集合：`*` 全部 / `*/n` 步进 / `a-b` 范围 / `a,b,c` 枚举。

    非法值返回 None（供调用方判定表达式非法）。
    """
    spec = (spec or "*").strip()
    if not spec:
        return None
    try:
        if spec == "*":
            return set(range(lo, hi + 1))
        if "/" in spec:
            base, _, step = spec.partition("/")
            step = int(step)
            if step <= 0:
                return None
            start = lo if base in ("*", "") else min(_field_values(base, lo, hi) or {lo})
            return set(range(start, hi + 1, step))
        if "-" in spec:
            a, _, b = spec.partition("-")
            a, b = int(a), int(b)
            if a < lo or b > hi or a > b:
                return None
            return set(range(a, b + 1))
        if "," in spec:
            vals = set()
            for part in spec.split(","):
                sub = _field_values(part, lo, hi)
                if sub is None:
                    return None
                vals |= sub
            return vals
        v = int(spec)
        if v < lo or v > hi:
            return None
        return {v}
    except (ValueError, TypeError):
        return None


def _parse_cron(expr: str, now=None):
    """cron 解析（5 段：分 时 日 月 周），计算**下一次**运行时间（精确到分钟）。

    - 支持 `*` / `*/n` / `a-b` / `a,b` / 单值
    - 找不到未来匹配点（如 2 月 30 日）返回 None
    """
    parts = (expr or "").strip().split()
    if len(parts) != 5:
        return None
    minute, hour, day, month, weekday = parts
    minutes = _field_values(minute, 0, 59)
    hours = _field_values(hour, 0, 23)
    days = _field_values(day, 1, 31)
    months = _field_values(month, 1, 12)
    # cron 约定：0/7=周日，1-6=周一..周六 → 映射为 Python weekday（0=周一..6=周日）
    cron_weekdays = _field_values(weekday, 0, 7)
    if None in (minutes, hours, days, months, cron_weekdays):
        return None
    if not (minutes and hours and days and months and cron_weekdays):
        return None
    weekdays = {6 if w in (0, 7) else w - 1 for w in cron_weekdays}

    now = now or datetime.now()
    cur = now.replace(second=0, microsecond=0)
    # 从下一分钟开始向后找，最多 400 天（覆盖跨年/闰年）
    from datetime import timedelta

    for _ in range(400 * 24 * 60):
        cur += timedelta(minutes=1)
        if cur.month not in months or cur.day not in days:
            continue
        if cur.weekday() not in weekdays:
            continue
        if cur.hour not in hours or cur.minute not in minutes:
            continue
        return cur.isoformat()
    return None


def _record_run(job_id: int, status: str, output: str = "", error: str = ""):
    """执行历史落库：新增一条运行记录，并回写 job 的 last_run/last_status。"""
    now = datetime.now().isoformat()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO scheduler_runs (job_id, status, output, error, started_at, finished_at) VALUES (?,?,?,?,?,?)",
            (job_id, status, output[:2000], error[:1000], now, now),
        )
        conn.execute(
            "UPDATE scheduler_jobs SET last_run=?, last_status=?, updated_at=? WHERE id=?",
            (now, status, now, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def _execute_job(job) -> tuple:
    """真正执行定时任务体，按 job_type 分发。返回 (ok, output)。"""
    job_type = (job.get("job_type") or "report").strip()
    try:
        if job_type == "notify":
            # 站内信：user_id→username 转换后复用 notify_api 统一发送函数
            from notify_api import send_inbox_message

            conn = get_db()
            try:
                row = conn.execute(
                    "SELECT username FROM users WHERE id=?", (str(job.get("user_id", 0)),)
                ).fetchone()
            finally:
                conn.close()
            username = row["username"] if row else "all"
            send_inbox_message(username, f"定时任务：{job.get('name', '')}", "由定时任务引擎自动发送")
            return True, "站内信已发送"
        if job_type == "backup":
            # 数据备份：复用 common.backup（失败不中断）
            from common.backup import run_backup

            out = run_backup()
            return True, f"备份完成：{out if isinstance(out, str) else 'ok'}"
        if job_type == "stock_report":
            # v21：每日定时股票分析报告（config: {symbol, period, analysis_type}）
            import asyncio

            cfg = json.loads(job.get("config") or "{}")
            symbol = (cfg.get("symbol") or "").strip()
            if not symbol:
                return False, "未配置股票代码（config.symbol）"
            period = str(cfg.get("period") or "3mo")
            analysis_type = str(cfg.get("analysis_type") or "comprehensive")

            from stock_tools import run_stock_analysis
            from notify_api import send_webhook_message

            out = asyncio.run(run_stock_analysis(symbol, period, analysis_type))
            report = str(out.get("result") or "")
            if not report.strip():
                return False, "AI 未返回分析内容"

            # 报告入库（stock_reports 表，用户前台可查历史）
            uid = str(job.get("user_id", ""))
            conn = get_db()
            try:
                conn.execute(
                    "INSERT INTO stock_reports (user_id, symbol, period, report, created_at) "
                    "VALUES (?,?,?,?,?)",
                    (uid, out.get("symbol") or symbol, period, report, datetime.now().isoformat()),
                )
                conn.commit()
            finally:
                conn.close()

            # Webhook 推送（飞书/企业微信等；未配置则静默跳过）
            pushed = asyncio.run(send_webhook_message(uid, f"每日股票分析：{symbol}", report[:2000]))
            return True, f"报告已生成{'(并推送 Webhook)' if pushed else ''}（{len(report)} 字）"
        if job_type == "enterprise_optimizer":
            # v18：企业级智能优化（每小时20分运行，全面提升系统到商用级别）
            try:
                from enterprise_optimizer import run_enterprise_optimizer
                report_path = run_enterprise_optimizer()
                return True, f"优化完成，报告：{report_path}"
            except Exception as e:
                logger.exception("[Scheduler] 企业级优化失败: %s", e)
                return False, str(e)
        # 默认 report：生成调度运行统计摘要
        conn = get_db()
        try:
            total = conn.execute("SELECT COUNT(*) FROM scheduler_jobs").fetchone()[0]
            runs = conn.execute("SELECT COUNT(*) FROM scheduler_runs WHERE status='success'").fetchone()[0]
        finally:
            conn.close()
        return True, f"调度自检报告：共 {total} 个任务，历史成功 {runs} 次"
    except Exception as e:
        logger.exception("[Scheduler] 任务执行失败: %s", job.get("name"))
        return False, str(e)


def _run_with_retry(fn, max_attempts: int = 3, base_delay: float = 2.0):
    """失败自动重试：最多 max_attempts 次，指数退避（2^n * base_delay 秒）。

    返回 (ok, output)；全部失败时 output 为最后一次错误。
    """
    attempts = 0
    last_err = ""
    while attempts < max(max_attempts, 1):
        attempts += 1
        ok, out = fn()
        if ok:
            return True, out
        last_err = out
        if attempts < max(max_attempts, 1):
            time.sleep(base_delay * (2 ** (attempts - 1)))
    return False, f"重试 {attempts} 次仍失败：{last_err}"


def _run_job(job) -> None:
    """执行单个任务（带重试），并落库运行历史。"""
    ok, out = _run_with_retry(lambda: _execute_job(job))
    _record_run(job["id"], "success" if ok else "failed", output=out if ok else "", error="" if ok else out)
    logger.info("[Scheduler] 任务 %s 执行%s: %s", job.get("name"), "成功" if ok else "失败", out)
    
    # v18: 企业级优化任务执行后自动生成报告并提交
    if job.get("job_type") == "enterprise_optimizer" and ok:
        try:
            import subprocess as _sp
            # 1. 生成优化报告（已运行，这里只是确认）
            # 2. Git提交报告
            report_dir = Path(__file__).parent / ".optimizer_reports"
            if report_dir.exists():
                _sp.run(["git", "add", str(report_dir)], cwd=str(PROJECT_DIR), capture_output=True)
                # 3. Git推送
                r = _sp.run(["git", "commit", "-m", f"docs: 自动优化报告 {datetime.now().strftime('%Y-%m-%d %H:%M')}", "--allow-empty"], 
                           cwd=str(PROJECT_DIR), capture_output=True, text=True)
                if r.returncode == 0:
                    _sp.run(["git", "push", "origin", "main"], cwd=str(PROJECT_DIR), capture_output=True, timeout=30)
                    logger.info("[Scheduler] 优化报告已自动提交推送")
        except Exception as e:
            logger.warning(f"[Scheduler] 自动提交失败: {e}")


def _run_scheduler_loop():
    """后台调度循环：每 10 秒检查一次到期任务和通知文件（v18）。"""
    global _scheduler_running
    while _scheduler_running:
        try:
            # 1. 检查数据库中的定时任务
            conn = get_db()
            try:
                jobs = [dict(r) for r in conn.execute("SELECT * FROM scheduler_jobs WHERE enabled=1").fetchall()]
            finally:
                conn.close()

            now = datetime.now()
            for job in jobs:
                # 首次调度：无 next_run 时按 cron 计算
                if not job["next_run"]:
                    next_time = _parse_cron(job["cron_expression"])
                    conn = get_db()
                    try:
                        conn.execute("UPDATE scheduler_jobs SET next_run=? WHERE id=?", (next_time, job["id"]))
                        conn.commit()
                    finally:
                        conn.close()
                    continue
                try:
                    due = datetime.fromisoformat(job["next_run"]) <= now
                except (ValueError, TypeError):
                    due = False
                if due:
                    logger.info(f"[Scheduler] Cron触发任务: {job.get('name')}")
                    _run_job(dict(job))
                    next_time = _parse_cron(job["cron_expression"])
                    conn = get_db()
                    try:
                        conn.execute("UPDATE scheduler_jobs SET next_run=? WHERE id=?", (next_time, job["id"]))
                        conn.commit()
                    finally:
                        conn.close()
            
            # 2. 检查通知文件（v18 企业级优化）
            _check_notification_files()
            
        except Exception as e:
            logger.error(f"[Scheduler] 调度循环异常: {e}")

        time.sleep(10)  # v18: 每10秒检查一次


def _check_notification_files():
    """检查通知文件并自动执行（v18 企业级优化）。"""
    import json as _json
    from pathlib import Path as _Path
    
    try:
        if not NOTIFY_DIR.exists():
            return
        
        # 查找未处理的通知文件
        for f in list(NOTIFY_DIR.glob("*.json")):
            try:
                content = _json.loads(f.read_text())
                job_type = content.get("job_type")
                
                # 只处理企业级优化通知
                if job_type == "enterprise_optimizer":
                    logger.info(f"[Scheduler] 发现通知文件: {f.name}，自动执行优化")
                    # 执行优化
                    from enterprise_optimizer import run_enterprise_optimizer
                    report_path = run_enterprise_optimizer()
                    
                    # 标记为已处理（重命名为.done）
                    done_file = f.with_suffix(".done")
                    try:
                        f.rename(done_file)
                    except Exception:
                        # 如果重命名失败，创建标记文件
                        (f.parent / f"{f.stem}_done").touch()
                        f.unlink(missing_ok=True)
                    
                    logger.info(f"[Scheduler] 通知文件驱动优化完成: {report_path}")
                    
            except Exception as e:
                logger.warning(f"[Scheduler] 处理通知文件失败 {f.name}: {e}")
    except Exception as e:
        logger.error(f"[Scheduler] 检查通知文件异常: {e}")


def create_notification(job_type: str, **kwargs):
    """创建通知文件（v18）。"""
    import json as _json
    from datetime import datetime as _dt
    
    notify_data = {
        "job_type": job_type,
        "created_at": _dt.now().isoformat(),
        **kwargs
    }
    
    filename = f"notify_{_dt.now().strftime('%Y%m%d_%H%M%S')}_{hash(str(notify_data)) % 10000:04d}.json"
    filepath = NOTIFY_DIR / filename
    
    try:
        filepath.write_text(_json.dumps(notify_data, ensure_ascii=False, indent=2))
        logger.info(f"[Scheduler] 创建通知文件: {filepath.name}")
        return str(filepath)
    except Exception as e:
        logger.error(f"[Scheduler] 创建通知文件失败: {e}")
        return None


def start_scheduler():
    """启动后台调度线程（由 main.py 在 lifespan 中调用）。"""
    global _scheduler_running, _scheduler_thread
    if _scheduler_running:
        return
    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_run_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    logger.info("[Scheduler] 后台调度已启动")


def stop_scheduler():
    """停止后台调度线程。"""
    global _scheduler_running
    _scheduler_running = False
    logger.info("[Scheduler] 后台调度已停止")


# ── API 端点 ──────────────────────────────────────────────


@router.get("")
def list_jobs(current_user: dict = Depends(require_auth)):
    """获取当前用户的定时任务列表。"""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM scheduler_jobs WHERE user_id=? ORDER BY created_at DESC",
            (current_user["user_id"],),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("")
def create_job(payload: dict, current_user: dict = Depends(require_auth)):
    """创建定时任务。

    请求体：{"name":"日报","job_type":"report","cron_expression":"0 9 * * *","description":"","config":{}}
    创建时校验 cron 表达式并初始化首次调度时间。
    """
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "任务名称不能为空")
    cron = (payload.get("cron_expression") or "0 9 * * *").strip()
    next_run = _parse_cron(cron)
    if not next_run:
        raise HTTPException(400, "Cron 格式非法，请检查表达式")
    now = datetime.now().isoformat()

    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO scheduler_jobs (user_id, name, description, job_type, cron_expression, config, next_run, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                current_user["user_id"],
                name,
                payload.get("description", ""),
                payload.get("job_type", "report"),
                cron,
                json.dumps(payload.get("config", {})),
                next_run,
                now,
                now,
            ),
        )
        conn.commit()
        job_id = cur.lastrowid
        return {"id": job_id, "name": name, "cron_expression": cron, "next_run": next_run, "created_at": now, "message": "任务创建成功"}
    finally:
        conn.close()


@router.put("/{job_id}")
def update_job(job_id: int, payload: dict, current_user: dict = Depends(require_auth)):
    """更新定时任务。"""
    conn = get_db()
    try:
        job = conn.execute(
            "SELECT * FROM scheduler_jobs WHERE id=? AND user_id=?",
            (job_id, current_user["user_id"]),
        ).fetchone()
        if not job:
            raise HTTPException(404, "任务不存在")

        updates = {}
        for field in ["name", "description", "job_type", "cron_expression", "config", "enabled"]:
            if field in payload:
                val = payload[field]
                if field == "config" and isinstance(val, dict):
                    val = json.dumps(val)
                updates[field] = val
        # cron 变更时重算 next_run；启用时若有 next_run 缺失也补算
        if "cron_expression" in updates:
            next_run = _parse_cron(updates["cron_expression"])
            if not next_run:
                raise HTTPException(400, "操作失败，请稍后重试")
            updates["next_run"] = next_run
        elif updates.get("enabled") == 1 and not job["next_run"]:
            updates["next_run"] = _parse_cron(job["cron_expression"])
        if updates:
            updates["updated_at"] = datetime.now().isoformat()
            set_clause = ", ".join(f"{k}=?" for k in updates)
            conn.execute(
                f"UPDATE scheduler_jobs SET {set_clause} WHERE id=?",
                (*updates.values(), job_id),
            )
            conn.commit()
        return {"message": "更新成功"}
    finally:
        conn.close()


@router.delete("/{job_id}")
def delete_job(job_id: int, current_user: dict = Depends(require_auth)):
    """删除定时任务。"""
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM scheduler_jobs WHERE id=? AND user_id=?",
            (job_id, current_user["user_id"]),
        )
        conn.commit()
        return {"message": "已删除"}
    finally:
        conn.close()


@router.get("/{job_id}/runs")
def list_job_runs(job_id: int, current_user: dict = Depends(require_auth)):
    """获取任务执行历史（最近 50 条：状态/起止时间/输出摘要/错误）。"""
    conn = get_db()
    try:
        job = conn.execute(
            "SELECT id FROM scheduler_jobs WHERE id=? AND user_id=?",
            (job_id, current_user["user_id"]),
        ).fetchone()
        if not job:
            raise HTTPException(404, "任务不存在")
        rows = conn.execute(
            "SELECT * FROM scheduler_runs WHERE job_id=? ORDER BY id DESC LIMIT 50",
            (job_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.post("/{job_id}/trigger")
def trigger_job(job_id: int, current_user: dict = Depends(require_auth)):
    """手动触发一次任务：立即执行（带重试）并落库运行历史，返回真实结果。"""
    conn = get_db()
    try:
        job = conn.execute(
            "SELECT * FROM scheduler_jobs WHERE id=? AND user_id=?",
            (job_id, current_user["user_id"]),
        ).fetchone()
        if not job:
            raise HTTPException(404, "任务不存在")
        job = dict(job)
    finally:
        conn.close()

    _run_job(job)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM scheduler_runs WHERE job_id=? ORDER BY id DESC LIMIT 1",
            (job_id,),
        ).fetchone()
    finally:
        conn.close()
    run = dict(row) if row else {}
    ok = run.get("status") == "success"
    return {
        "message": f"任务「{job['name']}」执行{'成功' if ok else '失败'}",
        "status": run.get("status", ""),
        "output": run.get("output", ""),
        "error": run.get("error", ""),
    }

# ══════════════════════════════════════════════════════════════
# 企业级优化器任务注册（v18.0）
# ══════════════════════════════════════════════════════════════
def _ensure_optimizer_job():
    """确保企业级优化器任务已注册（每小时20分运行）。"""
    conn = get_db()
    try:
        # 检查是否已存在
        row = conn.execute(
            "SELECT id FROM scheduler_jobs WHERE name='企业级智能优化'"
        ).fetchone()
        if row:
            # 更新 cron 表达式为每小时20分
            conn.execute(
                "UPDATE scheduler_jobs SET cron_expression='20 * * * *', enabled=1 WHERE name='企业级智能优化'"
            )
            conn.commit()
            logger.info("✅ 企业级优化器任务已更新: 每小时20分")
        else:
            # 插入新任务
            conn.execute(
                "INSERT INTO scheduler_jobs (user_id, name, description, job_type, cron_expression, enabled) VALUES (?, ?, ?, ?, ?, ?)",
                ("admin", "企业级智能优化", "每小时自动运行，全面提升系统到商用级别", "enterprise_optimizer", "20 * * * *", 1)
            )
            conn.commit()
            logger.info("✅ 企业级优化器任务已注册: 每小时20分")
    finally:
        conn.close()


# 启动时注册
_ensure_optimizer_job()
