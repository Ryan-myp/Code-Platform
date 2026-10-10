#!/usr/bin/env python3
"""工具族深度质量抽样（不只"调通没"，而是结构 + 内容 + 样式/格式三层核查）。

用法：先起探测服务（DB_PATH=/tmp/deep_probe.db PORT=8012 APP_ENV=dev），再
  `python scripts/tool_deep_qa.py [BASE_URL]`

设计原则：每个工具按其 **prompt 自身规定的输出格式** 写断言（章节/表格/数量/
领域词），而非泛泛看长度。这样能区分"关键词命中但内容空泛/格式崩"的真缺陷。
严格串行（一次一个 LLM 调用），避免限流。
"""

import re
import secrets
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8012"


def md_table_rows(t: str) -> int:
    return sum(1 for ln in t.split("\n") if ln.strip().startswith("|") and ln.count("|") >= 3)


class C:
    def __init__(self) -> None:
        self.client = httpx.Client(base_url=BASE, timeout=300)
        self.client.headers["Authorization"] = f"Bearer {self.register()}"

    def register(self) -> str:
        uname = f"deep_{secrets.token_hex(3)}"
        r = self.client.post("/api/auth/register", json={"username": uname, "password": "pass1234", "email": f"{uname}@t.cn"})
        tok = (r.json().get("access_token") or r.json().get("token") or "") if r.status_code < 400 else ""
        if not tok:
            r = self.client.post("/api/auth/login", json={"username": uname, "password": "pass1234"})
            tok = r.json().get("access_token") or r.json().get("token") or ""
        return tok

    def run(self, tool_id: str, inp: str, params: dict) -> tuple[int, str]:
        r = self.client.post("/api/tools/run", params={"sync": "true"}, json={"tool_id": tool_id, "input": inp, "params": params})
        d = r.json()
        blob = d.get("result") or d.get("content") or d.get("output") or ""
        if isinstance(blob, dict):
            blob = blob.get("content", "")
        return r.status_code, str(blob)


