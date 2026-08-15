# SQLite 生产环境部署指南

> 适用于小团智能平台使用 SQLite 作为生产数据库的场景。

## 现状

当前 `common/db.py` 已启用以下 SQLite 优化：

| 配置项 | 值 | 作用 |
|---|---|---|
| `journal_mode` | `WAL` | 写前日志 → 读写不互锁，支持并发读 |
| `busy_timeout` | `30000ms` | 写冲突时等待最多 30s，避免 `database is locked` |
| `foreign_keys` | `ON` | 强制外键约束 |
| 连接复用 | 线程级池 | 减少创建/关闭开销 |

## 适用规模

- **推荐**：< 5 并发用户，每日 < 1000 次写操作
- **可用**：10~20 并发用户，轻量读多写少场景
- **不适用**：高并发写入、多进程写入（如 Kubernetes 多副本无共享锁）

## 生产调优建议

### 1. 确保 WAL 模式持久化

WAL 文件 (`platform.db-wal`) 需纳入备份策略：

```bash
# 备份时同时包含 WAL 文件
tar czf backup-$(date +%Y%m%d).tar.gz \
  platform.db platform.db-wal platform.db-shm
```

### 2. 增加超时与缓存（通过环境变量）

```bash
# .env 中追加
DB_BUSY_TIMEOUT=60000       # 写冲突等待 60s（默认 30s）
DB_CACHE_SIZE=-64000        # 页缓存 64MB（默认 -2000 页 ≈ 20MB）
DB_MMAP_SIZE=-134217728     # 内存映射 128MB
```

### 3. 定期 VACUUM 维护

WAL 模式下 `.db-wal` 文件不会自动截断，建议每周执行一次：

```python
# 可在管理员后台添加定时任务
import sqlite3
conn = sqlite3.connect("platform.db")
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
conn.execute("VACUUM")
conn.close()
```

### 4. 磁盘监控

健康检查端点 `/api/health` 已包含磁盘空间检测：
- `< 5GB` 警告
- `< 2GB` 严重（status=degraded）

建议在监控系统中订阅该端点的 `disk_status` 字段。

## 何时迁移到 PostgreSQL

出现以下情况时，应迁移至 PostgreSQL（项目已支持）：

| 信号 | 说明 |
|---|---|
| 频繁 `database is locked` | 即使 busy_timeout=30s 仍不够 |
| 多进程部署 | Kubernetes/Docker Swarm 多副本写入冲突 |
| 并发用户 > 20 | 写锁竞争成为瓶颈 |
| 需要高级特性 | JSON 查询、全文搜索、行级锁 |

迁移步骤：
1. 设置 `ASYNC_PG_URL=postgresql://user:pass@host:5432/xiaotuan` 环境变量
2. 平台启动时自动检测并启用异步连接池
3. 执行数据迁移：`sqlite3 platform.db ".dump" \| psql ASYNC_PG_URL`

## 参考

- [SQLite Concurrent Access](https://www.sqlite.org/sharedcache.html)
- [SQLite WAL Mode](https://www.sqlite.org/wal.html)
- [SQLite Tuning](https://www.sqlite.org/tuning.html)
