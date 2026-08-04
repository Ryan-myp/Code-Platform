#!/usr/bin/env python3
"""小游戏工坊 — AI 生成双版本小游戏（网页版 + 微信小游戏）。

- 内置经典玩法模板（贪吃蛇/2048/飞机大战/打砖块/记忆翻牌），选模板 + 输入需求 → LLM 生成
- 双版本：web/（单文件 index.html，浏览器直接玩，支持 iframe 在线试玩）+ wx/（微信小游戏原生项目）
- 在线试玩：web 版强制单文件（含内联兜底），前端 srcdoc 直接运行，无需后端静态服务
- 项目保存到 game_projects（files 为 {web: {path: content}, wx: {path: content}} JSON）
- 支持 ZIP 打包下载（web/ + wx/ 双目录）
"""

import io
import json
import logging
import re
import time
import uuid
import zipfile
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.llm import call_llm_async, log_usage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/games", tags=["小游戏工坊"])

# 内置玩法模板：玩法说明注入生成 prompt，约束游戏逻辑
TEMPLATES = [
    {
        "id": "snake",
        "name": "贪吃蛇",
        "icon": "🐍",
        "color": "from-emerald-500 to-green-600",
        "description": "经典贪吃蛇：键盘/触屏控制方向，吃食物变长，撞墙或撞自己结束",
        "play": (
            "经典贪吃蛇玩法：蛇从屏幕中央出发，吃食物（随机刷新的方块）后蛇身变长、得分增加；"
            "撞到墙壁或自己的身体游戏结束；支持键盘方向键（网页版）与触屏滑动（双版本都要支持滑动）；"
            "显示当前分数与历史最高分（本地存储）。"
        ),
    },
    {
        "id": "2048",
        "name": "2048",
        "icon": "🔢",
        "color": "from-amber-500 to-orange-600",
        "description": "数字合并：滑动合并相同数字，合成 2048 获胜",
        "play": (
            "2048 玩法：4×4 棋盘，每次滑动所有方块向该方向移动并合并相同数字（合并一次只计一次分）；"
            "每步随机生成一个 2 或 4；棋盘满且无法移动时游戏结束；合成 2048 显示胜利；"
            "支持方向键与触屏滑动，显示分数与最高分。"
        ),
    },
    {
        "id": "plane",
        "name": "飞机大战",
        "icon": "✈️",
        "color": "from-blue-500 to-indigo-600",
        "description": "射击闯关：控制飞机躲避并击落敌机，得分升级",
        "play": (
            "飞机大战玩法：玩家飞机在屏幕底部，左右移动躲避从上方下落的敌机，发射子弹击落敌机得分；"
            "敌机速度随得分逐渐加快；玩家被敌机撞到或敌机越过底线则游戏结束；"
            "支持键盘左右键（网页版）与触屏拖动；显示分数与最高分。"
        ),
    },
    {
        "id": "brick",
        "name": "打砖块",
        "icon": "🧱",
        "color": "from-red-500 to-rose-600",
        "description": "弹球消砖：挡板反弹小球，清空砖块过关",
        "play": (
            "打砖块玩法：底部挡板左右移动反弹小球，小球撞击上方砖块将其消除并得分；"
            "砖块按行排列，撞到不同行砖块得分不同；小球落到屏幕底部游戏结束，清空全部砖块获胜；"
            "支持键盘左右键（网页版）与触屏拖动挡板；显示分数、剩余砖块数与最高分。"
        ),
    },
    {
        "id": "memory",
        "name": "记忆翻牌",
        "icon": "🃏",
        "color": "from-violet-500 to-purple-600",
        "description": "配对记忆：翻牌找相同图案，步数越少越好",
        "play": (
            "记忆翻牌玩法：4×4 共 16 张卡片（8 对相同图案），点击翻开两张，图案相同则配对成功保持翻开；"
            "不同则翻回；全部配对成功获胜；记录步数，步数越少越好；"
            "支持点击/触屏翻牌；显示步数与最佳纪录（本地存储）。"
        ),
    },
    {
        "id": "tetris",
        "name": "俄罗斯方块",
        "icon": "🧩",
        "color": "from-cyan-500 to-teal-600",
        "description": "经典下落消除：七种方块旋转堆叠，满行消除，等级加速",
        "play": (
            "俄罗斯方块玩法：七种形状方块（I/O/T/S/Z/J/L）从顶部下落，玩家左右移动与旋转方块，"
            "方块落到堆叠区后固定，填满整行即消除并得分（同时消除多行有额外加分）；"
            "堆叠到顶部游戏结束；分数每过 1000 分下一等级，下落速度加快；"
            "支持键盘方向键/旋转键（网页版）与触屏滑动/点击旋转；显示分数、等级与最高分（本地存储）；"
            "显示下一个方块预览。"
        ),
    },
    {
        "id": "minesweeper",
        "name": "扫雷",
        "icon": "💣",
        "color": "from-lime-500 to-green-600",
        "description": "推理扫雷：翻格子找地雷，数字提示周边雷数，零失误过关",
        "play": (
            "扫雷玩法：9×9 棋盘随机埋 10 颗雷，点击翻格子；翻到雷游戏结束；"
            "格子显示数字表示周边 8 格地雷数量，长按/右键标记地雷；"
            "数字为 0 时自动展开相邻区域；翻开全部安全格即获胜；"
            "支持点击翻开与标记（网页版右键/长按，触屏版长按）；记录用时与最快纪录（本地存储）。"
        ),
    },
    {
        "id": "match3",
        "name": "三消消乐",
        "icon": "🍬",
        "color": "from-pink-500 to-rose-600",
        "description": "爽快三消：交换相邻糖果，三个相同即消除，连锁加分",
        "play": (
            "三消玩法：8×8 棋盘铺满不同颜色糖果（4-5 种），交换相邻两个位置，"
            "横/竖方向三个及以上相同颜色即消除并得分，上方糖果下落补位，"
            "若自动形成新的消除则连锁加分（Combo）；无法交换时自动洗牌；"
            "支持点击选中+点击相邻位置交换（或触屏滑动交换）；显示分数与最高分（本地存储），消除时有简单的粒子反馈效果。"
        ),
    },
    {
        "id": "custom",
        "name": "自定义",
        "icon": "✨",
        "color": "from-gray-500 to-gray-700",
        "description": "自由发挥：描述你的玩法，AI 设计实现",
        "play": "根据用户需求自行设计合理的玩法与界面（建议复杂度适中，可玩性优先）。",
    },
]

