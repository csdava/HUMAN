from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntakeRecommendation:
    age_years: int
    calories_kcal_min: int
    calories_kcal_max: int
    protein_g_min: int
    protein_g_max: int
    notes: str


def recommend_intake_for_age(age_years: int | None) -> IntakeRecommendation | None:
    """
    非医疗建议：用于产品端“参考范围”展示与自我管理提示。
    数值为粗略区间，后续可由营养师/指南校准。
    """
    if age_years is None:
        return None
    a = max(0, int(age_years))

    # 简化分段（幼儿园/小学低年级/小学高年级/青春前期）
    if a <= 3:
        return IntakeRecommendation(a, 1000, 1300, 15, 25, "学龄前幼儿参考范围，实际以身高体重与活动量为准。")
    if 4 <= a <= 6:
        return IntakeRecommendation(a, 1200, 1600, 20, 35, "幼儿园阶段参考范围，注意奶类与优质蛋白。")
    if 7 <= a <= 9:
        return IntakeRecommendation(a, 1400, 1800, 30, 45, "小学低年级参考范围，建议三餐规律+水果蔬菜。")
    if 10 <= a <= 12:
        return IntakeRecommendation(a, 1600, 2200, 40, 55, "小学高年级参考范围，运动日可偏上限。")
    return IntakeRecommendation(a, 1800, 2600, 45, 70, "青春期前后参考范围，建议结合医生/营养师建议调整。")

