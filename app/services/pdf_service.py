import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

SEVERITY_COLORS = {
    "CRITICAL": colors.HexColor("#DC2626"),
    "HIGH": colors.HexColor("#EA580C"),
    "MEDIUM": colors.HexColor("#CA8A04"),
    "LOW": colors.HexColor("#16A34A"),
}


def build_report(incident: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=1 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=20,
        spaceAfter=6,
        alignment=TA_CENTER,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=14,
        spaceAfter=6,
        textColor=colors.HexColor("#1E3A5F"),
    )
    body_style = styles["Normal"]
    body_style.fontSize = 10
    body_style.leading = 15

    severity = incident.get("severity", "MEDIUM")
    severity_color = SEVERITY_COLORS.get(severity, colors.grey)

    story = []

    story.append(Paragraph("AI Log Analysis Report", title_style))
    story.append(
        Paragraph(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            ParagraphStyle("sub", parent=body_style, alignment=TA_CENTER, textColor=colors.grey),
        )
    )
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E5E7EB")))
    story.append(Spacer(1, 10))

    meta_data = [
        ["Filename", incident.get("filename", "—")],
        ["Severity", severity],
        ["Confidence Score", f"{round(incident.get('confidence_score', 0) * 100, 1)}%"],
        ["Uploaded At", str(incident.get("uploaded_at", "—"))],
        ["Affected Services", ", ".join(incident.get("affected_services", [])) or "None detected"],
    ]

    meta_table = Table(meta_data, colWidths=[2 * inch, 4.5 * inch])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (1, 0), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
                ("TEXTCOLOR", (1, 1), (1, 1), severity_color),
                ("FONTNAME", (1, 1), (1, 1), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Summary", heading_style))
    story.append(Paragraph(incident.get("summary", "N/A"), body_style))

    story.append(Paragraph("Root Cause", heading_style))
    story.append(Paragraph(incident.get("root_cause", "N/A"), body_style))

    recommendations = incident.get("recommendations", [])
    if recommendations:
        story.append(Paragraph("Recommendations", heading_style))
        for i, rec in enumerate(recommendations, 1):
            story.append(Paragraph(f"{i}. {rec}", body_style))

    timeline = incident.get("timeline", [])
    if timeline:
        story.append(Paragraph("Incident Timeline", heading_style))
        tl_data = [["Timestamp", "Level", "Event"]]
        for event in timeline[:30]:
            level_color = SEVERITY_COLORS.get(event.get("level", ""), colors.black)
            tl_data.append([
                event.get("timestamp") or "—",
                event.get("level", ""),
                event.get("event", "")[:120],
            ])

        tl_table = Table(tl_data, colWidths=[1.5 * inch, 0.8 * inch, 4.2 * inch])
        tl_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(tl_table)

    similar = incident.get("similar_incidents", [])
    if similar:
        story.append(Paragraph("Similar Incidents", heading_style))
        sim_data = [["Incident ID", "Filename", "Similarity", "Summary"]]
        for s in similar:
            sim_data.append([
                s.get("incident_id", "")[:12] + "...",
                s.get("filename", ""),
                f"{round(s.get('similarity_score', 0) * 100)}%",
                s.get("summary", "")[:80],
            ])
        sim_table = Table(sim_data, colWidths=[1.2 * inch, 1.5 * inch, 0.8 * inch, 3 * inch])
        sim_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(sim_table)

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E5E7EB")))
    story.append(
        Paragraph(
            "Generated by AI Log Analyzer",
            ParagraphStyle("footer", parent=body_style, alignment=TA_CENTER, textColor=colors.grey, fontSize=8),
        )
    )

    doc.build(story)
    buffer.seek(0)
    return buffer.read()
