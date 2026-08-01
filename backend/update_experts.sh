#!/bin/bash
python3 -c "
import sqlite3, json, os

DB_PATH = 'platform.db'
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
now = '2026-07-30T12:00:00Z'

# Skills
cur.execute('UPDATE skills SET active=0 WHERE name IN (\"test\",\"test_skill\",\"代码规范\")')
print('Deactivated old skills:', cur.rowcount)

skills = [
    ('SKILL-DEV-001', '高级代码审查与重构', '深度代码分析，识别性能瓶颈、安全漏洞和架构缺陷，提供重构建议。支持静态分析工具链集成。', json.dumps(['后端开发','系统优化','代码质量'])),
    ('SKILL-QA-001', '全栈测试设计与自动化', '编写单元测试、集成测试和端到端测试用例，设计自动化测试框架，覆盖率提升至95%+。含JUnit/Pytest/Selenium模板。', json.dumps(['QA','DevOps','CI/CD'])),
    ('SKILL-PM-001', '产品经理需求分析与PRD撰写', '精通用户需求调研、竞品分析、功能拆解，输出结构化PRD文档及原型说明，推动跨团队协作。含敏捷冲刺规划模板。', json.dumps(['产品规划','需求工程'])),
    ('SKILL-UI-001', 'UI/UX交互设计与可视化', '主导用户研究、信息架构、视觉设计和原型制作，输出高保真界面稿和设计规范，提升用户体验满意度。支持Figma/Sketch输出。', json.dumps(['UX/UI设计','前端表现'])),
    ('SKILL-ARCH-001', '系统架构设计与选型', '承担微服务拆分、API网关设计、数据一致性方案和云原生架构选型，保障系统可扩展性与稳定性。含架构图模板与技术决策日志。', json.dumps(['系统设计','架构治理'])),
    ('SKILL-PMGT-001', '项目管理与风险控制', '制定项目计划、资源分配、进度跟踪与风险管理，运用甘特图/燃尽图等工具保障交付质量与时效。含PMP最佳实践融合。', json.dumps(['项目统筹','敏捷管理'])),
    ('SKILL-DBA-001', '数据库管理与SQL优化', '负责数据库建模、索引优化、慢查询分析及高可用部署，保障数据完整性与查询性能。支持MySQL/PostgreSQL主流引擎。', json.dumps(['数据库运维','性能调优'])),
    ('SKILL-SRE-001', '站点可靠性与运维自动化', '构建监控告警体系、制定SLI/SLO目标、实现故障自愈与容量弹性伸缩，保障服务高可用性。含Prometheus/Grafana配置指南。', json.dumps(['SRE','DevOps','运维自动化']))
]

for s in skills:
    cur.execute(\"INSERT OR REPLACE INTO skills (id,name,description,content,created_at,active) VALUES?,?,?,?,?,?\", (s[0], s[1], s[2], s[3], now, 1))
    print('  Skill:', s[1])

# Knowledge Bases
cur.execute('UPDATE knowledge_bases SET active=0 WHERE name IN (\"test\",\"测试知识库\",\"test123\")')
print('Deactivated old KBs:', cur.rowcount)

kbs = [
    ('KB-POLICY-001', '企业研发合规与安全策略', 'Policy Docs', '内部法务/安全委员会联合编制，含GDPR/ISO27001对齐条款。Q1更新 + 事件驱动后更新。', '全员可见（部分敏感字段脱敏）'),
    ('KB-CODEBASE-002', '核心业务代码规范与最佳实践', 'Code Standards', '架构组+资深工程师贡献，包含命名规范、异常处理、日志标准等。每月更新一次。', '研发组成员可见'),
    ('KB-API-REF-003', '开放平台API技术参考手册', 'API Reference', '后端团队维护 + Auto-generated from Swagger。每次版本迭代同步，附带请求示例、错误码说明、速率限制。', '公开+内部双通道'),
    ('KB-FAQ-CUST-004', '客户常见问题解答库', 'FAQ', 'CS团队收集+产品线输入，每季度复审+实时补充，支持多语言版本切换。', '客服+销售优先可见'),
    ('KB-HANDLING-005', '突发事件应急响应流程手册', 'Emergency Procedure', 'SRE+运营联合编制，含Contact List、Checklist、回滚脚本。重大事件后立即更新。', '授权人员仅见'),
    ('KB-INTERNAL-WIKI-006', '公司内部协作知识图谱', 'Internal Wiki', 'Notion/Confluence导出归档，持续增量存储，按RBAC分级开放，整合会议纪要、项目复盘、制度文件。', '按RBAC分级开放')
]

for k in kbs:
    cur.execute(\"INSERT OR REPLACE INTO knowledge_bases (id,name,type,path,url,filter,created_at,active) VALUES?,?,?,?,?,?,?,?\", (k[0], k[1], k[2], k[3], '', k[4], now, 1))
    print('  KB:', k[1])

conn.commit()
conn.close()
print('\\nSUCCESS: Expert Skills and KBs fully replaced!')
"
