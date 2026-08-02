#!/usr/bin/env python3
"""collab_engine 单元测试 — 评论 CRUD、点赞、Skill 文件管理。"""

import asyncio
import sys
from pathlib import Path

import pytest

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

    with pytest.raises(Exception):
        CommentCreateRequest(
            content="",
            author_id="user1",
            target_type="requirement",
            target_id="req_001",
        )


def test_create_comment_missing_target(test_db_path):
    """缺少 target_type / target_id 应拒绝（Pydantic 在模型构造时校验）"""
    from common.models import CommentCreateRequest

    with pytest.raises(Exception):
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
# Skill 文件管理
# ══════════════════════════════════════════════════════════════

def test_create_skill_file(test_db_path):
    """创建 Skill 文件"""
    from collab_engine import create_skill_file
    from common.models import SkillFileCreateRequest

    _seed_skill("skill_file_1")
    req = SkillFileCreateRequest(folder="src", filename="main.py", content="print('hello')")
    result = run(create_skill_file("skill_file_1", req))
    assert "id" in result
    assert result["filename"] == "main.py"


def test_create_skill_file_empty_filename(test_db_path):
    """空文件名应拒绝（Pydantic 在模型构造时校验）"""
    from common.models import SkillFileCreateRequest

    with pytest.raises(Exception):
        SkillFileCreateRequest(folder="src", filename="", content="print('hello')")


def test_list_skill_files(test_db_path):
    """列出 Skill 文件"""
    from collab_engine import create_skill_file, list_skill_files
    from common.models import SkillFileCreateRequest

    _seed_skill("skill_file_3")
    run(create_skill_file("skill_file_3", SkillFileCreateRequest(folder="src", filename="a.py", content="a")))
    run(create_skill_file("skill_file_3", SkillFileCreateRequest(folder="src", filename="b.py", content="b")))

    result = run(list_skill_files("skill_file_3"))
    assert len(result) == 2


def test_update_skill_file(test_db_path):
    """更新 Skill 文件"""
    from collab_engine import create_skill_file, list_skill_files, update_skill_file
    from common.models import SkillFileCreateRequest, SkillFileUpdateRequest

    _seed_skill("skill_file_4")
    created = run(create_skill_file("skill_file_4",
        SkillFileCreateRequest(folder="src", filename="main.py", content="original")))
    file_id = created["id"]

    run(update_skill_file("skill_file_4", str(file_id),
        SkillFileUpdateRequest(content="updated content")))

    files = run(list_skill_files("skill_file_4"))
    assert files[0]["content"] == "updated content"


def test_delete_skill_file(test_db_path):
    """删除 Skill 文件"""
    from collab_engine import create_skill_file, delete_skill_file, list_skill_files
    from common.models import SkillFileCreateRequest

    _seed_skill("skill_file_5")
    created = run(create_skill_file("skill_file_5",
        SkillFileCreateRequest(folder="src", filename="to_delete.py", content="x")))
    file_id = created["id"]

    run(delete_skill_file("skill_file_5", str(file_id)))

    files = run(list_skill_files("skill_file_5"))
    assert len(files) == 0
