#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, render_template, request, jsonify
from datetime import datetime
import json


BASE_DIR = Path(__file__).resolve().parent


class Category:
    def __init__(self, key: str, display_name: str, csv_filename: str) -> None:
        self.key = key
        self.display_name = display_name
        self.csv_path = BASE_DIR / csv_filename

    def load_items(self) -> List[Dict[str, str]]:
        items: List[Dict[str, str]] = []
        if not self.csv_path.exists():
            return items
        # 使用 csv 模块读取，支持带 BOM 的 utf-8-sig
        import csv

        with self.csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 统一列名与空值
                name = (row.get("name") or "").strip()
                price = (row.get("avg_price") or "").strip()
                dishes = (row.get("recommended_dishes") or "").strip()
                items.append({
                    "name": name,
                    "avg_price": price,
                    "recommended_dishes": dishes,
                })
        return items


CATEGORIES: List[Category] = [
    Category("economy", "经济餐", "Economy meal_filtered.csv"),
    Category("medium", "中档餐", "Medium meal_filtered.csv"),
    Category("top", "高档餐", "Top meal_filtered.csv"),
]

CATEGORY_BY_KEY: Dict[str, Category] = {c.key: c for c in CATEGORIES}


def choose_category_by_weights(weights: Dict[str, int]) -> Optional[Category]:
    # 过滤掉非正权重
    valid_pairs = [(CATEGORY_BY_KEY[k], max(0, int(v))) for k, v in weights.items() if k in CATEGORY_BY_KEY]
    total = sum(w for _, w in valid_pairs)
    if total <= 0:
        return None
    threshold = random.randint(1, total)
    cursor = 0
    for category, w in valid_pairs:
        cursor += w
        if threshold <= cursor:
            return category
    return None


def pick_random_item(items: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    if not items:
        return None
    return random.choice(items)


app = Flask(__name__)


def _default_weights() -> Dict[str, int]:
    # 默认 7:2:1 （经济:中档:高档）
    return {"economy": 7, "medium": 2, "top": 1}


WEIGHTS_FILE = BASE_DIR / "weights.json"


def _load_weights() -> Dict[str, int]:
    if WEIGHTS_FILE.exists():
        try:
            data = json.loads(WEIGHTS_FILE.read_text(encoding="utf-8"))
            # 只保留已知类别
            weights = {c.key: int(max(0, int(data.get(c.key, 0)))) for c in CATEGORIES}
            # 若全为 0，则回退默认
            if sum(weights.values()) <= 0:
                return _default_weights()
            return weights
        except Exception:
            return _default_weights()
    return _default_weights()


def _save_weights(weights: Dict[str, int]) -> None:
    safe = {c.key: int(max(0, int(weights.get(c.key, 0)))) for c in CATEGORIES}
    WEIGHTS_FILE.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_weights_from_request() -> Dict[str, int]:
    weights: Dict[str, int] = {}
    for c in CATEGORIES:
        raw = request.values.get(f"weight_{c.key}")
        try:
            # 若未提供则采用默认值
            default_val = _default_weights()[c.key]
            val = int(raw) if raw is not None else default_val
        except (TypeError, ValueError):
            val = _default_weights()[c.key]
        weights[c.key] = max(0, val)
    return weights


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        weights = _parse_weights_from_request()
        # 保存用户在页面上调整的权重
        _save_weights(weights)
    else:
        weights = _load_weights()

    chosen_category: Optional[Category] = None
    chosen_item: Optional[Dict[str, str]] = None
    error_message: Optional[str] = None

    if request.method == "POST":
        chosen_category = choose_category_by_weights(weights)
        if chosen_category is None:
            error_message = "请设置至少一个大于 0 的权重"
        else:
            items = chosen_category.load_items()
            if not items:
                error_message = f"{chosen_category.display_name} 的 CSV 为空或不存在：{chosen_category.csv_path.name}"
            else:
                chosen_item = pick_random_item(items)

    # 统计每个类别的可选数量
    counts = {c.key: len(c.load_items()) for c in CATEGORIES}

    return render_template(
        "index.html",
        categories=CATEGORIES,
        weights=weights,
        counts=counts,
        chosen_category=chosen_category,
        chosen_item=chosen_item,
        error_message=error_message,
        success_message=None,
    )


@app.route("/api/draw", methods=["GET"])
def api_draw():
    # GET /api/draw?weight_economy=3&weight_medium=2&weight_top=1
    weights = _parse_weights_from_request()
    chosen_category = choose_category_by_weights(weights)
    if chosen_category is None:
        return jsonify({"ok": False, "error": "invalid_weights"}), 400
    items = chosen_category.load_items()
    if not items:
        return jsonify({"ok": False, "error": "empty_category", "category": chosen_category.key}), 400
    item = pick_random_item(items) or {}
    return jsonify({
        "ok": True,
        "category": {
            "key": chosen_category.key,
            "name": chosen_category.display_name,
            "csv": chosen_category.csv_path.name,
        },
        "item": item,
        "weights": weights,
    })


def _append_decision(category_key: str, shop: Dict[str, str]) -> Path:
    out_path = BASE_DIR / "decisions.csv"
    exists = out_path.exists()
    import csv

    with out_path.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["timestamp", "category_key", "category_name", "name", "avg_price", "recommended_dishes"])
        category = CATEGORY_BY_KEY.get(category_key)
        writer.writerow([
            datetime.now().isoformat(timespec="seconds"),
            category_key,
            category.display_name if category else category_key,
            shop.get("name", ""),
            shop.get("avg_price", ""),
            shop.get("recommended_dishes", ""),
        ])
    return out_path


