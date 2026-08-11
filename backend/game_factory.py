#!/usr/bin/env python3
"""小游戏工坊 — AI 生成双版本小游戏（网页版 + 微信小游戏）。

- 内置经典玩法模板（贪吃蛇/2048/飞机大战/打砖块/记忆翻牌），选模板 + 输入需求 → LLM 生成
- 双版本：web/（单文件 index.html，浏览器直接玩，支持 iframe 在线试玩）+ wx/（微信小游戏原生项目）
- 在线试玩：web 版强制单文件（含内联兜底），前端 srcdoc 直接运行，无需后端静态服务
- 项目保存到 game_projects（files 为 {web: {path: content}, wx: {path: content}} JSON）
- 支持 ZIP 打包下载（web/ + wx/ 双目录）
"""

import asyncio
import io
import json
import logging
import os
import re
import time
import uuid
import zipfile
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from common.auth import require_auth
from common.llm import call_llm_async, log_usage
from content_safety import check_text, quality_report
from publish_kit import build_publish_zip, license_text, pack_dir_name, publish_registry
from task_queue import create_task, register_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/games", tags=["小游戏工坊"])

# 内置玩法模板：玩法说明注入生成 prompt，约束游戏逻辑
TEMPLATES = [
    {
        "id": "snake",
        "name": "贪吃蛇",
        "icon": "🐍",
        "color": "from-emerald-500 to-green-600",
        "category": "休闲",
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
        "category": "休闲",
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
        "category": "休闲",
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
        "category": "休闲",
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
        "category": "休闲",
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
        "category": "休闲",
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
        "category": "益智",
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
        "category": "休闲",
        "description": "爽快三消：交换相邻糖果，三个相同即消除，连锁加分",
        "play": (
            "三消玩法：8×8 棋盘铺满不同颜色糖果（4-5 种），交换相邻两个位置，"
            "横/竖方向三个及以上相同颜色即消除并得分，上方糖果下落补位，"
            "若自动形成新的消除则连锁加分（Combo）；无法交换时自动洗牌；"
            "支持点击选中+点击相邻位置交换（或触屏滑动交换）；显示分数与最高分（本地存储），消除时有简单的粒子反馈效果。"
        ),
    },
    {
        "id": "tower-defense",
        "name": "策略塔防",
        "icon": "🏰",
        "color": "from-orange-500 to-amber-600",
        "category": "策略",
        "description": "策略塔防：布塔防守，升级炮塔，抵御一波波敌人进攻",
        "play": (
            "策略塔防玩法：敌人沿固定路径从入口走向终点，玩家在路径旁建造炮塔阻止敌人抵达终点（漏掉扣生命，生命归零失败）；"
            "至少 3 种炮塔（如箭塔/炮塔/冰塔），各有不同射程、伤害、攻速与特效（冰塔减速）；"
            "击杀敌人获得金币，可建造新塔或升级已有塔（至多 3 级，升级提升属性）；"
            "波次系统：至少 5 波敌人，敌人种类逐波增加（普通/快速/重甲/首领），波次间自动开启建造阶段；"
            "建造/升级通过点击塔位弹出选择面板（Canvas 内绘制按钮）完成；"
            "支持触屏点击与鼠标点击；显示金币、生命、波次与击杀数；本地存储最高纪录。"
        ),
    },
    {
        "id": "turn-rpg",
        "name": "回合制RPG",
        "icon": "🧙",
        "color": "from-purple-500 to-indigo-600",
        "category": "回合制",
        "description": "回合制战斗：角色属性克制，技能抉择，击败怪物首领闯关",
        "play": (
            "回合制 RPG 战斗玩法：玩家与敌人轮流行动（回合制状态机：玩家回合→选择指令→结算→敌人回合→循环）；"
            "玩家角色拥有 HP/MP/攻击力/防御力与至少 3 个技能（普通攻击/强力技能消耗 MP/防御姿态），技能各有特效与消耗；"
            "至少 3 类敌人（史莱姆/骷髅/首领龙），属性逐渐增强，击败后获得经验与金币；"
            "经验累积升级：等级提升增加属性上限并恢复满 HP/MP；金币可在商店购买药水/装备（商店在关卡间出现）；"
            "连战系统：连续击败 3 个敌人后遭遇首领，击败首领通关；死亡后显示重试；"
            "战斗指令通过 Canvas 内绘制按钮面板选择（攻击/技能/防御/道具）；"
            "显示双方 HP/MP 血条、回合提示文字与技能动画效果；支持点击/触屏操作。"
        ),
    },
    {
        "id": "card-battle",
        "name": "回合制卡牌",
        "icon": "🎴",
        "color": "from-rose-500 to-pink-600",
        "category": "回合制",
        "description": "卡牌对战：抽卡出牌，能量管理，击败对手获胜",
        "play": (
            "回合制卡牌对战玩法：玩家与 AI 对手轮流回合，每回合开始抽 1 张牌（手牌上限 5，回合结束丢弃超出部分）；"
            "每回合获得 1 点能量（上限 3），打出卡牌消耗能量；至少 10 种卡牌：攻击类（火球/剑击/连击）、防御类（护盾/治疗）、效果类（抽牌/加能量/强化）；"
            "双方各有 HP（玩家 30，AI 对手 25）与护盾值，护盾优先抵消伤害；"
            "AI 对手按简单启发式决策（优先攻击、低血量时防御/治疗）；"
            "打出卡牌时点击手牌区域的卡牌再点击「出牌」按钮（Canvas 内绘制），有卡牌拖拽/点击高亮反馈；"
            "一方 HP 归零即分出胜负；显示双方 HP/护盾/能量、当前回合数与卡牌动画（出牌飞行动效）；"
            "支持点击/触屏操作；本地存储最高连胜纪录。"
        ),
    },
    {
        "id": "gomoku",
        "name": "五子棋",
        "icon": "⚫",
        "color": "from-slate-500 to-gray-700",
        "category": "回合制",
        "description": "回合制棋类：与 AI 对弈五子棋，先连五子者胜，难度可选",
        "play": (
            "五子棋玩法：15×15 棋盘，玩家执黑先手、AI 执白后手，轮流落子（回合制），横/竖/斜任意方向连成五子即获胜；"
            "AI 采用启发式评分算法：遍历所有空位，按攻防权重评分（成五/活四/冲四/活三/眠三/活二等棋型加权），选最高分落子，兼顾进攻与防守；"
            "提供 3 档 AI 难度（简单/普通/困难），简单档随机夹杂低权重落子、困难档纯最优决策；"
            "落子后显示最后一步标记（如红点），棋盘有木纹底色与网格线，棋子有立体渐变质感；"
            "支持悔棋（回退最后一步）、重新开局；提示当前轮到谁，胜负出现时高亮获胜连线；"
            "支持点击/触屏落子；本地存储胜/负/平统计。"
        ),
    },
    {
        "id": "idle-manager",
        "name": "放置经营",
        "icon": "🏪",
        "color": "from-teal-500 to-emerald-600",
        "category": "模拟",
        "description": "放置经营：开店摆摊自动赚钱，升级扩张，离线收益",
        "play": (
            "放置经营玩法：经营一家小吃摊/小店，顾客自动上门消费产生金币收入（放置挂机核心）；"
            "至少 4 种可解锁设施（摊位/货架/招牌/员工），每个设施可升级（至多 5 级），提升每秒收入；"
            "收入自动累积，玩家点击「收取」或自动入账；升级设施需要花费金币，设施间有前置解锁关系（如先摊位后货架）；"
            "成就系统：达成累计收入里程碑（如 100/1000/10000 金币）触发成就弹窗；"
            "离线收益：重进游戏时按离线时长发放 50% 收益；"
            "界面为 Canvas 绘制：店铺场景 + 底部设施升级面板（点击设施弹出升级/价格按钮），金币飘字动效；"
            "支持点击/触屏操作；本地存储存档（金币/设施等级/成就）。"
        ),
    },
    {
        "id": "quiz",
        "name": "答题闯关",
        "icon": "🧠",
        "color": "from-yellow-500 to-amber-600",
        "category": "益智",
        "description": "益智答题：多类型题库闯关，答错扣命，限时挑战",
        "play": (
            "答题闯关玩法：连续答对闯关，题库至少 15 题覆盖常识/数学/成语/科学多类型，每题 4 个选项；"
            "答对得分+1 并进入下一题，答错扣 1 条命（初始 3 条命），命归零游戏结束；"
            "每题限时 15 秒，超时视为答错；连续答对 5 题触发「连击」提示加分；"
            "题目与选项在 Canvas 内绘制（题目顶部、四个选项按钮），选中后立即显示对错反馈（绿/红高亮）再进下一题；"
            "通关后显示得分、正确率与最高纪录（本地存储 Top 5），支持重玩；"
            "题库内置在代码中（数组常量），可循环随机出题不重复（用完洗牌重抽）；"
            "支持点击/触屏选择选项；界面活泼配色，有答题音效（对/错）。"
        ),
    },
    {
        "id": "runner",
        "name": "无尽跑酷",
        "icon": "🏃",
        "color": "from-indigo-500 to-blue-600",
        "category": "休闲",
        "description": "无尽跑酷：跳跃/下滑躲避障碍，速度渐快，吃金币得分",
        "play": (
            "无尽跑酷玩法：角色在横向卷轴场景中自动向前奔跑，玩家控制跳跃（点击/上滑）与下滑（下滑键/下滑手势）躲避障碍物；"
            "至少 3 种障碍（矮栏/高栏/空中障碍），速度随得分逐渐加快；"
            "拾取金币加分，金币有飘字反馈；撞到障碍游戏结束；"
            "场景有滚动背景层（远景/近景视差），角色有奔跑/跳跃动画帧；"
            "支持键盘空格/上键（网页版）与触屏点击/上滑（微信版）；显示得分、金币数与历史最高分（本地存储）。"
        ),
    },
    {
        "id": "whack",
        "name": "打地鼠",
        "icon": "🔨",
        "color": "from-amber-500 to-yellow-600",
        "category": "休闲",
        "description": "限时敲击：地鼠冒头即敲，敲中得分，别误敲炸弹",
        "play": (
            "打地鼠玩法：3×3 地洞网格，地鼠随机从洞中冒头（每次 1-3 只），玩家点击敲击得分；"
            "地鼠冒头停留 0.8-1.5 秒后缩回；偶发冒炸弹，敲中炸弹扣分；"
            "60 秒限时，倒计时结束显示本局得分与最高分；"
            "地鼠有探出/缩回动画与敲击命中反馈（星星飘字）；"
            "支持点击/触屏敲击；显示得分、剩余时间与历史最高分（本地存储）。"
        ),
    },
    {
        "id": "pong",
        "name": "乒乓对决",
        "icon": "🏓",
        "color": "from-sky-500 to-cyan-600",
        "category": "休闲",
        "description": "经典乒乓：挡板反弹小球，率先得 11 分获胜，可双人对战",
        "play": (
            "乒乓对决玩法：竖屏上下分区，玩家挡板在下、AI 挡板在上，小球在中间反弹运动；"
            "玩家左右移动挡板接球，球落到底线对手得分；先得 11 分获胜（分差需 ≥2）；"
            "AI 挡板追踪球的水平位置（带移动速度上限与随机误差，难度适中）；"
            "小球碰到挡板时角度随击中位置变化，速度随回合数轻微加快；"
            "得分时有提示文字与音效，中场休息 1 秒；"
            "支持键盘左右键（网页版）与触屏拖动（微信版）；显示双方得分与历史最高分。"
        ),
    },
    {
        "id": "sudoku",
        "name": "数独",
        "icon": "🧮",
        "color": "from-blue-500 to-indigo-600",
        "category": "益智",
        "description": "经典数独：九宫格推理填数，三档难度，即时校验",
        "play": (
            "数独玩法：9×9 棋盘（3×3 宫），初始预置部分数字（简单 36 格/中等 30 格/困难 24 格，内置题库数组至少 3 题或按难度生成）；"
            "点击格子选中（高亮同行同列同宫），再点数字面板（1-9）填入；填错红字提示、可擦除；"
            "辅助功能：选中格同数字高亮、剩余数字计数、计时器与错误次数统计；"
            "全部填对即胜利，显示用时与历史最佳（本地存储 Top 5）；"
            "支持点击/触屏操作；棋盘数字与候选区清晰可读，配色护眼。"
        ),
    },
    {
        "id": "rhythm",
        "name": "节奏音游",
        "icon": "🎵",
        "color": "from-fuchsia-500 to-pink-600",
        "category": "音游",
        "description": "节奏打击：音符随音乐下落，精准敲击得分，连击 Combo 加成",
        "play": (
            "节奏音游玩法：音符沿判定线从上方下落（至少 3 个轨道），玩家在音符到达判定线时点击对应轨道敲击；"
            "判定分 Perfect/Great/Good/Miss 四档（时间窗口与分数不同，Perfect 最高），连续 Perfect 累计 Combo 并额外加分；"
            "至少内置 1 首可播放曲目（WebAudio 程序化合成旋律，含节拍驱动），谱面为代码内数组（音符时间/轨道）；"
            "生命值系统：Miss 扣生命，生命归零失败；曲终结算分数、最大 Combo、评级（S/A/B/C）；"
            "界面为 Canvas 绘制：背景星空动效随节拍脉冲、音符下落的拖尾效果、Perfect/Great 判定飘字；"
            "支持键盘按键（网页版可自定义键位映射）与触屏点击轨道（微信版）；显示分数、Combo 与最高纪录（本地存储）。"
        ),
    },
    {
        "id": "escape",
        "name": "密室逃脱",
        "icon": "🔐",
        "color": "from-stone-500 to-neutral-700",
        "category": "解谜",
        "description": "解谜逃脱：线索收集与道具组合，破解谜题逃离密室",
        "play": (
            "密室逃脱玩法：一个封闭房间场景（至少 6 个可交互点：柜子/保险箱/画框/书架/地毯/门），玩家点击探索收集线索与道具；"
            "至少 4 个关联谜题：数字密码锁（线索藏在画框数字/书页页码）、图案旋转对位、颜色组合、道具组合使用（如钥匙+柜子）；"
            "道具栏：点击道具可查看/使用/组合，组合结果提示；解错有轻提示但不扣分（以解谜流畅为优先）；"
            "全部谜题解开后门解锁，显示通关用时与步数，本地存储最佳纪录 Top 5；"
            "场景为 Canvas 绘制：房间手绘风透视场景、交互点高亮呼吸光圈、道具放大查看弹层、谜题面板独立绘制；"
            "支持点击/触屏操作；每解开一个谜题有提示音与飘字反馈，提供「提示」按钮（消耗提示次数，最多 3 次）。"
        ),
    },
    {
        "id": "platformer",
        "name": "平台跳跃",
        "icon": "🦘",
        "color": "from-lime-500 to-green-600",
        "category": "休闲",
        "description": "横版跳跃：闯关收集金币，躲避陷阱，抵达终点旗杆过关",
        "play": (
            "平台跳跃玩法：横向卷轴关卡（至少 3 关，每关不同地形主题：草地/洞穴/雪地），角色左右移动 + 跳跃（可二段跳）；"
            "关卡元素：平台/移动平台/尖刺陷阱/金币/终点旗杆；踩到尖刺或坠落深渊掉 1 条命（初始 3 条），命尽游戏结束；"
            "收集金币过关时结算（每关 5-10 枚，集齐有额外奖励）；抵达旗杆进入下一关，通关后显示总分与用时；"
            "卷轴镜头跟随角色（保留回头空间），有视差背景层与粒子效果（跳跃尘土/金币闪光）；"
            "物理：重力/跳跃高度/移动速度手感调优，移动平台来回匀速运动（角色站上平台随动）；"
            "支持键盘左右/空格（网页版）与触屏虚拟按键（微信版：左/右/跳跃三键）；显示关卡、生命、金币与最高分（本地存储）。"
        ),
    },
    {
        "id": "custom",
        "name": "自定义",
        "icon": "✨",
        "color": "from-gray-500 to-gray-700",
        "category": "自定义",
        "description": "自由发挥：描述你的玩法，AI 设计实现",
        "play": "根据用户需求自行设计合理的玩法与界面（建议复杂度适中，可玩性优先）。",
    },
]

