"""Pre-publish safety checklist.

A purely-offline interactive script that walks a writer through choices that
affect how exposed they are after publishing. Output: a risk score and a
list of concrete suggestions.

This module deliberately avoids making the writer feel surveilled or judged.
The phrasing is "consideration" not "violation"; the score is a hint, not a
verdict.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Question:
    key: str
    prompt: str
    options: list[tuple[str, str, int]]  # (key, label, points-if-chosen)
    explainer: str = ""  # shown when the user picks a higher-risk option


@dataclass
class ChecklistResult:
    score: int                 # higher = higher exposure
    max_score: int
    answers: dict[str, str]
    suggestions: list[str] = field(default_factory=list)

    @property
    def band(self) -> str:
        ratio = self.score / max(self.max_score, 1)
        if ratio < 0.25:
            return "low"
        if ratio < 0.55:
            return "moderate"
        return "high"


QUESTIONS: list[Question] = [
    Question(
        key="visibility",
        prompt="作品的可见范围设置是什么？",
        options=[
            ("registered", "仅注册用户可见", 0),
            ("public", "对所有访客公开", 3),
            ("unsure", "我不确定 / 还没设置", 3),
        ],
        explainer="对所有访客公开会让无账号爬虫直接抓取。AO3 提供 'visible only to registered users' 选项。",
    ),
    Question(
        key="download",
        prompt="是否允许下载（PDF / EPUB / MOBI 等）？",
        options=[
            ("off", "已关闭下载选项", 0),
            ("on", "开启下载", 2),
            ("unsure", "不清楚", 2),
        ],
        explainer="关闭下载不能阻止爬虫，但能减少二次传播时的便利性。",
    ),
    Question(
        key="real_name",
        prompt="作品页面（包括简介、备注、用户名）是否包含可关联到现实身份的信息？",
        options=[
            ("none", "没有任何真实身份关联", 0),
            ("nickname_only", "只有常用昵称，与现实身份隔离", 1),
            ("partial", "可能包含微博 / QQ / 真名片段", 3),
            ("unsure", "不确定", 2),
        ],
        explainer="跨平台关联是去匿名化的主要路径。考虑给同人创作单独维护一套身份。",
    ),
    Question(
        key="contact",
        prompt="是否在作品里留了私下联系方式（QQ / 微信 / 邮箱）？",
        options=[
            ("no", "完全没有", 0),
            ("burner", "有，但是一次性 / 专用账号", 1),
            ("primary", "有，是常用账号", 3),
        ],
        explainer="常用联系方式一旦被截图传播，定位代价远高于换号代价。",
    ),
    Question(
        key="content_sensitivity",
        prompt="作品内容的敏感程度（仅你自己评估，不必告诉任何人）：",
        options=[
            ("low", "圈外人看也无害", 0),
            ("moderate", "圈内向，圈外可能引起举报", 2),
            ("high", "明显敏感，圈外曝光会带来现实风险", 4),
        ],
        explainer="越敏感的内容越应该收紧可见范围、断开身份关联。",
    ),
    Question(
        key="backup",
        prompt="本地是否有作品的完整备份（不依赖发布平台）？",
        options=[
            ("yes", "有", 0),
            ("partial", "部分章节", 1),
            ("no", "没有", 2),
        ],
        explainer="平台账号被封 / 锁是常见情况。完整本地备份 + 哈希存证是最低成本的自保。",
    ),
    Question(
        key="fingerprint",
        prompt="是否对作品做过指纹 / 存证处理？",
        options=[
            ("both", "指纹和时间戳都有", 0),
            ("one", "只有其中之一", 1),
            ("none", "都没有", 2),
        ],
        explainer="即使不能阻止爬取，事后维权也需要『我比对方更早持有这份内容』的证据。",
    ),
]


def suggestions_for(answers: dict[str, str]) -> list[str]:
    out: list[str] = []
    if answers.get("visibility") in ("public", "unsure"):
        out.append("考虑把作品改为仅注册用户可见（AO3 设置项 \"visible only to registered users\"）。")
    if answers.get("download") in ("on", "unsure"):
        out.append("如果不希望被快速二次分发，可以在作品设置中关闭下载选项。")
    if answers.get("real_name") in ("partial", "unsure"):
        out.append("检查作品页面、用户名、简介、章节备注是否含有可关联现实身份的信息；为同人创作单独建立一套身份。")
    if answers.get("contact") == "primary":
        out.append("把作品里的联系方式换成一次性账号或干脆移除。")
    if answers.get("content_sensitivity") in ("moderate", "high"):
        out.append("敏感度越高，越应该收紧可见范围、断开跨平台身份关联，并保留好本地证据。")
    if answers.get("backup") in ("partial", "no"):
        out.append("准备一份完整本地备份；可以配合 `fic-guard timestamp` 生成哈希存证。")
    if answers.get("fingerprint") in ("one", "none"):
        out.append("用 `fic-guard fingerprint` 生成签名句指纹，用 `fic-guard timestamp` 生成时间戳存证。")
    if not out:
        out.append("从清单上看，已经处理得不错。定期重新评估（每次有新作品时跑一次）即可。")
    return out


def score_answers(answers: dict[str, str]) -> ChecklistResult:
    score = 0
    max_score = 0
    for q in QUESTIONS:
        chosen = answers.get(q.key)
        opt_map = {k: p for k, _, p in q.options}
        if chosen in opt_map:
            score += opt_map[chosen]
        max_score += max(p for _, _, p in q.options)
    return ChecklistResult(
        score=score,
        max_score=max_score,
        answers=dict(answers),
        suggestions=suggestions_for(answers),
    )


def run_interactive(prompt_fn: Callable[[str, list[tuple[str, str]]], str]) -> ChecklistResult:
    """Run the checklist using a UI-agnostic prompt function.

    `prompt_fn(prompt, options)` should return the key of the chosen option.
    This decoupling lets the CLI use Rich while tests can pass a stub.
    """
    answers: dict[str, str] = {}
    for q in QUESTIONS:
        choice = prompt_fn(q.prompt, [(k, label) for k, label, _ in q.options])
        answers[q.key] = choice
    return score_answers(answers)
