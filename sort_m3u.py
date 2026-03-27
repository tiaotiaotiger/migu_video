# -*- coding: utf-8 -*-
import re

# ====================== 配置 ======================
input_file = "migu.txt"           # 你的原始 m3u 文件
output_full = "migu.m3u"   # 完整排序文件（央视+卫视+其它）
output_cctv = "cctv.migu.m3u"         # 只包含央视 CCTV 频道的文件

# =================================================

def parse_m3u(content):
    channels = []
    lines = content.strip().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            extinf = line
            url = ""
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("#EXTINF:"):
                if lines[i].strip() and not lines[i].strip().startswith("#"):
                    url = lines[i].strip()
                i += 1
            if url:
                channels.append((extinf, url))
            continue
        i += 1
    return channels


def get_group_priority_and_key(extinf):
    """返回 (分组优先级, 组内排序键), group"""
    name_match = re.search(r',(.+?)$', extinf)
    name = name_match.group(1).strip() if name_match else ""

    # 分组判断
    if "央视" in extinf or any(c in name.upper() for c in ["CCTV", "CGTN"]):
        group = "央视"
        priority = 0
    elif "卫视" in extinf or "卫视" in name:
        group = "卫视"
        priority = 1
    else:
        group = "其它"
        priority = 2

    # 组内排序键（仅央视需要精细排序）
    if group == "央视":
        num_match = re.search(r'CCTV(\d+)', name)
        if num_match:
            num = int(num_match.group(1))
            sort_key = (0, num, name)          # CCTV数字排序
        elif "CGTN" in name:
            sort_key = (1, 0, name)
        elif any(x in name for x in ["欧洲", "美洲"]):
            sort_key = (2, 0, name)
        else:
            sort_key = (3, 0, name)
    else:
        sort_key = (0, 0, name)

    return (priority, *sort_key), group


def is_cctv_channel(extinf):
    """判断是否为纯央视 CCTV 频道，支持排除列表"""
    name_match = re.search(r',(.+?)$', extinf)
    name = name_match.group(1).strip() if name_match else ""
    
    # ============ 需要排除的频道列表（可随意添加） ============
    exclude_keywords = ["洲"]
    
    if any(keyword in name for keyword in exclude_keywords):
        return False
    # =========================================================
    
    # 保留条件
    return (
        "央视" in extinf 
        or bool(re.search(r'CCTV\d+', name)) 
        # or "CGTN" in name 
        # or "老故事" in name 
        # or "发现之旅" in name 
        # or "中学生" in name
    )


def main():
    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 提取头部
    header_match = re.match(r'(#EXTM3U.*?)(\n#EXTINF:|$)', content, re.DOTALL | re.IGNORECASE)
    header = header_match.group(1).strip() if header_match else "#EXTM3U"

    channels = parse_m3u(content)

    # 去重
    seen = {}
    unique_channels = []
    for extinf, url in channels:
        tvg_id = re.search(r'tvg-id="([^"]+)"', extinf)
        tvg_name = re.search(r'tvg-name="([^"]+)"', extinf)
        key = (tvg_id.group(1) if tvg_id else "") or (tvg_name.group(1) if tvg_name else "") or extinf
        if key not in seen:
            seen[key] = True
            unique_channels.append((extinf, url))

    # ==================== 生成完整排序文件 ====================
    sorted_channels = sorted(unique_channels, key=lambda x: get_group_priority_and_key(x[0])[0])

    with open(output_full, "w", encoding="utf-8") as f:
        f.write(header + "\n\n")
        current_group = None
        for extinf, url in sorted_channels:
            _, group = get_group_priority_and_key(extinf)
            if group != current_group:
                f.write(f"# ================================== {group} ==================================\n\n")
                current_group = group
            f.write(extinf + "\n")
            f.write(url + "\n\n")

    # ==================== 生成只包含央视 CCTV 的文件 ====================
    cctv_channels = [ch for ch in unique_channels if is_cctv_channel(ch[0])]
    # 对央视频道进行排序
    cctv_sorted = sorted(cctv_channels, key=lambda x: get_group_priority_and_key(x[0])[0][1:])  # 只用组内键排序

    with open(output_cctv, "w", encoding="utf-8") as f:
        f.write(header + "\n\n")
        f.write("# ================================== 央视 CCTV 频道 ==================================\n\n")
        for extinf, url in cctv_sorted:
            f.write(extinf + "\n")
            f.write(url + "\n\n")

    print(f"✅ 处理完成！")
    print(f"   输入频道数：{len(channels)}")
    print(f"   去重后频道数：{len(unique_channels)}")
    print(f"   央视 CCTV 频道数：{len(cctv_channels)}")
    print(f"   输出文件1（完整版）：{output_full}")
    print(f"   输出文件2（仅央视）：{output_cctv}")


if __name__ == "__main__":
    main()
