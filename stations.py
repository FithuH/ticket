"""
车站名称与拼音码映射模块：自动下载并解析 station_name.js
"""

import re
import requests
from config import BASE_URLS, Endpoints, HEADERS

_station_dict = None


def load_station_dict():
    """从 12306 下载 station_name.js 并解析为 {中文站名: 拼音码(大写)} 字典"""
    global _station_dict
    if _station_dict is not None:
        return _station_dict

    url = BASE_URLS["kyfw"] + Endpoints.STATION_JS
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    # 格式示例: '@bjb|北京北|VAP|beijingbei|bjb|...'
    text = resp.text
    # 提取所有 @ 开头的数据块
    pattern = r"@([a-z]+)\|([^|]+)\|([A-Z]+)\|"
    matches = re.findall(pattern, text)
    _station_dict = {}
    for pinyin_short, chinese, code in matches:
        # 使用大写字母码作为站码
        _station_dict[chinese] = code
    return _station_dict


def get_station_code(name: str) -> str:
    """根据中文站名返回拼音码（大写），若不存在则抛出异常"""
    stations = load_station_dict()
    code = stations.get(name)
    if not code:
        raise ValueError(f"未找到车站 '{name}' 的对应拼音码，请检查站名")
    return code


# 模块导入时自动加载
load_station_dict()