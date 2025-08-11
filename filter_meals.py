#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path
from typing import List
import re

import pandas as pd


NON_MEAL_KEYWORDS: List[str] = [
    "奶茶", "咖啡", "甜品", "蛋糕", "饮品", "饮料", "烘焙", "面包", "吐司",
    "冰淇淋", "雪糕", "奶酪", "乳酪", "下午茶", "茶饮", "珍珠", "抹茶", "可可",
]


def filter_dataframe(df: pd.DataFrame, keywords: List[str]) -> pd.DataFrame:
    combined_text = df.get("name", "").fillna("").astype(str) + df.get("recommended_dishes", "").fillna("").astype(str)
    pattern = "|".join(re.escape(k) for k in keywords)
    mask = ~combined_text.str.contains(pattern, case=False, regex=True)
    return df[mask].reset_index(drop=True)


def process_file(csv_path: Path) -> None:
    if not csv_path.exists():
        print(f"Skip: {csv_path} not found")
        return

    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="utf-8")

    before_n = len(df)
    filtered = filter_dataframe(df, NON_MEAL_KEYWORDS)
    after_n = len(filtered)

    out_path = csv_path.with_name(f"{csv_path.stem}_filtered{csv_path.suffix}")
    filtered.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"{csv_path.name}: {before_n} -> {after_n}, saved: {out_path.name}")


def main() -> None:
    base = Path('.')
    targets = [
        base / 'Economy meal.csv',
        base / 'Medium meal.csv',
        base / 'Top meal.csv',
    ]
    for p in targets:
        process_file(p)


if __name__ == "__main__":
    main()


