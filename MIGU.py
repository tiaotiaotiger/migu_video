import os
import requests
import json
import time
import random
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

thread_mum = 1  # 并发线程数（1 为顺序执行，减轻对代理/咪咕的突发压力）

headers = {
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 Edg/145.0.0.0",
    "appCode": "miguvideo_default_h5",
    "appId": "miguvideo",
    "channel": "H5",
    "sec-ch-ua": "\"Chromium\";v=\"145\", \"Microsoft Edge\";v=\"145\", \"Not.A/Brand\";v=\"99\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "terminalId": "h5"
}

"""
lives = ['央视', '卫视', '地方', '体育', '影视', '少儿', '新闻', '教育', '纪实']
LIVE = {
    '热门': 'e7716fea6aa1483c80cfc10b7795fcb8',
    '体育': '7538163cdac044398cb292ecf75db4e0',
    '央视': '1ff892f2b5ab4a79be6e25b69d2f5d05',
    '卫视': '0847b3f6c08a4ca28f85ba5701268424',
    '地方': '855e9adc91b04ea18ef3f2dbd43f495b',
    '影视': '10b0d04cb23d4ac5945c4bc77c7ac44e',
    '新闻': 'c584f67ad63f4bc983c31de3a9be977c',
    '教育': 'af72267483d94275995a4498b2799ecd',
    '熊猫': 'e76e56e88fff4c11b0168f55e826445d',
    '综艺': '192a12edfef04b5eb616b878f031f32f',
    '少儿': 'fc2f5b8fd7db43ff88c4243e731ecede',
    '纪实': 'e1165138bdaa44b9a3138d74af6c6673'
}
"""
lives = ['央视', '卫视']
LIVE = {
    '央视': '1ff892f2b5ab4a79be6e25b69d2f5d05',
    '卫视': '0847b3f6c08a4ca28f85ba5701268424'
}
PID_NOT=['608807419', '608807416', '609006446', '609006476', '609154345', '609006450', '884121956', '708869532']

path = 'mig.m3u'
appVersion = "2600034600"
All_Live = []

# ---------- HTTP：Session 复用连接（program-sc + Apipost）----------
_http_session = None


def _get_http_session():
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
    # requests.Session 非线程安全；当前 thread_mum=1 无并发写 Session。若增大线程数请改用每线程 Session 或加锁。
    return _http_session


# ---------- Apipost 代理请求体：静态骨架只建一份，每次只换 header/query/url ----------
_PROJECT_REQUEST_STATIC_TAIL = {
    "body": {"parameter": []},
    "cookie": {"parameter": []},
    "auth": {"type": "noauth"},
    "pre_tasks": [],
    "post_tasks": [],
}

_COLLECTION_REQUEST_STATIC_TAIL = {
    "auth": {"type": "inherit"},
    "body": {
        "mode": "None",
        "parameter": [],
        "raw": "",
        "raw_parameter": [],
        "raw_schema": {"type": "object"},
        "binary": None,
    },
    "pre_tasks": [],
    "post_tasks": [],
    "cookie": {"parameter": [], "cookie_encode": 1},
    "restful": {"parameter": []},
    "tabs_default_active_key": "query",
}

_COLLECTION_ITEM_META = {
    "target_id": "3c5fd6a9786002",
    "target_type": "api",
    "parent_id": "0",
    "name": "MIGU",
    "parents": [],
    "method": "GET",
    "protocol": "http/1.1",
    "pre_url": "",
}

_STATIC_OPTION_ENV = {
    "env_id": "1",
    "env_name": "默认环境",
    "env_pre_url": "",
    "env_pre_urls": {
        "1": {"server_id": "1", "name": "默认服务", "sort": 1000, "uri": ""},
        "default": {"server_id": "1", "name": "默认服务", "sort": 1000, "uri": ""},
    },
    "environment": {},
}

_STATIC_OPTION_COOKIES = {"switch": 1, "data": []}

_STATIC_OPTION_SYSTEM_CONFIGS = {
    "send_timeout": 0,
    "auto_redirect": -1,
    "max_redirect_time": 5,
    "auto_gen_mock_url": -1,
    "request_param_auto_json": -1,
    "proxy": {
        "type": 2,
        "envfirst": 1,
        "bypass": [],
        "protocols": ["http"],
        "auth": {"authenticate": -1, "host": "", "username": "", "password": ""},
    },
    "ca_cert": {"open": -1, "path": "", "base64": ""},
    "client_cert": {},
}

_STATIC_CUSTOM_FUNCTIONS = {}

_STATIC_TEST_EVENTS = [
    {
        "type": "api",
        "data": {
            "target_id": "3c5fd6a9786002",
            "project_id": "57a21612a051000",
            "parent_id": "0",
            "target_type": "api",
        },
    }
]


