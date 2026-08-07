#!/usr/bin/env python3
"""collab_engine 单元测试 — 评论 CRUD、点赞、Skill 文件管理（文件系统语义）。"""

import asyncio
import io
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))


def run(coro):
    """同步执行 async 函数的辅助。"""
    return asyncio.run(coro)


def _seed_skill(skill_id="skill_collab_test"):
    """在数据库中创建测试 Skill。"""
    from common.db import get_db

    conn = get_db()
    conn.execute(
        "INSERT INTO skills (id, name, description, content, created_at, active) VALUES (?, ?, ?, ?, ?, 1)",
        (skill_id, "测试Skill", "用于测试", "# 技能说明", "2024-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════
# 评论 CRUD
# ══════════════════════════════════════════════════════════════


def test_create_comment(test_db_path):
    """创建评论"""
    from collab_engine import create_comment
    from common.models import CommentCreateRequest

    req = CommentCreateRequest(
        content="测试评论",
        author_id="user1",
        target_type="requirement",
        target_id="req_001",
    )
    result = run(create_comment(req))
    assert "id" in result
    assert "created_at" in result


def test_create_comment_empty(test_db_path):
    """空评论内容应拒绝（Pydantic 在模型构造时校验）"""
    from common.models import CommentCreateRequest

    with pytest.raises(ValidationError):
        CommentCreateRequest(
            content="",
            author_id="user1",
            target_type="requirement",
            target_id="req_001",
        )


def test_create_comment_missing_target(test_db_path):
    """缺少 target_type / target_id 应拒绝（Pydantic 在模型构造时校验）"""
    from common.models import CommentCreateRequest

    with pytest.raises(ValidationError):
        CommentCreateRequest(
            content="测试评论",
            author_id="user1",
            target_type="",
            target_id="",
        )


def test_list_comments(test_db_path):
    """列出评论"""
    from collab_engine import create_comment, list_comments
    from common.models import CommentCreateRequest

    req = CommentCreateRequest(
        content="评论1",
        author_id="user1",
        target_type="requirement",
        target_id="req_list",
    )
    run(create_comment(req))

    result = run(list_comments("requirement", "req_list"))
    assert len(result) >= 1
    assert result[0]["content"] == "评论1"


def test_get_comment_thread(test_db_path):
    """获取评论线程（含回复树）"""
    from collab_engine import create_comment, get_comment_thread
    from common.models import CommentCreateRequest

    # 创建父评论
    parent_req = CommentCreateRequest(
        content="父评论",
        author_id="user1",
        target_type="requirement",
        target_id="req_thread",
    )
    parent = run(create_comment(parent_req))

    # 创建子评论
    child_req = CommentCreateRequest(
        content="子评论",
        author_id="user2",
        target_type="requirement",
        target_id="req_thread",
        parent_comment_id=parent["id"],
    )
    run(create_comment(child_req))

    result = run(get_comment_thread("requirement", "req_thread"))
    assert len(result) == 1  # 一个根评论
    assert result[0]["content"] == "父评论"
    assert len(result[0]["replies"]) == 1
    assert result[0]["replies"][0]["content"] == "子评论"


def test_delete_comment(test_db_path):
    """删除评论（软删除）"""
    from collab_engine import create_comment, delete_comment, list_comments
    from common.models import CommentCreateRequest

    req = CommentCreateRequest(
        content="待删除",
        author_id="user1",
        target_type="requirement",
        target_id="req_del",
    )
    created = run(create_comment(req))
    run(delete_comment(created["id"]))

    result = run(list_comments("requirement", "req_del"))
    assert len(result) == 0


# ══════════════════════════════════════════════════════════════
# 点赞
# ══════════════════════════════════════════════════════════════


def test_like_comment(test_db_path):
    """点赞评论"""
    from collab_engine import create_comment, like_comment
    from common.models import CommentCreateRequest, CommentLikeRequest

    req = CommentCreateRequest(
        content="被点赞的评论",
        author_id="user1",
        target_type="requirement",
        target_id="req_like",
    )
    created = run(create_comment(req))

    like_req = CommentLikeRequest(user_id="user2")
    result = run(like_comment(created["id"], like_req))
    assert result["liked"] is True
    assert result["likes"] == 1


def test_unlike_comment(test_db_path):
    """取消点赞"""
    from collab_engine import create_comment, like_comment
    from common.models import CommentCreateRequest, CommentLikeRequest

    req = CommentCreateRequest(
        content="被取消点赞的评论",
        author_id="user1",
        target_type="requirement",
        target_id="req_unlike",
    )
    created = run(create_comment(req))

    like_req = CommentLikeRequest(user_id="user3")
    # 点赞
    run(like_comment(created["id"], like_req))
    # 取消点赞
    result = run(like_comment(created["id"], like_req))
    assert result["liked"] is False
    assert result["likes"] == 0


# ══════════════════════════════════════════════════════════════
# Skill 文件管理（标准目录结构：SKILL.md + scripts/references/examples/assets）
# ══════════════════════════════════════════════════════════════


def test_write_and_read_skill_file(test_db_path):
    """写入并读取 Skill 文件（自动创建父目录）"""
    from collab_engine import read_skill_file, write_skill_file
    from common.models import SkillFileWriteRequest
    from skills_store import skill_root

    _seed_skill("skill_fs_1")
    result = run(
        write_skill_file(
            "skill_fs_1",
            "scripts/main.py",
            SkillFileWriteRequest(content="print('hello')"),
        )
    )
    assert result["path"] == "scripts/main.py"
    # 文件系统断言：真实落盘 + 自动建父目录
    assert (skill_root("skill_fs_1") / "scripts" / "main.py").is_file()

    data = run(read_skill_file("skill_fs_1", "scripts/main.py"))
    assert data["is_text"] is True
    assert data["content"] == "print('hello')"
    assert data["path"] == "scripts/main.py"


def test_write_skill_md_syncs_db(test_db_path):
    """写入 SKILL.md 时同步 DB 元数据（name/description/content）"""
    from collab_engine import write_skill_file
    from common.db import get_db
    from common.models import SkillFileWriteRequest

    _seed_skill("skill_md_1")
    md = "---\nname: 新名字\ndescription: 新描述\n---\n\n# 正文内容"
    result = run(write_skill_file("skill_md_1", "SKILL.md", SkillFileWriteRequest(content=md)))
    assert result["synced_db"] is True

    conn = get_db()
    row = conn.execute("SELECT name, description, content FROM skills WHERE id='skill_md_1'").fetchone()
    conn.close()
    assert row["name"] == "新名字"
    assert row["description"] == "新描述"
    assert "正文内容" in row["content"]


def test_skill_file_tree_and_stats(test_db_path):
    """目录树 + 分目录统计（scripts/references/examples/assets）"""
    from skills_store import list_tree, write_file

    _seed_skill("skill_tree_1")
    write_file("skill_tree_1", "SKILL.md", "# 技能")
    write_file("skill_tree_1", "scripts/run.py", "print(1)")
    write_file("skill_tree_1", "references/usage.md", "用法")
    write_file("skill_tree_1", "examples/demo.py", "demo")
    write_file("skill_tree_1", "notes/private.md", "自定义目录")

    tree = list_tree("skill_tree_1")
    assert tree["file_count"] == 5
    assert tree["dir_counts"] == {"scripts": 1, "references": 1, "examples": 1, "assets": 0}
    dirs = {c["name"]: c for c in tree["children"] if c["type"] == "dir"}
    assert set(dirs) == {"scripts", "references", "examples", "notes"}
    assert dirs["scripts"]["file_count"] == 1
    assert dirs["scripts"]["children"][0]["path"] == "scripts/run.py"


def test_delete_skill_file(test_db_path):
    """删除文件与目录（递归）"""
    from fastapi import HTTPException

    from collab_engine import delete_skill_file, read_skill_file
    from skills_store import skill_root, write_file

    _seed_skill("skill_del_1")
    write_file("skill_del_1", "scripts/a.py", "a")
    write_file("skill_del_1", "scripts/b.py", "b")

    run(delete_skill_file("skill_del_1", "scripts/a.py"))
    assert not (skill_root("skill_del_1") / "scripts" / "a.py").exists()
    with pytest.raises(HTTPException) as ei:
        run(read_skill_file("skill_del_1", "scripts/a.py"))
    assert ei.value.status_code == 404

    # 删除整个目录
    run(delete_skill_file("skill_del_1", "scripts"))
    assert not (skill_root("skill_del_1") / "scripts").exists()
    # 删除不存在的路径 → 404
    with pytest.raises(HTTPException) as ei2:
        run(delete_skill_file("skill_del_1", "scripts"))
    assert ei2.value.status_code == 404


def test_create_skill_folder_idempotent(test_db_path):
    """创建目录（幂等）"""
    from collab_engine import create_skill_folder
    from skills_store import skill_root

    _seed_skill("skill_dir_1")
    run(create_skill_folder("skill_dir_1", "examples/子目录"))
    assert (skill_root("skill_dir_1") / "examples" / "子目录").is_dir()
    # 重复创建不报错
    run(create_skill_folder("skill_dir_1", "examples/子目录"))


def test_upload_skill_file(test_db_path):
    """上传文件到指定目录（folder 语义）"""
    from starlette.datastructures import UploadFile

    from collab_engine import read_skill_file, upload_skill_file

    _seed_skill("skill_up_1")
    f = UploadFile(file=io.BytesIO(b"print('hello')"), filename="tool.py")
    result = run(upload_skill_file("skill_up_1", f, "scripts"))
    assert result["path"] == "scripts/tool.py"

    data = run(read_skill_file("skill_up_1", "scripts/tool.py"))
    assert data["content"] == "print('hello')"


def test_read_binary_file(test_db_path):
    """二进制文件（图片等）读取返回 is_text=False"""
    from collab_engine import read_skill_file
    from skills_store import write_file

    _seed_skill("skill_bin_1")
    write_file("skill_bin_1", "assets/logo.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    data = run(read_skill_file("skill_bin_1", "assets/logo.png"))
    assert data["is_text"] is False
    assert data["content"] == ""
    assert data["size"] == 72


def test_path_traversal_rejected(test_db_path):
    """路径穿越请求（../、绝对路径、空段）全部拒绝"""
    from fastapi import HTTPException

    from collab_engine import create_skill_folder, delete_skill_file, read_skill_file, write_skill_file
    from common.models import SkillFileWriteRequest
    from skills_store import resolve_path

    _seed_skill("skill_trav_1")
    # 底层 resolve_path 直接抛 ValueError
    with pytest.raises(ValueError):
        resolve_path("skill_trav_1", "../../etc/passwd")

    # 接口层转为 400
    for bad in ("../../etc/passwd", "scripts/../../evil", "..", "/etc/passwd", "a//b", "a/./b"):
        with pytest.raises(HTTPException) as ei:
            run(write_skill_file("skill_trav_1", bad, SkillFileWriteRequest(content="x")))
        assert ei.value.status_code == 400
        with pytest.raises(HTTPException) as ei2:
            run(read_skill_file("skill_trav_1", bad))
        assert ei2.value.status_code == 400
        with pytest.raises(HTTPException) as ei3:
            run(delete_skill_file("skill_trav_1", bad))
        assert ei3.value.status_code == 400
        with pytest.raises(HTTPException) as ei4:
            run(create_skill_folder("skill_trav_1", bad))
        assert ei4.value.status_code == 400
    # 目录内未被写入任何文件
    assert not (resolve_path("skill_trav_1", "") / "etc").exists()
