"""各实验组的提示词和请求（configs/prompts/<arm>.md、configs/requests/<arm>.json）的渲染。

A2、A3r、A3v 都在 A1 的全文上只做增加（A3 另把 A1 里"不许用生成器"那一句换成"或用下面的生成工具"），
tests/test_prompts.py 检查这一点。用法：python -m smallobj.prompts <arm> <out_prompt> <out_request> KEY=VALUE ...
"""
import re
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parents[2]
ARMS = ("A0", "A1", "A2", "A3r", "A3v")


def template(arm: str) -> str:
    return (PROJ / "configs" / "prompts" / f"{arm}.md").read_text()


def _fill(text: str, values: dict) -> str:
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    left = re.findall(r"\{\{[A-Z_]+\}\}", text)
    if left:
        raise ValueError(f"模板里还有没填的变量：{sorted(set(left))}")
    return text


def render(arm: str, values: dict) -> tuple:
    if arm not in ARMS:
        raise ValueError(f"不认识的实验组 {arm}")
    return _fill(template(arm), values), _fill((PROJ / "configs" / "requests" / f"{arm}.json").read_text(), values)


if __name__ == "__main__":
    arm, out_prompt, out_request = sys.argv[1:4]
    values = dict(a.split("=", 1) for a in sys.argv[4:])
    prompt, request = render(arm, values)
    Path(out_prompt).write_text(prompt)
    Path(out_request).write_text(request)
