from collections import Counter
from datetime import datetime


def generate_chart_data(items: list[dict], section_map: dict[str, list[dict]] | None = None) -> list[dict]:
    source_counter = Counter((x.get("source_name") or x.get("media_name") or "未知来源") for x in items)
    time_counter = Counter()
    for x in items:
        dt = x.get("published_at")
        if not dt:
            continue
        if isinstance(dt, datetime):
            key = dt.strftime("%Y-%m-%d")
        else:
            key = str(dt)[:10]
        time_counter[key] += 1

    section_counter = Counter({k: len(v) for k, v in (section_map or {}).items()})

    charts = [
        {
            "type": "bar",
            "chart_type": "bar",
            "title": "来源分布",
            "labels": list(source_counter.keys())[:10],
            "values": list(source_counter.values())[:10],
            "notes": "按抓取来源统计",
        },
        {
            "type": "line",
            "chart_type": "line",
            "title": "时间分布",
            "labels": sorted(time_counter.keys()),
            "values": [time_counter[k] for k in sorted(time_counter.keys())],
            "notes": "按发布日期统计",
        },
        {
            "type": "pie",
            "chart_type": "pie",
            "title": "分类分布",
            "labels": list(section_counter.keys()),
            "values": list(section_counter.values()),
            "notes": "按报告章节分类统计",
        },
    ]
    return charts