_GENERATE_SYSTEM = """你是一位资深游戏开发工程师，擅长 HTML5 Canvas 与微信小游戏开发。
请根据用户需求生成一个双版本小游戏：网页版 + 微信小游戏版，两个版本玩法完全一致。

硬性要求：
1. 只输出一个 JSON 对象（不要输出任何解释文字、不要用 markdown 代码块包裹），结构如下：
   {"web": {"index.html": "..."}, "wx": {"game.js": "...", "game.json": "...", "project.config.json": "..."}}
2. web 版本必须只有一个文件 index.html，CSS 与 JS 全部内联在该文件内（双击即可运行、iframe 可直接加载），
   使用 HTML5 Canvas 渲染，原生 JavaScript，不使用任何框架
3. wx 版本是微信小游戏（不是小程序！）：
   - game.js 为入口文件，使用 wx.createCanvas() 获取主画布、wx.onTouchStart/onTouchMove/onTouchEnd 处理触摸
   - game.json 配置（deviceOrientation: "portrait"、showStatusBar: false）
   - project.config.json 配置（appid 用 "touristappid" 测试号、compileType 为 "game"）
   - 微信小游戏没有 DOM，不能用 document/window/Canvas 2D 的 document.createElement，只能用小游戏 API 与 Canvas 2D 上下文
4. 双版本玩法逻辑一致：相同的规则、计分、难度曲线
5. 游戏代码必须完整可用，注释清晰，界面美观（配色协调、画布自适应屏幕）
6. 图片/音效一律用代码绘制或省略，不引用外部资源文件
7. 输出必须精简！web 版 index.html 不超过 600 行，wx 版 game.js 不超过 500 行，
   全部文件总字符数必须控制在 40000 以内，严禁超长输出
8. 游戏需真实可玩：完整游戏循环（update/render）、碰撞检测、计分与结束判定，不要留 TODO
9. 所有状态变量声明时必须初始化（如数组初始化为 []、对象初始化为 null），
   所有可能被事件回调触发的绘制/更新函数（如 resize 监听触发 draw）开头必须先判空（if (!data) return;），
   严禁出现未初始化变量被回调访问导致的运行时报错"""


class GenerateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80, description="游戏名称")
    template: str = Field("custom", description="模板 ID")
    requirement: str = Field(..., min_length=2, max_length=2000, description="玩法需求")


def _extract_json(text: str) -> dict:
    """从 LLM 输出中提取 JSON 对象（容忍 ```json 包裹与前后噪音）。"""
    text = (text or "").strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("LLM 输出中未找到 JSON 对象")
    return json.loads(text[start:end + 1])


def _inline_web_files(web: dict) -> dict:
    """把 web 版合并为单文件 index.html（供 iframe srcdoc 在线试玩）。

    - <script src="x.js"> → <script>内容</script>
    - <link rel="stylesheet" href="x.css"> → <style>内容</style>
    - 未被引用的 .js 文件追加到 </body> 前
    """
    html = (web.get("index.html") or "").strip()
    if not html:
        raise ValueError("web 版缺少 index.html")

    def repl_script(m):
        src = m.group(1)
        content = web.get(src) or web.get(src.lstrip("./"))
        return f"<script>{content}</script>" if content else m.group(0)

    def repl_style(m):
        href = m.group(1)
        content = web.get(href) or web.get(href.lstrip("./"))
        return f"<style>{content}</style>" if content else m.group(0)

    html = re.sub(r"<script[^>]+src=[\"']([^\"']+)[\"'][^>]*></script>", repl_script, html)
    html = re.sub(r"<link[^>]+href=[\"']([^\"']+\.css)[\"'][^>]*>", repl_style, html)

    # 兜底：未被引用的 JS 追加到 </body> 前
    for path, content in web.items():
        if path == "index.html" or not path.endswith(".js"):
            continue
        if path not in html and f'"{path}"' not in html:
            if "</body>" in html:
                html = html.replace("</body>", f"<script>{content}</script></body>")
            else:
                html += f"\n<script>{content}</script>"
    return {"index.html": html}


def _validate_files(files: dict) -> dict:
    """校验并整理生成结果：确保 web 单文件、wx 基础文件齐全。返回 {web, wx}。"""
    if not isinstance(files, dict) or not files:
        raise ValueError("AI 未生成任何文件")
    web = files.get("web")
    wx = files.get("wx")
    if not isinstance(web, dict) or not web:
        raise ValueError("缺少 web 版文件")
    web = _inline_web_files(web)
    result = {"web": web}
    if isinstance(wx, dict) and wx:
        # 微信小游戏必需文件兜底
        if "game.json" not in wx:
            wx["game.json"] = json.dumps(
                {"deviceOrientation": "portrait", "showStatusBar": False},
                ensure_ascii=False, indent=2,
            )
        if "project.config.json" not in wx:
            wx["project.config.json"] = json.dumps(
                {"appid": "touristappid", "compileType": "game",
                 "setting": {"urlCheck": False}, "projectname": "wxgame"},
                ensure_ascii=False, indent=2,
            )
        if "game.js" not in wx:
            raise ValueError("wx 版缺少 game.js 入口文件")
        result["wx"] = wx
    return result


@router.get("/templates")
async def list_templates(current_user: dict = require_auth()):
    return TEMPLATES


@router.get("/projects")
async def list_projects(current_user: dict = require_auth()):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, template, requirement, created_at, updated_at, favorite, tags, iterations "
        "FROM game_projects ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["tags"] = json.loads(d.get("tags") or "[]")
        except Exception:
            d["tags"] = []
        result.append(d)
    return result


