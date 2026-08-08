# 迭代四：沙箱预置服务去重 + 服务控制台（Redis Key 操作 / SQL 查询）

> 依据用户实测反馈的两点问题：① 沙箱「预置服务」有重复项；② 缺少直接进服务操作的入口（Redis 查看/修改 Key、MySQL 查数据）。

## 一、问题根因

### 问题 1：预置服务重复
- 前端 `SandboxPage.jsx` 硬编码 `PRESET_SERVICES`（6 项：python/node/go/postgres/redis/mysql）
- 后端 `SERVICE_TEMPLATES`（6 项：redis/postgres/mysql/rabbitmq/nginx/mongo）
- 两处定义在 services tab **同时渲染** → postgres、redis、mysql 各出现 2 次

### 问题 2：无服务操作入口
- 运行中的 redis/mysql 容器只能「访问」端口，无法查看 Key、执行查询
- 服务卡片仅展示，不能直接创建项目

## 二、改动清单

| 文件 | 改动 |
|---|---|
| `backend/sandbox.py` | `SERVICE_TEMPLATES` 合并为 9 项唯一数据源（+python/node/go）；`_run_cmd` 补 `stdin=DEVNULL`（防 SIGTTIN）；新增 `exec_command()`（podman exec 进容器，兼容 deploy 前缀容器名） |
| `backend/main.py` | 新增 `POST /api/sandbox/projects/{id}/redis/command`：Redis 安全白名单 47 个数据命令（禁 FLUSHALL/FLUSHDB/SHUTDOWN/CONFIG/EVAL 等），argv 传参防注入；新增 `POST /api/sandbox/projects/{id}/sql/query`：只读白名单（SELECT/SHOW/DESC/DESCRIBE/EXPLAIN）+ 单语句限制，凭据从项目 config.env 动态读取（不硬编码），mysql/psql 输出解析为结构化表格 |
| `backend/common/models.py` | `SandboxRedisCommandRequest` / `SandboxSqlQueryRequest` |
| `backend/main.py`（第二轮扩展） | 新增 `POST /api/sandbox/projects/{id}/mongo/command`：mongosh 只读白名单（正则匹配 + 禁词双重拦截，禁 insert/update/delete/drop/create/aggregate/$out 等）；新增 `POST /api/sandbox/projects/{id}/rabbitmq/command`：rabbitmqctl 只读白名单（status/list_*）+ 参数格式校验；新增 `POST /api/sandbox/projects/{id}/nginx/command`：仅 nginx -v/-V/-t/-T；新增 `_sandbox_project_env()` 统一读取项目凭据（SQL/Mongo 复用） |
| `backend/sandbox.py`（第二轮） | `exec_command` 成功时合并 stderr 到输出（nginx -v/-t 结果写 stderr，否则丢失）；SQL 端点同步过滤 mysql 凭据警告行防表格污染 |
| `frontend/src/pages/SandboxPage.jsx`（第二轮） | `serviceTypeOf` 扩展 6 种中间件；`CONSOLE_META` 配置表驱动控制台（端点/说明/快捷命令/默认输入/徽标色）；`ServiceConsoleModal` 泛化为 3 种渲染模式：redis 智能（key 列表点击 GET）/ sql 表格 / raw 文本（mongo/rabbitmq/nginx） |
| `frontend/src/pages/SandboxPage.jsx` | 删除前端硬编码 `PRESET_SERVICES`，services tab 改为单一数据源渲染（9 卡片无重复）+ 每卡片「一键创建项目」+「支持控制台」标记；项目卡片新增数据库控制台按钮（运行中的 redis/mysql/postgres 显示）；新增 `ServiceConsoleModal`（Redis 命令台：快捷命令/Key 列表点击 GET/复制；SQL 台：结果表格渲染）；新增 `handleQuickCreate` 模板一键建项目 |

## 三、实测证据

