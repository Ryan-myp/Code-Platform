#!/usr/bin/env python3
"""Skills 文件系统存储层 — 标准 Agent Skills 目录结构的事实源。

backend/skills_files/<skill_id>/
├── SKILL.md            # frontmatter(name/description) + 正文，必需
├── scripts/            # 可执行脚本（.py 等）
├── references/         # 参考资料（.md/.txt/.pdf）
├── examples/           # 示例文件
└── assets/             # 资源文件（图片等）

所有对外路径均为相对路径（posix 风格），内部统一做防路径穿越校验。
"""

import io
import json
import logging
import posixpath
import re
import shutil
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

# 标准目录（用于统计与前端徽章展示）
STANDARD_DIRS = ("scripts", "references", "examples", "assets")

# 文本文件扩展名（其余按二进制处理）
TEXT_EXTS = {
    ".md", ".markdown", ".txt", ".py", ".js", ".jsx", ".ts", ".tsx", ".json",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".sh", ".bash", ".zsh", ".ps1",
    ".css", ".html", ".htm", ".xml", ".csv", ".sql", ".java", ".go", ".rs",
    ".c", ".cpp", ".h", ".hpp", ".rb", ".php", ".vue", ".env", ".gitignore",
    ".dockerfile", ".ipynb", ".log", ".rst", ".svg",
}

_SKILL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


# ══════════════════════════════════════════════════════════════
# 路径解析与校验（防路径穿越）
# ══════════════════════════════════════════════════════════════

def get_skills_dir() -> Path:
    """返回 skills 根目录（动态读取，支持测试替换 SKILLS_DIR）。"""
    from common import config

    config.SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    return config.SKILLS_DIR


def validate_skill_id(skill_id: str) -> None:
    if not skill_id or not _SKILL_ID_RE.match(skill_id):
        raise ValueError(f"非法 skill_id: {skill_id!r}")


def skill_root(skill_id: str) -> Path:
    validate_skill_id(skill_id)
    return get_skills_dir() / skill_id


def resolve_path(skill_id: str, rel_path: str) -> Path:
    """将相对路径解析为 skill 根目录内的绝对路径，防路径穿越。

    rel_path 允许 ""（根目录）、"SKILL.md"、"scripts/foo.py"、"references/usage/a.md"。
    拒绝绝对路径（/ 开头）、.. 段、空段。
    """
    raw = (rel_path or "").strip().replace("\\", "/")
    if raw.startswith("/"):
        raise ValueError(f"非法路径（不允许绝对路径）: {rel_path!r}")
    rel = raw.strip("/")
    if not rel:
        return skill_root(skill_id)
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise ValueError(f"非法路径（不允许空段或 ..）: {rel_path!r}")
    root = skill_root(skill_id)
    target = root.joinpath(*parts)
    if root not in target.parents:
        raise ValueError(f"路径越界: {rel_path!r}")
    return target


# ══════════════════════════════════════════════════════════════
# SKILL.md frontmatter 解析 / 渲染
# ══════════════════════════════════════════════════════════════

def parse_skill_markdown(text: str) -> dict:
    """解析标准 SKILL.md：--- frontmatter（name/description） + 正文。

    兼容 Agent Skills 标准格式（Anthropic / Qoder / Claude Code 等）。
    """
    text = (text or "").strip()
    if not text.startswith("---"):
        return {"name": "", "description": "", "content": text}
    end = text.find("\n---", 3)
    if end == -1:
        return {"name": "", "description": "", "content": text}
    fm = text[3:end]
    body = text[end + 4:].strip()
    name, description = "", ""
    for line in fm.splitlines():
        line = line.strip()
        if line.startswith("name:"):
            name = line[5:].strip().strip("'\"")
        elif line.startswith("description:"):
            description = line[12:].strip().strip("'\"")
    return {"name": name, "description": description, "content": body}


def render_skill_markdown(skill: dict) -> str:
    """生成标准 SKILL.md（frontmatter + 正文），可与任意 Agent 工具互通。"""
    lines = ["---", f"name: {skill.get('name', '')}"]
    if skill.get("description"):
        lines.append(f"description: {skill['description']}")
    lines.append("---")
    body = (skill.get("content") or "").strip()
    return "\n".join(lines) + ("\n\n" + body if body else "")


# ══════════════════════════════════════════════════════════════
# 目录树与统计
# ══════════════════════════════════════════════════════════════

