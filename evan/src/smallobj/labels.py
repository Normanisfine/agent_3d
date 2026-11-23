"""清单 v2 的开放词表（借 SceneRig：先让视觉语言模型列出画面里的物体，再按类别分割）。

每个场景一次 Claude 调用，看几张高清帧，列出看到的物体类别（scripts/propose_labels.sh），
再并进固定类别表 configs/inventory_labels.json。只看输入视频的帧，不碰真值。
"""
import json
import re


def _singular(word: str) -> str:
    w = word
    if len(w) > 3 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and w.endswith(("ches", "shes", "sses", "xes")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def _norm(label: str) -> str:
    words = re.sub(r"\s+", " ", str(label).strip().lower()).split(" ")
    if not words or not words[0]:
        return ""
    words[-1] = _singular(words[-1])
    return " ".join(words)


def parse(text: str, max_words: int = 4, max_labels: int = 80) -> list:
    """从模型回复里取出 {"labels": [...]}：统一小写、末词变单数、去重；空的、超过 max_words 个词的、
    带奇怪字符的丢掉。取不到就返回空表。"""
    for m in re.finditer(r"\{.*?\}", text, flags=re.S):
        try:
            raw = json.loads(m.group(0)).get("labels")
        except (json.JSONDecodeError, AttributeError):
            continue
        if not isinstance(raw, list):
            continue
        out = []
        for lab in raw:
            n = _norm(lab)
            if n and len(n.split(" ")) <= max_words and re.fullmatch(r"[a-z][a-z '\-]*", n) and n not in out:
                out.append(n)
        return out[:max_labels]
    return []


def merge(fixed: list, proposed: list) -> list:
    """固定类别表照原样、原顺序在前，后面接新提出的（下划线和空格当成一样）。"""
    seen = {f.replace("_", " ") for f in fixed}
    out = list(fixed)
    for p in proposed:
        if p.replace("_", " ") not in seen:
            seen.add(p.replace("_", " "))
            out.append(p)
    return out