@app.route("/confirm", methods=["POST"])
def confirm():
    category_key = request.form.get("category_key", "")
    shop = {
        "name": request.form.get("name", ""),
        "avg_price": request.form.get("avg_price", ""),
        "recommended_dishes": request.form.get("recommended_dishes", ""),
    }

    error_message: Optional[str] = None
    success_message: Optional[str] = None

    if category_key not in CATEGORY_BY_KEY or not shop.get("name"):
        error_message = "确认失败：参数不完整"
    else:
        out_path = _append_decision(category_key, shop)
        success_message = f"已确认并保存到 {out_path.name}"
        # 确认后将该类别权重减一
        weights_now = _load_weights()
        current_val = int(weights_now.get(category_key, _default_weights()[category_key]))
        weights_now[category_key] = max(0, current_val - 1)
        _save_weights(weights_now)

    weights = _load_weights()
    counts = {c.key: len(c.load_items()) for c in CATEGORIES}

    return render_template(
        "index.html",
        categories=CATEGORIES,
        weights=weights,
        counts=counts,
        chosen_category=None,
        chosen_item=None,
        error_message=error_message,
        success_message=success_message,
    )


@app.route("/reset", methods=["POST"])
def reset_weights():
    defaults = _default_weights()
    _save_weights(defaults)
    counts = {c.key: len(c.load_items()) for c in CATEGORIES}
    return render_template(
        "index.html",
        categories=CATEGORIES,
        weights=defaults,
        counts=counts,
        chosen_category=None,
        chosen_item=None,
        error_message=None,
        success_message="权重已重置为 7:2:1（每周一手动重置）",
    )


def _remove_shop_from_category(category_key: str, shop: Dict[str, str]) -> int:
    category = CATEGORY_BY_KEY.get(category_key)
    if category is None or not category.csv_path.exists():
        return 0
    import csv

    # 读取全部
    with category.csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    def _norm(s: Optional[str]) -> str:
        return (s or "").strip()

    before = len(rows)
    kept = [
        r for r in rows
        if not (
            _norm(r.get("name")) == _norm(shop.get("name")) and
            _norm(r.get("avg_price")) == _norm(shop.get("avg_price")) and
            _norm(r.get("recommended_dishes")) == _norm(shop.get("recommended_dishes"))
        )
    ]
    removed = before - len(kept)

    if removed > 0:
        with category.csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "avg_price", "recommended_dishes"])
            writer.writeheader()
            for r in kept:
                writer.writerow({
                    "name": r.get("name", ""),
                    "avg_price": r.get("avg_price", ""),
                    "recommended_dishes": r.get("recommended_dishes", ""),
                })
    return removed


@app.route("/remove", methods=["POST"])
def remove_shop():
    category_key = request.form.get("category_key", "")
    shop = {
        "name": request.form.get("name", ""),
        "avg_price": request.form.get("avg_price", ""),
        "recommended_dishes": request.form.get("recommended_dishes", ""),
    }

    error_message: Optional[str] = None
    success_message: Optional[str] = None

    if category_key not in CATEGORY_BY_KEY or not shop.get("name"):
        error_message = "删除失败：参数不完整"
    else:
        removed = _remove_shop_from_category(category_key, shop)
        if removed > 0:
            success_message = f"已从 {CATEGORY_BY_KEY[category_key].display_name} 列表删除：{shop.get('name')}"
        else:
            error_message = "未在列表中找到完全匹配的记录（可能已删除或字段不一致）"

    weights = _load_weights()
    counts = {c.key: len(c.load_items()) for c in CATEGORIES}
    return render_template(
        "index.html",
        categories=CATEGORIES,
        weights=weights,
        counts=counts,
        chosen_category=None,
        chosen_item=None,
        error_message=error_message,
        success_message=success_message,
    )


if __name__ == "__main__":
    # 使用开发服务器启动
    app.run(host="0.0.0.0", port=5000, debug=True)


