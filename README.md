# Smart R&D Platform v6.4 - AI-Powered Intelligent Business Orchestration Engine

![Status](https://img.shields.io/badge/status-production-brightgreen.svg) [License](LICENSE)

An intelligent workflow orchestration platform that uses AI agents to automate complex business processes across industries (software development, education, healthcare, manufacturing, finance). Visual drag-and-drop interface for building automated pipelines with customizable nodes.

## Core Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     VISUAL EDITOR (Frontend)                    │
│  • Node library (LLM, File, API, Skill, Decision)               │
│  • Canvas with drag/drop & connection wiring                   │
│  • Real-time property panels                                   │
│  • Import/Export (JSON)                                        │
│                                                              │
│  ▼                                                                    │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │           WORKFLOW ENGINE (Backend Core)                     │ │
│ │  • WorkflowDefinition: typed node sequences                 │ │
│ │  • WorkflowInstance: runtime state tracking                │ │
│ │  • StepExecutor: sequential/conditional execution logic     │ │
│ │  • StatePersistence: save/load instance status             │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                              │
│  ▼                                                                    │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │            NODE TYPES (Extensible Plugin System)             │ │
│ │  LLMNode      - Call AI models with prompt templates         │ │
│ │  FileNode     - Read/write/delete/move files on disk         │ │
│ │  APINode      - Make HTTP requests to external APIs          │ │
│ │  SkillNode    - Execute custom Python function scripts       │ │
│ │  DecisionNode - Branch based on Python expressions           │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                              │
│  ▼                                                                    │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │               EXTERNAL SYSTEM INTEGRATIONS                 │ │
│ │  GitHub/AWS/Azure   Cloud deployment                      │ │
│ │  PostgreSQL/MySQL   Persistent storage                    │ │
│ │  SendGrid/Mailgun   Email notifications                   │ │
│ │  Slack/Discord      Team communication                    │ │
│ └──────────────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────────┘
</pre>

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Basic understanding of REST APIs

### Quick Start (Development Mode)

```bash
# Clone repository
git clone https://github.com/your-org/smart-rd-platform.git
cd smart-rd-platform

# Set up virtual environment (Python backend)
cd backend
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Run backend server (in one terminal)
uvicorn main:app --host 0.0.0.0 --port 8888 --reload

# In second terminal, start frontend
cd ../frontend
npm install
npm run dev
```

Visit http://localhost:5173 to access the visual workflow editor.

### Production Deployment (Docker)

```bash
# Build Docker images
docker-compose build

# Start services in background
docker-compose up -d

# Verify all containers are running
docker compose ps

# View logs
docker compose logs -f
```

Access at:
- Frontend: `http://localhost` (port 80)
- Backend API: `http://localhost:8888/docs` (Swagger UI)
- Backend health: `http://localhost:8888/api/health`

## Using the Platform

### Step 1: Select Node Types from Library

Drag nodes from the left panel onto the canvas:
- 🤖 **LLM Agent**: Call AI models (OpenAI-compatible endpoints)
- 📁 **File Operation**: Read/write files on disk or cloud storage
- 🔌 **API Call**: Connect to external services via REST/gRPC
- ⚙️ **Skill Execution**: Run custom Python functions from skill modules
- 🎯 **Decision Node**: Add conditional branches using Python expressions

### Step 2: Configure Each Node

Select a node on canvas → property panel appears on right. Configure type-specific parameters:

**Example - LLM Node:**
```json
{
  "type": "llm_node",
  "node_id": "analyze_review",
  "name": "Review Analysis",
  "prompt_template": "Extract key insights from this review:\n\n{input_text}\n\nReturn JSON: {sentiment, topics, suggestions}",
  "model": "agnes-2.0-flash",
  "input_schema": {"input_text": "string"}
}
```

**Example - File Node:**
```json
{
  "type": "file_node",
  "node_id": "save_output",
  "operation_type": "write",
  "path": "/var/www/output/result_{timestamp}.md",
  "content": "{analyze_review.output}"  // Reference previous node's output
}
```

### Step 3: Connect Nodes

Click on the right edge of a node, then drag to the left edge of the next node to create execution flow arrows. Nodes execute sequentially by default.

### Step 4: Register Workflow

Enter a workflow name (e.g., "Content Processing Pipeline") and click **"Register Workflow"**. This saves the configuration to the backend engine and makes it available for execution.

### Step 5: Execute Workflow

Click **"Run Workflow"** to start a new instance. The system will:

1. Create a fresh instance with unique ID
2. Execute each node in sequence (or in parallel for independent branches)
3. Pass outputs from one node as inputs to subsequent ones
4. Log execution progress and capture any errors
5. Return completion status with results

### Real-World Use Cases

#### Case A: Automated PRD Generation (Software Engineering)

```
[User Input] → [LLM: Analyze Requirements] → [LLM: Generate PRD Structure] 
             → [File: Save to /prd/ folder] → [API: Notify Slack Channel]
```

**Result**: Complete product requirement document generated automatically from natural language description.

#### Case B: Customer Support Ticket Routing (Service Industry)

```
[Ticket Received] → [LLM: Classify Category] → {Decision: Urgent?}
     ├── Yes → [Assign to Senior Agent + Escalate Manager]
     └── No  → [Route to Standard Queue + Auto-respond Customer]
                  → [File: Archive in CRM]
```

**Result**: Intelligent triage system prioritizes urgent issues and handles routine requests automatically.

#### Case C: Data ETL Pipeline (Finance/Business Analytics)

```
[Fetch from DB] → [Clean/Transform (Python Skill)] → [Calculate KPIs (LLM)]
       → [Upload to Data Lake] → [Generate Report (LLM)] → [Email Stakeholders]
```

**Result**: End-to-end automated data processing pipeline runs nightly without human intervention.

## AI Content Factories & Publish-Ready Packs (v14)

Six AI content factories (meme / music / image / video / game / miniapp) now output **publish-ready packs**:
content quality gate (safety review + aesthetics self-check) + platform-spec compliance + companion
materials, all bundled into a zip you can submit directly to the target platform.

| Factory | Publish API | Pack contents |
|---|---|---|
| Meme | `POST /api/meme/publish-pack` | WeChat sticker spec (main 240 / thumb 120 / icon 50 / banner 750x400) + upload guide + quality report |
| Music | `POST /api/music-factory/publish-pack` | mp3 + wav master (44.1kHz/16bit) + flac + cover + lrc/txt lyrics + platform specs (NetEase/Tencent/Douyin) |
| Image | `POST /api/image-factory/publish-pack` | platform-spec output (Xiaohongshu/Douyin/Taobao/WeChat) + 2x upscale + listing copy |
| Video | `POST /api/video-factory/publish-pack` | platform-spec transcode (Douyin/Bilibili/WeChat Channels) + cover frame + publish copy |
| Game | `GET /api/games/{proj_id}/publish-pack` | web/wx build + cover + README + launch checklist + quality report |
| Miniapp | `GET /api/miniapp/{proj_id}/export-zip` | project code + intro + review checklist + LICENSE + quality report |

Every pack includes `LICENSE.txt` (AI-generated commercial-use authorization), `platform-spec.md`,
an upload guide, and a `quality report` (text safety review + image quality score). Text is filtered by
`check_text` before generation (high-risk content is rejected), and generated images are self-checked by
`quality_check_image`. A `PublishProvider` registry reserves the extension point for future automatic
publishing (requires enterprise qualification on most platforms).

## Deep Evolution Across All Modules (v15)

Four-dimension upgrade (feature depth / AI professionalism / frontend UX / stability) applied to every
module — no demo-grade modules left:

| Category | Highlights |
|---|---|
| Shared foundation | `safe_guard` error fallback decorator; three-state request hook (loading / retryable error / empty); unified page header & empty-state components |
| Platform base (12) | AB test run/results endpoints + score cards; scheduler run history + auto-retry; in-app notifications with read state; role-permission matrix view; API key expiry/usage; admin health check |
| Efficiency tools (10) | Contract risk-graded review + PDF compress; 4-class PPT template library; Excel formula docs + outlier detection; translation glossary memory + bilingual export; mind-map PNG export; DocQA citation tracing; sandbox whitelist/timeout hints; search time/domain filters; batch task templates with per-item retry |
| Business analysis (8) | SEO keyword grouping/difficulty/priority matrix; insight-anomaly-advice report format; forecast confidence band; stock risk cards + report export; competitor change diff; content calendar + topic tag filters; segmented video analysis |
| Creation factories (8) | Meme style previews + multi-set merge; music rhyme/section params + custom cover; image history thumbnail wall; video script template library + batch transcode; game template library + iteration diff; miniapp template library + review-material generator; short-drama shot-sheet Excel export + material manifest; digital-human script samples + lip-sync-friendly script check (`POST /api/digital-human/script-check`, auto-fix long segments/emoji/digits) |

All modules covered by unit tests (`tests/unit/test_*_v15.py`); full pytest suite green, eslint 0 errors.

## Extending the Platform

### Creating Custom Node Types

To add a new node type, create a file in `backend/nodes/types/`:

```python
# backend/custom_nodes/crm_node.py
from nodes.base import BusinessNode
from nodes.types.validation import RequiredFieldsValidator, TypeValidator

class CRMDomainNode(BusinessNode):
    """Custom domain-specific node for CRM operations"""
    
    def __init__(self, node_id, name, crm_operation="lookup"):
        super().__init__(node_id, name, f"CRM {crm_operation} operation")
        
        # Add input validation
        self.add_validator(RequiredFieldsValidator(["contact_id"]))
        self.add_validator(TypeValidator({"contact_id": str}))
        
        self.crm_operation = crm_operation
    
    def execute(self, context):
        contact_id = context.get("current_node_input", {}).get("contact_id")
        
        # Call external CRM API or local SDK
        response = self._query_crm_system(contact_id)
        
        return NodeResult.success(
            output={"result": response},
            messages=[f"CRM {self.crm_operation} completed for {contact_id}"]
        )
    
    def _query_crm_system(self, contact_id: str) -> dict:
        """Internal method to query CRM backend"""
        # Implementation depends on specific CRM system
        return {"contact_id": contact_id, "status": "found"}
```

Then register it in your workflow editor configuration.

### Adding New Templates

Define reusable workflow templates in `backend/templates/`:

```python
# backend/templates/prd_generation.py
from nodes.types.llm_node import LLMNode
from nodes.types.file_node import FileOperationNode

def get_prd_workflow_template() -> dict:
    """Returns a pre-configured PRD generation workflow definition"""
    
    llm_node = LLMNode(
        node_id="extract_requirements",
        name="Requirements Extraction",
        model="agnes-2.0-flash",
        prompt_template="""Parse user requirements and extract structured product information:

User input: {input_text}

Output required fields: {product_name, target_users, core_features, must_have_features}
""",
        input_schema={"input_text": str}
    )
    
    file_node = FileOperationNode(
        node_id="write_prd",
        operation_type="write",
        path="/prd/{product_name}_{timestamp}.md",
        content="{extract_requirements.output}"
    )
    
    return {
        "template_id": "prd_template_v1",
        "name": "PRD Auto-generator v1",
        "nodes": [llm_node, file_node],
        "description": "Fully automated PRD documentation generation"
    }
```

Load these templates via the `/api/workflows/templates` endpoint in your frontend.

## API Reference

All endpoints are under `/api/workflows/`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/templates` | List available workflow templates |
| GET | `/node-types` | Get metadata about supported node types |
| POST | `/register` | Submit new workflow definition for registration |
| GET | `/{id}/definition` | Retrieve details of a registered workflow |
| DELETE | `/{id}/unregister` | Remove a workflow definition |
| POST | `/run` | Start a new workflow instance with given context |
| GET | `/instances` | List all recent workflow executions |
| GET | `/{instance_id}` | Get detailed status/results of an instance |
| GET | `/{instance_id}/result` | Poll for complete result once finished |

## Security Considerations

⚠️ **Important security notes before production deployment:**

1. **Authentication**: This implementation does not include built-in auth. Add JWT middleware before exposing to untrusted networks.

2. **Rate limiting**: Implement per-client rate limits on API endpoints.

3. **Input validation**: All user-provided node configurations are executed as code—validate rigorously before deserialization.

4. **Secret management**: Never hardcode API keys in source code. Use environment variables or secure secret store.

5. **Node isolation**: Consider sandboxing custom SkillNode execution in separate process/container.

6. **Network access**: Restrict outbound connections from the platform unless explicitly needed.

## Contributing

Contributions welcome! Please follow these guidelines:

1. Fork the repository
2. Create feature branch (`git checkout -b feature/awesome-feature`)
3. Commit changes (`git commit -m 'Add awesome feature'`)
4. Push to branch (`git push origin feature/awesome-feature`)
5. Open Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Questions?** Contact support@example.com or open an issue on GitHub.

*Powered by Agno Agent Framework • Built with FastAPI + React • Database: SQLite*
