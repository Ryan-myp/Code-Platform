"""KB 检索质量黄金集（v18 P2）：量化门禁，防未来检索重构悄悄退化。

用 tests/golden/ 的固定语料 + query→期望文件映射，对 file 型检索跑 hit@3，
命中率达到阈值才通过。任何改动检索打分/分块/重排的 PR 都应跑这里看指标。
"""

import json
from pathlib import Path

GOLDEN_DIR = Path(__file__).parent.parent.parent / "tests" / "golden"
# hit@3 达标线：10 条里至少 8 条 top3 命中（留 2 条容错，防个别措辞波动）
MIN_HIT_RATE = 0.8


def _load_cases():
    data = json.loads((GOLDEN_DIR / "golden.json").read_text(encoding="utf-8"))
    corpus = (GOLDEN_DIR / data["corpus_dir"]).resolve()
    kb = {"id": "kb-golden", "name": "黄金集", "type": "file", "path": str(corpus), "config": "{}"}
    return kb, data["cases"]


def test_kb_search_golden_hit_rate(setup_test_db):
    """file 型检索 hit@3 ≥ MIN_HIT_RATE；同时打印逐条命中便于人工审阅。"""
    import kb_api

    kb, cases = _load_cases()
    hits_ok = 0
    report = []
    for c in cases:
        res = kb_api._kb_search_file(kb, c["query"], 3)
        files = [h.get("file") for h in (res.get("hits") or [])]
        ok = c["expect"] in files
        hits_ok += int(ok)
        report.append(f"  [{'PASS' if ok else 'MISS'}] {c['query']} -> {files[:3]}")
    rate = hits_ok / len(cases)
    detail = "\n".join(report)
    assert rate >= MIN_HIT_RATE, f"KB 检索 hit@3 低于阈值 {MIN_HIT_RATE}（实际 {rate:.0%}）：\n{detail}"