### API 层（curl 实测）
- 服务列表：9 项、`dup: 无重复`
- Redis 全链路：`PING→PONG`、`SET user:1 hello→OK`、`GET user:1→hello`、`KEYS *→user:1`、`DEL user:1→1`
- 安全拦截：`FLUSHALL`→400「不在安全白名单内」；`DELETE FROM users`→400「仅支持只读查询」；`SELECT 1; DROP TABLE users`→400「一次只能执行一条 SQL」；非数据库项目执行 SQL→400
- MySQL 全链路（真实容器）：`SELECT VERSION()→8.4.11`、`SHOW DATABASES→5 库`、真实表查询返回结构化表格（表头+4 行完整）、`DESC platform.users` 6 列解析正确
- 凭据动态读取：部署容器密码 `platform123`（非默认 password）经 config.env 读取成功

### 浏览器回归（子代理实测，10 项全过）
- 预置服务 9 卡片无重复（DOM 计数 9/9/无重复）
- Redis 控制台：PING/SET/GET/DEL/KEYS 空态全部正确，弹窗不崩溃
- MySQL 控制台：表格展示表头+4 行（首行未被吞）、多语句拦截提示、多列表格正常
- Console：无 JS 异常，唯一 error 为多语句 SQL 被拦截的预期 400

### 回归
- `pytest tests/`：**388 passed**（196s）
- `vite build`：成功（12.6s，仅既有 chunk 体积警告）

## 四、过程中发现并修复的真实 Bug（浏览器实测抓到）

1. **【严重/阻断】** `SandboxPage.jsx` 控制台弹窗使用未定义变量 `isExecuting`（应为 `executing`）→ 弹窗渲染即崩溃（ReferenceError）。浏览器复现 2 次 → 修复 → 回归通过。
2. **【中】** SQL 解析：`mysql -N` 跳过列名导致首行数据被解析器当表头吞掉（4 行只剩 3 行）。改为非交互 `-e` 默认表头模式（psql 同步去掉 `-t`），回归确认 4 行完整。

## 五、遗留说明
- `SHOW TABLES;` 在未设默认库的容器上会报「No database selected」（MySQL 原生行为），前端提示用户用 `information_schema` 或 `库名.表` 写法

## 六、第二轮扩展：全部 6 种预制中间件支持命令控制台（用户反馈）

### 支持矩阵（全部实测）

| 中间件 | 端点 | 允许命令 | 实测结果（真实容器） |
|---|---|---|---|
| Redis | `redis/command` | 47 个数据命令白名单 | PING→PONG、SET/GET/DEL、KEYS ✅ |
| MySQL | `sql/query` | SELECT/SHOW/DESC/EXPLAIN | VERSION 8.4.11、5 库、真实表 4 行 ✅ |
| PostgreSQL | `sql/query` | SELECT/SHOW/DESC/EXPLAIN | 连接串传凭据（防交互阻塞）✅ |
| MongoDB | `mongo/command` | show dbs / use db / find / stats 等只读 | show dbs 3 库、db.stats()、getCollectionNames ✅ |
| RabbitMQ | `rabbitmq/command` | status / list_queues / list_users 等只读 | status 节点信息、list_users ✅ |
| Nginx | `nginx/command` | -v / -V / -t / -T | 版本 1.31.3、syntax ok ✅ |

### 安全拦截实测（全部 400）
- Redis：FLUSHALL；SQL：DELETE / 多语句 / DROP；Mongo：drop()、aggregate($out)、任意 JS（print(process.env.HOME)）；RabbitMQ：purge_queue、参数注入（`list_queues name; rm -rf /`）；Nginx：-s reload、`rm -rf /`

### 本轮发现并修复的真实 Bug
1. **nginx -v / -t 输出丢失**：结果写 stderr，`exec_command` 只收 stdout → 输出为空。修复：成功时合并 stderr（同时 SQL 端点过滤 mysql 凭据警告行，防止表格首行污染），回归确认 `nginx version: nginx/1.31.3` 与表格解析正常。

### 浏览器回归（子代理，7 项全过）
- 预置服务 6 个中间件卡片均带「支持控制台」徽标（DOM 样式断言验证）
- Redis 弹窗 PING→PONG；Nginx 弹窗（青色徽标/说明/快捷按钮/默认输入）正常，nginx -v / -t 输出正确，-s reload 被拦截
- Console 无 JS 异常，仅白名单拦截的预期 400 日志

### 回归
- `pytest tests/`：**388 passed**（187s）；`vite build` 成功