def _build_apipost_body(header_parameter, query_parameter, url):
    project_request = {
        "header": {"parameter": header_parameter},
        "query": {"parameter": query_parameter},
        **_PROJECT_REQUEST_STATIC_TAIL,
    }
    collection_request = {
        "header": {"parameter": header_parameter},
        "query": {"parameter": query_parameter, "query_add_equal": 1},
        **_COLLECTION_REQUEST_STATIC_TAIL,
    }
    collection_item = {
        **_COLLECTION_ITEM_META,
        "request": collection_request,
        "url": url,
    }
    return {
        "option": {
            "scene": "http_request",
            "lang": "zh-cn",
            "globals": {},
            "project": {"request": project_request},
            "env": _STATIC_OPTION_ENV,
            "cookies": _STATIC_OPTION_COOKIES,
            "system_configs": _STATIC_OPTION_SYSTEM_CONFIGS,
            "custom_functions": _STATIC_CUSTOM_FUNCTIONS,
            "collection": [collection_item],
            "database_configs": {},
        },
        "test_events": _STATIC_TEST_EVENTS,
    }


def format_date_ymd():
    current_date = datetime.now()
    return f"{current_date.year}{current_date.month:02d}{current_date.day:02d}"


def writefile(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def md5(text):
    md5_obj = hashlib.md5()
    md5_obj.update(text.encode('utf-8'))
    return md5_obj.hexdigest()


def getSaltAndSign(pid):
    timestamp = str(int(time.time() * 1000))
    random_num = random.randint(0, 999999)
    salt = f"{random_num:06d}25"
    suffix = "2cac4f2c6c3346a5b34e085725ef7e33migu" + salt[:4]
    app_t = timestamp + pid + appVersion[:8]
    sign = md5(md5(app_t) + suffix)
    return {
        "salt": salt,
        "sign": sign,
        "timestamp": timestamp
    }


def _play_url_from_response(resp_data):
    """从 playurl 响应中取出 url 与 urlInfo。"""
    url_info = (resp_data.get("body") or {}).get("urlInfo") or {}
    return url_info.get("url"), url_info


def _http_debug_enabled():
    """环境变量 MIGU_DEBUG_HTTP=1/true/yes/on 时打印每个频道的请求与解析后的响应。"""
    return os.environ.get("MIGU_DEBUG_HTTP", "").strip().lower() in ("1", "true", "yes", "on")


def _http_debug_max_chars():
    """响应/大段文本最大打印字符数；MIGU_DEBUG_HTTP_MAX=0 表示不截断（日志可能极大）。"""
    try:
        return int(os.environ.get("MIGU_DEBUG_HTTP_MAX", "12000"))
    except ValueError:
        return 12000


def _emit_http_debug_block(heading, text):
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


def get_content(pid, rate_type=None, http_debug_label=None):
    """
    请求咪咕 playurl。rate_type 为 None 时：广东卫视默认 2，其余默认 3。
    传入具体档位则强制使用该 rateType（用于失败后的清晰度回退）。
    """
    _headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "apipost-client-id": "8844aba6-ff71-4272-922e-3ac35106af4a",
        "apipost-language": "zh-cn",
        "apipost-machine": "13d46013f5c002",
        "apipost-platform": "Win",
        "apipost-terminal": "web",
        "apipost-token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJwYXlsb2FkIjp7InVzZXJfaWQiOjQwMjE2NjM4Mzk1NTcwNTg1NiwidGltZSI6MTc3MzI5NDk5NywidXVpZCI6IjNiOGU5NjUwLTFkZDgtMTFmMS05NDdiLTUyZTY1ODM4NDNhOSJ9fQ.7MLfNWaF0zh4Y2LGFzJvyZ33qdtsLvcqhRpN82DaWHo",
        "apipost-version": "8.2.6",
        "cache-control": "no-cache",
        "content-type": "application/json",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "sec-ch-ua": '"Google Chrome";v="145", "Chromium";v="145", "Not A(Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "cookie": "apipost-token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJwYXlsb2FkIjp7InVzZXJfaWQiOjQwMjE2NjM4Mzk1NTcwNTg1NiwidGltZSI6MTc3MzI5NDk5NywidXVpZCI6IjNiOGU5NjUwLTFkZDgtMTFmMS05NDdiLTUyZTY1ODM4NDNhOSJ9fQ.7MLfNWaF0zh4Y2LGFzJvyZ33qdtsLvcqhRpN82DaWHo; SERVERID=2861ec4778a7319ab8919bb9945cb13a|1773295099|1773295099; SERVERCORSID=2861ec4778a7319ab8919bb9945cb13a|1773295099|1773295099",
        "Referer": "https://workspace.apipost.net/594c83209c88000/apis",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }

    # ==================== 默认清晰度 ====================
    if rate_type is not None:
        rateType = str(rate_type)
    elif pid == "608831231":
        rateType = "2"   # 广东卫视默认 rateType=2 更稳定
        print("[特殊处理] 广东卫视 使用 rateType=2")
    else:
        rateType = "3"   # 其它频道默认 720P（非会员常用档位）
    # ====================================================

    client_id = md5(str(int(time.time() * 1000)))

    result = getSaltAndSign(pid)

    # 额外参数
    extra_params_str = "&flvEnable=true&super4k=true"

    URL = (f"https://play.miguvideo.com/playurl/v1/play/playurl?"
           f"sign={result['sign']}&rateType={rateType}&contId={pid}&"
           f"timestamp={result['timestamp']}&salt={result['salt']}{extra_params_str}")

    params_list = URL.split("?")[1].split("&")

    # 构建 Apipost Header
    header_parameter = [
        {"description": "", "field_type": "string", "is_checked": 1, "key": "AppVersion",
         "value": "2600034600", "not_None": 1, "schema": {"type": "string"}, "param_id": "3c60653273e0b3"},
        {"description": "", "field_type": "string", "is_checked": 1, "key": "TerminalId",
         "value": "android", "not_None": 1, "schema": {"type": "string"}, "param_id": "3c6075c1f3e0e1"},
        {"description": "", "field_type": "string", "is_checked": 1, "key": "X-UP-CLIENT-CHANNEL-ID",
         "value": "2600034600-99000-201600010010028", "not_None": 1, "schema": {"type": "string"}, "param_id": "3c60858bb3e10c"},
        {"description": "", "field_type": "string", "is_checked": 1, "key": "ClientId",
         "value": client_id, "not_None": 1, "schema": {"type": "string"}, "param_id": "clientid_new"}
    ]

    # CCTV5 / CCTV5+ 不加 appCode
    if pid not in ["641886683", "641886773"]:
        header_parameter.append({
            "description": "", "field_type": "string", "is_checked": 1, "key": "appCode",
            "value": "miguvideo_default_android", "not_None": 1, "schema": {"type": "string"}, "param_id": "appcode_new"
        })

    # 动态生成 query parameter
    query_parameter = []
    for idx, p in enumerate(params_list):
        if '=' in p:
            k, v = p.split('=', 1)
            query_parameter.append({
                "param_id": f"qp_{idx}",
                "field_type": "string",
                "is_checked": 1,
                "key": k,
                "not_None": 1,
                "value": v,
                "description": ""
            })

    body = _build_apipost_body(header_parameter, query_parameter, URL)

    body_str = json.dumps(body, separators=(",", ":"))
    proxy_url = "https://workspace.apipost.net/proxy/v2/http"

    resp = _get_http_session().post(proxy_url, headers=_headers, data=body_str, timeout=15)
    
    try:
        result = resp.json()
        response_body = result["data"]["data"]["response"]["body"]
        resp_obj = json.loads(response_body)
    except Exception as e:
        print(f"Apipost 返回解析失败: {e}")
        print("原始响应:", resp.text[:500])
        if _http_debug_enabled():
            _emit_http_debug_block(
                f"Apipost 原始 HTTP 文本 (status={resp.status_code})",
                resp.text or "",
            )
        raise

    if _http_debug_enabled():
        tag = http_debug_label or pid
        req_lines = [
            f"频道标识: {tag}  pID={pid}  rateType={rateType}",
            f"咪咕 playurl: {URL}",
            f"经 Apipost 代理: POST {proxy_url}",
            f"Apipost 请求体 JSON 长度: {len(body_str)} 字节",
        ]
        if os.environ.get("MIGU_DEBUG_HTTP_FULL", "").strip().lower() in ("1", "true", "yes", "on"):
            req_lines.append("--- Apipost 请求体 JSON（可能含 token，勿公开日志）---")
            req_lines.append(body_str)
        _emit_http_debug_block(f"[playurl] 请求摘要 / 频道 [{tag}]", "\n".join(req_lines))
        _emit_http_debug_block(
            f"[playurl] 解析后的业务响应 / 频道 [{tag}]",
            json.dumps(resp_obj, ensure_ascii=False, indent=2),
        )

    return resp_obj


