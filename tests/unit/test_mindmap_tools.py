"""v15 思维导图增强单测：节点批量编辑（树 ↔ 缩进大纲互转）+ apply-edit 端点。

覆盖：
- tree_to_outline：树 → Tab 缩进大纲（空树/空节点名安全）
- outline_to_tree：大纲 → 树（首行=根、跳级缩进自动修复、空行/空名跳过、层级与长度上限）
- 往返一致性：tree → outline → tree 结构不变
- POST /api/mindmap/apply-edit：返回规范化树
"""

import asyncio
import sys
from pathlib import Path

import pytest

BACKEND = str(Path(__file__).resolve().parents[2] / "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

USER = {"user_id": "u1", "username": "user1"}


def sample_tree():
    return {
        "name": "中心主题",
        "children": [
            {"name": "分支A", "children": [{"name": "A1", "children": []}, {"name": "A2", "children": []}]},
            {"name": "分支B", "children": []},
        ],
    }


class TestTreeToOutline:
    def test_basic_tree(self):
        from mindmap import tree_to_outline

        outline = tree_to_outline(sample_tree())
        assert outline == "中心主题\n\t分支A\n\t\tA1\n\t\tA2\n\t分支B"

    def test_empty_root(self):
        from mindmap import tree_to_outline

        assert tree_to_outline(None) == ""
        assert tree_to_outline({}) == ""

    def test_blank_node_name_skipped(self):
        from mindmap import tree_to_outline

        tree = {"name": "根", "children": [{"name": "  ", "children": []}, {"name": "有效", "children": []}]}
        assert "有效" in tree_to_outline(tree)
        assert "根\n\t有效" == tree_to_outline(tree)


class TestOutlineToTree:
    def test_standard_outline(self):
        from mindmap import outline_to_tree

        tree = outline_to_tree("中心主题\n\t分支A\n\t\tA1\n\t分支B")
        assert tree["name"] == "中心主题"
        assert [c["name"] for c in tree["children"]] == ["分支A", "分支B"]
        assert [c["name"] for c in tree["children"][0]["children"]] == ["A1"]

    def test_skip_blank_lines_and_names(self):
        from mindmap import outline_to_tree

        tree = outline_to_tree("根\n\n\t子1\n   \n\t子2")
        assert tree["name"] == "根"
        assert [c["name"] for c in tree["children"]] == ["子1", "子2"]

    def test_jump_level_auto_fixed(self):
        from mindmap import outline_to_tree

        # 跳级：第3层前没有第2层 → 自动挂到最近合法父级（分支A）
        tree = outline_to_tree("根\n\t分支A\n\t\t\t深度跳跃")
        assert tree["children"][0]["children"][0]["name"] == "深度跳跃"

    def test_single_line_becomes_root(self):
        from mindmap import outline_to_tree

        tree = outline_to_tree("只有一行")
        assert tree["name"] == "只有一行"
        assert tree["children"] == []

    def test_empty_outline_fallback(self):
        from mindmap import outline_to_tree

        tree = outline_to_tree("")
        assert tree["name"] == "未命名主题"
        assert outline_to_tree("\n\n").get("name") == "未命名主题"

    def test_name_truncated_and_level_capped(self):
        from mindmap import outline_to_tree

        long_name = "长" * 100
        tree = outline_to_tree(f"根\n{chr(9) * 20}{long_name}")
        # 20 个 Tab 封顶 6 层：仍挂在根节点下（不越级到根外）
        assert len(tree["children"][0]["name"]) <= 60


class TestRoundTrip:
    def test_tree_outline_tree_identical(self):
        from mindmap import outline_to_tree, tree_to_outline

        tree = sample_tree()
        rebuilt = outline_to_tree(tree_to_outline(tree))
        assert rebuilt == tree


class TestApplyEditEndpoint:
    def test_apply_returns_tree(self, setup_test_db):
        import mindmap as mm

        resp = asyncio.run(
            mm.apply_outline_edit(
                mm.MindMapEditRequest(outline="新主题\n\t节点1\n\t节点2"), current_user=USER
            )
        )
        assert resp["ok"] is True
        assert resp["tree"]["name"] == "新主题"
        assert [c["name"] for c in resp["tree"]["children"]] == ["节点1", "节点2"]

    def test_apply_oversize_rejected(self, setup_test_db):
        import mindmap as mm
        from fastapi import HTTPException
        from pydantic import ValidationError

        with pytest.raises((HTTPException, ValidationError)):
            asyncio.run(
                mm.apply_outline_edit(
                    mm.MindMapEditRequest(outline="x" * 20001), current_user=USER
                )
            )
