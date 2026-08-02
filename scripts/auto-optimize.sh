#!/bin/bash
# 小团智能平台自动优化脚本
# 用于定时任务，持续改进平台

set -e

echo "🚀 小团智能平台自动优化开始 - $(date)"
echo "=========================================="

PROJECT_DIR="/Users/yanping.ma/PycharmProjects/Code-Platform"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# 1. 检查后端语法
echo ""
echo "【1】检查后端代码..."
cd "$BACKEND_DIR"
python3 -c "import ast; ast.parse(open('main.py').read())" && echo "✅ main.py 语法正确" || echo "❌ main.py 语法错误"

# 2. 检查数据库状态
echo ""
echo "【2】检查数据库状态..."
sqlite3 "$BACKEND_DIR/platform.db" "SELECT 'Skills: ' || COUNT(*) FROM skills" 2>/dev/null || echo "⚠️ Skills 表不存在"
sqlite3 "$BACKEND_DIR/platform.db" "SELECT 'Agents: ' || COUNT(*) FROM agents" 2>/dev/null || echo "⚠️ Agents 表不存在"
sqlite3 "$BACKEND_DIR/platform.db" "SELECT 'Knowledge Bases: ' || COUNT(*) FROM knowledge_bases" 2>/dev/null || echo "⚠️ KB 表不存在"

# 3. 同步 Skills 到文件系统
echo ""
echo "【3】同步 Skills 到文件系统..."
python3 -c "
import sqlite3, os
conn = sqlite3.connect('$BACKEND_DIR/platform.db')
skills = conn.execute('SELECT id, name, content FROM skills WHERE active=1').fetchall()
skills_dir = '$BACKEND_DIR/skills_files'
os.makedirs(skills_dir, exist_ok=True)
for s in skills:
    skill_dir = os.path.join(skills_dir, s[0])
    os.makedirs(skill_dir, exist_ok=True)
    skill_md = os.path.join(skill_dir, 'SKILL.md')
    with open(skill_md, 'w', encoding='utf-8') as f:
        f.write(s[2] if s[2] else f'# {s[1]}\n\n## Description\n{s[1]}\n')
print(f'✅ 同步 {len(skills)} 个 Skills 到文件系统')
conn.close()
"

# 4. 检查前端构建
echo ""
echo "【4】检查前端构建..."
if [ -f "$FRONTEND_DIR/dist/index.html" ]; then
    echo "✅ 前端构建文件存在"
else
    echo "⚠️ 前端需要重新构建"
fi

# 5. 检查后端服务状态
echo ""
echo "【5】检查后端服务..."
if curl -s http://localhost:8888/api/health > /dev/null 2>&1; then
    echo "✅ 后端服务运行中"
else
    echo "⚠️ 后端服务未运行"
fi

# 6. 检查前端服务状态
echo ""
echo "【6】检查前端服务..."
if curl -s http://localhost:5173 > /dev/null 2>&1; then
    echo "✅ 前端服务运行中"
else
    echo "⚠️ 前端服务未运行"
fi

# 7. 生成优化报告
echo ""
echo "【7】生成优化报告..."
REPORT_FILE="$BACKEND_DIR/optimization_$(date +%Y%m%d_%H%M%S).md"
cat > "$REPORT_FILE" << 'EOF'
# 小团智能平台优化报告

## 系统状态
- 检查时间: $(date)
- 后端状态: [检查中]
- 前端状态: [检查中]

## 数据状态
- Skills: [统计中]
- Agents: [统计中]
- Knowledge Bases: [统计中]

## 建议优化项
1. Skills 文件编辑器增强
2. 知识库搜索功能优化
3. Agent 调试日志完善
4. 沙箱运行环境搭建
5. 项目管理功能完善
6. 成果仓库功能完善

## 下一步计划
- [ ] 完善 Skills 管理界面
- [ ] 添加知识库文件上传
- [ ] 实现 Agent 调试日志
- [ ] 搭建沙箱运行环境
- [ ] 优化 UI/UX 体验
EOF

echo "✅ 优化报告已生成: $REPORT_FILE"

echo ""
echo "=========================================="
echo "🎉 自动优化完成"
echo ""