def get_content_with_fallback(pid, channel_name=""):
    """
    部分卫视在 rateType=3 时偶发无 url；按清晰度回退并重试同一档位，提高成功率。
    广东卫视优先 2，其余优先 3。
    """
    if pid == "608831231":
        rate_candidates = ["2", "3", "1"]
    else:
        rate_candidates = ["3", "2", "1"]

    last_resp = None
    last_err = None
    for ri, rt in enumerate(rate_candidates):
        for attempt in range(2):
            try:
                time.sleep(0.08 + random.random() * 0.22)
                resp_data = get_content(pid, rate_type=rt, http_debug_label=channel_name or None)
                last_resp = resp_data
                raw_url, _ = _play_url_from_response(resp_data)
                if raw_url:
                    if ri > 0 or attempt > 0:
                        tag = channel_name or pid
                        print(f"[回退/重试] 频道 [{tag}] rateType={rt} 第{attempt + 1}次 → 拿到播放地址")
                    return resp_data
            except Exception as e:
                last_err = e
                tag = channel_name or pid
                print(f"[重试] 频道 [{tag}] rateType={rt} 第{attempt + 1}次 请求异常: {e}")
            time.sleep(0.35 + random.random() * 0.35)
    if last_resp is not None:
        tag = channel_name or pid
        print(f"--- playurl 仍无地址（分类参考）频道 [{tag}] pID={pid} 最后一次响应 ---")
        print(json.dumps(last_resp, ensure_ascii=False, indent=2))
    raise ValueError("接口未返回播放地址 url（已尝试 rateType 回退与重试）") from last_err


