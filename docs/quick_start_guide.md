# 🚀 Smart R&D Platform v6.4 — 快速入门指南

## 项目概述

本平台是一个**智能业务编排系统**，利用AI Agent和可视化工具构建自动化工作流。可用于软件开发、数据分析、客户服务等各种场景。

```
前端 (React/Vite) ←→ 后端 (FastAPI/SQLite) ←→ AI Agents (Agno)
       ↑                             ↑
   可视化工作流编辑器           工作流执行引擎
```

---

## 快速启动（开发环境）

### 1. 准备依赖

确保已安装以下软件：
- Python 3.10+ (推荐 3.11+)
- Node.js 18+ (LTS)
- pip, npm

### 2. 配置环境变量

创建 `.env` 文件（位于 `backend/.env`）：

```bash
# AI模型配置
AGNES_API_KEY=你的API密钥
AGNES_API_BASE=https://apihub.agnes-ai.com/v1
MODEL_NAME=agnes-2.0-flash

# 数据库（使用默认即可）
DB_PATH=./platform.db

# 安全设置（开发环境用）
SECRET_KEY=change-this-in-production
DEBUG=true
```

> ⚠️ **生产环境务必修改 SECRET_KEY 并启用认证！**

### 3. 启动后端

```bash
cd backend
pip install -r requirements.txt  # 首次运行需要安装
python3 main.py  # 或 uvicorn main:app --reload
```

访问 http://localhost:8888/docs 查看完整的 REST API 文档（Swagger UI）。

### 4. 启动前端

```bash
cd frontend
npm install  # 首次运行需要安装
npm run dev
```

访问 http://localhost:5173 进入应用界面。

---

## 核心功能介绍

### 🔧 工作流编排（Workflows Page）

这是平台的核心功能入口，提供可视化拖拽式工作流设计器：

1. **添加节点**：从左侧库选择节点类型（LLM/文件/API/技能/决策），拖到画布
2. **配置属性**：点击节点右侧面板，填写该节点特有的参数
3. **连接流程**：拖拽连线建立节点间的数据流向和顺序依赖
4. **注册保存**：输入工作流名称，点击"注册工作流"保存定义
5. **执行测试**：点击"运行工作流"，查看实时执行状态和结果

![示意图：左侧节点库，中间画布带多个节点和连线，右侧配置面板](workflow-editor-demo.png) *示意*

### 📡 API端点参考

所有工作流相关API都在 `/api/workflows/` 路径下：

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | `/api/workflows/templates` | 获取预置模板列表 |
| GET | `/api/workflows/node-types` | 获取节点类型元数据（供前端使用） |
| POST | `/api/workflows/register` | 注册新工作流定义 |
| GET | `/api/workflows/{id}/definition` | 获取工作流定义详情 |
| DELETE | `/api/workflows/{id}/unregister` | 卸载工作流定义 |
| POST | `/api/workflows/run` | 启动新工作流实例 |
| GET | `/api/workflows/instances` | 列出最近执行的实例 |
| GET | `/api/workflows/{instance_id}` | 获取实例详细状态 |

**示例：注册工作流**

```json
POST /api/workflows/register

{
  "workflow_id": "my_first_workflow",
  "name": "我的第一个工作流",
  "nodes": [
    {
      "type": "llm_node",
      "node_id": "step1",
      "name": "分析任务",
      "prompt_template": "请分析此文本: {{input_text}}",
      "model": "agnes-2.0-flash"
    },
    {
      "type": "file_node",
      "node_id": "step2",
      "operation_type": "write",
      "path": "/tmp/result_{timestamp}.txt",
      "content": "{step1.output}"
    }
  ]
}
```

响应：
```json
{
  "success": true,
  "workflow_id": "my_first_workflow",
  "name": "我的第一个工作流",
  "node_count": 2,
  "message": "Workflow 'my_first_workflow' has been registered successfully..."
}
```

---

## 使用场景示例

### 场景一：自动生成PRD文档

**工作流步骤：**
1. **LLM节点** - 收集用户原始需求描述
2. **LLM节点** - 根据需求生成结构化PRD内容
3. **文件节点** - 将生成的PRD保存到文件 `/prd_*.md`
4. **API节点** - 发送邮件通知团队负责人完成

**配置要点**：在LLM节点中编写详细的Prompt模板，指定输出格式（JSON/Markdown等）。

### 场景二：数据采集与处理流水线

**工作流步骤：**
1. **API节点** - 从外部REST API获取原始数据
2. **Skill节点** - 调用自定义Python脚本清洗数据
3. **LLM节点** - 对清洗后的数据进行分析和摘要
4. **文件节点** - 保存分析报告为CSV/JSON文件

**配置要点**：Skill节点需要预先写好Python脚本放在 `skills/` 目录下，包含可导出的函数。

---

## 扩展指南

### 添加新的节点类型

要在平台中添加全新的节点类型：

1. 在 `backend/nodes/types/` 创建新文件 `your_node_type.py`
2. 继承 `BusinessNode` 基类，实现 `execute(context)` 方法
3. 在 `nodes/types/__init__.py` 导出该类
4. （可选）在 `workflows.py` 的 `list_node_types_metadata()` 中添加前端配置信息

示例框架：

```python
from nodes.base import BusinessNode, NodeResult

class YourCustomNode(BusinessNode):
    def __init__(self, node_id, name, custom_param1):
        super().__init__(node_id, name, "Your custom node description")
        self.custom_param1 = custom_param1
    
    def execute(self, context):
        # 从上下文中读取输入
        current_input = context.get("current_node_input", {})
        
        # 执行业务逻辑...
        result_data = f"Processed with param={self.custom_param1}"
        
        return NodeResult.success(
            output={"result": result_data},
            messages=[f"{self.name} completed"]
        )
```

### 预置工作流模板

在 `workflows.py` 中的 `get_workflow_templates()` 函数里添加常用场景的预设模板，方便用户快速开始：

```python
def get_preset_templates() -> List[Dict[str, Any]]:
    templates = []
    
    # PRD生成模板
    prd_template = create_prd_workflow_template()
    templates.append({
        "id": "prd_gen_v1",
        "name": "PRD自动生成",
        "description": "从自然语言需求到PRD文档的完整流程",
        "nodes": prd_template["nodes"]
    })
    
    return templates
```

---

## 常见问题解答

**Q: 如何调试工作中的节点？**  
A: 检查后端日志（`/tmp/backend.log`），每个节点执行都会记录输入输出和错误信息。

**Q: 工作流执行超时怎么办？**  
A: 在APINode中调整timeout参数；在LLM节点中简化prompt模板减少计算量。

**Q: 如何将工作流持久化到数据库？**  
A: 当前内存存储适合开发/测试。要持久化，需扩展`WorkflowEngine`将定义写入SQL表，实现反序列化还原。

**Q: 前端页面加载后空白？**  
A: 检查浏览器控制台是否有CORS错误；确保后端已在8888端口运行且前端代理配置正确（vite.config.js）。

---

## 下一步建议

完成以下任务可将原型提升为可用产品：

1. [ ] **添加认证和权限控制**（JWT/OAuth2 + RBAC）
2. [ ] **持久化工作流定义**（替代内存存储）
3. [ ] **增加错误处理和重试机制**
4. [ ] **完善前端工作流编辑器的交互体验**
5. [ ] **添加监控仪表板和执行历史查询**
6. [ ] **编写完整用户文档和操作指南**
7. [ ] **创建Docker容器化部署方案**
8. [ ] **实现工作流的版本控制和回滚**

---

**版本**: v6.4  
**最后更新**: 2026年7月  
**联系**: support@example.com  
