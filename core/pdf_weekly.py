"""家长端 / 学校端：近 N 天健康周报 PDF（膳食 + 任务 + 手环；ReportLab + STSong-Light 中文）。"""
from __future__ import annotations

import html
from io import BytesIO

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _esc(s) -> str:
    return html.escape(str(s) if s is not None else "", quote=False)


def _ensure_cjk_font() -> str:
    name = "STSong-Light"
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(name))
    return name


class _DrawingFlowable(Flowable):
    """将 ReportLab Drawing 作为 Platypus 流式对象嵌入 PDF（矢量，不依赖 renderPM）。"""

    def __init__(self, drawing: Drawing):
        Flowable.__init__(self)
        self.drawing = drawing
        self.width = drawing.width
        self.height = drawing.height

    def draw(self):
        self.drawing.drawOn(self.canv, 0, 0)


def _x_tick_labels(n: int) -> list[int]:
    if n <= 1:
        return [0]
    if n <= 12:
        return list(range(n))
    step = max(1, n // 8)
    ticks = list(range(0, n, step))
    if ticks[-1] != n - 1:
        ticks.append(n - 1)
    return ticks


def _weekly_trends_flowable(daily_rows: list, font: str) -> _DrawingFlowable | None:
    rows = daily_rows or []
    n = len(rows)
    if n < 1:
        return None

    labels = []
    for r in rows:
        d = str(r.get("date") or "")
        labels.append(d[5:] if len(d) >= 10 else d)

    def xfmt(v):
        i = int(round(float(v)))
        if 0 <= i < len(labels):
            return labels[i]
        return ""

    kcal_pts = [(i, float(r.get("day_calories") or 0)) for i, r in enumerate(rows)]
    score_pts = [(i, float(r.get("avg_score") or 0)) for i, r in enumerate(rows)]
    task_pts = [(i, int(r.get("tasks_completed") or 0)) for i, r in enumerate(rows)]
    step_vals = [int(r["steps"]) if r.get("steps") is not None else 0 for r in rows]
    show_steps = any(r.get("steps") is not None for r in rows)

    w = 480
    if show_steps:
        d = Drawing(w, 360)
        bottom_chart_top = 78
    else:
        d = Drawing(w, 285)
        bottom_chart_top = 0

    d.add(String(8, d.height - 12, "热量 (kcal)", fontName=font, fontSize=8, fillColor=colors.grey))
    lp_k = LinePlot()
    lp_k.x = 32
    lp_k.y = d.height - 92
    lp_k.width = w - 40
    lp_k.height = 72
    lp_k.data = [kcal_pts]
    lp_k.lines[0].strokeColor = colors.HexColor("#ef6c00")
    lp_k.lines[0].strokeWidth = 1.25
    lp_k.xValueAxis.valueMin = 0
    lp_k.xValueAxis.valueMax = max(0, n - 1)
    lp_k.xValueAxis.labelTextFormat = xfmt
    lp_k.xValueAxis.labels.fontName = font
    lp_k.xValueAxis.labels.fontSize = 7
    lp_k.xValueAxis.valueSteps = _x_tick_labels(n)
    yk_max = max((p[1] for p in kcal_pts), default=0) * 1.12 or 1.0
    lp_k.yValueAxis.valueMin = 0
    lp_k.yValueAxis.valueMax = yk_max
    lp_k.yValueAxis.labels.fontName = font
    lp_k.yValueAxis.labels.fontSize = 7
    lp_k.joinedLines = 1
    d.add(lp_k)

    d.add(String(8, d.height - 102, "五色均分 (0-5)", fontName=font, fontSize=8, fillColor=colors.grey))
    lp_s = LinePlot()
    lp_s.x = 32
    lp_s.y = d.height - 182
    lp_s.width = w - 40
    lp_s.height = 72
    lp_s.data = [score_pts]
    lp_s.lines[0].strokeColor = colors.HexColor("#1565c0")
    lp_s.lines[0].strokeWidth = 1.25
    lp_s.xValueAxis.valueMin = 0
    lp_s.xValueAxis.valueMax = max(0, n - 1)
    lp_s.xValueAxis.labelTextFormat = xfmt
    lp_s.xValueAxis.labels.fontName = font
    lp_s.xValueAxis.labels.fontSize = 7
    lp_s.xValueAxis.valueSteps = _x_tick_labels(n)
    lp_s.yValueAxis.valueMin = 0
    lp_s.yValueAxis.valueMax = 5.0
    lp_s.yValueAxis.labels.fontName = font
    lp_s.yValueAxis.labels.fontSize = 7
    lp_s.joinedLines = 1
    d.add(lp_s)

    d.add(String(8, d.height - 192, "已确认任务 (次/日)", fontName=font, fontSize=8, fillColor=colors.grey))
    lp_t = LinePlot()
    lp_t.x = 32
    lp_t.y = d.height - 272
    lp_t.width = w - 40
    lp_t.height = 72
    lp_t.data = [task_pts]
    lp_t.lines[0].strokeColor = colors.HexColor("#2e7d32")
    lp_t.lines[0].strokeWidth = 1.25
    lp_t.xValueAxis.valueMin = 0
    lp_t.xValueAxis.valueMax = max(0, n - 1)
    lp_t.xValueAxis.labelTextFormat = xfmt
    lp_t.xValueAxis.labels.fontName = font
    lp_t.xValueAxis.labels.fontSize = 7
    lp_t.xValueAxis.valueSteps = _x_tick_labels(n)
    yt_max = max((p[1] for p in task_pts), default=0) + 1
    if yt_max < 2:
        yt_max = 2.0
    lp_t.yValueAxis.valueMin = 0
    lp_t.yValueAxis.valueMax = float(yt_max)
    lp_t.yValueAxis.labels.fontName = font
    lp_t.yValueAxis.labels.fontSize = 7
    lp_t.joinedLines = 1
    d.add(lp_t)

    if show_steps:
        d.add(String(8, bottom_chart_top + 58, "步数 (柱为当日值, 无同步为 0)", fontName=font, fontSize=8, fillColor=colors.grey))
        bc = VerticalBarChart()
        bc.x = 32
        bc.y = 6
        bc.width = w - 40
        bc.height = 64
        bc.data = [step_vals]
        bc.categoryAxis.categoryNames = labels
        bc.categoryAxis.labels.fontName = font
        bc.categoryAxis.labels.fontSize = 6
        bc.categoryAxis.visibleGrid = 0
        bc.valueAxis.valueMin = 0
        smax = max(step_vals) if step_vals else 0
        bc.valueAxis.valueMax = smax * 1.15 if smax > 0 else 100.0
        bc.valueAxis.labels.fontName = font
        bc.valueAxis.labels.fontSize = 7
        bc.bars[0].fillColor = colors.HexColor("#6a1b9a")
        d.add(bc)

    return _DrawingFlowable(d)


def build_parent_weekly_pdf(ctx: dict) -> bytes:
    """
    ctx 字段：
      title, child_label, period_label,
      daily_rows: [{date, meal_count, day_calories, avg_score, tasks_completed, steps, sleep_minutes}, ...],
      totals: {kcal, protein, carb, fat}, avg_daily_score,
      task_completed_count, tasks_summary: [{code, name, count}],
      avg_daily_steps (可空), health_days_with_data (int),
      diet_notes (可空), allergy_tags, medical_tags,
      intake: {calories_kcal_min, ...} (可空)
    """
    font = _ensure_cjk_font()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "T",
        parent=styles["Heading1"],
        fontName=font,
        fontSize=18,
        leading=22,
        alignment=1,
        spaceAfter=6 * mm,
    )
    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName=font,
        fontSize=13,
        leading=18,
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )
    body = ParagraphStyle(
        "B",
        parent=styles["Normal"],
        fontName=font,
        fontSize=10,
        leading=14,
    )
    small = ParagraphStyle(
        "S",
        parent=styles["Normal"],
        fontName=font,
        fontSize=9,
        leading=12,
        textColor=colors.grey,
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=_esc(ctx.get("title", "健康周报")),
    )
    story = []

    story.append(Paragraph(_esc(ctx.get("title", "儿童健康周报")), title_style))
    story.append(Paragraph(_esc(ctx.get("child_label", "")), body))
    story.append(Paragraph(_esc(ctx.get("period_label", "")), body))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("一、按日汇总 (膳食 + 任务 + 手环)", h2_style))
    hdr = ["日期", "餐次", "热量", "五色分", "任务", "步数", "睡眠分"]
    data = [[_esc(h) for h in hdr]]
    for row in ctx.get("daily_rows") or []:
        st = row.get("steps")
        sl = row.get("sleep_minutes")
        data.append(
            [
                _esc(row.get("date", "")),
                _esc(row.get("meal_count", 0)),
                _esc(f"{float(row.get('day_calories', 0) or 0):.0f}"),
                _esc(f"{float(row.get('avg_score', 0) or 0):.1f}"),
                _esc(row.get("tasks_completed", 0)),
                _esc("-" if st is None else str(int(st))),
                _esc("-" if sl is None else str(int(sl))),
            ]
        )
    t = Table(
        data,
        colWidths=[24 * mm, 12 * mm, 18 * mm, 16 * mm, 14 * mm, 16 * mm, 18 * mm],
        repeatRows=1,
    )
    t.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), font, 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e3f2fd")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1565c0")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
            ]
        )
    )
    story.append(t)
    story.append(
        Paragraph(
            "说明: 热量为当日各餐合计 kcal; 任务为当日家长已确认完成次数; "
            "步数与睡眠来自儿童端或 App 同步的手环数据 (无则显示 -).",
            small,
        )
    )
    story.append(Spacer(1, 4 * mm))

    trend = _weekly_trends_flowable(ctx.get("daily_rows") or [], font)
    if trend:
        story.append(Paragraph("二、趋势图 (矢量折线 / 步数柱状)", h2_style))
        story.append(trend)
        story.append(
            Paragraph(
                "横轴日期为月-日; 步数柱形图中 0 表示当日无同步记录 (非一定未走动).",
                small,
            )
        )
        story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("三、周期合计", h2_style))
    tot = ctx.get("totals") or {}
    lines = [
        f"总热量: {float(tot.get('kcal', 0) or 0):.0f} kcal",
        f"蛋白质: {float(tot.get('protein', 0) or 0):.1f} g",
        f"碳水化合物: {float(tot.get('carb', 0) or 0):.1f} g",
        f"脂肪: {float(tot.get('fat', 0) or 0):.1f} g",
        f"日均五色营养分: {float(ctx.get('avg_daily_score', 0) or 0):.1f}",
        f"周期内已确认任务总次数: {int(ctx.get('task_completed_count', 0) or 0)}",
    ]
    ads = ctx.get("avg_daily_steps")
    hdays = int(ctx.get("health_days_with_data") or 0)
    if ads is not None and hdays > 0:
        lines.append(f"有手环数据的 {hdays} 天内, 日均步数约: {ads}")
    for line in lines:
        story.append(Paragraph(_esc(line), body))

    story.append(Paragraph("四、健康任务分布 (已确认)", h2_style))
    ts = ctx.get("tasks_summary") or []
    if ts:
        tdata = [["任务", "代码", "次数"]]
        for item in ts:
            tdata.append([_esc(item.get("name", "")), _esc(item.get("code", "")), _esc(item.get("count", 0))])
        tt = Table(tdata, colWidths=[70 * mm, 28 * mm, 22 * mm], repeatRows=1)
        tt.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, -1), font, 9),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3e5f5")),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(tt)
    else:
        story.append(Paragraph("本周期暂无已确认任务记录.", body))

    intake = ctx.get("intake")
    if intake:
        story.append(Paragraph("五、每日建议摄入 (参考范围)", h2_style))
        story.append(
            Paragraph(
                _esc(
                    f"能量: {intake.get('calories_kcal_min')}-{intake.get('calories_kcal_max')} kcal/天; "
                    f"蛋白质: {intake.get('protein_g_min')}-{intake.get('protein_g_max')} g/天"
                ),
                body,
            )
        )
        if intake.get("notes"):
            story.append(Paragraph(_esc(intake.get("notes")), small))
    else:
        story.append(Paragraph("五、每日建议摄入", h2_style))
        story.append(Paragraph("未填写出生日期, 无法按年龄给出参考区间 (请在家庭端维护).", small))

    allergy_tags = ctx.get("allergy_tags") or []
    medical_tags = ctx.get("medical_tags") or []
    if allergy_tags or medical_tags:
        story.append(Paragraph("六、过敏与医嘱标签 (家长维护)", h2_style))
        if allergy_tags:
            story.append(Paragraph(_esc("过敏: " + "、".join([str(x) for x in allergy_tags])), body))
        if medical_tags:
            story.append(Paragraph(_esc("医嘱: " + "、".join([str(x) for x in medical_tags])), body))
    else:
        story.append(Paragraph("六、过敏与医嘱标签", h2_style))
        story.append(Paragraph("未登记.", small))

    notes = (ctx.get("diet_notes") or "").strip()
    if notes:
        story.append(Paragraph("七、膳食备注 (家长填写)", h2_style))
        story.append(Paragraph(_esc(notes), body))

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(_esc(ctx.get("footer", "")), small))

    doc.build(story)
    return buf.getvalue()
