from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import feedparser
import requests
import yaml
from dateutil import parser as date_parser
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "sources.yml"
SKILL_PATH = ROOT / "skills" / "hotspot-analyst" / "SKILL.md"
TEMPLATE_DIR = ROOT / "templates"
PUBLIC_DIR = ROOT / "public"
DATA_DIR = PUBLIC_DIR / "data"
ARCHIVE_DIR = PUBLIC_DIR / "archive"
LOCAL_ENV_FILES = (ROOT / ".env.local", ROOT / ".env")


@dataclass
class Item:
    id: str
    title: str
    url: str
    source_id: str
    source_name: str
    source_type: str
    published_at: str | None
    summary: str
    author: str | None = None
    engagement: int = 0
    score: float = 0.0
    keywords: list[str] | None = None


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_local_env() -> None:
    for path in LOCAL_ENV_FILES:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            name = name.strip()
            value = value.strip().strip('"').strip("'")
            if name and name not in os.environ:
                os.environ[name] = value


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def stable_id(*parts: str) -> str:
    raw = "|".join(part or "" for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = date_parser.parse(str(value))
        except (TypeError, ValueError, OverflowError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso_or_none(value: Any) -> str | None:
    dt = parse_date(value)
    return dt.isoformat() if dt else None


def request_json(url: str, headers: dict[str, str] | None = None, params: dict[str, str] | None = None) -> Any:
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_rss(source: dict[str, Any], max_items: int) -> tuple[list[Item], str]:
    feed = feedparser.parse(source["url"])
    status = "ok"
    if getattr(feed, "bozo", False):
        status = f"warning: {getattr(feed, 'bozo_exception', 'feed parse issue')}"

    items: list[Item] = []
    for entry in feed.entries[:max_items]:
        title = strip_html(entry.get("title", "Untitled"))
        url = entry.get("link") or source["url"]
        published = entry.get("published") or entry.get("updated")
        summary = strip_html(entry.get("summary") or entry.get("description") or "")
        author = entry.get("author")
        items.append(
            Item(
                id=stable_id(source["id"], url, title),
                title=title,
                url=url,
                source_id=source["id"],
                source_name=source["name"],
                source_type=source["type"],
                published_at=iso_or_none(published),
                summary=summary[:900],
                author=author,
            )
        )
    return items, status


def fetch_github_search(source: dict[str, Any], max_items: int) -> tuple[list[Item], str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "claude-skills-hotspot-report",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = request_json(source["url"], headers=headers)
    repos = payload.get("items", [])[:max_items]
    items: list[Item] = []
    for repo in repos:
        full_name = repo.get("full_name", "unknown/repo")
        stars = int(repo.get("stargazers_count") or 0)
        forks = int(repo.get("forks_count") or 0)
        engagement = stars + forks
        summary_bits = [
            repo.get("description") or "",
            f"Stars: {stars}",
            f"Language: {repo.get('language') or 'unknown'}",
        ]
        items.append(
            Item(
                id=stable_id(source["id"], repo.get("html_url", ""), full_name),
                title=full_name,
                url=repo.get("html_url") or repo.get("url") or source["url"],
                source_id=source["id"],
                source_name=source["name"],
                source_type=source["type"],
                published_at=iso_or_none(repo.get("pushed_at") or repo.get("updated_at")),
                summary=strip_html(" | ".join(summary_bits)),
                author=repo.get("owner", {}).get("login"),
                engagement=engagement,
            )
        )
    return items, "ok"


def flatten_tweets(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("tweets", "data", "statuses", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    nested = payload.get("result")
    if isinstance(nested, dict):
        return flatten_tweets(nested)
    return []


def fetch_twitterapi_search(source: dict[str, Any], max_items: int) -> tuple[list[Item], str]:
    key_env = source.get("api_key_env", "TWITTERAPI_KEY")
    api_key = os.getenv(key_env)
    if not api_key:
        return [], f"skipped: missing {key_env}"

    payload = request_json(
        source["url"],
        headers={"X-API-Key": api_key, "User-Agent": "claude-skills-hotspot-report"},
        params={"query": source.get("query", "AI"), "queryType": source.get("query_type", "Top")},
    )
    tweets = flatten_tweets(payload)[:max_items]
    items: list[Item] = []
    for tweet in tweets:
        text = strip_html(tweet.get("text") or tweet.get("content") or tweet.get("full_text") or "")
        tweet_id = str(tweet.get("id") or tweet.get("tweet_id") or stable_id(text))
        author = tweet.get("author") or tweet.get("user") or {}
        username = author.get("userName") or author.get("screen_name") if isinstance(author, dict) else None
        url = tweet.get("url")
        if not url and username:
            url = f"https://x.com/{username}/status/{tweet_id}"
        like_count = int(tweet.get("likeCount") or tweet.get("favorite_count") or 0)
        repost_count = int(tweet.get("retweetCount") or tweet.get("retweet_count") or 0)
        items.append(
            Item(
                id=stable_id(source["id"], tweet_id, text),
                title=text[:120] or "X post",
                url=url or source["url"],
                source_id=source["id"],
                source_name=source["name"],
                source_type=source["type"],
                published_at=iso_or_none(tweet.get("createdAt") or tweet.get("created_at")),
                summary=text[:900],
                author=username,
                engagement=like_count + repost_count,
            )
        )
    return items, "ok"


FETCHERS = {
    "rss": fetch_rss,
    "github_search": fetch_github_search,
    "twitterapi_search": fetch_twitterapi_search,
}


def normalize_url(url: str) -> str:
    url = re.sub(r"[?&](utm_[^=]+|fbclid|gclid)=[^&]+", "", url)
    return url.rstrip("/").lower()


def find_keywords(item: Item, keywords: list[str]) -> list[str]:
    haystack = f"{item.title} {item.summary}".lower()
    hits = []
    for keyword in keywords:
        if keyword.lower() in haystack:
            hits.append(keyword)
    return hits


def score_items(items: list[Item], config: dict[str, Any], now: datetime) -> list[Item]:
    settings = config["settings"]
    sources = {source["id"]: source for source in config["sources"]}
    freshness_hours = float(settings.get("freshness_hours", 96))
    keywords = settings.get("keywords", [])

    for item in items:
        source_weight = float(sources.get(item.source_id, {}).get("weight", 1.0))
        item.keywords = find_keywords(item, keywords)
        keyword_score = len(item.keywords) * 3.0
        engagement_score = math.log1p(max(item.engagement, 0))
        recency_score = 0.0
        published = parse_date(item.published_at)
        if published:
            age_hours = max((now - published).total_seconds() / 3600, 0)
            recency_score = max(0.0, (freshness_hours - age_hours) / freshness_hours) * 8.0
        item.score = round((source_weight * 10) + keyword_score + engagement_score + recency_score, 2)
    return sorted(items, key=lambda value: value.score, reverse=True)


def dedupe_items(items: list[Item]) -> list[Item]:
    seen: set[str] = set()
    deduped: list[Item] = []
    for item in items:
        key = normalize_url(item.url) or item.title.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def collect_items(config: dict[str, Any]) -> tuple[list[Item], list[dict[str, Any]]]:
    settings = config["settings"]
    max_items = int(settings.get("max_items_per_source", 16))
    all_items: list[Item] = []
    statuses: list[dict[str, Any]] = []

    for source in config.get("sources", []):
        if not source.get("enabled", True):
            statuses.append({"source": source["name"], "status": "disabled", "count": 0})
            continue
        fetcher = FETCHERS.get(source.get("type"))
        if not fetcher:
            statuses.append({"source": source["name"], "status": f"skipped: unsupported type {source.get('type')}", "count": 0})
            continue
        try:
            items, status = fetcher(source, max_items)
            all_items.extend(items)
            statuses.append({"source": source["name"], "status": status, "count": len(items)})
        except Exception as exc:  # Keep the scheduled run alive even if one source fails.
            statuses.append({"source": source["name"], "status": f"error: {exc}", "count": 0})

    return all_items, statuses


def extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    candidates = [text]
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def compact_error(exc: Exception) -> str:
    message = str(exc)
    if "insufficient_quota" in message or "exceeded your current quota" in message:
        return "OpenAI quota is insufficient. Please enable billing or add credits in the OpenAI Platform project."
    if "model_not_found" in message or "does not exist" in message:
        return "The configured model is not available for this API key. Change OPENAI_MODEL or config/sources.yml."
    message = re.sub(r"\s+", " ", message).strip()
    return message[:220]


def build_analysis_prompt(items: list[Item]) -> str:
    compact_items = [
        {
            "id": item.id,
            "title": item.title,
            "url": item.url,
            "source": item.source_name,
            "published_at": item.published_at,
            "summary": item.summary[:520],
            "engagement": item.engagement,
            "score": item.score,
            "keywords": item.keywords or [],
        }
        for item in items[:40]
    ]
    return (
        "请分析这些热点候选，输出符合 Skill 要求的 JSON。"
        "重点关注 AI Agent、自动化、模型、开发工具、内容生产和商业机会。\n\n"
        f"{json.dumps(compact_items, ensure_ascii=False)}"
    )


def analyze_with_openai(items: list[Item], config: dict[str, Any]) -> tuple[dict[str, Any], str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return fallback_analysis(items, config), "fallback: missing OPENAI_API_KEY"

    try:
        from openai import OpenAI
    except ImportError:
        return fallback_analysis(items, config), "fallback: openai package unavailable"

    model = os.getenv("OPENAI_MODEL") or config["settings"].get("openai_model", "gpt-5.5")
    skill = SKILL_PATH.read_text(encoding="utf-8")
    prompt = build_analysis_prompt(items)

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model=model,
            instructions=skill,
            input=prompt,
            max_output_tokens=3500,
        )
        text = getattr(response, "output_text", "") or ""
        parsed = extract_json(text)
        if parsed:
            return parsed, f"openai: {model}"
        return fallback_analysis(items, config), "fallback: OpenAI returned non-JSON"
    except Exception as exc:
        return fallback_analysis(items, config), f"fallback: OpenAI error: {compact_error(exc)}"


def analyze_with_claude(items: list[Item], config: dict[str, Any]) -> tuple[dict[str, Any], str]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return fallback_analysis(items, config), "fallback: missing ANTHROPIC_API_KEY"

    try:
        from anthropic import Anthropic
    except ImportError:
        return fallback_analysis(items, config), "fallback: anthropic package unavailable"

    model = os.getenv("ANTHROPIC_MODEL") or config["settings"].get("anthropic_model", "claude-sonnet-4-6")
    skill = SKILL_PATH.read_text(encoding="utf-8")
    prompt = build_analysis_prompt(items)

    try:
        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=3500,
            temperature=0.2,
            system=skill,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "\n".join(block.text for block in message.content if getattr(block, "type", "") == "text")
        parsed = extract_json(text)
        if parsed:
            return parsed, f"claude: {model}"
        return fallback_analysis(items, config), "fallback: Claude returned non-JSON"
    except Exception as exc:
        return fallback_analysis(items, config), f"fallback: Claude error: {compact_error(exc)}"


def analyze_items(items: list[Item], config: dict[str, Any]) -> tuple[dict[str, Any], str]:
    provider = (os.getenv("AI_PROVIDER") or config["settings"].get("provider", "openai")).lower()
    providers = ["openai", "anthropic"] if provider == "openai" else ["anthropic", "openai"]

    statuses: list[str] = []
    for candidate in providers:
        if candidate == "openai":
            analysis, status = analyze_with_openai(items, config)
        else:
            analysis, status = analyze_with_claude(items, config)
        if not status.startswith("fallback:"):
            return analysis, status
        statuses.append(status)

    return fallback_analysis(items, config), "fallback: " + " | ".join(statuses)


def fallback_analysis(items: list[Item], config: dict[str, Any]) -> dict[str, Any]:
    keywords = config["settings"].get("keywords", [])
    counts: dict[str, int] = {keyword: 0 for keyword in keywords}
    for item in items:
        for keyword in item.keywords or []:
            counts[keyword] = counts.get(keyword, 0) + 1

    top_keywords = [item for item in sorted(counts.items(), key=lambda pair: pair[1], reverse=True) if item[1] > 0][:5]
    trend_radar = [
        {
            "name": keyword,
            "signal": "上升" if count >= 3 else "观察",
            "why": f"本轮采集中出现 {count} 次，值得继续跟踪。",
            "evidence": [item.id for item in items if keyword in (item.keywords or [])][:3],
            "action": "查看来源原文，判断是否适合沉淀成选题或自动化用例。",
        }
        for keyword, count in top_keywords
    ]
    briefs = [
        {
            "item_id": item.id,
            "title": item.title[:80],
            "takeaway": item.summary[:120] or "该条目在当前来源中得分靠前。",
            "why_it_matters": f"来自 {item.source_name}，综合热度分 {item.score}。",
            "tags": item.keywords[:4] if item.keywords else [item.source_type],
        }
        for item in items[:10]
    ]
    return {
        "executive_summary": "本次报告使用本地规则完成摘要，因为还没有配置 ANTHROPIC_API_KEY。页面和抓取链路已经跑通，接入 Claude 后会自动生成更细的趋势判断、机会点和风险提醒。",
        "trend_radar": trend_radar,
        "briefs": briefs,
        "opportunities": ["把高频关键词沉淀成固定监控主题。", "将高分条目转成内容选题、产品灵感或竞品观察清单。"],
        "watchlist": ["连续 2-3 次报告都出现的主题。", "GitHub 上近期高活跃但还没有形成主流讨论的项目。"],
        "risks": ["RSS/API 来源可能限流或返回噪声，需要持续维护关键词和来源白名单。"],
    }


def build_stats(items: list[Item], statuses: list[dict[str, Any]], analysis_status: str, generated_at: datetime) -> dict[str, Any]:
    source_counts: dict[str, int] = {}
    keyword_counts: dict[str, int] = {}
    for item in items:
        source_counts[item.source_name] = source_counts.get(item.source_name, 0) + 1
        for keyword in item.keywords or []:
            keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1
    return {
        "total_items": len(items),
        "active_sources": len([status for status in statuses if status["count"] > 0]),
        "source_counts": sorted(source_counts.items(), key=lambda pair: pair[1], reverse=True),
        "keyword_counts": sorted(keyword_counts.items(), key=lambda pair: pair[1], reverse=True)[:12],
        "analysis_status": analysis_status,
        "generated_at_iso": generated_at.isoformat(),
    }


def copy_latest_archive(index_path: Path, generated_at: datetime) -> str:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_name = f"report-{generated_at.strftime('%Y%m%d-%H%M%S')}.html"
    archive_path = ARCHIVE_DIR / archive_name
    shutil.copyfile(index_path, archive_path)
    return f"archive/{archive_name}"


def render_report(
    items: list[Item],
    analysis: dict[str, Any],
    stats: dict[str, Any],
    statuses: list[dict[str, Any]],
    config: dict[str, Any],
    generated_at_local: datetime,
) -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("report.html")
    data = {
        "settings": config["settings"],
        "generated_at": generated_at_local.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "items": [asdict(item) for item in items],
        "analysis": analysis,
        "stats": stats,
        "statuses": statuses,
    }
    (DATA_DIR / "latest.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    index_path = PUBLIC_DIR / "index.html"
    html = template.render(**data, archive_href=None)
    index_path.write_text(html, encoding="utf-8")
    archive_href = copy_latest_archive(index_path, generated_at_local)
    html = template.render(**data, archive_href=archive_href)
    index_path.write_text(html, encoding="utf-8")


def main() -> int:
    load_local_env()
    config = load_config()
    tz = ZoneInfo(config["settings"].get("timezone", "Asia/Shanghai"))
    now = datetime.now(timezone.utc)
    generated_at_local = now.astimezone(tz)

    raw_items, statuses = collect_items(config)
    items = dedupe_items(raw_items)
    items = score_items(items, config, now)
    max_total = int(config["settings"].get("max_total_items", 80))
    top_items = int(config["settings"].get("top_items", 30))
    items = items[:max_total]
    analysis, analysis_status = analyze_items(items[:top_items], config)
    stats = build_stats(items, statuses, analysis_status, generated_at_local)
    render_report(items[:top_items], analysis, stats, statuses, config, generated_at_local)

    print(json.dumps({"items": len(items), "analysis": analysis_status, "output": "public/index.html"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