def list_tree(skill_id: str) -> dict:
    """递归目录树，节点含 name/type/file_count/path/size/ext。

    顶层额外携带 dir_counts：标准目录（scripts/references/examples/assets）文件数。
    """
    root = skill_root(skill_id)
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        return _empty_tree(skill_id)

    def build(directory: Path, rel: str) -> dict:
        children = []
        count = 0
        for child in sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            child_rel = posixpath.join(rel, child.name) if rel else child.name
            if child.is_dir():
                sub = build(child, child_rel)
                sub.update(name=child.name, path=child_rel, type="dir")
                count += sub["file_count"]
                children.append(sub)
            else:
                children.append({
                    "name": child.name,
                    "type": "file",
                    "path": child_rel,
                    "size": child.stat().st_size,
                    "ext": child.suffix.lower().lstrip("."),
                })
                count += 1
        return {"name": directory.name, "path": rel, "type": "dir", "children": children, "file_count": count}

    tree = build(root, "")
    tree["dir_counts"] = {
        d: (next((c["file_count"] for c in tree["children"] if c["type"] == "dir" and c["name"] == d), 0))
        for d in STANDARD_DIRS
    }
    return tree


def _empty_tree(skill_id: str) -> dict:
    return {
        "name": skill_id, "path": "", "type": "dir", "children": [], "file_count": 0,
        "dir_counts": {d: 0 for d in STANDARD_DIRS},
    }


def scan_stats() -> dict:
    """一次性扫描所有 skill 目录，返回 {skill_id: {file_count, dir_counts}}。

    供 GET /api/skills 列表使用，避免 N+1 扫描。
    """
    root = get_skills_dir()
    stats = {}
    if not root.exists():
        return stats
    for d in root.iterdir():
        if not d.is_dir() or not _SKILL_ID_RE.match(d.name):
            continue
        try:
            tree = list_tree(d.name)
            stats[d.name] = {"file_count": tree["file_count"], "dir_counts": tree["dir_counts"]}
        except Exception as e:  # noqa: BLE001 - 单目录异常不影响整体扫描
            logger.warning("scan_stats 跳过 %s: %s", d.name, e)
    return stats


# ══════════════════════════════════════════════════════════════
# 文件读写
# ══════════════════════════════════════════════════════════════

def read_file(skill_id: str, rel_path: str) -> dict:
    """读取文件内容。文本文件返回 content 字符串；二进制返回 is_text=False。"""
    target = resolve_path(skill_id, rel_path)
    if not target.is_file():
        raise FileNotFoundError(f"文件不存在: {rel_path}")
    data = target.read_bytes()
    ext = target.suffix.lower()
    is_text = ext in TEXT_EXTS or not data
    text = ""
    if is_text:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            is_text = False
    return {
        "path": posixpath.normpath(rel_path).strip("/"),
        "name": target.name,
        "size": len(data),
        "is_text": is_text,
        "content": text,
    }


