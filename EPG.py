#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
根据 channels_pid.json（频道显示名 -> 咪咕直播 pID）拉取当日节目单，生成 epg.xml。
可单独运行，不依赖 MIGU.py。

示例：
  python EPG.py
  python EPG.py -c channels_pid.json -o epg.xml -d 20260507
环境变量 MIGU_DEBUG_HTTP=1 时打印各频道接口 JSON（与 MIGU.py 一致）。
"""

import argparse
import json
import os
import random
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Origin": "https://m.miguvideo.com",
    "Pragma": "no-cache",
    "Referer": "https://m.miguvideo.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Support-Pendant": "1",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0"
    ),
    "appCode": "miguvideo_default_h5",
    "appId": "miguvideo",
    "channel": "H5",
    "sec-ch-ua": '"Chromium";v="145", "Microsoft Edge";v="145", "Not.A/Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "terminalId": "h5",
}

CN_TZ = timezone(timedelta(hours=8))

_http_session: Optional[requests.Session] = None


def _session() -> requests.Session:
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
    return _http_session


def _http_debug_enabled() -> bool:
    return os.environ.get("MIGU_DEBUG_HTTP", "").strip().lower() in ("1", "true", "yes", "on")


def _http_debug_max_chars() -> int:
    try:
        return int(os.environ.get("MIGU_DEBUG_HTTP_MAX", "12000"))
    except ValueError:
        return 12000


def _emit_http_debug_block(heading: str, text: str) -> None:
    if not _http_debug_enabled():
        return
    total = len(text)
    mx = _http_debug_max_chars()
    if mx <= 0 or total <= mx:
        print(f"========== {heading} (长度 {total}) ==========\n{text}\n==========\n")
    else:
        print(
            f"========== {heading} (长度 {total}，已截断至 {mx}；设 MIGU_DEBUG_HTTP_MAX=0 可全量) ==========\n"
            f"{text[:mx]}\n...(截断)\n==========\n"
        )


def china_date_yyyymmdd() -> str:
    d = datetime.now(CN_TZ)
    return f"{d.year}{d.month:02d}{d.day:02d}"


def _xml_escape_text(s) -> str:
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _xml_escape_attr(s) -> str:
    return _xml_escape_text(s)


def ms_to_xmltv_time(ms) -> str:
    if ms is None:
        return ""
    dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).astimezone(CN_TZ)
    return dt.strftime("%Y%m%d%H%M%S") + " +0800"


def fetch_day_programmes(pid: str, yyyymmdd: str, channel_label: str = "") -> list:
    url = f"https://program-sc.miguvideo.com/live/v2/tv-programs-data/{pid}/{yyyymmdd}"
    resp = _session().get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if _http_debug_enabled():
        tag = channel_label or pid
        _emit_http_debug_block(
            f"[EPG] GET {url}  status={resp.status_code}  频道={tag}",
            json.dumps(data, ensure_ascii=False, indent=2),
        )
    if str(data.get("code")) != "200" and data.get("code") != 200:
        print(f"[EPG] 接口非 200 频道 [{channel_label or pid}] code={data.get('code')} msg={data.get('message')}")
        return []
    body = data.get("body") or {}
    rows = []
    for block in body.get("program") or []:
        for item in block.get("content") or []:
            rows.append(item)
    rows.sort(key=lambda x: (x.get("startTime") or 0, x.get("ranking") or ""))
    return rows


def build_epg_xml(mapping: dict, yyyymmdd: str) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<tv generator-info-name="Tak" generator-info-url="https://github.com/develop202/migu_video">',
    ]
    for name, pid in mapping.items():
        pid = str(pid).strip()
        nid = _xml_escape_attr(name)
        dname = _xml_escape_text(name)
        lines.append(f'    <channel id="{nid}">')
        lines.append(f'        <display-name lang="zh">{dname}</display-name>')
        lines.append("    </channel>")
        try:
            time.sleep(0.06 + random.random() * 0.12)
            progs = fetch_day_programmes(pid, yyyymmdd, channel_label=name)
        except Exception as e:
            print(f"[EPG] 拉取失败 [{name}] pID={pid}: {e}")
            progs = []
        for p in progs:
            title = p.get("contName") or ""
            st = ms_to_xmltv_time(p.get("startTime"))
            et = ms_to_xmltv_time(p.get("endTime"))
            if not st or not et:
                continue
            lines.append(f'    <programme channel="{nid}" start="{st}" stop="{et}">')
            lines.append(f'        <title lang="zh">{_xml_escape_text(title)}</title>')
            lines.append("    </programme>")
        print(f"[EPG] 频道 [{name}] 节目条数: {len(progs)}")
    lines.append("</tv>")
    return "\n".join(lines) + "\n"


def load_channels_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"{path} 根节点必须是 JSON 对象（频道名: pID）")
    return raw


def write_utf8(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main() -> None:
    ap = argparse.ArgumentParser(description="从 channels_pid.json 生成 epg.xml")
    ap.add_argument("-c", "--channels", default="channels_pid.json", help="频道映射 JSON 路径")
    ap.add_argument("-o", "--output", default="epg.xml", help="输出 XML 路径")
    ap.add_argument(
        "-d",
        "--date",
        default=None,
        help="节目单日期 yyyyMMdd；默认东八区当天",
    )
    args = ap.parse_args()

    ymd = args.date or china_date_yyyymmdd()
    if len(ymd) != 8 or not ymd.isdigit():
        raise SystemExit(f"无效日期: {ymd!r}，应为 8 位 yyyyMMdd")

    mapping = load_channels_json(args.channels)
    if not mapping:
        raise SystemExit(f"映射为空: {args.channels}")

    print(f"读取: {args.channels}  共 {len(mapping)} 个频道")
    print(f"日期: {ymd}  输出: {args.output}")

    xml = build_epg_xml(mapping, ymd)
    write_utf8(args.output, xml)
    print("完成:", args.output)


if __name__ == "__main__":
    main()
