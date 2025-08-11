#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path
from typing import List, Optional
import re

import pandas as pd


# 明确的奶茶/饮品/甜品品牌（店名命中任意即剔除）
BRAND_BLACKLIST: List[str] = [
    # 奶茶连锁
    '蜜雪冰城', '茶百道', '喜茶', '奈雪', '奈雪的茶', '乐乐茶', 'LELECHA', '鹿角巷',
    '一点点', 'CoCo', '都可', '贡茶', '益禾堂', '书亦烧仙草', '霸王茶姬', '桂桂茶',
    '古茗', '柠季', '半山柠', '柠檬向右', '茶理宜世', 'NOYEYENOTEA', '爷爷不泡茶', 'CHAGEE',
    'Uniboba', '优尼波巴', 'angtea',
    # 咖啡连锁
    '星巴克', 'COSTA', 'Manner Coffee', 'UN CAFFE', 'DECATHLON COFFEE',
    # 甜品/小吃常见品牌
    '鲜芋仙', '7分甜', '喜识', '糖小满', '开心鬼酸奶',
]


# 甜品/饮品类关键词（店名命中则剔除；推荐菜仅作参考不直接剔除）
SHOP_KEYWORDS: List[str] = [
    '奶茶', '咖啡', '茶饮', '果茶', '柠檬茶', '手打柠檬茶', '冰茶', '椰子水', '酸奶',
    '甜品', '糖水', '冰糖葫芦', '双皮奶', '龟苓膏', '烧仙草', '芋圆', '糯米糍', '豆花',
]


def compile_pattern(words: List[str]) -> re.Pattern:
    return re.compile(r"(" + "|".join(re.escape(w) for w in words) + r")", flags=re.IGNORECASE)


def _parse_price(price_str: str) -> Optional[float]:
    if not isinstance(price_str, str):
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", price_str)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def refine(csv_path: Path) -> None:
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return

    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding='utf-8')

    # 规范列
    for col in ['name', 'avg_price', 'recommended_dishes']:
        if col not in df.columns:
            df[col] = ''
    name_series = df['name'].fillna('').astype(str)

    brand_pat = compile_pattern(BRAND_BLACKLIST)
    kw_pat = compile_pattern(SHOP_KEYWORDS)

    brand_mask = name_series.str.contains(brand_pat)
    kw_mask = name_series.str.contains(kw_pat)

    # 规则1：品牌/店名关键词
    remove_mask = brand_mask | kw_mask
    kept_df = df[~remove_mask].reset_index(drop=True)

    # 规则2：人均价格 < 20 过滤
    prices = kept_df['avg_price'].fillna('').astype(str).map(_parse_price)
    price_mask = prices >= 20
    final_df = kept_df[price_mask.fillna(False)].reset_index(drop=True)

    removed_count = len(df) - len(final_df)
    # 覆盖写回原文件
    final_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"{csv_path.name}: total={len(df)}, removed={removed_count}, kept={len(final_df)} (in-place saved)")


def main() -> None:
    refine(Path('Economy meal_filtered.csv'))


if __name__ == '__main__':
    main()


