#!/usr/bin/env python3
"""智能研发平台 v6.0 — SQLite持久化 + Agno Agent"""

import os, time, json, sqlite3, logging, importlib
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agno.agent import Agent
from agno.team import Team
from agno.workflow import Workflow
from agno.models.openai import OpenAIChat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
AGNES_API_KEY = os.environ.get("AGNES_API_KEY", "")
AGNES_API_BASE = os.environ.get("AGNES_API_BASE", "https://apihub.agnes-ai.com/v1")
MODEL_NAME = os.environ.get("MODEL_NAME", "agnes-2.0-flash")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "platform.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
            instructions TEXT DEFAULT '', model TEXT DEFAULT 'agnes-2.0-flash',
            enable_memory INTEGER DEFAULT 0, enable_reasoning INTEGER DEFAULT 0,
            tools TEXT DEFAULT '[]', knowledge_base_id TEXT, skills TEXT DEFAULT '[]',
            created_at TEXT, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS teams (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
            mode TEXT DEFAULT 'coordinate', members TEXT DEFAULT '[]',
            instructions TEXT DEFAULT '', respond_directly INTEGER DEFAULT 0,
            created_at TEXT, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
            steps TEXT DEFAULT '[]', created_at TEXT, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, task_type TEXT,
            input_length INTEGER, output_length INTEGER, response_time REAL, success INTEGER
        );
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, title TEXT DEFAULT '',
            created_at TEXT, updated_at TEXT, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL,
            role TEXT NOT NULL, content TEXT NOT NULL, timestamp TEXT,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS knowledge_bases (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT DEFAULT 'file',
            path TEXT DEFAULT '', url TEXT DEFAULT '', filter TEXT DEFAULT '',
            top_k INTEGER DEFAULT 5, created_at TEXT, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
            content TEXT DEFAULT '', created_at TEXT, active INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS mcp_servers (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, transport_type TEXT DEFAULT 'stdio',
            command TEXT DEFAULT '', args TEXT DEFAULT '[]', env TEXT DEFAULT '{}',
            url TEXT DEFAULT '', enabled INTEGER DEFAULT 1, created_at TEXT
        );
    """)
    conn.commit()
    conn.close()

def get_config(key):
    """从数据库读取配置"""
    try:
        conn = get_db()
        row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception:
        pass
    return ""


def set_config(key, value):
    """保存配置到数据库"""
    try:
        conn = get_db()
        conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to save config {key}: {e}")
        return False


def load_config_from_db():
    """从数据库加载配置到内存"""
    global AGNES_API_KEY, AGNES_API_BASE, MODEL_NAME
    db_key = get_config("agnes_api_key")
    db_base = get_config("agnes_api_base")
    db_model = get_config("model_name")
    if db_key:
        AGNES_API_KEY = db_key
    if db_base:
        AGNES_API_BASE = db_base
    if db_model:
        MODEL_NAME = db_model




def get_knowledge_bases():
    conn = get_db()
    rows = conn.execute("SELECT * FROM knowledge_bases WHERE active = 1").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_knowledge_base(kb):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO knowledge_bases (id, name, type, path, url, filter, top_k, created_at, active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (kb["id"], kb["name"], kb.get("type", "file"), kb.get("path", ""), kb.get("url", ""), kb.get("filter", ""), kb.get("top_k", 5), datetime.now().isoformat(), 1)
    )
    conn.commit()
    conn.close()


def delete_knowledge_base(kb_id):
    conn = get_db()
    conn.execute("UPDATE knowledge_bases SET active = 0 WHERE id = ?", (kb_id,))
    conn.commit()
    conn.close()


def get_skills():
    conn = get_db()
    rows = conn.execute("SELECT * FROM skills WHERE active = 1").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_skill(skill):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO skills (id, name, description, content, created_at, active) VALUES (?, ?, ?, ?, ?, ?)",
        (skill["id"], skill["name"], skill.get("description", ""), skill.get("content", ""), datetime.now().isoformat(), 1)
    )
    conn.commit()
    conn.close()


def delete_skill(skill_id):
    conn = get_db()
    conn.execute("UPDATE skills SET active = 0 WHERE id = ?", (skill_id,))
    conn.commit()
    conn.close()


def get_mcp_servers():
    conn = get_db()
    rows = conn.execute("SELECT * FROM mcp_servers WHERE enabled = 1").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_mcp_server(server):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO mcp_servers (id, name, transport_type, command, args, env, url, enabled, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (server["id"], server["name"], server.get("transport_type", "stdio"), server.get("command", ""), json.dumps(server.get("args", [])), json.dumps(server.get("env", {})), server.get("url", ""), 1 if server.get("enabled", True) else 0, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def delete_mcp_server(server_id):
    conn = get_db()
    conn.execute("UPDATE mcp_servers SET enabled = 0 WHERE id = ?", (server_id,))
    conn.commit()
    conn.close()


def resolve_knowledge(kb_ids):
    """Resolve knowledge base IDs to agno Knowledge objects"""
    if not kb_ids:
        return []
    from agno.knowledge import FileSystemKnowledge
    resolved = []
    for kid in kb_ids:
        try:
            conn = get_db()
            row = conn.execute("SELECT * FROM knowledge_bases WHERE id = ?", (kid,)).fetchone()
            conn.close()
            if row:
                kb_dict = dict(row)
                if kb_dict["type"] == "file":
                    resolved.append(FileSystemKnowledge(path=kb_dict["path"]))
                elif kb_dict["type"] == "web":
                    resolved.append(FileSystemKnowledge(path=kb_dict["url"]))
        except Exception as e:
            logger.warning(f"Failed to load knowledge base {kid}: {e}")
    return resolved


def resolve_skills(skill_ids):
    """Resolve skill IDs to instruction strings"""
    if not skill_ids:
        return []
    conn = get_db()
    rows = conn.execute("SELECT * FROM skills WHERE id IN ({})".format(",".join(["?"] * len(skill_ids))), skill_ids).fetchall()
    conn.close()
    return [dict(r)["content"] for r in rows if dict(r).get("content")]


def resolve_mcp_servers(server_ids):
    """Resolve MCP server IDs to config dicts"""
    if not server_ids:
        return []
    conn = get_db()
    rows = conn.execute("SELECT * FROM mcp_servers WHERE id IN ({})".format(",".join(["?"] * len(server_ids))))
    server_list = [dict(r) for r in rows.fetchall()]
    conn.close()
    return server_list

def get_model():
    # Ensure config is loaded from DB
    load_config_from_db()
    return OpenAIChat(id=MODEL_NAME, api_key=AGNES_API_KEY, base_url=AGNES_API_BASE)

# --- Tool Mapping ---
TOOL_MAPPING = {
    "web_search": ("agno.tools.websearch", "WebSearchTools"),
    "duckduckgo": ("agno.tools.duckduckgo", "DuckDuckGoTools"),
    "tavily": ("agno.tools.tavily", "TavilySearchResults"),
    "serper": ("agno.tools.serper", "SerperTool"),
    "bravesearch": ("agno.tools.bravesearch", "BraveSearchTool"),
    "searxng": ("agno.tools.searxng", "SearXNGTool"),
    "searchapi": ("agno.tools.searchapi", "SearchAPITool"),
    "serpapi": ("agno.tools.serpapi", "SerpAPITool"),
    "exa": ("agno.tools.exa", "ExaSearchTool"),
    "youcom": ("agno.tools.youcom", "YouComTool"),
    "linkup": ("agno.tools.linkup", "LinkupTool"),
    "baidusearch": ("agno.tools.baidusearch", "BaiduSearchTool"),
    "brightdata": ("agno.tools.brightdata", "BrightDataTool"),
    "oxylabs": ("agno.tools.oxylabs", "OxylabsTool"),
    "scavio": ("agno.tools.scavio", "ScavioTool"),
    "seltz": ("agno.tools.seltz", "SeltzTool"),
    "jina": ("agno.tools.jina", "JinaReaderTool"),
    "valyu": ("agno.tools.valyu", "ValyuTool"),
    "wikipedia": ("agno.tools.wikipedia", "WikipediaTool"),
    "arxiv": ("agno.tools.arxiv", "ArxivTool"),
    "pubmed": ("agno.tools.pubmed", "PubMedTool"),
    "hackernews": ("agno.tools.hackernews", "HackerNewsTool"),
    "reddit": ("agno.tools.reddit", "RedditTool"),
    "openweather": ("agno.tools.openweather", "OpenWeatherTools"),
    "python": ("agno.tools.python", "PythonTool"),
    "coding": ("agno.tools.coding", "CodingTool"),
    "shell": ("agno.tools.shell", "ShellTool"),
    "github": ("agno.tools.github", "GitHubTool"),
    "gitlab": ("agno.tools.gitlab", "GitLabTool"),
    "docker": ("agno.tools.docker", "DockerTool"),
    "sql": ("agno.tools.sql", "SQLTool"),
    "postgres": ("agno.tools.postgres", "PostgreSQLTool"),
    "pandas": ("agno.tools.pandas", "PandasTool"),
    "file": ("agno.tools.file", "FileTool"),
    "local_file_system": ("agno.tools.local_file_system", "LocalFileSystemTool"),
    "apify": ("agno.tools.apify", "ApifyTool"),
    "browserbase": ("agno.tools.browserbase", "BrowserbaseTool"),
    "spider": ("agno.tools.spider", "SpiderTool"),
    "firecrawl": ("agno.tools.firecrawl", "FirecrawlTool"),
    "crawl4ai": ("agno.tools.crawl4ai", "Crawl4AITool"),
    "gmail": ("agno.tools.gmail", "GmailTool"),
    "slack": ("agno.tools.slack", "SlackTool"),
    "discord": ("agno.tools.discord", "DiscordTool"),
    "telegram": ("agno.tools.telegram", "TelegramTool"),
    "notion": ("agno.tools.notion", "NotionTool"),
    "jira": ("agno.tools.jira", "JiraTool"),
    "linear": ("agno.tools.linear", "LinearTool"),
    "trello": ("agno.tools.trello", "TrelloTool"),
    "dalle": ("agno.tools.dalle", "DALLETool"),
    "youtube": ("agno.tools.youtube", "YouTubeTool"),
    "spotify": ("agno.tools.spotify", "SpotifyTool"),
}

def resolve_tools(tool_ids: list) -> list:
    resolved = []
    for tid in tool_ids or []:
        if tid in TOOL_MAPPING:
            try:
                mod_path, cls_name = TOOL_MAPPING[tid]
                mod = importlib.import_module(mod_path)
                resolved.append(getattr(mod, cls_name)())
            except Exception as e:
                logger.warning(f"Failed to load tool {tid}: {e}")
    return resolved

prompt_templates = {
    "prd": {"instructions": """你是一个资深产品经理。请基于用户需求生成详细的**中文**产品需求文档（PRD）。

## 任务要求
- **语言**: 必须使用**中文**输出。
- **内容范围**: 仅包含产品层面的需求描述，严禁包含技术实现细节。
- **排版要求**:
  - 所有列表请使用 Markdown 列表格式。
  - 数据字典、功能列表等结构化信息，必须使用标准的 Markdown 表格格式。
  - 严禁使用纯文本竖线 `|` 拼接表格内容。
- **必须包含**:
  1. **功能概述**: 简要说明项目背景和目标。
  2. **用户故事**: 从不同角色角度描述核心场景。
  3. **功能列表**: 详细的功能点拆解。
  4. **非功能需求**: 性能、安全、合规性等要求。
  5. **数据字典**: 核心业务实体及其字段含义（使用表格）。

请使用 Markdown 格式输出。"""},
    "review": {"instructions": """你是一个资深产品经理和技术专家。请审查以下PRD，识别P0/P1/P2级别的问题，并给出修改建议。

## 要求
- 识别功能缺失、逻辑矛盾、边界条件遗漏等问题
- 按严重程度分级（P0-阻塞性，P1-重要，P2-一般）
- 给出具体修改建议

请用 Markdown 格式输出审查报告。"""},
    "technical_design": {"instructions": """你是一个资深系统架构师。请基于以下PRD生成完整的技术方案。

## 要求
- 系统架构设计（模块划分、数据流向）
- 数据库表结构设计
- API接口设计（RESTful风格）
- 核心业务流程图（Mermaid格式）
- 性能与安全设计

请用 Markdown 格式输出技术方案。"""},
    "test_cases": {"instructions": """你是一个资深测试工程师。请基于以下PRD生成完整的测试用例。

## 要求
- 正向流程测试用例
- 异常场景测试用例
- 边界值测试用例
- 性能与安全测试要点

请用 Markdown 格式输出测试用例清单。"""},
    "code_generation": {"instructions": """你是一个资深开发工程师。请基于以下技术需求生成{language}语言代码。

## 要求
- Handler层代码（路由处理）
- Service层代码（业务逻辑）
- DAO层代码（数据访问）
- Model定义（结构体）
- 错误码定义
- 测试用例代码

请用 Markdown 格式输出代码，每个文件用代码块包裹。"""},
}

class TaskRequest(BaseModel):
    task_type: Optional[str] = None
    prd_text: Optional[str] = None
    message: Optional[str] = None
    tech_design: Optional[str] = None
    language: Optional[str] = None
    repo_path: Optional[str] = None

class AgentCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    instructions: Optional[str] = ""
    model: Optional[str] = "agnes-2.0-flash"
    enable_memory: bool = False
    enable_reasoning: bool = False
    tools: Optional[List[str]] = []
    knowledge_base_ids: Optional[List[str]] = []
    skill_ids: Optional[List[str]] = []
    mcp_server_ids: Optional[List[str]] = []

class AgentUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    model: Optional[str] = None
    enable_memory: Optional[bool] = None
    enable_reasoning: Optional[bool] = None
    tools: Optional[List[str]] = None
    knowledge_base_ids: Optional[List[str]] = None
    skill_ids: Optional[List[str]] = None
    mcp_server_ids: Optional[List[str]] = None

class TeamCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    mode: str = "coordinate"
    members: List[str]
    instructions: Optional[str] = ""
    respond_directly: bool = False

class WorkflowCreateRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    steps: List[Dict[str, Any]]

app = FastAPI(title="Smart R&D Platform (Agno Powered)", version="6.0.0")

# Initialize DB on startup
init_db()
load_config_from_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

def log_usage(task_type: str, input_text: str, output_text: str, response_time: float, success: bool):
    conn = get_db()
    conn.execute(
        "INSERT INTO usage_logs (timestamp, task_type, input_length, output_length, response_time, success) VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), task_type, len(input_text), len(output_text), response_time, int(success))
    )
    conn.commit()
    conn.close()

def create_agent_instance(config: dict) -> Agent:
    instructions = config.get("instructions", "")
    tools_raw = config.get("tools")
    if tools_raw is None:
        tools = []
    elif isinstance(tools_raw, list):
        tools = resolve_tools(tools_raw)
    elif isinstance(tools_raw, str):
        try:
            tools = resolve_tools(json.loads(tools_raw))
        except:
            tools = []
    else:
        tools = []
    if tools:
        tool_names = ", ".join([t.name for t in tools])
        instructions += f"\n\n## 工具使用说明\n你有以下工具可以使用：{tool_names}\n当用户询问需要查询信息、搜索内容、执行代码等操作时，你必须使用这些工具来完成任务。不要直接拒绝说无法联网或无法获取数据。"

    # Resolve knowledge bases
    kb_ids = config.get("knowledge_base_ids", [])
    knowledge_list = resolve_knowledge(kb_ids)

    # Resolve skills
    skill_ids = config.get("skill_ids", [])
    skill_contents = resolve_skills(skill_ids)
    if skill_contents:
        instructions += "\n\n## 技能\n" + "\n---\n".join(skill_contents)

    # Resolve MCP servers
    mcp_ids = config.get("mcp_server_ids", [])
    mcp_configs = resolve_mcp_servers(mcp_ids)

    kwargs = {
        "name": config["name"],
        "model": get_model(),
        "instructions": instructions,
        "enable_agentic_memory": bool(config.get("enable_memory", False)),
        "reasoning": bool(config.get("enable_reasoning", False)),
    }
    if tools:
        kwargs["tools"] = tools
    if knowledge_list:
        kwargs["knowledge"] = knowledge_list
    if skill_contents:
        kwargs["skills"] = skill_contents
    if mcp_configs:
        kwargs["mcp"] = mcp_configs
    return Agent(**kwargs)

def row_to_dict(row):
    if row is None:
        return None
    d = dict(row)
    for k in ("tools", "skills", "members", "steps"):
        if d.get(k) and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except:
                pass
    return d

# --- Agent CRUD ---
@app.post("/api/agents")
async def create_agent(request: AgentCreateRequest):
    agent_id = f"agent_{int(time.time()*1000)}"
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO agents (id, name, description, instructions, model, enable_memory, enable_reasoning, tools, knowledge_base_ids, skill_ids, mcp_server_ids, created_at, active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (agent_id, request.name, request.description or "", request.instructions or "", request.model or "agnes-2.0-flash", int(request.enable_memory), int(request.enable_reasoning), json.dumps(request.tools or []), json.dumps(request.knowledge_base_ids or []), json.dumps(request.skill_ids or []), json.dumps(request.mcp_server_ids or []), now, 1)
    )
    conn.commit()
    conn.close()
    return {"id": agent_id, "message": "Agent created successfully"}

@app.get("/api/agents")
async def list_agents():
    conn = get_db()
    rows = conn.execute("SELECT * FROM agents WHERE active = 1 ORDER BY created_at DESC").fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str):
    conn = get_db()
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    return row_to_dict(row)

@app.put("/api/agents/{agent_id}")
async def update_agent(agent_id: str, request: AgentUpdateRequest):
    conn = get_db()
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Agent not found")
    update_data = request.model_dump(exclude_unset=True)
    fields = []
    values = []
    for k, v in update_data.items():
        if k in ("enable_memory", "enable_reasoning"):
            fields.append(f"{k} = ?")
            values.append(int(v))
        elif k in ("tools", "skills", "knowledge_base_ids", "skill_ids", "mcp_server_ids"):
            fields.append(f"{k} = ?")
            values.append(json.dumps(v))
        else:
            fields.append(f"{k} = ?")
            values.append(v)
    if fields:
        conn.execute(f"UPDATE agents SET {', '.join(fields)} WHERE id = ?", values + [agent_id])
        conn.commit()
    conn.close()
    return {"message": "Agent updated successfully"}

@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str):
    conn = get_db()
    conn.execute("UPDATE agents SET active = 0 WHERE id = ?", (agent_id,))
    conn.commit()
    conn.close()
    return {"message": "Agent deleted successfully"}

# --- Team CRUD ---
@app.post("/api/teams")
async def create_team(request: TeamCreateRequest):
    team_id = f"team_{int(time.time()*1000)}"
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO teams (id, name, description, mode, members, instructions, respond_directly, created_at, active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (team_id, request.name, request.description or "", request.mode, json.dumps(request.members), request.instructions or "", int(request.respond_directly), now, 1)
    )
    conn.commit()
    conn.close()
    return {"id": team_id, "message": "Team created successfully"}

@app.get("/api/teams")
async def list_teams():
    conn = get_db()
    rows = conn.execute("SELECT * FROM teams WHERE active = 1 ORDER BY created_at DESC").fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

@app.post("/api/teams/{team_id}/run")
async def run_team(team_id: str, request: TaskRequest):
    conn = get_db()
    row = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Team not found")
    team_config = row_to_dict(row)
    member_configs = []
    for mid in team_config.get("members", []):
        mrow = conn.execute("SELECT * FROM agents WHERE id = ?", (mid,)).fetchone()
        if mrow:
            member_configs.append(row_to_dict(mrow))
    conn.close()
    member_agents = [create_agent_instance(c) for c in member_configs]
    team = Team(
        name=team_config["name"],
        members=member_agents,
        mode=team_config.get("mode", "coordinate"),
        instructions=team_config.get("instructions", ""),
        respond_directly=bool(team_config.get("respond_directly")),
    )
    start_time = time.time()
    result = team.run(request.message or request.prd_text or "")
    elapsed = time.time() - start_time
    log_usage("team_run", request.message or "", str(result), elapsed, True)
    return {"task_id": f"task_{int(time.time()*1000)}", "status": "success", "result": result.content if result.content else str(result)}

# --- Workflow CRUD ---
@app.post("/api/workflows")
async def create_workflow(request: WorkflowCreateRequest):
    workflow_id = f"workflow_{int(time.time()*1000)}"
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO workflows (id, name, description, steps, created_at, active) VALUES (?, ?, ?, ?, ?, ?)",
        (workflow_id, request.name, request.description or "", json.dumps(request.steps), now, 1)
    )
    conn.commit()
    conn.close()
    return {"id": workflow_id, "message": "Workflow created successfully"}

@app.get("/api/workflows")
async def list_workflows():
    conn = get_db()
    rows = conn.execute("SELECT * FROM workflows WHERE active = 1 ORDER BY created_at DESC").fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

@app.post("/api/workflows/{workflow_id}/run")
async def run_workflow(workflow_id: str, request: TaskRequest):
    conn = get_db()
    row = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Workflow not found")
    wf_config = row_to_dict(row)
    steps = []
    for step in wf_config.get("steps", []):
        agent_id = step.get("agent_id")
        if agent_id:
            arow = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
            if arow:
                steps.append(create_agent_instance(row_to_dict(arow)))
    conn.close()
    workflow = Workflow(name=wf_config["name"], description=wf_config["description"], steps=steps)
    start_time = time.time()
    result = workflow.run(request.message or request.prd_text or "")
    elapsed = time.time() - start_time
    log_usage("workflow_run", request.message or "", str(result), elapsed, True)
    return {"task_id": f"task_{int(time.time()*1000)}", "status": "success", "result": result.content if result.content else str(result)}

# --- Execution Endpoints ---
@app.post("/api/agents/{agent_id}/run")
async def run_agent(agent_id: str, request: TaskRequest):
    conn = get_db()
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Agent not found")
    config = row_to_dict(row)
    conn.close()
    start_time = time.time()
    conversation_id = request.model_dump().get("conversation_id")
    try:
        agent = create_agent_instance(config)
        input_text = request.prd_text or request.message or ""
        result = agent.run(input_text)
        elapsed = time.time() - start_time
        
        # Save conversation messages
        if conversation_id:
            now = datetime.now().isoformat()
            cconn = get_db()
            cconn.execute(
                "INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, 'user', ?, ?)",
                (conversation_id, input_text, now)
            )
            cconn.execute(
                "INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, 'assistant', ?, ?)",
                (conversation_id, result.content if result.content else str(result), now)
            )
            cconn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
            cconn.commit()
            cconn.close()
        
        log_usage("agent_run", input_text, str(result), elapsed, True)
        return {"task_id": f"task_{int(time.time()*1000)}", "status": "success", "result": result.content if result.content else str(result)}
    except Exception as e:
        elapsed = time.time() - start_time
        log_usage("agent_run", request.prd_text or "", "", elapsed, False)
        return {"task_id": f"task_{int(time.time()*1000)}", "status": "failed", "result": str(e)}

@app.post("/api/prd/generate")
async def generate_prd(request: TaskRequest):
    start_time = time.time()
    try:
        agent = Agent(name="PRD生成器", model=get_model(), instructions=prompt_templates["prd"]["instructions"])
        result = agent.run(request.prd_text or "")
        elapsed = time.time() - start_time
        log_usage("generate", request.prd_text or "", str(result), elapsed, True)
        return {"task_id": f"task_{int(time.time()*1000)}", "status": "success", "result": result.content if result.content else str(result)}
    except Exception as e:
        return {"task_id": f"task_{int(time.time()*1000)}", "status": "failed", "result": str(e)}

@app.post("/api/prd/review")
async def review_prd(request: TaskRequest):
    start_time = time.time()
    try:
        agent = Agent(name="PRD审查员", model=get_model(), instructions=prompt_templates["review"]["instructions"])
        result = agent.run(request.prd_text or "")
        elapsed = time.time() - start_time
        log_usage("review", request.prd_text or "", str(result), elapsed, True)
        return {"task_id": f"task_{int(time.time()*1000)}", "status": "success", "result": result.content if result.content else str(result)}
    except Exception as e:
        return {"task_id": f"task_{int(time.time()*1000)}", "status": "failed", "result": str(e)}

@app.post("/api/prd/technical-design")
async def technical_design(request: TaskRequest):
    start_time = time.time()
    try:
        agent = Agent(name="架构师", model=get_model(), instructions=prompt_templates["technical_design"]["instructions"])
        result = agent.run(request.prd_text or "")
        elapsed = time.time() - start_time
        log_usage("td", request.prd_text or "", str(result), elapsed, True)
        return {"task_id": f"task_{int(time.time()*1000)}", "status": "success", "result": result.content if result.content else str(result)}
    except Exception as e:
        return {"task_id": f"task_{int(time.time()*1000)}", "status": "failed", "result": str(e)}

@app.post("/api/prd/test-cases")
async def test_cases(request: TaskRequest):
    start_time = time.time()
    try:
        agent = Agent(name="测试工程师", model=get_model(), instructions=prompt_templates["test_cases"]["instructions"])
        result = agent.run(request.prd_text or "")
        elapsed = time.time() - start_time
        log_usage("test", request.prd_text or "", str(result), elapsed, True)
        return {"task_id": f"task_{int(time.time()*1000)}", "status": "success", "result": result.content if result.content else str(result)}
    except Exception as e:
        return {"task_id": f"task_{int(time.time()*1000)}", "status": "failed", "result": str(e)}

@app.post("/api/prd/generate-code")
async def generate_code(request: TaskRequest):
    start_time = time.time()
    try:
        instr = prompt_templates["code_generation"]["instructions"].replace("{language}", request.language or "Go")
        agent = Agent(name="代码生成器", model=get_model(), instructions=instr)
        result = agent.run(request.tech_design or request.prd_text or "")
        elapsed = time.time() - start_time
        log_usage("code", request.tech_design or request.prd_text or "", str(result), elapsed, True)
        return {"task_id": f"task_{int(time.time()*1000)}", "status": "success", "result": result.content if result.content else str(result)}
    except Exception as e:
        return {"task_id": f"task_{int(time.time()*1000)}", "status": "failed", "result": str(e)}

@app.post("/api/prd/code-chat")
async def code_chat(request: TaskRequest):
    start_time = time.time()
    try:
        instr = prompt_templates["code_generation"]["instructions"].replace("{language}", request.language or "Go")
        agent = Agent(name="代码助手", model=get_model(), instructions=instr)
        result = agent.run(request.message or "")
        elapsed = time.time() - start_time
        log_usage("code_chat", request.message or "", str(result), elapsed, True)
        return {"task_id": f"task_{int(time.time()*1000)}", "status": "success", "result": result.content if result.content else str(result)}
    except Exception as e:
        return {"task_id": f"task_{int(time.time()*1000)}", "status": "failed", "result": str(e)}

@app.post("/api/agents/{agent_id}/conversations")
async def create_conversation(agent_id: str):
    """创建新对话"""
    conn = get_db()
    row = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Agent not found")
    
    conv_id = f"conv_{int(time.time()*1000)}"
    now = datetime.now().isoformat()
    agent_name = row["name"]
    conn.execute(
        "INSERT INTO conversations (id, agent_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (conv_id, agent_id, f"{agent_name}的对话", now, now)
    )
    conn.commit()
    conn.close()
    return {"id": conv_id, "message": "Conversation created"}


@app.get("/api/agents/{agent_id}/conversations")
async def list_conversations(agent_id: str):
    """获取Agent的所有对话"""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE agent_id = ? AND active = 1 ORDER BY updated_at DESC",
            (agent_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            # Get message count
            msg_count = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
                (d["id"],)
            ).fetchone()[0]
            d["message_count"] = msg_count
            result.append(d)
        return result
    finally:
        conn.close()


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """获取对话消息列表"""
    conn = get_db()
    conv = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    if not conv:
        conn.close()
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    messages = conn.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC",
        (conversation_id,)
    ).fetchall()
    conn.close()
    return {
        "conversation": dict(conv),
        "messages": [dict(m) for m in messages]
    }


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """删除对话"""
    conn = get_db()
    conn.execute("UPDATE conversations SET active = 0 WHERE id = ?", (conversation_id,))
    conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
    conn.commit()
    conn.close()
    return {"message": "Conversation deleted"}


@app.post("/api/conversations/{conversation_id}/messages")
async def add_message(conversation_id: str, request: dict):
    """添加消息到对话"""
    conn = get_db()
    conv = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    if not conv:
        conn.close()
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
        (conversation_id, request.get("role", "user"), request.get("content", ""), now)
    )
    conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
    conn.commit()
    conn.close()
    return {"message": "Message added"}



# --- Knowledge Base CRUD ---
@app.post("/api/knowledge-bases")
async def create_knowledge_base(request: dict):
    kb = request.copy()
    kb["id"] = kb.get("id", f"kb_{int(time.time()*1000)}")
    save_knowledge_base(kb)
    return {"id": kb["id"], "message": "Knowledge base created"}


@app.get("/api/knowledge-bases")
async def list_knowledge_bases():
    return get_knowledge_bases()


@app.delete("/api/knowledge-bases/{kb_id}")
async def remove_knowledge_base(kb_id: str):
    delete_knowledge_base(kb_id)
    return {"message": "Knowledge base deleted"}


# --- Skills CRUD ---
@app.post("/api/skills")
async def create_skill(request: dict):
    skill = request.copy()
    skill["id"] = skill.get("id", f"skill_{int(time.time()*1000)}")
    save_skill(skill)
    return {"id": skill["id"], "message": "Skill created"}


@app.get("/api/skills")
async def list_skills():
    return get_skills()


@app.delete("/api/skills/{skill_id}")
async def remove_skill(skill_id: str):
    delete_skill(skill_id)
    return {"message": "Skill deleted"}


# --- MCP Servers CRUD ---
@app.post("/api/mcp-servers")
async def create_mcp_server(request: dict):
    server = request.copy()
    server["id"] = server.get("id", f"mcp_{int(time.time()*1000)}")
    save_mcp_server(server)
    return {"id": server["id"], "message": "MCP server created"}


@app.get("/api/mcp-servers")
async def list_mcp_servers():
    return get_mcp_servers()


@app.delete("/api/mcp-servers/{server_id}")
async def remove_mcp_server(server_id: str):
    delete_mcp_server(server_id)
    return {"message": "MCP server deleted"}



@app.get("/api/config")
async def get_config_endpoint():
    """获取当前配置（不返回 API Key）"""
    return {
        "api_url": AGNES_API_BASE,
        "model_name": MODEL_NAME,
        "has_api_key": bool(AGNES_API_KEY)
    }


@app.post("/api/config")
async def update_config(request: dict):
    """更新配置（保存到数据库）"""
    if "api_key" in request and request["api_key"]:
        set_config("agnes_api_key", request["api_key"])
        AGNES_API_KEY = request["api_key"]
    if "api_url" in request and request["api_url"]:
        set_config("agnes_api_base", request["api_url"])
        AGNES_API_BASE = request["api_url"]
    if "model_name" in request and request["model_name"]:
        set_config("model_name", request["model_name"])
        MODEL_NAME = request["model_name"]
    return {"message": "Configuration saved successfully"}


init_db()

@app.get("/api/health")
async def health():
    return {"status": "ok"}

@app.get("/api/usage-stats")
async def get_usage_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM usage_logs").fetchone()[0]
    by_type = {}
    avg_time = 0
    errors = 0
    if total > 0:
        rows = conn.execute("SELECT task_type, AVG(response_time) FROM usage_logs GROUP BY task_type").fetchall()
        for r in rows:
            by_type[r[0]] = r[1]
        errors = conn.execute("SELECT COUNT(*) FROM usage_logs WHERE success=0").fetchone()[0]
        avg_time = conn.execute("SELECT AVG(response_time) FROM usage_logs").fetchone()[0] or 0
    conn.close()
    return {
        "total_requests": total,
        "by_task_type": by_type,
        "avg_response_time": avg_time,
        "error_rate": errors / total if total > 0 else 0
    }

@app.post("/api/config/save")
async def save_config(request: dict):
    """保存配置到数据库"""
    if "api_key" in request and request["api_key"]:
        set_config("agnes_api_key", request["api_key"])
        AGNES_API_KEY = request["api_key"]
    if "api_url" in request and request["api_url"]:
        set_config("agnes_api_base", request["api_url"])
        AGNES_API_BASE = request["api_url"]
    if "model_name" in request and request["model_name"]:
        set_config("model_name", request["model_name"])
        MODEL_NAME = request["model_name"]
    return {"message": "Configuration saved successfully"}


@app.get("/api/evolution/prompts")
async def get_prompt_history():
    prompts = [{"module": k, "version": 1, "instructions": v["instructions"], "usage_count": 0, "last_optimized": None} for k, v in prompt_templates.items()]
    return {"prompts": prompts, "total": len(prompts)}
