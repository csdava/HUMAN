"""从食谱「食材清单」文本估算营养：优先匹配食材库 FoodMaterial，其次内置常见食材表。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# 常见别名 → 食材库中可能存在的名称
ALIASES = {
    '西红柿': '番茄',
    '蕃茄': '番茄',
    '鲜奶': '牛奶',
    '白米': '大米',
    '米饭': '大米',
    '鸡胸肉': '鸡肉',
    '鸡腿肉': '鸡肉',
    '瘦肉末': '瘦肉',
    '牛肉末': '牛肉',
}

# 每 100g：热量 kcal、蛋白质、碳水、脂肪；以及五色大类（用于建议标签）
# 数值为常见营养表量级近似，便于未建全食材库时仍能估算
COMMON_FOODS: dict[str, tuple[float, float, float, float, str]] = {
    '番茄': (19, 0.9, 3.9, 0.2, 'vegetable'),
    '鸡蛋': (144, 13.0, 1.1, 9.6, 'protein'),
    '大米': (347, 7.4, 78.0, 0.8, 'grain'),
    '小米': (364, 9.0, 75.0, 3.0, 'grain'),
    '燕麦': (389, 15.0, 66.0, 7.0, 'grain'),
    '面条': (280, 9.0, 56.0, 1.5, 'grain'),
    '面粉': (364, 10.0, 76.0, 1.0, 'grain'),
    '土豆': (77, 2.0, 17.0, 0.1, 'grain'),
    '红薯': (86, 1.6, 20.0, 0.1, 'grain'),
    '玉米': (112, 4.0, 22.8, 1.2, 'grain'),
    '冬瓜': (11, 0.4, 2.6, 0.2, 'vegetable'),
    '黄瓜': (16, 0.7, 2.9, 0.2, 'vegetable'),
    '西兰花': (34, 2.8, 6.6, 0.4, 'vegetable'),
    '菠菜': (28, 2.9, 3.6, 0.4, 'vegetable'),
    '青菜': (15, 1.5, 2.7, 0.2, 'vegetable'),
    '胡萝卜': (41, 0.9, 9.6, 0.2, 'vegetable'),
    '茄子': (25, 1.1, 5.9, 0.2, 'vegetable'),
    '豆角': (31, 2.0, 7.0, 0.1, 'vegetable'),
    '蘑菇': (22, 3.1, 3.3, 0.4, 'vegetable'),
    '苹果': (54, 0.3, 14.0, 0.2, 'fruit'),
    '香蕉': (93, 1.1, 22.0, 0.3, 'fruit'),
    '橙子': (48, 0.9, 11.0, 0.1, 'fruit'),
    '牛奶': (60, 3.0, 5.0, 3.2, 'dairy'),
    '酸奶': (72, 2.5, 9.3, 2.7, 'dairy'),
    '芝士': (350, 25.0, 2.0, 28.0, 'dairy'),
    '豆腐': (81, 8.1, 4.2, 3.7, 'protein'),
    '豆浆': (31, 3.0, 1.2, 1.6, 'dairy'),
    '鸡肉': (167, 19.0, 0.0, 9.4, 'protein'),
    '牛肉': (250, 26.0, 0.0, 15.0, 'protein'),
    '猪肉': (242, 17.0, 0.0, 18.0, 'protein'),
    '瘦肉': (143, 20.3, 1.5, 6.2, 'protein'),
    '虾仁': (87, 18.6, 0.9, 0.7, 'protein'),
    '鲈鱼': (105, 18.6, 0.0, 2.5, 'protein'),
    '三文鱼': (139, 20.0, 0.0, 6.0, 'protein'),
    '排骨': (250, 16.7, 0.0, 20.0, 'protein'),
    '花生': (563, 24.8, 16.2, 44.3, 'protein'),
}

# 调料等：油类给脂肪
CONDIMENT_FAT_G_PER_10G = {
    '橄榄油': 10.0,
    '花生油': 10.0,
    '色拉油': 10.0,
    '香油': 10.0,
    '黄油': 8.0,
    '油': 10.0,
}

CONDIMENT_SKIP = frozenset({
    '盐', '糖', '白糖', '冰糖', '生抽', '老抽', '醋', '料酒', '胡椒粉', '花椒',
    '淀粉', '水', '清水', '葱', '姜', '蒜', '蒜末', '姜丝', '葱花',
})


@dataclass
class MatchedLine:
    raw: str
    name_part: str
    weight_g: float
    food_name: str | None
    calories: float
    protein: float
    carbohydrate: float
    fat: float


def _unit_to_grams(amount: float, unit: str) -> float:
    u = (unit or '').lower()
    if u in ('kg', '公斤'):
        return amount * 1000.0
    if u in ('g', '克'):
        return amount
    if u in ('ml', '毫升'):
        return amount
    if u in ('l', '升'):
        return amount * 1000.0
    return amount


def _piece_weight_grams(name: str, unit: str) -> float:
    """按「个/枚」估算单份克重（粗略）。"""
    base = {'个': 80.0, '枚': 50.0, '颗': 20.0, '朵': 40.0, '片': 25.0}.get(unit, 80.0)
    if any(x in name for x in ('蛋', '鸡蛋', '鸭蛋', '鹌鹑蛋')):
        return 50.0 if unit in ('个', '枚') else base
    if any(x in name for x in ('冬瓜', '南瓜', '哈密瓜', '西瓜')):
        return 400.0 if unit == '个' else base
    if any(x in name for x in ('番茄', '西红柿', '苹果', '橙子', '梨')):
        return 150.0 if unit == '个' else base
    if any(x in name for x in ('香蕉',)):
        return 100.0 if unit == '根' else 120.0 if unit == '个' else base
    return base


def _split_segments(text: str) -> list[str]:
    t = (text or '').strip()
    if not t:
        return []
    parts = re.split(r'[\n、，,;；]+', t)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p or p in ('适量', '少许', '一点点', '若干'):
            continue
        for sub in re.split(r'[和及\+\/]+', p):
            sub = sub.strip()
            if sub:
                out.append(sub)
    return out


def _parse_name_weight(segment: str) -> tuple[str, float]:
    """解析「番茄200g」「牛奶200ml」「鸡蛋2个」等。"""
    seg = segment.strip()
    default_w = 100.0

    m_piece = re.search(r'(\d+)\s*(个|枚|颗|朵|片|根)\s*$', seg)
    if m_piece:
        n = int(m_piece.group(1))
        unit_cn = m_piece.group(2)
        name = seg[: m_piece.start()].strip()
        name = re.sub(r'[（(].*?[)）]', '', name).strip()
        name = re.sub(r'^[\d\s\.]+', '', name).strip() or seg[: m_piece.start()].strip()
        w = _piece_weight_grams(name, unit_cn) * max(1, n)
        return name, max(1.0, min(w, 5000.0))

    m = re.search(
        r'(\d+(?:\.\d+)?)\s*(g|克|G|kg|公斤|KG|ml|毫升|ML|l|升|L)\s*$',
        seg,
        flags=re.I,
    )
    if not m:
        return seg, default_w
    amount = float(m.group(1))
    unit = m.group(2)
    name = seg[: m.start()].strip()
    name = re.sub(r'[（(].*?[)）]', '', name).strip()
    name = re.sub(r'^[\d\s\.]+', '', name).strip()
    if not name:
        name = seg[: m.start()].strip()
    w = _unit_to_grams(amount, unit)
    return (name or seg[: m.start()].strip()), max(1.0, min(w, 5000.0))


def _condiment_estimate(name: str, weight_g: float) -> tuple[float, float, float, float] | None:
    for k in sorted(CONDIMENT_FAT_G_PER_10G.keys(), key=len, reverse=True):
        if k in name:
            fat_per_10 = CONDIMENT_FAT_G_PER_10G[k]
            fat = fat_per_10 * (weight_g / 10.0)
            return fat * 9.0, 0.0, 0.0, fat
    if name in CONDIMENT_SKIP:
        return 0.0, 0.0, 0.0, 0.0
    for s in CONDIMENT_SKIP:
        if s in name and len(name) <= len(s) + 2:
            return 0.0, 0.0, 0.0, 0.0
    return None


def _resolve_common(name_part: str) -> tuple[str, tuple[float, float, float, float, str]] | None:
    if name_part in ALIASES:
        alt = ALIASES[name_part]
        if alt in COMMON_FOODS:
            return alt, COMMON_FOODS[alt]
    for k in sorted(COMMON_FOODS.keys(), key=len, reverse=True):
        if k in name_part:
            return k, COMMON_FOODS[k]
    return None


def estimate_from_ingredients_text(
    ingredients_text: str,
    food_qs=None,
) -> dict[str, Any]:
    from .models import FoodMaterial

    materials = list((food_qs or FoodMaterial.objects.all()).order_by())
    by_name = {fm.name: fm for fm in materials}
    sorted_names = sorted(by_name.keys(), key=len, reverse=True)

    def resolve_db(name_part: str):
        if not name_part:
            return None
        if name_part in ALIASES:
            alt = ALIASES[name_part]
            if alt in by_name:
                return by_name[alt]
        for nm in sorted_names:
            if nm in name_part:
                return by_name[nm]
        return None

    tot_c = tot_p = tot_cb = tot_f = 0.0
    lines: list[MatchedLine] = []
    cat_hits: dict[str, int] = {}
    matched_any = False

    for seg in _split_segments(ingredients_text):
        name_part, w_g = _parse_name_weight(seg)
        if not name_part:
            continue
        cond = _condiment_estimate(name_part, w_g)
        if cond is not None:
            c, p, cb, f = cond
            tot_c += c
            tot_p += p
            tot_cb += cb
            tot_f += f
            lines.append(MatchedLine(seg, name_part, w_g, None, c, p, cb, f))
            continue

        fm = resolve_db(name_part)
        if fm is not None:
            ratio = w_g / 100.0
            c = fm.calories * ratio
            p = fm.protein * ratio
            cb = fm.carbohydrate * ratio
            f = fm.fat * ratio
            tot_c += c
            tot_p += p
            tot_cb += cb
            tot_f += f
            cat_hits[fm.category] = cat_hits.get(fm.category, 0) + 1
            lines.append(MatchedLine(seg, name_part, w_g, fm.name, c, p, cb, f))
            matched_any = True
            continue

        common = _resolve_common(name_part)
        if common is not None:
            key, tup = common
            cal100, p100, cb100, f100, cat = tup
            ratio = w_g / 100.0
            c = cal100 * ratio
            p = p100 * ratio
            cb = cb100 * ratio
            f = f100 * ratio
            tot_c += c
            tot_p += p
            tot_cb += cb
            tot_f += f
            cat_hits[cat] = cat_hits.get(cat, 0) + 1
            lines.append(MatchedLine(seg, name_part, w_g, key, c, p, cb, f))
            matched_any = True
            continue

        lines.append(MatchedLine(seg, name_part, w_g, None, 0.0, 0.0, 0.0, 0.0))

    if not matched_any and tot_c + tot_p + tot_cb + tot_f < 1e-6:
        tot_c, tot_p, tot_cb, tot_f = 250.0, 12.0, 30.0, 8.0

    label_map = [
        ('vegetable', '蔬菜'),
        ('fruit', '水果'),
        ('protein', '蛋白质'),
        ('grain', '谷物'),
        ('dairy', '乳制品'),
        ('other', '其他'),
    ]
    tags = []
    for cat, zh in label_map:
        if cat_hits.get(cat, 0) > 0:
            tags.append(zh)
    suggested = '、'.join(tags[:5]) if tags else '家常菜'

    return {
        'calories': round(tot_c, 1),
        'protein': round(tot_p, 1),
        'carbohydrate': round(tot_cb, 1),
        'fat': round(tot_f, 1),
        'suggested_target_nutrients': suggested[:100],
        'lines': [
            {
                'raw': x.raw,
                'name_part': x.name_part,
                'weight_g': round(x.weight_g, 1),
                'matched_food': x.food_name,
                'calories': round(x.calories, 1),
                'protein': round(x.protein, 2),
                'carbohydrate': round(x.carbohydrate, 2),
                'fat': round(x.fat, 2),
            }
            for x in lines
        ],
    }