def main() -> None:
    c = C()
    print(f"user={c.client.headers['Authorization']}\n", flush=True)
    grand_pass = grand_total = 0

    # ── 1. 商品标题优化（电商运营）：5 个标题 + 关键词分析 + SEO 表 ─────────
    sc, txt = c.run(
        "product-title",
        "无线蓝牙耳机，主打通勤降噪，价格 300-500 元，目标人群 25-35 岁上班族",
        {"platform": "淘宝/天猫", "category": "数码家电", "count": "5个", "language": "中文"},
    )
    n_titles = len(re.findall(r"###\s*标题\s*\d", txt))
    checks = [
        ("HTTP 200", sc == 200, f"status={sc}"),
        ("长度>800字", len(txt) > 800, f"len={len(txt)}"),
        ("关键词分析章节", "关键词" in txt, "缺"),
        ("优化标题章节", re.search(r"(优化标题|标题方案)", txt) is not None, "缺"),
        ("标题数≥5", n_titles >= 5, f"实际={n_titles}"),
        ("落到商品领域(非空泛)", any(k in txt for k in ["蓝牙", "降噪", "耳机", "TWS"]), "内容空泛"),
        ("SEO 评分表", ("SEO" in txt and "⭐" in txt), "缺"),
        ("markdown 表格≥5行", md_table_rows(txt) >= 5, f"表行={md_table_rows(txt)}"),
        ("无裸花括号泄漏", "{" not in txt and "}" not in txt, "残留 {}"),
        ("无 [待补充] 占位", ("[待补充]" not in txt and "[从内容提取]" not in txt), "有占位"),
    ]
    _report("商品标题优化[电商]", checks, c, txt, "qa_product_title.md")
    grand_pass += sum(1 for _, ok, _ in checks if ok)
    grand_total += len(checks)

    # ── 2. 配色方案（设计创意）：3 套 + HEX/rgb + WCAG + 比例 ──────────────
    sc, txt = c.run(
        "color-scheme",
        "有机食品品牌官网首页，调性清新自然、可信健康",
        {"style": "自然绿", "scene": "电商设计", "language": "中文"},
    )
    hexes = re.findall(r"#[0-9A-Fa-f]{6}\b", txt)
    schemes = len(re.findall(r"##\s*方案[一二三123]", txt))
    rgb = re.findall(r"rgb\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*\)", txt)
    checks = [
        ("HTTP 200", sc == 200, f"status={sc}"),
        ("长度>800字", len(txt) > 800, f"len={len(txt)}"),
        ("≥3个配色方案", schemes >= 3, f"方案={schemes}"),
        ("有效HEX≥6", len(set(hexes)) >= 6, f"去重={sorted(set(hexes))[:6]}"),
        ("含 rgb() 值", len(rgb) >= 3, f"rgb={len(rgb)}"),
        ("色彩比例章节", "比例" in txt, "缺"),
        ("WCAG/对比度(样式专业度)", any(k in txt for k in ["WCAG", "对比度", "无障碍", "AA"]), "缺可访问性说明"),
        ("色彩表≥6行", md_table_rows(txt) >= 6, f"表行={md_table_rows(txt)}"),
        ("无裸花括号泄漏", "{" not in txt and "}" not in txt, "残留 {}"),
    ]
    _report("配色方案[设计]", checks, c, txt, "qa_color_scheme.md")
    grand_pass += sum(1 for _, ok, _ in checks if ok)
    grand_total += len(checks)

    # ── 3. 面试题库（人力资源）：N 题 + STAR + 评分表 + 面试官指南 ─────────
    sc, txt = c.run(
        "interview-questions",
        "高级后端工程师(Python/Go)，5年以上，重点考察高并发与系统架构设计",
        {"job_type": "技术岗", "round": "技术面(专业)", "count": "10题(快速)", "difficulty": "高级"},
    )
    qn = len(re.findall(r"###\s*题目\s*\d", txt))
    checks = [
        ("HTTP 200", sc == 200, f"status={sc}"),
        ("长度>1000字", len(txt) > 1000, f"len={len(txt)}"),
        ("专业能力题章节", "专业能力" in txt, "缺"),
        ("STAR 行为面", ("STAR" in txt or "行为" in txt), "缺"),
        ("题目数≥10", qn >= 10, f"实际={qn}"),
        ("落到岗位领域(非通用)", any(k in txt for k in ["高并发", "架构", "后端", "Go", "Python", "微服务"]), "与岗位脱节"),
        ("评分标准表≥4行", ("评分" in txt and md_table_rows(txt) >= 4), f"表行={md_table_rows(txt)}"),
        ("面试官指南/流程", ("面试官" in txt or "流程" in txt), "缺"),
        ("无裸花括号泄漏", "{" not in txt and "}" not in txt, "残留 {}"),
        ("无 [待补充] 占位", ("[待补充]" not in txt and "[从内容提取]" not in txt), "有占位"),
    ]
    _report("面试题库[HR]", checks, c, txt, "qa_interview.md")
    grand_pass += sum(1 for _, ok, _ in checks if ok)
    grand_total += len(checks)

    print(f"\n═══ 深度质量抽样：结构/内容/样式 {grand_pass}/{grand_total} 项 ═══", flush=True)
    sys.exit(0 if grand_pass == grand_total else 1)


def _report(name: str, checks, c: C, txt: str, fname: str) -> None:
    import pathlib

    p = sum(1 for _, ok, _ in checks if ok)
    print(f"\n[{name}] {p}/{len(checks)} 项", flush=True)
    for label, ok, detail in checks:
        print(f"   [{'✓' if ok else '✗'}] {label}" + (f" — {detail}" if (detail and not ok) else ""), flush=True)
    pathlib.Path("/tmp", fname).write_text(txt)


if __name__ == "__main__":
    main()
