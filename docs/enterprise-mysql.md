# 企业级 MySQL 部署指南（规划中）

> ⚠️ 状态说明：当前 `common/db.py` 为纯 SQLite 实现，尚未支持 MySQL 引擎。
> 本文档为**规划蓝图**，数据库已就绪（独立实例 code_platform），驱动层适配待后续实现。

默认平台使用 SQLite（单文件，零配置，适合单机/开发）。企业级部署建议迁移到
MySQL，获得并发写入、行级锁、在线备份等能力。

## 一、本地 MySQL 实例（已就绪）

本机 MySQL（8.0+）运行于 `127.0.0.1:3306`，已创建**独立数据库**（与
dap-agent 等其他项目完全隔离）：

| 项 | 值 |
|----|----|
| 数据库名 | `code_platform` |
| 专用用户 | `code_platform` @ `localhost` |
| 密码 | 见 `.env`（`DATABASE_URL`） |
| 字符集 | `utf8mb4`（支持中文 + emoji） |
| 权限 | 仅 `code_platform.*`（最小权限） |

## 二、启用 MySQL 连接

在 `backend/.env` 设置：

```bash
DB_ENGINE=mysql
DATABASE_URL=mysql+pymysql://code_platform:密码@127.0.0.1:3306/code_platform?charset=utf8mb4
```

安装驱动：

```bash
pip install pymysql cryptography
```

## 三、表结构迁移

平台启动时会对 MySQL 执行与 SQLite 相同的 `CREATE TABLE IF NOT EXISTS`，
首次启动自动建表。已有 SQLite 数据迁移：

```bash
# 使用 mysqldump 导出 SQLite 需先转标准 SQL，或使用工具：
python scripts/migrate_sqlite_to_mysql.py
```

## 四、验证

```bash
mysql -ucode_platform -p -e "USE code_platform; SHOW TABLES;"
```

## 五、注意事项

- 密码含特殊字符时在 URL 中需 URL 编码（`@` → `%40`，`#` → `%23`）
- 生产环境建议使用独立 MySQL 服务器 + 主从复制 + 每日备份
- 当前代码的 SQL 以 SQLite 方言为主（`?` 占位符），MySQL 模式下 `common/db.py`
  自动切换到 `%s` 占位符（`mysql` 引擎检测）