def write_file(skill_id: str, rel_path: str, content: str | bytes) -> dict:
    """写入文件（自动创建父目录）。"""
    target = resolve_path(skill_id, rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8") if isinstance(content, str) else content
    target.write_bytes(data)
    return {"path": posixpath.normpath(rel_path).strip("/"), "name": target.name, "size": len(data)}


def delete_path(skill_id: str, rel_path: str) -> None:
    """删除文件或目录（递归）。"""
    target = resolve_path(skill_id, rel_path)
    if not target.exists():
        raise FileNotFoundError(f"路径不存在: {rel_path}")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()


def mkdir(skill_id: str, rel_path: str) -> None:
    """创建目录（幂等）。"""
    target = resolve_path(skill_id, rel_path)
    target.mkdir(parents=True, exist_ok=True)


def ensure_root(skill_id: str) -> None:
    """确保 skill 根目录存在。"""
    skill_root(skill_id).mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════
# ZIP 导入 / 导出
# ══════════════════════════════════════════════════════════════

def parse_skill_zip(zip_bytes: bytes) -> dict:
    """解析标准 skill zip 包，返回 {name, description, files: [(rel_path, bytes), ...]}。

    兼容两种形态：
    1. 顶层直接放文件（根目录含 SKILL.md）
    2. 带公共顶层目录（skill-name/SKILL.md），自动剥离该前缀
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        raise ValueError("无效的 ZIP 文件") from e

    entries = []
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if info.is_dir() or not name:
            continue
        if "__MACOSX" in name.split("/"):
            continue
        if name.rsplit("/", 1)[-1] == ".DS_Store":
            continue
        parts = name.split("/")
        if any(p in ("", ".", "..") for p in parts) or name.startswith("/"):
            raise ValueError(f"ZIP 包含非法路径: {name}")
        entries.append((name, zf.read(info)))

    if not entries:
        raise ValueError("ZIP 中没有任何文件")

    # 剥离公共顶层目录（skill-name/SKILL.md → SKILL.md）
    top_names = {e[0].split("/", 1)[0] for e in entries}
    strip_prefix = None
    if len(top_names) == 1 and all("/" in e[0] for e in entries):
        strip_prefix = next(iter(top_names))

    files = []
    skill_md = None
    for name, data in entries:
        rel = name.split("/", 1)[1] if strip_prefix else name
        if not rel:
            continue
        files.append((rel, data))
        if rel == "SKILL.md":
            skill_md = data.decode("utf-8", errors="replace")

    if not skill_md:
        raise ValueError("ZIP 中未找到 SKILL.md（标准 Skill 必须包含 SKILL.md）")

    meta = parse_skill_markdown(skill_md)
    return {"name": meta["name"], "description": meta["description"], "files": files}


def extract_zip_to(skill_id: str, zip_bytes: bytes) -> dict:
    """将标准 zip 包解压到 skill 目录，返回 {name, description, imported}。"""
    parsed = parse_skill_zip(zip_bytes)
    if not parsed["name"]:
        raise ValueError("SKILL.md 缺少 frontmatter name，无法识别技能名称")
    imported = 0
    for rel, data in parsed["files"]:
        write_file(skill_id, rel, data)
        imported += 1
    return {"name": parsed["name"], "description": parsed["description"], "imported": imported}


def sanitize_dir_name(name: str) -> str:
    """将名称清洗为合法的目录名（zip 顶层目录使用）。"""
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", (name or "").strip()).strip(" .")
    return cleaned or "skill"


def export_zip(skill_id: str, top_name: str | None = None) -> tuple[bytes, str]:
    """打包整个 skill 目录为 zip，返回 (bytes, filename)。顶层目录用清洗后的名称。"""
    root = skill_root(skill_id)
    if not root.exists():
        raise FileNotFoundError("Skill 目录不存在")
    top = sanitize_dir_name(top_name) if top_name else skill_id
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                rel = path.relative_to(root).as_posix()
                zf.write(path, f"{top}/{rel}")
    return buf.getvalue(), f"{top}.zip"


# ══════════════════════════════════════════════════════════════
# SKILL.md 与 DB 元数据同步
# ══════════════════════════════════════════════════════════════

def read_skill_md(skill_id: str) -> str | None:
    """读取磁盘 SKILL.md（不存在返回 None）。"""
    try:
        target = resolve_path(skill_id, "SKILL.md")
    except ValueError:
        return None
    return target.read_text(encoding="utf-8") if target.is_file() else None


def sync_db_from_skill_md(skill_id: str, markdown: str) -> dict:
    """SKILL.md 写入后同步 DB 元数据（name/description/content）。"""
    from common.db import get_db

    meta = parse_skill_markdown(markdown)
    conn = get_db()
    row = conn.execute("SELECT * FROM skills WHERE id=?", (skill_id,)).fetchone()
    if not row:
        conn.close()
        raise FileNotFoundError(f"Skill 不存在: {skill_id}")
    name = meta["name"] or row["name"]
    conn.execute(
        "UPDATE skills SET name=?, description=?, content=? WHERE id=?",
        (name, meta["description"], meta["content"], skill_id),
    )
    conn.commit()
    conn.close()
    return {"name": name, "description": meta["description"]}


# ══════════════════════════════════════════════════════════════
# 启动迁移（幂等）
# ══════════════════════════════════════════════════════════════

def _clean_legacy_text(val: str | None) -> str:
    """清洗历史文本字段：空 JSON（{} / []）视为空。"""
    text = (val or "").strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, (dict, list)) and not parsed:
            return ""
    except (ValueError, TypeError):
        pass
    return text


def migrate_legacy() -> int:
    """启动幂等迁移：将 skills 表记录与 skills_files 表存量落盘为标准目录结构。

    返回本次迁移处理的行数。可重复执行（SKILL.md 已存在则跳过）。
    """
    from common.db import get_db

    conn = get_db()
    skills = conn.execute("SELECT * FROM skills").fetchall()
    legacy_files = conn.execute(
        "SELECT skill_id, folder, filename, content FROM skills_files ORDER BY skill_id"
    ).fetchall()
    conn.close()

    migrated = 0
    for row in skills:
        s = dict(row)
        try:
            root = skill_root(s["id"])
        except ValueError:
            logger.warning("migrate_legacy 跳过非法 skill_id: %r", s.get("id"))
            continue
        if not (root / "SKILL.md").exists():
            root.mkdir(parents=True, exist_ok=True)
            write_file(s["id"], "SKILL.md", render_skill_markdown(s))
            refs = _clean_legacy_text(s.get("references"))
            if refs:
                write_file(s["id"], "references/references.md", refs)
            migrated += 1

    # skills_files 表存量落盘（幂等：目标文件已存在则跳过）
    seen = set()
    for row in legacy_files:
        try:
            rel = posixpath.join(row["folder"] or "", row["filename"] or "")
            if not rel or rel in seen:
                continue
            seen.add(rel)
            target = resolve_path(row["skill_id"], rel)
            if not target.exists() and row["content"]:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(row["content"], encoding="utf-8")
                migrated += 1
        except (ValueError, OSError) as e:
            logger.warning("migrate_legacy 跳过文件 %r: %s", row.get("filename"), e)
    return migrated
