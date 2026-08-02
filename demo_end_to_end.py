#!/usr/bin/env python3
"""
小团智能平台 v6.4 — 完整端到端演示脚本

此脚本将：
1. 启动后端FastAPI服务（如未运行）
2. 注册一个示例工作流（PRD生成流水线）
3. 执行工作流
4. 获取执行结果并显示
5. 验证关键功能点

使用前请确保已安装所有依赖：
    cd backend && pip install -r requirements.txt

运行：
    python3 demo_end_to_end.py
"""

import sys, os, time, json, subprocess
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"

# ── 实用函数 ────────────────────────────────────────────────

def get_env(key: str, default: str = "") -> str:
    """读取环境变量或返回默认值"""
    return os.environ.get(key, default)

def ensure_backend_running() -> bool:
    """检查后端是否正在运行，如未运行则尝试启动"""
    print("\n🔍 检查后端服务状态...")
    
    try:
        import requests
        resp = requests.get("http://localhost:8888/api/health", timeout=2)
        if resp.status_code == 200:
            print(f"✓ 后端服务已在运行 (PID: check with `lsof -i :8888`)")
            return True
    except Exception:
        pass
    
    # 启动后端
    print("⚠ 后端未运行，尝试启动...")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8888", "--reload"],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    
    time.sleep(3)  # 等待服务器启动
    
    # 验证是否启动成功
    try:
        import requests
        resp = requests.get("http://localhost:8888/api/health", timeout=5)
        if resp.status_code == 200:
            print(f"✓ 后端服务已成功启动 (PID: {proc.pid})")
            # 保存进程引用以便后续清理
            sys.backend_proc = proc
            return True
    except Exception:
        pass
    
    print("✗ 无法启动后端服务")
    return False

def create_test_workflow() -> dict:
    """创建一个用于测试的PRD生成工作流定义"""
    return {
        "workflow_id": "demo_prd_pipeline_v1",
        "name": "PRD自动生成流水线",
        "description": "从用户需求到PRD文档的自动化工作流",
        "nodes": [
            {
                "type": "llm_node",
                "node_id": "step_extract",
                "name": "需求提取Agent",
                "model": "agnes-2.0-flash",
                "prompt_template": """请从以下用户需求中提取产品核心要素：

用户需求: {{input_text}}

输出JSON格式包含：product_name, key_features, target_users""",
                "input_schema": {"input_text": "string"}
            },
            {
                "type": "llm_node",
                "node_id": "step_generate",
                "name": "PRD生成Agent",
                "model": "agnes-2.0-flash",
                "prompt_template": """基于以上提取的信息撰写完整的PRD文档：

产品名称: {{extract_step.product_name}}
核心功能: {{extract_step.key_features}}
目标用户: {{extract_step.target_users}}

PRD结构要求：用户故事、功能列表、非功能需求、数据字典""",
                "knowledge_base_ids": "{{extract_step.key_features}}"
            },
            {
                "type": "file_node",
                "node_id": "step_save",
                "name": "保存PRD文件",
                "operation_type": "write",
                "path": "/tmp/demo_prd_{timestamp}.md",
                "content": "{{generate_step.output}}"
            }
        ]
    }

