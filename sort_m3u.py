# -*- coding: utf-8 -*-
import re
from collections import defaultdict

# ====================== 配置 ======================
input_file = "migu.txt"      # 你的原始 m3u 文件名
output_file = "migu.m3u"  # 输出文件名

# =================================================

def parse_m3u(content):
    channels = []
    lines = content.strip().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            # 提取频道信息
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


def get_group_and_sort_key(extinf):
    name_match = re.search(r',(.+?)$', extinf)
    name = name_match.group(1).strip() if name_match else ""

    # 判断分组
    if "央视" in extinf or any(cctv in name.upper() for cctv in ["CCTV", "CGTN"]):
        group = "央视"
    elif "卫视" in extinf or any(ws in name for ws in ["卫视"]):
        group = "卫视"
    else:
        group = "其它"

    # 央视组内的排序键
    if group == "央视":
        # 提取数字
        num_match = re.search(r'CCTV(\d+)', name)
        if num_match:
            num = int(num_match.group(1))
            return group, (0, num, name)   # 优先按数字排序
        elif "CGTN" in name:
            return group, (1, 0, name)
        elif "欧洲" in name or "美洲" in name:
            return group, (2, 0, name)
        else:
            return group, (3, 0, name)
    else:
        return group, (0, 0, name)


def main():
    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 提取头部
    header_match = re.match(r'(#EXTM3U.*?)(\n#EXTINF:|$)', content, re.DOTALL)
    header = header_match.group(1).strip() if header_match else "#EXTM3U"

    channels = parse_m3u(content)

    # 去重：使用 tvg-id 或 tvg-name 作为唯一标识
    seen = {}
    unique_channels = []
    for extinf, url in channels:
        tvg_id = re.search(r'tvg-id="([^"]+)"', extinf)
        tvg_name = re.search(r'tvg-name="([^"]+)"', extinf)
        key = (tvg_id.group(1) if tvg_id else None) or (tvg_name.group(1) if tvg_name else None) or extinf
        if key not in seen:
            seen[key] = (extinf, url)
            unique_channels.append((extinf, url))

    # 按分组和排序键排序
    sorted_channels = sorted(unique_channels, key=lambda x: get_group_and_sort_key(x[0]))

    # 写入输出文件
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(header + "\n\n")
        
        current_group = None
        for extinf, url in sorted_channels:
            group = get_group_and_sort_key(extinf)[0]
            if group != current_group:
                f.write(f"# ================================== {group} ==================================\n\n")
                current_group = group
            f.write(extinf + "\n")
            f.write(url + "\n\n")

    print(f"✅ 处理完成！")
    print(f"   输入频道数：{len(channels)}")
    print(f"   去重后频道数：{len(unique_channels)}")
    print(f"   输出文件：{output_file}")


if __name__ == "__main__":
    main()