def getddCalcu720p(url, pID):
    puData = url.split("&puData=")[1]
    keys = "cdabyzwxkl"
    ddCalcu = []
    for i in range(0, int(len(puData) / 2)):
        ddCalcu.append(puData[int(len(puData)) - i - 1])
        ddCalcu.append(puData[i])
        if i == 1:
            ddCalcu.append("v")
        if i == 2:
            ddCalcu.append(keys[int(format_date_ymd()[2])])
        if i == 3:
            ddCalcu.append(keys[int(pID[6])])
        if i == 4:
            ddCalcu.append("a")
    return f'{url}&ddCalcu={"".join(ddCalcu)}&sv=10004&ct=android'


def append_All_Live(live, flag, data):
    try:
        respData = get_content_with_fallback(data["pID"], data.get("name", ""))
        raw_url, url_info = _play_url_from_response(respData)
        if not raw_url:
            raise ValueError("接口未返回播放地址 url")
        real_pid = respData.get("body", {}).get("content", {}).get("contId", data["pID"])

        playurl = getddCalcu720p(raw_url, real_pid)
        rate = url_info.get("rateType", "未知")

        pics = data.get("pics") or {}
        logo = pics.get("highResolutionH", "")

        content = f'#EXTINF:-1 tvg-id="{data["name"]}" tvg-name="{data["name"]}" tvg-logo="{logo}" group-title="{live}",{data["name"]}\n{playurl}\n'
        All_Live[flag] = content
        print(f'频道 [{data["name"]}] rateType={rate} → 更新成功')
    except Exception as e:
        print(f'频道 [{data["name"]}] 更新失败！ ERROR: {e}')


def update(live, url):
    global All_Live
    pool = ThreadPoolExecutor(thread_mum)
    resp = _get_http_session().get(url, headers=headers, timeout=15)
    response = resp.json()
    if _http_debug_enabled():
        _emit_http_debug_block(
            f"[节目单] GET {url}  status={resp.status_code}  分类={live}",
            json.dumps(response, ensure_ascii=False, indent=2),
        )
    dataList = response["body"]["dataList"]
    for data in dataList:
        if data["pID"] in PID_NOT:
            continue
        # 必须用当前列表长度作为下标：跳过 PID_NOT 时 enumerate 的下标会与 append 次数不一致
        idx = len(All_Live)
        All_Live.append("")
        pool.submit(append_All_Live, live, idx, data)
    pool.shutdown()


def main():
    header = (
        r'#EXTM3U x-tvg-url="https://cdn.jsdelivr.net/gh/develop202/migu_video/playback.xml,https://ghfast.top/raw.githubusercontent.com/develop202/migu_video/refs/heads/main/playback.xml,https://hk.gh-proxy.org/raw.githubusercontent.com/develop202/migu_video/refs/heads/main/playback.xml,https://develop202.github.io/migu_video/playback.xml,https://raw.githubusercontents.com/develop202/migu_video/refs/heads/main/playback.xml" catchup="append" catchup-source="&playbackbegin=${(b)yyyyMMddHHmmss}&playbackend=${(e)yyyyMMddHHmmss}"'
        + "\n"
    )

    for live in lives:
        print(f"\n分类 ----- [{live}] ----- 开始更新...")
        url = f'https://program-sc.miguvideo.com/live/v2/tv-data/{LIVE[live]}'
        update(live, url)
    
    chunks = []
    for content in All_Live:
        if content:
            chunks.append(content)
    writefile(path, header + "".join(chunks))
    
    print("\n全部更新完成！m3u 文件已生成：", path)


if __name__ == "__main__":
    main()