@router.post("/generate")
async def generate_game(req: GenerateRequest, current_user: dict = require_auth()):
    """选模板 + 需求 → AI 生成双版本小游戏。"""
    tpl = next((t for t in TEMPLATES if t["id"] == req.template), None)
    if req.template != "custom" and not tpl:
        raise HTTPException(400, f"未知模板: {req.template}")

    user_prompt = f"""游戏名称：{req.name}
选择模板：{tpl['name'] if tpl else '自定义'}
模板玩法：
{tpl['play'] if tpl else '根据用户需求自行设计玩法。'}

用户需求：
{req.requirement}

请生成双版本小游戏 JSON。"""

    start = time.time()
    try:
        result = await call_llm_async(_GENERATE_SYSTEM, user_prompt, max_tokens=16000, temperature=0.4)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"生成失败: {e}") from e

    files = None
    try:
        files = _validate_files(_extract_json(result))
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning("game JSON parse failed (will retry compact): %s", e)
        # 输出截断/超长：自动降级为精简版重试（优先保证 web 单文件可玩）
        try:
            retry_prompt = user_prompt + (
                "\n\n重要：上次输出因过长被截断导致失败。本次请严格精简：\n"
                "1. web 版 index.html 控制在 300 行以内，wx 版 game.js 控制在 250 行以内\n"
                "2. 只保留核心玩法循环、碰撞检测与计分，去掉非必要装饰\n"
                "3. 全部文件总字符数不超过 20000"
            )
            result = await call_llm_async(_GENERATE_SYSTEM, retry_prompt, max_tokens=10000, temperature=0.3)
            files = _validate_files(_extract_json(result))
        except (ValueError, json.JSONDecodeError, HTTPException) as e2:
            raise HTTPException(502, f"AI 输出格式异常（已自动重试精简版仍失败），请重试或更换模型。详情: {e2}") from e2

    proj_id = f"game_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute(
        """INSERT INTO game_projects (id, name, template, requirement, files, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?)""",
        (proj_id, req.name, req.template, req.requirement,
         json.dumps(files, ensure_ascii=False), now, now),
    )
    conn.commit()
    conn.close()

    elapsed = round(time.time() - start, 2)
    log_usage("game_generate", len(user_prompt), len(result), elapsed)
    return {
        "id": proj_id,
        "name": req.name,
        "template": req.template,
        "versions": list(files.keys()),
        "file_count": sum(len(v) for v in files.values()),
        "files": files,
    }


@router.get("/deploy-guide")
async def deploy_guide(current_user: dict = require_auth()):
    """微信小游戏部署指引。注意：必须注册在 /{proj_id} 之前，避免路径冲突。"""
    return {
        "steps": [
            "下载生成的 ZIP 项目包并解压，`wx/` 目录就是微信小游戏项目",
            "安装微信开发者工具（微信公众平台官网 → 下载 → 稳定版），登录时选择「小游戏」类型",
            "打开开发者工具 → 「导入项目」→ 选择解压后的 `wx/` 目录",
            "AppID 选择「测试号」或填入你的小游戏 AppID，点击「编译」即可在模拟器试玩",
            "确认无误后：登录 mp.weixin.qq.com → 小游戏 → 开发管理 → 版本管理 → 上传代码",
            "在微信公众平台提交审核，审核通过后点击「发布」即可上线",
            "网页版（web/index.html）可直接双击运行，或部署到任意静态网站（如 GitHub Pages）分享给朋友",
        ],
        "note": "个人主体即可注册小游戏账号；用「测试号」可以先体验完整开发流程。",
    }


