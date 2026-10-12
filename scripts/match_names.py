#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
match_names.py — 中国无接口清单「名称比对」辅助（归一化 + 精确命中 + 候选标记）

给定待查实体/个人名列表与从官方公告摘录的名单正文（或逐行实体列表），输出：
  - 命中：待查名（归一化后）作为子串精确出现在名单文本中
  - 候选：未精确命中，但归一化后与名单文本存在较多二元共现（疑似简称/变体），交人工终判

归一化规则（避免 AERKOMM INC. 与 Aerkomm Inc. 这类漏检）：
  - 统一大小写（英文转小写）
  - 全角转半角、去除标点与空白
  - 剥离公司/机构后缀：Inc / Co / Ltd / LLC / Corp / Company / Limited
    以及中文"公司""有限公司""集团""股份"

仅做辅助标记，不自动定性"命中/未命中"——模糊项一律标"候选"。

用法：
    python match_names.py --names names.txt --list extracted.txt
    python match_names.py --names names.txt --list extracted.txt --out report.md

依赖：仅 Python 标准库
"""
import argparse
import io
import re
import sys

SUFFIXES = [
    "incorporated", "corporation", "company", "limited", "holdings",
    "inc", "co", "ltd", "llc", "corp",
    "股份有限公司", "有限责任公司", "有限公司", "控股集团", "集团公司", "股份公司", "集团", "公司",
]
SUFFIX_RE = re.compile("(" + "|".join(SUFFIXES) + r")+$")
NONWORD_RE = re.compile(r"[^0-9a-z一-鿿]+")


def normalize(s):
    """归一化：全角转半角、转小写、去标点空白、剥离公司后缀。"""
    s = (s or "").strip()
    # 全角字母数字 → 半角
    s = "".join(chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c for c in s)
    s = s.lower()
    # 只保留字母/数字/汉字（英文须连写，故用分隔符保护单词边界）
    parts = NONWORD_RE.split(s)
    words = [p for p in parts if p]
    # 英文按空格保留单词，中文直接相连
    out = []
    for w in words:
        if re.search(r"[一-鿿]", w):
            out.append(w)
        else:
            out.extend(re.findall(r"[0-9a-z]+", w))
    # 重新拼接时保留分隔，避免 "aerkomminc" 这类误合
    joined = " ".join(out) if any(re.search(r"[一-鿿]", o) for o in out) else "".join(out)
    # 反复剥离后缀
    prev = None
    while prev != joined:
        prev = joined
        joined = SUFFIX_RE.sub("", joined).strip()
    return joined


def bigrams(s):
    s = s.strip()
    return set(s[i:i + 2] for i in range(len(s) - 1)) if len(s) >= 2 else set()


def load_lines(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return [ln.strip() for ln in f if ln.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", required=True, help="待查实体/个人名，一行一个")
    ap.add_argument("--list", required=True, help="摘录的名单文本或逐行实体列表")
    ap.add_argument("--out", help="把报告额外写出到此文件")
    args = ap.parse_args()

    targets = load_lines(args.names)
    list_text = "\n".join(load_lines(args.list))
    norm_text = normalize(list_text)
    list_bigrams = bigrams(norm_text)

    rows = []
    hit, cand = 0, 0
    for name in targets:
        norm = normalize(name)
        if not norm:
            continue
        if norm in norm_text:
            status, note = "命中", "归一化后精确子串命中"
            hit += 1
        else:
            nb = bigrams(norm)
            if nb:
                overlap = len(nb & list_bigrams) / len(nb)
                if overlap >= 0.5:
                    status, note = "候选", f"二元共现 {overlap:.0%}，疑似简称/变体，请人工核对"
                    cand += 1
                else:
                    status, note = "未命中", "无显著共现"
            else:
                status, note = "未命中", "名称过短无法比对"
        rows.append((name, norm, status, note))

    lines = ["# 名称比对报告（已归一化）", "",
             f"- 待查：{len(rows)} 个｜命中：{hit}｜候选：{cand}｜其余未命中",
             "", "| 待查名 | 归一化 | 结果 | 说明 |", "|--------|--------|------|------|"]
    for name, norm, status, note in rows:
        lines.append(f"| {name} | {norm} | {status} | {note} |")
    lines.append("")
    lines.append("> 候选项须经人工终判（名称变体/简称），不得自动定性为命中。")
    report = "\n".join(lines)

    print(report)
    if args.out:
        with io.open(args.out, "w", encoding="utf-8-sig", newline="") as f:
            f.write(report + "\n")
        print(f"\n报告已写出: {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