_GENERATE_SYSTEM = """你是一位资深游戏开发工程师，擅长 HTML5 Canvas 与微信小游戏开发，作品需达到可上架商店的商用品质。
请根据用户需求生成一个双版本小游戏：网页版 + 微信小游戏版，两个版本玩法完全一致。

商用级硬性要求：
1. 只输出一个 JSON 对象（不要输出任何解释文字、不要用 markdown 代码块包裹），结构如下：
   {"web": {"index.html": "..."}, "wx": {"game.js": "...", "game.json": "...", "project.config.json": "..."}}
2. web 版本必须只有一个文件 index.html，CSS 与 JS 全部内联在该文件内（双击即可运行、iframe 可直接加载），
   使用 HTML5 Canvas 渲染，原生 JavaScript，不使用任何框架
3. wx 版本是微信小游戏（不是小程序！）：
   - game.js 为入口文件，使用 wx.createCanvas() 获取主画布、wx.onTouchStart/onTouchMove/onTouchEnd 处理触摸
   - game.json 配置（deviceOrientation: "portrait"、showStatusBar: false）
   - project.config.json 配置（appid 用 "touristappid" 测试号、compileType 为 "game"）
   - 微信小游戏没有 DOM，不能用 document/window/Canvas 2D 的 document.createElement，只能用小游戏 API 与 Canvas 2D 上下文
4. 双版本玩法逻辑一致：相同的规则、计分、难度曲线；
   两个版本都必须完整输出、缺一不可：建议先输出 wx 版（体积较小）再输出 web 版，
   严禁只输出一个版本或将 wx 版简写成占位/注释；若代码量大，适当精简注释与重复代码
5. 必须包含完整游戏状态机与界面（商用游戏最低标准，双版本都要有）：
   - 开始界面：游戏标题、一句玩法说明、操作提示、「开始游戏」按钮（网页版可用 Enter/空格键，微信版触屏按钮）
   - 游戏中：完整循环（update/render）、碰撞检测、计分、难度曲线
   - 暂停功能：网页版按 P 或 Esc 暂停/继续并显示半透明暂停遮罩，微信版提供屏幕暂停按钮
   - 结束界面：显示本局得分、历史最高分、「再来一局」按钮
   - 排行榜：本地存储保存最高分 Top 5（网页版 localStorage，微信版 wx.setStorageSync），允许输入昵称（默认"我"）
6. 商用级表现力（全部用代码实现，禁止引用任何外部资源文件）：
   - 音效：用 WebAudio 程序化合成至少 3 种音效（得分/碰撞/按钮点击），微信版用 wx.createWebAudioContext 实现同款音效
   - 动效：得分飘字、消除/击中时的粒子爆炸反馈、按钮按下反馈
   - 视觉：渐变色背景或星空氛围层、圆角按钮、统一配色方案，避免大面积纯色块的廉价感
7. 代码必须完整可用，注释清晰，界面美观，画布自适应屏幕（含 resize 处理）
8. 输出控制在合理范围：web 版 index.html 不超过 1000 行，wx 版 game.js 不超过 900 行，总字符数 70000 以内；不要写与玩法无关的冗余代码
9. 所有状态变量声明时必须初始化（如数组初始化为 []、对象初始化为 null），
   所有可能被事件回调触发的绘制/更新函数（如 resize 监听触发 draw）开头必须先判空（if (!data) return;），
   严禁出现未初始化变量被回调访问导致的运行时报错

回合制/策略/模拟类游戏专项要求（仅当所选模板属于这些类型时强制执行，即时类游戏忽略）：
A. 回合状态机：必须用 phase 状态字段管理回合流转（如 player-turn → resolve → enemy-turn → player-turn），
   每个阶段有独立的 update/处理函数，回合切换时显示过渡提示文字与动效
B. AI 对手决策：敌方/AI 行动必须实现明确的决策函数（如启发式评分/规则优先级），
   严禁 AI 每回合随机乱动；决策后给出 0.5-1s 的思考/行动动画延迟再结算
C. 资源经济系统：金币/能量/MP 等资源必须有获取与消耗的完整闭环，
   资源不足时按钮置灰并给出提示，不允许出现负资源
D. 操作面板 UI：选择类操作（塔位建造/战斗指令/卡牌出牌/设施升级）必须用 Canvas 内绘制的按钮面板实现，
   点击区域命中检测要覆盖按钮绘制区域，面板打开时游戏主体暂停/不受影响
E. 棋盘/网格类：格子坐标换算统一用 (col,row) 与像素 (x,y) 的转换函数，
   点击判定用格坐标而非像素直接比较，边界检查必须完整（拒绝越界落子/移动）
F. 数值平衡：回合制战斗单局时长控制在 3-8 分钟，敌人强度随关卡递进，
   玩家平均 3 次尝试内可通关首关，避免数值崩坏（如敌人秒杀或玩家无双）
G. 双版本一致：回合逻辑、AI 决策、资源规则在网页版与微信版完全一致，
   微信版用 wx.onTouchStart 做按钮/棋盘点击命中，禁止使用 document 事件"""


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
    raw = text[start : end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        # 截断修复：输出接近 token 上限被截断时，从出错位置回退到引号边界再补全闭合
        fixed = _repair_truncated_json(raw, e.pos)
        if fixed is not None:
            return fixed
        raise


def _repair_truncated_json(raw: str, err_pos: int) -> dict | None:
    """尝试修复被截断的 JSON：从错误位置向前回退，补全未闭合的引号/数组/对象。

    模型输出接近 token 上限被截断时，JSON 尾部不完整（如字符串未闭合、
    数组/对象缺少闭合符），从截断点逐字符回退并尝试多种闭合方式。
    """
    if err_pos <= 0 or err_pos > len(raw):
        return None
    for back in range(min(err_pos, 400)):
        seg = raw[: err_pos - back].rstrip()
        for closer in ('"', '"}', '"]', '"}}', '"]}', "}", "]}", '}"'):
            try:
                return json.loads(seg + closer)
            except (json.JSONDecodeError, ValueError):
                continue
    return None


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
    # 微信版为交付核心之一：缺失或 game.js 为空直接判定失败（触发自动重试）
    if not isinstance(wx, dict) or not wx or not (wx.get("game.js") or "").strip():
        raise ValueError("wx 版缺失或 game.js 为空，必须输出完整的双版本")
    # 微信小游戏必需文件兜底
    if "game.json" not in wx:
        wx["game.json"] = json.dumps(
            {"deviceOrientation": "portrait", "showStatusBar": False},
            ensure_ascii=False,
            indent=2,
        )
    if "project.config.json" not in wx:
        wx["project.config.json"] = json.dumps(
            {
                "appid": "touristappid",
                "compileType": "game",
                "setting": {"urlCheck": False},
                "projectname": "wxgame",
            },
            ensure_ascii=False,
            indent=2,
        )
    if "game.js" not in wx:
        raise ValueError("wx 版缺少 game.js 入口文件")
    result["wx"] = wx
    return result


def _node_check_js(js: str) -> tuple[bool, str]:
    """node --check 语法门禁：校验 JS 代码语法（node 不可用时跳过放行）。"""
    import subprocess
    import tempfile

    try:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(js)
            tmp = f.name
        try:
            r = subprocess.run(["node", "--check", tmp], capture_output=True, text=True, timeout=20)
            if r.returncode == 0:
                return True, "语法通过"
            return False, (r.stderr or r.stdout or "").strip()[:400]
        finally:
            os.unlink(tmp)
    except FileNotFoundError:
        return True, "node 不可用，跳过"
    except Exception as e:
        return True, f"校验器异常，跳过: {e}"


# 商用要素门禁：生成的游戏必须包含以下能力（双版本任一命中即可）
_FEATURE_SPECS = [
    ("Canvas 渲染", ["getContext", "createCanvas"]),
    ("开始界面", ["开始游戏", "startGame"]),
    ("暂停功能", ["暂停", "pause"]),
    ("结束界面", ["再来一局", "gameOver", "restart"]),
    ("最高分记录", ["最高分", "best", "localStorage", "setStorage"]),
    ("程序化音效", ["AudioContext", "oscillator"]),
    ("粒子动效", ["particle", "粒子"]),
]


def _check_html_pairs(html: str) -> str | None:
    """HTML 结构门禁：script/style 开闭标签计数配对 + canvas/内联脚本入口存在，错误返回问题描述。"""
    if not html:
        return "缺少 index.html"
    for tag in ("script", "style"):
        opens = len(re.findall(rf"<{tag}[^>]*>", html))
        closes = len(re.findall(rf"</{tag}>", html))
        if opens != closes:
            return f"<{tag}> 标签不配对（开 {opens} / 闭 {closes}）"
    if "<canvas" not in html:
        return "缺少 <canvas> 画布元素"
    if "<script" not in html:
        return "缺少 <script> 脚本入口"
    return None


def _qc_check(files: dict) -> dict:
    """生成产物质量门禁（QC）：文件完整性 + HTML 结构 + JS 语法 + 商用要素，失败时返回问题清单供自动修复。"""
    checks = []
    web = files.get("web") or {}
    html = web.get("index.html") or ""
    wx = files.get("wx") or {}
    # 1) 文件完整性：web 版必须有 index.html；wx 三件套必须齐全（双版本缺一不可）
    checks.append({"item": "web index.html 存在", "ok": bool(html), "detail": "已生成" if html else "缺失"})
    for name in ("game.js", "game.json", "project.config.json"):
        ok = bool((wx or {}).get(name))
        checks.append({"item": f"wx {name} 存在", "ok": ok, "detail": "已生成" if ok else "缺失"})
    # 2) HTML 结构：script/style 配对 + canvas/入口存在
    if html:
        err = _check_html_pairs(html)
        checks.append({"item": "HTML 结构完整", "ok": err is None, "detail": err or "结构正常"})
    js_blocks = re.findall(r"<script[^>]*>([\s\S]*?)</script>", html)
    if js_blocks:
        ok, msg = _node_check_js("\n".join(js_blocks))
        checks.append({"item": "web JS 语法", "ok": ok, "detail": msg})
    wx_js = wx.get("game.js") or ""
    if wx_js:
        ok, msg = _node_check_js(wx_js)
        checks.append({"item": "wx game.js 语法", "ok": ok, "detail": msg})
    src = (html + "\n" + wx_js).lower()
    for label, kws in _FEATURE_SPECS:
        hit = any(k.lower() in src for k in kws)
        checks.append({"item": label, "ok": hit, "detail": "已包含" if hit else "缺失"})
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


@router.get("/templates")
async def list_templates(current_user: dict = require_auth()):
    return TEMPLATES


@router.get("/projects")
async def list_projects(current_user: dict = require_auth()):
    conn = get_db()
    _ensure_cover_column(conn)
    rows = conn.execute(
        "SELECT id, name, template, requirement, created_at, updated_at, favorite, tags, iterations, cover "
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


async def _game_generate_worker(payload: dict, progress: Callable | None = None) -> dict:  # noqa: C901
    """AI 生成双版本小游戏（同步/异步任务共用执行体，异步时回报进度）。"""
    req = GenerateRequest(**payload)
    tpl = next((t for t in TEMPLATES if t["id"] == req.template), None)
    if req.template != "custom" and not tpl:
        raise HTTPException(400, f"未知模板: {req.template}")

    def _report(pct: float, stage: str) -> None:
        if progress:
            try:
                progress(pct, stage)
            except Exception:
                pass

    user_prompt = f"""游戏名称：{req.name}
选择模板：{tpl["name"] if tpl else "自定义"}
模板玩法：
{tpl["play"] if tpl else "根据用户需求自行设计玩法。"}

用户需求：
{req.requirement}

请生成双版本小游戏 JSON。"""
    _report(10, "已受理，正在组织生成提示词…")

    start = time.time()
    files = None
    qc = None
    last_err = ""
    # 首次 LLM 调用：上游抖动自动重试（最多 3 次，指数退避）
    result = None
    for _attempt in range(3):
        try:
            _report(25, f"AI 正在生成双版本代码（第 {_attempt + 1} 次尝试）…")
            result = await call_llm_async(_GENERATE_SYSTEM, user_prompt, max_tokens=22000, temperature=0.4, timeout=300)
            break
        except HTTPException as e:
            if e.status_code < 500:
                raise  # 4xx 属业务/参数问题，不重试
            last_err = f"{e.status_code}: {e.detail}"
            logger.warning("game LLM upstream error (attempt %d): %s", _attempt + 1, str(e.detail)[:200])
        except Exception as e:
            last_err = str(e)
            logger.warning("game LLM exception (attempt %d): %s", _attempt + 1, str(e)[:200])
        await asyncio.sleep(2 * (_attempt + 1))
    if result is None:
        raise HTTPException(502, f"LLM 服务暂时不可用，已自动重试仍失败，请稍后重试。详情: {last_err}")

    # 生成链路质量门禁：最多 3 轮（解析失败→精简重试；QC 未过→附问题清单自动修复重试）
    for attempt in range(3):
        _report(55, f"正在执行质量门禁检查（第 {attempt + 1} 轮）…")
        try:
            files = _validate_files(_extract_json(result))
            qc = _qc_check(files)
            if qc["ok"]:
                break
            last_err = "；".join(f"{c['item']}: {c['detail']}" for c in qc["checks"] if not c["ok"])
            logger.warning("game QC failed (attempt %d): %s", attempt + 1, last_err)
            retry_prompt = user_prompt + (
                "\n\n重要：上次输出的代码未通过质量门禁（商用交付前必须全部通过）。"
                f"问题清单：{last_err}\n"
                "请针对性地修复以上问题，重新输出完整的双版本 JSON（不要省略任何文件、不要截断）。"
            )
            result = await call_llm_async(
                _GENERATE_SYSTEM, retry_prompt, max_tokens=22000, temperature=0.3, timeout=300
            )
        except (ValueError, json.JSONDecodeError) as e:
            last_err = str(e)
            logger.warning(
                "game JSON parse failed (attempt %d): %s (output_len=%d, head=%r)",
                attempt + 1,
                e,
                len(result or ""),
                (result or "")[:200],
            )
            # 输出截断/超长：自动降级为精简版重试（优先保证 web 单文件可玩）
            retry_prompt = user_prompt + (
                "\n\n重要：上次输出未通过解析，错误为：" + str(e) + "。\n"
                "本次请严格：\n"
                "1. 只输出合法 JSON 对象，不要 markdown 代码块、不要任何解释文字\n"
                "2. 所有字符串正确转义（引号/换行），内容不要截断\n"
                "3. web 版 index.html 控制在 300 行以内，wx 版 game.js 控制在 250 行以内，总字符数不超过 20000"
            )
            result = await call_llm_async(
                _GENERATE_SYSTEM, retry_prompt, max_tokens=14000, temperature=0.3, timeout=300
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"生成失败: {e}") from e
    if not files or qc is None:
        raise HTTPException(502, f"AI 输出格式异常（已自动重试仍失败），请重试或更换模型。详情: {last_err}")
    if not qc["ok"]:
        raise HTTPException(502, f"质量门禁未通过（已自动修复重试 3 次）：{last_err}")

    proj_id = f"game_{uuid.uuid4().hex[:12]}"
    now = datetime.now().isoformat()
    conn = get_db()
    _ensure_qc_column(conn)
    conn.execute(
        """INSERT INTO game_projects (id, name, template, requirement, files, qc, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            proj_id,
            req.name,
            req.template,
            req.requirement,
            json.dumps(files, ensure_ascii=False),
            json.dumps(qc, ensure_ascii=False),
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()
    _report(85, "项目已保存")

    elapsed = round(time.time() - start, 2)
    log_usage("game_generate", len(user_prompt), len(result), elapsed)
    return {
        "id": proj_id,
        "name": req.name,
        "template": req.template,
        "versions": list(files.keys()),
        "file_count": sum(len(v) for v in files.values()),
        "files": files,
        "qc": qc,
    }


@router.post("/generate")
async def generate_game(
    req: GenerateRequest,
    sync: bool = Query(False, description="true=同步执行（兼容旧客户端/脚本）；默认异步任务"),
    current_user: dict = require_auth(),
):
    """选模板 + 需求 → AI 生成双版本小游戏（默认异步任务，立即返回 task_id）。"""
    tpl = next((t for t in TEMPLATES if t["id"] == req.template), None)
    if req.template != "custom" and not tpl:
        raise HTTPException(400, f"未知模板: {req.template}")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    if sync:
        return await _game_generate_worker(req.model_dump())
    task = create_task("game_generate", req.model_dump(), username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"],
        "status": "pending",
        "message": "游戏生成任务已提交，后台执行中，可在任务中心查看进度",
        "task": task,
    }


class CoverRequest(BaseModel):
    cover: str = Field(..., description="封面 base64 dataURL（前端试玩 iframe canvas.toDataURL 截取）")


COVER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_covers")


def _ensure_cover_column(conn) -> None:
    """幂等补列：game_projects.cover 存封面 URL。"""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(game_projects)").fetchall()]
    if "cover" not in cols:
        conn.execute("ALTER TABLE game_projects ADD COLUMN cover TEXT DEFAULT ''")
        conn.commit()


def _ensure_history_column(conn) -> None:
    """game_projects 表确保 version_history 列存在（v15 迭代历史快照）。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(game_projects)").fetchall()}
    if "version_history" not in cols:
        conn.execute("ALTER TABLE game_projects ADD COLUMN version_history TEXT DEFAULT '[]'")
        conn.commit()


def _ensure_qc_column(conn) -> None:
    """幂等补列：game_projects.qc 存商用质量门禁报告（JSON）。"""
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(game_projects)").fetchall()]
    if "qc" not in cols:
        conn.execute("ALTER TABLE game_projects ADD COLUMN qc TEXT DEFAULT ''")
        conn.commit()


@router.post("/{proj_id}/cover")
async def save_cover(proj_id: str, req: CoverRequest, current_user: dict = require_auth()):
    """保存游戏封面：前端试玩时截取首屏画面，作为项目卡片商用展示。"""
    import base64

    data = (req.cover or "").strip()
    if not data.startswith("data:image"):
        raise HTTPException(400, "cover 必须是 data:image 开头的 base64 图片")
    try:
        _, b64 = data.split(",", 1)
        raw = base64.b64decode(b64)
    except Exception as e:
        raise HTTPException(400, "cover base64 解码失败") from e
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(400, "封面图片过大（≤5MB）")
    conn = get_db()
    _ensure_cover_column(conn)
    row = conn.execute("SELECT id FROM game_projects WHERE id=?", (proj_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "游戏项目不存在")
    os.makedirs(COVER_DIR, exist_ok=True)
    ext = "jpg" if "image/jpeg" in data else "png"
    fname = f"{proj_id}.{ext}"
    with open(os.path.join(COVER_DIR, fname), "wb") as f:
        f.write(raw)
    cover_url = f"/api/games/{proj_id}/cover-image"
    conn.execute(
        "UPDATE game_projects SET cover=?, updated_at=? WHERE id=?", (cover_url, datetime.now().isoformat(), proj_id)
    )
    conn.commit()
    conn.close()
    return {"success": True, "cover": cover_url}


class AiCoverRequest(BaseModel):
    prompt: str = Field("", max_length=500, description="自定义封面提示词（留空自动按游戏生成）")


def _fallback_game_cover(name: str, tpl_name: str) -> bytes:
    """文生图失败时的 PIL 兜底封面：渐变底 + 游戏名 + 玩法说明。"""
    from PIL import Image, ImageDraw, ImageFont

    w, h = 1024, 1024
    schemes = [((99, 102, 241), (139, 92, 246)), ((16, 185, 129), (14, 165, 233))]
    top, bottom = schemes[sum(ord(c) for c in name) % len(schemes)]
    img = Image.new("RGB", (w, h), top)
    px = img.load()
    for y in range(h):
        t = y / h
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)
    draw = ImageDraw.Draw(img)
    for k in range(3):
        draw.ellipse(
            [w * (0.58 + k * 0.12), h * 0.14, w * (0.98 + k * 0.12), h * 0.62],
            outline=(255, 255, 255, 44 - k * 12),
            width=2,
        )
    font = None
    for fp in ("/System/Library/Fonts/PingFang.ttc", "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"):
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, 64)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()
    title = (name or "AI 小游戏")[:12]
    bbox = draw.textbbox((0, 0), title, font=font)
    draw.text(((w - (bbox[2] - bbox[0])) / 2, h // 2 - 90), title, fill=(255, 255, 255, 240), font=font)
    sub = f"{tpl_name} · 双版本小游戏"
    draw.text(((w - (bbox[2] - bbox[0])) / 2, h // 2 + 20), sub, fill=(255, 255, 255, 170), font=font)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


@router.post("/{proj_id}/ai-cover")
async def generate_ai_cover(proj_id: str, req: AiCoverRequest, current_user: dict = require_auth()):
    """AI 生成游戏封面：按游戏名/模板自动生成提示词 → 文生图保存为封面；失败自动降级 PIL 兜底。"""
    import requests as _requests

    conn = get_db()
    row = conn.execute("SELECT name, template FROM game_projects WHERE id=?", (proj_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "游戏项目不存在")
    tpl = next((t for t in TEMPLATES if t["id"] == row["template"]), None)
    tpl_name = tpl["name"] if tpl else "小游戏"
    prompt = req.prompt.strip() or (
        f"Mobile game cover art, cartoon style, vibrant gradient background, "
        f"game theme: {row['name']}, {tpl_name} gameplay scene, "
        "colorful illustration, game poster composition, no text, no watermark"
    )
    raw = None
    try:
        from common.config import AGNES_API_BASE, AGNES_API_KEY

        if not AGNES_API_KEY:
            raise RuntimeError("AGNES_API_KEY 未配置")
        resp = await asyncio.to_thread(
            _requests.post,
            f"{AGNES_API_BASE}/images/generations",
            headers={"Authorization": f"Bearer {AGNES_API_KEY}", "Content-Type": "application/json"},
            json={"model": "agnes-image-2.1-flash", "prompt": prompt, "size": "1024x1024", "n": 1},
            timeout=120,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"文生图失败: {resp.text[:200]}")
        img_url = resp.json().get("data", [{}])[0].get("url")
        if not img_url:
            raise RuntimeError("文生图未返回图片 URL")
        img_resp = await asyncio.to_thread(_requests.get, img_url, timeout=60)
        if img_resp.status_code != 200:
            raise RuntimeError("封面图片下载失败")
        raw = img_resp.content
    except Exception as e:
        logger.warning("AI 封面生成失败，使用兜底封面: %s", str(e)[:200])
        raw = _fallback_game_cover(row["name"], tpl_name)
    os.makedirs(COVER_DIR, exist_ok=True)
    fname = f"{proj_id}.jpg"
    with open(os.path.join(COVER_DIR, fname), "wb") as f:
        f.write(raw)
    cover_url = f"/api/games/{proj_id}/cover-image"
    conn = get_db()
    conn.execute(
        "UPDATE game_projects SET cover=?, updated_at=? WHERE id=?",
        (cover_url, datetime.now().isoformat(), proj_id),
    )
    conn.commit()
    conn.close()
    return {"success": True, "cover": cover_url, "prompt": prompt}


@router.get("/{proj_id}/cover-image")
async def get_cover(proj_id: str):
    """读取游戏封面图片。"""
    for ext in ("png", "jpg"):
        p = os.path.join(COVER_DIR, f"{proj_id}.{ext}")
        if os.path.exists(p):
            return FileResponse(p, media_type="image/png" if ext == "png" else "image/jpeg")
    raise HTTPException(404, "暂无封面，可在试玩页截取保存")


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


async def _game_evolve_worker(payload: dict, progress: Callable | None = None) -> dict:  # noqa: C901
    """AI 二次迭代（同步/异步任务共用执行体）。"""
    proj_id = payload.get("proj_id", "")
    req = EvolveRequest(**payload.get("params", payload))
    conn = get_db()
    _ensure_history_column(conn)
    row = conn.execute("SELECT * FROM game_projects WHERE id=?", (proj_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "游戏项目不存在")
    files = json.loads(row["files"] or "{}")
    if not files:
        conn.close()
        raise HTTPException(400, "项目没有代码文件，无法迭代")

    def _report(pct: float, stage: str) -> None:
        if progress:
            try:
                progress(pct, stage)
            except Exception:
                pass

    # 注入现有代码（截断保护 token 上限）
    web_html = (files.get("web", {}).get("index.html") or "")[:24000]
    wx_js = (files.get("wx", {}).get("game.js") or "")[:20000]
    user_prompt = f"""游戏名称：{row["name"]}

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
    _report(15, "已受理，正在组织迭代提示词…")

    start = time.time()
    try:
        _report(40, "AI 正在生成升级版代码…")
        result = await call_llm_async(_EVOLVE_SYSTEM, user_prompt, max_tokens=20000, temperature=0.4, timeout=300)
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
    log.append(
        {
            "requirement": req.requirement,
            "created_at": datetime.now().isoformat(),
            "chars": len(result),
        }
    )
    # v15：迭代前保存当前版本快照（用于历史对比与回滚）
    try:
        history = json.loads(row["version_history"] or "[]")
    except Exception:
        history = []
    history.append(
        {
            "version": len(history) + 1,
            "created_at": datetime.now().isoformat(),
            "requirement": f"迭代前快照：{req.requirement[:60]}",
            "files": files,
        }
    )
    conn.execute(
        """UPDATE game_projects SET files=?, iterations=iterations+1, iteration_log=?, version_history=?, updated_at=?
           WHERE id=?""",
        (
            json.dumps(new_files, ensure_ascii=False),
            json.dumps(log[-20:], ensure_ascii=False),
            json.dumps(history[-20:], ensure_ascii=False),
            datetime.now().isoformat(),
            proj_id,
        ),
    )
    conn.commit()
    conn.close()
    _report(85, "升级版代码已保存")

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


@router.post("/{proj_id}/evolve")
async def evolve_game(
    proj_id: str,
    req: EvolveRequest,
    sync: bool = Query(False, description="true=同步执行；默认异步任务"),
    current_user: dict = require_auth(),
):
    """AI 二次迭代：基于现有代码 + 新需求，生成升级版双版本代码（默认异步任务）。"""
    # 预检：项目存在性快速失败，避免无效任务入队
    conn = get_db()
    row = conn.execute("SELECT id, files FROM game_projects WHERE id=?", (proj_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "游戏项目不存在")
    if not json.loads(row["files"] or "{}"):
        raise HTTPException(400, "项目没有代码文件，无法迭代")
    user = current_user.get("username", "") if isinstance(current_user, dict) else ""
    uid = current_user.get("user_id", "") if isinstance(current_user, dict) else ""
    role = current_user.get("role", "") if isinstance(current_user, dict) else ""
    payload = {"proj_id": proj_id, "params": req.model_dump()}
    if sync:
        return await _game_evolve_worker(payload)
    task = create_task("game_evolve", payload, username=user, user_id=uid, role=role)
    return {
        "task_id": task["id"],
        "status": "pending",
        "message": "迭代任务已提交，后台执行中，可在任务中心查看进度",
        "task": task,
    }


@router.get("/{proj_id}")
async def get_project(proj_id: str, current_user: dict = require_auth()):
    conn = get_db()
    _ensure_history_column(conn)
    row = conn.execute("SELECT * FROM game_projects WHERE id=?", (proj_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "游戏项目不存在")
    d = dict(row)
    d["files"] = json.loads(d.get("files") or "{}")
    d["qc"] = json.loads(d.get("qc") or "null")
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
        headers={"Content-Disposition": (f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}")},
    )


@router.get("/{proj_id}/publish-pack")
async def game_publish_pack(proj_id: str, current_user: dict = require_auth()):
    """游戏发布包：网页成品 + 微信小游戏包 + 封面 + 上线清单 + 质量报告，一键交付可发布。"""
    conn = get_db()
    row = conn.execute("SELECT * FROM game_projects WHERE id=?", (proj_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "游戏项目不存在")
    row = dict(row)  # sqlite3.Row 无 .get，转 dict 供发布物料模板使用
    files = json.loads(row["files"] or "{}")
    if not files:
        raise HTTPException(400, "项目没有文件")

    root = pack_dir_name("game_release")
    entries: dict = {}
    for version in ("web", "wx"):
        if version not in files:
            continue
        for path in sorted(files[version].keys()):
            entries[f"{root}/{version}/{path.lstrip('/')}"] = files[version][path]
    # 封面（AI 封面或用户上传，存在则附带）
    cover_src = None
    for ext in ("png", "jpg"):
        p = os.path.join(COVER_DIR, f"{proj_id}.{ext}")
        if os.path.exists(p):
            cover_src = p
            break
    if cover_src:
        entries[f"{root}/封面.{cover_src.rsplit('.', 1)[-1]}"] = cover_src  # key=zip 路径, value=磁盘路径

    entries[f"{root}/README.md"] = (
        f"# 《{row['name']}》AI 小游戏\n\n- 模板：{row.get('template', '自定义')}\n"
        f"- 说明：{row.get('requirement', '')[:200]}\n\n"
        "## 目录\n"
        "- `web/`：网页版，index.html 双击即玩，也可部署到 GitHub Pages/云托管等任意静态站点\n"
        "- `wx/`：微信小游戏原生项目，用微信开发者工具导入即可编译\n"
        "- `封面`：游戏封面图（平台审核与商店展示用）\n\n"
        "## 发布方式\n"
        "1. 网页版：静态托管（GitHub Pages / 腾讯云 / 自有服务器），分享链接即可传播；\n"
        "2. 微信小游戏：mp.weixin.qq.com 注册小游戏账号 → 开发者工具上传 → 提交审核 → 发布。"
    )
    guide = await deploy_guide(current_user=current_user)
    entries[f"{root}/上线清单.md"] = (
        "# 上线清单（发布前逐项核对）\n\n## 部署步骤\n"
        + "\n".join(f"{i + 1}. {s}" for i, s in enumerate(guide.get("steps", [])))
        + f"\n\n## 备注\n{guide.get('note', '')}\n\n"
        "## 提交审核物料\n"
        "- 游戏名称、简介（取自项目名，可在公众平台修改）\n"
        "- 封面图（本包已附带，建议 ≥800×800）\n"
        "- 截图：试玩页面截图 1-5 张（微信审核必填，需含主要玩法画面）\n"
        "- 类目：选择「游戏」类目，个人主体支持大部分休闲游戏\n"
        "- 隐私声明：如涉及用户信息需在后台填写（本项目默认不采集）"
    )
    entries[f"{root}/LICENSE.txt"] = license_text(f"小游戏《{row['name']}》")

    # 生产级内容保障：质量自检报告（QC 门禁 + 名称/需求安全审核）
    try:
        qc = json.loads(row.get("qc") or "null")
        name_check = check_text(row["name"], "文案")
        req_check = check_text(row.get("requirement") or "", "prompt") if row.get("requirement") else None
        failed = [c for c in (qc or {}).get("checks", []) if not c.get("ok")]
        extra = [
            f"QC 门禁：{'全部通过 ✓' if (qc or {}).get('ok') else f'{len(failed)} 项未过（{', '.join(c['item'] for c in failed[:3])}）'}",
            "双版本：web（网页版）+ wx（微信小游戏）",
        ]
        entries[f"{root}/质量自检报告.md"] = quality_report(
            f"小游戏《{row['name']}》",
            text_check=name_check if name_check and not name_check["ok"] else (req_check if req_check and not req_check["ok"] else None),
            image_quality=None,
            extra=extra,
        )
    except Exception as e:
        logger.debug(f"游戏质量自检报告生成失败: {e}")

    buf = build_publish_zip(entries, "game_release")
    publish = publish_registry.publish("game_platform", {"proj": proj_id, "name": row["name"]})
    return StreamingResponse(
        io.BytesIO(buf.getvalue()),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="game_release_{int(time.time())}.zip"',
            "X-Publish-Result": f"published={str(publish.get('published')).lower()}",
        },
    )


# ── 迭代历史对比（v15）：版本快照 + 逐版变更统计 + 回滚 ──
def diff_file_stats(old_text: str, new_text: str) -> dict:
    """逐行 diff 统计：返回 {added, removed} 行数（纯函数，供历史对比视图使用）。"""
    import difflib

    old_lines = (old_text or "").splitlines()
    new_lines = (new_text or "").splitlines()
    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    added = removed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "insert":
            added += j2 - j1
        elif tag == "delete":
            removed += i2 - i1
        elif tag == "replace":
            removed += i2 - i1
            added += j2 - j1
    return {"added": added, "removed": removed}


def _flatten_files(files: dict) -> dict:
    """嵌套 {版本: {路径: 内容}} → 扁平 {版本/路径: 内容}（纯函数）。"""
    flat: dict = {}
    for ver, paths in (files or {}).items():
        if isinstance(paths, dict):
            for p, content in paths.items():
                flat[f"{ver}/{p.lstrip('/')}"] = content
    return flat


def build_version_stats(prev_files: dict, files: dict) -> dict:
    """对比两个版本逐文件的行数变更统计（纯函数）。"""
    prev_flat = _flatten_files(prev_files)
    cur_flat = _flatten_files(files)
    stats = {}
    for p in sorted(set(prev_flat) | set(cur_flat)):
        old_t = prev_flat.get(p, "")
        new_t = cur_flat.get(p, "")
        if old_t != new_t:
            stats[p] = diff_file_stats(old_t, new_t)
    return stats


class RestoreRequest(BaseModel):
    version: int = Field(..., description="要恢复的历史版本号")


@router.get("/{proj_id}/history")
async def project_history(proj_id: str, current_user: dict = require_auth()):
    """迭代历史：版本时间线 + 逐版变更行数统计（相对上一版）。"""
    conn = get_db()
    _ensure_history_column(conn)
    row = conn.execute(
        "SELECT name, iterations, version_history FROM game_projects WHERE id=?", (proj_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "游戏项目不存在")
    try:
        history = json.loads(row["version_history"] or "[]")
    except Exception:
        history = []
    out = []
    for i, item in enumerate(history):
        stats = {}
        if i > 0:
            stats = build_version_stats(history[i - 1].get("files") or {}, item.get("files") or {})
        out.append(
            {
                "version": item.get("version"),
                "created_at": item.get("created_at", ""),
                "requirement": item.get("requirement", ""),
                "stats": stats,
            }
        )
    return {"name": row["name"], "iterations": row["iterations"], "history": out}


@router.get("/{proj_id}/history/{version}")
async def project_history_version(proj_id: str, version: int, current_user: dict = require_auth()):
    """查看指定历史版本的完整文件内容。"""
    conn = get_db()
    _ensure_history_column(conn)
    row = conn.execute("SELECT version_history FROM game_projects WHERE id=?", (proj_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "游戏项目不存在")
    try:
        history = json.loads(row["version_history"] or "[]")
    except Exception:
        history = []
    item = next((h for h in history if h.get("version") == version), None)
    if not item:
        raise HTTPException(404, f"版本 v{version} 不存在")
    return {
        "version": item["version"],
        "created_at": item.get("created_at", ""),
        "requirement": item.get("requirement", ""),
        "files": item.get("files") or {},
    }


@router.post("/{proj_id}/restore")
async def restore_project(proj_id: str, req: RestoreRequest, current_user: dict = require_auth()):
    """回滚到指定历史版本：当前版本先快照入历史，再恢复目标版本文件。"""
    conn = get_db()
    _ensure_history_column(conn)
    row = conn.execute(
        "SELECT files, iterations, iteration_log, version_history FROM game_projects WHERE id=?", (proj_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "游戏项目不存在")
    try:
        history = json.loads(row["version_history"] or "[]")
    except Exception:
        history = []
    target = next((h for h in history if h.get("version") == req.version), None)
    if not target:
        conn.close()
        raise HTTPException(404, f"版本 v{req.version} 不存在")
    current_files = json.loads(row["files"] or "{}")
    if current_files:
        history.append(
            {
                "version": len(history) + 1,
                "created_at": datetime.now().isoformat(),
                "requirement": f"回滚前快照（回滚到 v{req.version}）",
                "files": current_files,
            }
        )
    try:
        log = json.loads(row["iteration_log"] or "[]")
    except Exception:
        log = []
    log.append(
        {
            "requirement": f"回滚到 v{req.version}",
            "created_at": datetime.now().isoformat(),
            "chars": 0,
        }
    )
    conn.execute(
        "UPDATE game_projects SET files=?, iterations=iterations+1, iteration_log=?, version_history=?, updated_at=? WHERE id=?",
        (
            json.dumps(target["files"], ensure_ascii=False),
            json.dumps(log[-20:], ensure_ascii=False),
            json.dumps(history[-20:], ensure_ascii=False),
            datetime.now().isoformat(),
            proj_id,
        ),
    )
    conn.commit()
    conn.close()
    return {
        "id": proj_id,
        "version": req.version,
        "versions": list(target["files"].keys()),
        "files": target["files"],
        "iterations": len(log),
        "message": f"已回滚到 v{req.version}",
    }


def get_db():
    from common.db import get_db as _get_db

    return _get_db()


# ══════════════════════════════════════════════════════════════
# 通用异步任务框架接入：生成/迭代为后台任务（默认异步，页面可关闭）
# ══════════════════════════════════════════════════════════════


async def _game_generate_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：生成双版本小游戏（async 由框架 asyncio.run 执行）。"""
    update(5, "任务已受理，正在准备生成…")
    return await _game_generate_worker(payload, progress=update)


async def _game_evolve_handler(task_id: str, payload: dict, update: Callable, ctx: dict) -> dict:
    """异步任务处理器：基于现有代码迭代升级。"""
    update(5, "任务已受理，正在准备迭代…")
    return await _game_evolve_worker(payload, progress=update)


register_handler("game_generate", _game_generate_handler, user_limit=2)
register_handler("game_evolve", _game_evolve_handler, user_limit=2)