@router.get("/stats")
async def game_stats(current_user: dict = require_auth()):
    """小游戏工坊统计：项目数 / 模板分布 / 总迭代次数 / 收藏数。"""
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) AS n FROM game_projects").fetchone()["n"]
    favorites = conn.execute("SELECT COUNT(*) AS n FROM game_projects WHERE favorite=1").fetchone()["n"]
    total_iter = conn.execute("SELECT COALESCE(SUM(iterations),0) AS n FROM game_projects").fetchone()["n"]
    template_dist = {}
    for r in conn.execute("SELECT template, COUNT(*) AS n FROM game_projects GROUP BY template").fetchall():
        tpl = next((t for t in TEMPLATES if t["id"] == r["template"]), None)
        template_dist[tpl["name"] if tpl else r["template"]] = r["n"]
    conn.close()
    return {"total": total, "favorites": favorites, "total_iterations": total_iter, "template_dist": template_dist}


class RenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=80, description="新名称")
    tags: list[str] = Field(default_factory=list, description="标签列表")


@router.put("/{proj_id}")
async def rename_project(proj_id: str, req: RenameRequest, current_user: dict = require_auth()):
    """重命名游戏项目 / 更新标签。"""
    conn = get_db()
    row = conn.execute("SELECT id FROM game_projects WHERE id=?", (proj_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "游戏项目不存在")
    conn.execute(
        "UPDATE game_projects SET name=?, tags=?, updated_at=? WHERE id=?",
        (req.name.strip(), json.dumps(req.tags[:10], ensure_ascii=False), datetime.now().isoformat(), proj_id),
    )
    conn.commit()
    conn.close()
    return {"success": True, "name": req.name.strip(), "tags": req.tags[:10]}


@router.post("/{proj_id}/favorite")
async def toggle_favorite(proj_id: str, current_user: dict = require_auth()):
    """收藏/取消收藏游戏项目（toggle）。"""
    conn = get_db()
    row = conn.execute("SELECT favorite FROM game_projects WHERE id=?", (proj_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "游戏项目不存在")
    new_val = 0 if row["favorite"] else 1
    conn.execute("UPDATE game_projects SET favorite=? WHERE id=?", (new_val, proj_id))
    conn.commit()
    conn.close()
    return {"success": True, "favorite": bool(new_val)}


class EvolveRequest(BaseModel):
    requirement: str = Field(..., min_length=2, max_length=2000, description="迭代需求")


_EVOLVE_SYSTEM = """你是一位资深游戏开发工程师，正在对一个已存在的双版本小游戏进行升级迭代。
请根据用户的新需求修改现有代码，两个版本玩法保持同步。

硬性要求：
1. 只输出一个 JSON 对象（不要输出任何解释文字、不要用 markdown 代码块包裹），结构如下：
   {"web": {"index.html": "..."}, "wx": {"game.js": "...", "game.json": "...", "project.config.json": "..."}}
2. 必须输出完整文件内容（不是 diff），基于下方现有代码修改：只改需求涉及的逻辑，其余保持不变
3. web 版保持单文件 index.html（CSS/JS 内联），wx 版保持微信小游戏 API 风格（无 DOM）
4. 双版本玩法逻辑一致：相同的规则、计分、难度曲线；新增功能两个版本都要有
5. 代码完整可用，注释清晰，界面美观；不引用外部资源文件
6. 输出必须精简！web 版 index.html 不超过 700 行，wx 版 game.js 不超过 600 行，
   全部文件总字符数必须控制在 50000 以内
7. 所有状态变量声明时必须初始化，事件回调触发的绘制/更新函数开头必须先判空，严禁运行时错误"""


@router.post("/{proj_id}/evolve")
async def evolve_game(proj_id: str, req: EvolveRequest, current_user: dict = require_auth()):
    """AI 二次迭代：基于现有代码 + 新需求，生成升级版双版本代码（覆盖保存，保留历史需求日志）。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM game_projects WHERE id=?", (proj_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "游戏项目不存在")
    files = json.loads(row["files"] or "{}")
    if not files:
        conn.close()
        raise HTTPException(400, "项目没有代码文件，无法迭代")

    # 注入现有代码（截断保护 token 上限）
    web_html = (files.get("web", {}).get("index.html") or "")[:24000]
    wx_js = (files.get("wx", {}).get("game.js") or "")[:20000]
    user_prompt = f"""游戏名称：{row['name']}

现有网页版代码（web/index.html，共 {len(web_html)} 字符）：
```
{web_html}
```

现有微信小游戏版代码（wx/game.js，共 {len(wx_js)} 字符）：
```
{wx_js}
```

用户的迭代需求：
{req.requirement}

请基于现有代码生成升级后的双版本小游戏 JSON。"""

    start = time.time()
    try:
        result = await call_llm_async(_EVOLVE_SYSTEM, user_prompt, max_tokens=16000, temperature=0.4)
    except HTTPException:
        conn.close()
        raise
    except Exception as e:
        conn.close()
        raise HTTPException(500, f"迭代生成失败: {e}") from e

    try:
        new_files = _validate_files(_extract_json(result))
    except (ValueError, json.JSONDecodeError) as e:
        conn.close()
        raise HTTPException(502, f"AI 输出格式异常，请重试。详情: {e}") from e

    # 合并保护：AI 输出缺失的版本/文件保留旧代码，避免迭代丢文件
    for ver in ("web", "wx"):
        if ver not in new_files and ver in files:
            new_files[ver] = files[ver]
        elif ver in new_files and ver in files:
            for path, content in files[ver].items():
                if path not in new_files[ver]:
                    new_files[ver][path] = content

    # 迭代日志：保留历史需求，追加本次
    try:
        log = json.loads(row["iteration_log"] or "[]")
    except Exception:
        log = []
    log.append({
        "requirement": req.requirement,
        "created_at": datetime.now().isoformat(),
        "chars": len(result),
    })
    conn.execute(
        """UPDATE game_projects SET files=?, iterations=iterations+1, iteration_log=?, updated_at=?
           WHERE id=?""",
        (json.dumps(new_files, ensure_ascii=False), json.dumps(log[-20:], ensure_ascii=False),
         datetime.now().isoformat(), proj_id),
    )
    conn.commit()
    conn.close()

    elapsed = round(time.time() - start, 2)
    log_usage("game_evolve", len(user_prompt), len(result), elapsed)
    return {
        "id": proj_id,
        "name": row["name"],
        "versions": list(new_files.keys()),
        "file_count": sum(len(v) for v in new_files.values()),
        "files": new_files,
        "iterations": len(log),
    }


@router.get("/{proj_id}")
async def get_project(proj_id: str, current_user: dict = require_auth()):
    conn = get_db()
    row = conn.execute("SELECT * FROM game_projects WHERE id=?", (proj_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "游戏项目不存在")
    d = dict(row)
    d["files"] = json.loads(d.get("files") or "{}")
    return d


@router.delete("/{proj_id}")
async def delete_project(proj_id: str, current_user: dict = require_auth()):
    conn = get_db()
    conn.execute("DELETE FROM game_projects WHERE id=?", (proj_id,))
    conn.commit()
    conn.close()
    return {"success": True}


@router.get("/{proj_id}/export-zip")
async def export_zip(proj_id: str, current_user: dict = require_auth()):
    conn = get_db()
    row = conn.execute("SELECT * FROM game_projects WHERE id=?", (proj_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "游戏项目不存在")
    files = json.loads(row["files"] or "{}")
    if not files:
        raise HTTPException(400, "项目没有文件")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for version in ("web", "wx"):
            if version not in files:
                continue
            for path in sorted(files[version].keys()):
                zf.writestr(f"{version}/{path.lstrip('/')}", files[version][path])
        # 根目录说明
        zf.writestr(
            "README.txt",
            f"《{row['name']}》小游戏项目包\n"
            "├── web/ 网页版：index.html 双击即可在浏览器游玩，也可部署到任意网站\n"
            "└── wx/   微信小游戏版：用微信开发者工具（小游戏类型）导入此目录\n",
        )
    data = buf.getvalue()
    # Content-Disposition：中文名走 RFC 5987 编码
    from urllib.parse import quote

    filename = f"{row['name']}.zip"
    try:
        filename.encode("latin-1")
        ascii_name = filename
    except UnicodeEncodeError:
        ascii_name = "game.zip"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}"
            )
        },
    )


def get_db():
    from common.db import get_db as _get_db

    return _get_db()
