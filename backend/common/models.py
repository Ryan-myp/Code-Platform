#!/usr/bin/env python3
"""Pydantic 请求模型 — 为 API 端点提供类型安全的输入验证。

替代各端点中的裸 dict 参数，确保字段类型与必填项在路由层即被校验。
"""

from typing import Any

from pydantic import BaseModel, Field

# ══════════════════════════════════════════════════════════════
# 认证
# ══════════════════════════════════════════════════════════════

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


# ══════════════════════════════════════════════════════════════
# Agent
# ══════════════════════════════════════════════════════════════

class AgentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Agent 名称")
    description: str = ""
    instructions: str = ""
    model: str = "agnes-2.5-flash"
    tools: list[str] = []
    knowledge_base_ids: list[str] = []
    skill_ids: list[str] = []
    mcp_server_ids: list[str] = []


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    instructions: str | None = None
    model: str | None = None
    active: bool | None = None
    tools: list[str] | None = None
    knowledge_base_ids: list[str] | None = None
    skill_ids: list[str] | None = None
    mcp_server_ids: list[str] | None = None


# ══════════════════════════════════════════════════════════════
# Workflow
# ══════════════════════════════════════════════════════════════

class WorkflowDefinition(BaseModel):
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []


class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="工作流名称")
    description: str = ""
    steps: list[dict[str, Any]] | None = None
    connections: list[dict[str, Any]] | None = None
    definition: WorkflowDefinition | str | None = None


class WorkflowUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    steps: list[dict[str, Any]] | None = None
    connections: list[dict[str, Any]] | None = None
    definition: WorkflowDefinition | str | None = None


class WorkflowRunRequest(BaseModel):
    message: str = Field(..., min_length=1, description="执行消息")


# ══════════════════════════════════════════════════════════════
# Team
# ══════════════════════════════════════════════════════════════

class TeamCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Team 名称")
    description: str = ""
    mode: str = "coordinate"
    members: list[Any] = []
    instructions: str = ""
    respond_directly: bool = False


class TeamUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    mode: str | None = None
    members: list[Any] | None = None
    instructions: str | None = None
    respond_directly: bool | None = None


class TeamRunRequest(BaseModel):
    message: str = Field(..., min_length=1, description="执行消息")


# ══════════════════════════════════════════════════════════════
# Skill
# ══════════════════════════════════════════════════════════════

class SkillCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Skill 名称")
    description: str = ""
    content: str = ""
    references: str = ""


class SkillUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None
    references: str | None = None


class SkillFileCreateRequest(BaseModel):
    filename: str = Field(..., min_length=1, description="文件名")
    folder: str = "references"
    content: str = ""


class SkillFileUpdateRequest(BaseModel):
    content: str = ""


# ══════════════════════════════════════════════════════════════
# Knowledge Base
# ══════════════════════════════════════════════════════════════

class KnowledgeBaseCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="知识库名称")
    type: str = "file"
    path: str = ""
    url: str = ""
    source_type: str | None = None
    source_path: str | None = None
    filter: dict[str, Any] = {}
    top_k: int = 5


class KnowledgeBaseUpdateRequest(BaseModel):
    name: str | None = None
    type: str | None = None
    source_type: str | None = None
    path: str | None = None
    source_path: str | None = None
    url: str | None = None
    top_k: int | None = None


# ══════════════════════════════════════════════════════════════
# MCP Server
# ══════════════════════════════════════════════════════════════

class MCPServerCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="MCP Server 名称")
    transport_type: str = "stdio"
    command: str = ""
    args: list[str] = []
    env: dict[str, str] = {}
    url: str = ""
    enabled: bool = True


class MCPServerUpdateRequest(BaseModel):
    name: str | None = None
    command: str | None = None
    url: str | None = None
    env: dict[str, str] | None = None
    transport: str | None = None
    transport_type: str | None = None
    args: list[str] | None = None
    enabled: bool | None = None


# ══════════════════════════════════════════════════════════════
# 评论
# ══════════════════════════════════════════════════════════════

class CommentCreateRequest(BaseModel):
    content: str = Field(..., min_length=1, description="评论内容")
    author_id: str = "admin"
    parent_comment_id: str = ""
    target_type: str = Field(..., min_length=1, description="目标类型")
    target_id: str = Field(..., min_length=1, description="目标 ID")


class CommentLikeRequest(BaseModel):
    user_id: str = "admin"


# ══════════════════════════════════════════════════════════════
# 沙箱
# ══════════════════════════════════════════════════════════════

class SandboxProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="项目名称")
    image: str = "python:3.12-alpine"
    ports: list[str] | str = []
    env: list[str] | str = []
    command: str | None = None


class SandboxPullImageRequest(BaseModel):
    image: str = Field(..., min_length=1, description="镜像名")


# ══════════════════════════════════════════════════════════════
# 对话
# ══════════════════════════════════════════════════════════════

class ConversationCreateRequest(BaseModel):
    title: str = "新对话"


class MessageCreateRequest(BaseModel):
    role: str = "user"
    content: str = Field(..., min_length=1, description="消息内容")


class AgentRunRequest(BaseModel):
    message: str = Field(..., min_length=1, description="执行消息")
    conversation_id: str | None = None


# ══════════════════════════════════════════════════════════════
# PRD / 研发流程
# ══════════════════════════════════════════════════════════════

class PRDGenerateRequest(BaseModel):
    prd_text: str = Field(..., min_length=1, description="需求描述")


class PRDReviewRequest(BaseModel):
    prd_text: str = Field(..., min_length=1, description="PRD 内容")
    repo_path: str = ""


class TechnicalDesignRequest(BaseModel):
    prd_text: str = Field(..., min_length=1, description="PRD 内容")
    repo_path: str = ""


class TestCasesRequest(BaseModel):
    prd_text: str = Field(..., min_length=1, description="PRD 内容")
    tech_design: str = ""


class CodeGenerateRequest(BaseModel):
    tech_design: str = Field(..., min_length=1, description="技术方案")
    language: str = "python"
    task_type: str = "code"


class CodeChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="消息")
    language: str = "python"


class RequirementCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="需求名称")
    description: str = ""
    status: str = "draft"
    priority: str = "P1"
    project_id: str = ""
    creator: str = "admin"


class RequirementUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    project_id: str | None = None
    prd_text: str | None = None
    review_report: str | None = None
    tech_design: str | None = None
    test_cases: str | None = None
    code: str | None = None


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="项目名称")
    description: str = ""
    status: str = "active"
    team_id: str = ""


class ArtifactCreateRequest(BaseModel):
    project_id: str = ""
    requirement_id: str = ""
    type: str = "doc"
    content: dict[str, Any] = {}
    version: str = "v1"
    author: str = "admin"


class PipelineOutputRequest(BaseModel):
    stage: str = Field(..., min_length=1, description="流水线阶段")
    content: str = Field(..., description="阶段输出内容")


# ══════════════════════════════════════════════════════════════
# 配置
# ══════════════════════════════════════════════════════════════

class ConfigSaveRequest(BaseModel):
    api_key: str | None = None
    api_url: str | None = None
    model_name: str | None = None


class OptimizePromptsRequest(BaseModel):
    target: str = "all"


# ══════════════════════════════════════════════════════════════
# 插件
# ══════════════════════════════════════════════════════════════

class PluginExecuteRequest(BaseModel):
    input_data: dict[str, Any] = {}