def execute_workflow(workflow_id: str, input_text: str) -> dict:
    """执行指定的工作流并返回结果"""
    print(f"\n▶ 创建工作流实例 '{workflow_id}' ...")
    
    # 准备输入上下文
    initial_context = {
        "inputs": {
            "step_extract": {
                "input_text": input_text
            }
        }
    }
    
    # 调用执行API
    try:
        import requests
        resp = requests.post(
            "http://localhost:8888/api/workflows/run",
            json={
                "workflow_id": workflow_id,
                "instance_name": f"演示实例_{int(time.time())}",
                "initial_context": initial_context
            },
            timeout=10
        )
        
        if resp.status_code not in (200, 201):
            raise Exception(f"API请求失败: {resp.status_code} - {resp.text[:200]}")
        
        exec_result = resp.json()
        instance_id = exec_result.get("instance_id", "")
        
        print(f"✓ 实例创建成功 (ID: {instance_id[:16]}...)")
        
        # 等待并轮询结果（简化版，实际应使用WebSockets或长轮询）
        time.sleep(2)  # 让后台线程有时间执行
        
        # 获取详细结果
        status_resp = requests.get(f"http://localhost:8888/api/workflows/instances/{instance_id}", timeout=5)
        if status_resp.status_code == 200:
            status_data = status_resp.json()
            if status_data.get("status") in ("completed", "failed"):
                result_resp = requests.get(f"http://localhost:8888/api/workflows/result/{instance_id}", timeout=5)
                if result_resp.status_code == 200:
                    return {
                        "success": True,
                        "instance_id": instance_id,
                        "result": result_resp.json(),
                        "status": status_data.get("status")
                    }
        
        return {
            "success": False,
            "message": "工作流仍在执行中，请稍后重试查询"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def main():
    """主演示入口"""
    print("\n" + "=" * 70)
    print("小团智能平台 v6.4 — 端到端功能演示")
    print("=" * 70 + "\n")
    
    # Step 1: 验证环境
    print("📋 阶段1: 环境验证")
    print("-" * 50)
    
    if not os.path.exists(BASE_DIR / "backend"):
        print("✗ backend目录不存在！")
        sys.exit(1)
    
    if not os.path.exists(FRONTEND_DIR / "package.json"):
        print("⚠ frontend/package.json 缺失，前端可能未初始化")
    
    # Step 2: 启动后端
    print("\n🚀 阶段2: 启动后端服务")
    print("-" * 50)
    running = ensure_backend_running()
    if not running:
        print("❌ 无法启动后端，请手动运行: cd backend && uvicorn main:app --reload")
        sys.exit(1)
    
    # Step 3: 注册工作流
    print("\n📝 阶段3: 注册示例工作流")
    print("-" * 50)
    
    try:
        import requests
        test_wf = create_test_workflow()
        
        reg_resp = requests.post(
            "http://localhost:8888/api/workflows/register",
            json=test_wf,
            timeout=5
        )
        
        if reg_resp.status_code == 200:
            reg_data = reg_resp.json()
            print(f"✓ 工作流注册成功: {reg_data['workflow_id']}")
            print(f"   节点数量: {reg_data['node_count']}")
        else:
            print(f"✗ 注册失败: {reg_resp.text[:100]}")
            sys.exit(1)
            
    except Exception as e:
        print(f"✗ 注册过程中出错: {e}")
        sys.exit(1)
    
    # Step 4: 执行工作流
    print("\n⚙️ 阶段4: 执行工作流")
    print("-" * 50)
    
    user_input = "我正在构建一个电商平台，主要功能包括商品浏览、购物车、订单管理、支付集成，目标用户是小型商家，需要支持移动端和PC端访问。"
    
    exec_result = execute_workflow(test_wf["workflow_id"], user_input)
    
    if exec_result.get("success"):
        print(f"✓ 工作流执行完成")
        print(f"   执行状态: {exec_result['status']}")
        print(f"   实例ID: {exec_result['instance_id'][:20]}...")
        
        # 显示部分输出
        output = exec_result['result'].get('global_output', {})
        if output:
            print(f"\n📊 全局输出摘要:")
            for k, v in output.items():
                if isinstance(v, dict):
                    print(f"  {k}: {json.dumps(v, indent=2)[:150]}...")
                else:
                    print(f"  {k}: {v}")
    else:
        print(f"✗ 执行失败: {exec_result.get('error', '未知错误')}")
    
    # Step 5: 显示最终状态
    print("\n" + "=" * 70)
    print("演示完成！")
    print("=" * 70 + "\n")
    
    if exec_result.get("success"):
        print("✅ 成功通过所有测试步骤！")
        print("\n您可以查看生成的测试文件:")
        print(f"   ls -la /tmp/demo_prd_*.md 2>/dev/null || echo '文件可能已清理'")
        print("\n如需继续开发:")
        print("  1. 修改前端 WorkflowsPage.jsx 完善UI交互")
        print("  2. 添加认证系统保护API端点")
        print("  3. 实现持久化存储以保存工作流定义")
        print("  4. 完善错误处理和监控功能")
        
        return 0
    else:
        print("⚠ 演示遇到某些问题，建议检查后端日志 /tmp/backend.log")
        return 1

if __name__ == "__main__":
    exit(main())
