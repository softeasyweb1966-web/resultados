"""
PDF Generator service using ReportLab.
Generates a styled PDF for a lab result, including:
  - Institution header with logo
  - Patient / order information
  - Exam result table (from LayoutCell grid)
  - Alarm markers for out-of-range values
  - Bacteriologist / reviewer signatures
  - QR code for authenticity verification
  - Configurable margins, page size, footer
"""
import io
import os
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, Image, HRFlowable, KeepTogether,
)
from reportlab.platypus.flowables import Flowable
from flask import url_for, current_app

from app.models import PDFConfig, LayoutCell


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_result_pdf(result):
    """
    Generate a PDF for the given Result instance.
    Returns bytes.
    """
    cfg = (
        PDFConfig.query.filter_by(is_default=True).first()
        or PDFConfig()
    )

    buf = io.BytesIO()
    page_size = letter if cfg.page_size == 'Letter' else A4
    margin_top = (cfg.margin_top or 20) * mm
    margin_bottom = (cfg.margin_bottom or 20) * mm
    margin_left = (cfg.margin_left or 20) * mm
    margin_right = (cfg.margin_right or 20) * mm

    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        topMargin=margin_top,
        bottomMargin=margin_bottom,
        leftMargin=margin_left,
        rightMargin=margin_right,
        title=f'Resultado {result.id}',
    )

    styles = getSampleStyleSheet()
    story = []

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    story.extend(_build_header(cfg, styles, page_size, margin_left, margin_right))
    story.append(Spacer(1, 6 * mm))

    # ------------------------------------------------------------------
    # Patient / order info
    # ------------------------------------------------------------------
    story.extend(_build_patient_info(result, styles))
    story.append(Spacer(1, 4 * mm))

    # ------------------------------------------------------------------
    # Exam info
    # ------------------------------------------------------------------
    story.extend(_build_exam_info(result, styles))
    story.append(Spacer(1, 4 * mm))

    # ------------------------------------------------------------------
    # Results grid
    # ------------------------------------------------------------------
    story.extend(_build_results_table(result, styles))
    story.append(Spacer(1, 6 * mm))

    # ------------------------------------------------------------------
    # Signatures
    # ------------------------------------------------------------------
    story.extend(_build_signatures(result, styles, page_size, margin_left, margin_right))
    story.append(Spacer(1, 4 * mm))

    # ------------------------------------------------------------------
    # QR code + footer
    # ------------------------------------------------------------------
    if cfg.show_qr and result.qr_token:
        story.extend(_build_qr(result, cfg, styles))

    if cfg.footer_text:
        story.append(Spacer(1, 4 * mm))
        story.append(HRFlowable(width='100%', thickness=0.5, color=colors.grey))
        story.append(Paragraph(cfg.footer_text, styles['Normal']))

    doc.build(story)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_header(cfg, styles, page_size, margin_left, margin_right):
    flowables = []
    usable_width = page_size[0] - margin_left - margin_right

    header_style = ParagraphStyle(
        'HeaderInstitution',
        parent=styles['Title'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=2,
    )
    sub_style = ParagraphStyle(
        'HeaderSub',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
    )

    logo_img = None
    if cfg.logo_path:
        logo_full = os.path.join(
            current_app.config['UPLOAD_FOLDER'], cfg.logo_path
        )
        if os.path.exists(logo_full):
            logo_img = Image(logo_full, width=40 * mm, height=20 * mm)

    rows = []
    if logo_img:
        text_col = []
        if cfg.institution_name:
            text_col.append(Paragraph(cfg.institution_name, header_style))
        if cfg.institution_address:
            text_col.append(Paragraph(cfg.institution_address, sub_style))
        if cfg.institution_phone:
            text_col.append(Paragraph(f'Tel: {cfg.institution_phone}', sub_style))
        if cfg.header_text:
            text_col.append(Paragraph(cfg.header_text, sub_style))

        header_table = Table(
            [[logo_img, text_col]],
            colWidths=[45 * mm, usable_width - 45 * mm],
        )
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        flowables.append(header_table)
    else:
        if cfg.institution_name:
            flowables.append(Paragraph(cfg.institution_name, header_style))
        if cfg.institution_address:
            flowables.append(Paragraph(cfg.institution_address, sub_style))
        if cfg.institution_phone:
            flowables.append(Paragraph(f'Tel: {cfg.institution_phone}', sub_style))
        if cfg.header_text:
            flowables.append(Paragraph(cfg.header_text, sub_style))

    flowables.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#0d6efd')))
    return flowables


def _build_patient_info(result, styles):
    order = result.order
    patient = order.patient
    bold = ParagraphStyle('Bold', parent=styles['Normal'], fontName='Helvetica-Bold')
    normal = styles['Normal']

    age_str = f'{patient.age} años' if patient.age else 'N/A'
    gender_str = 'Masculino' if patient.gender == 'M' else ('Femenino' if patient.gender == 'F' else 'N/A')

    data = [
        [Paragraph('INFORMACIÓN DEL PACIENTE', bold), ''],
        ['Nombre:', patient.name],
        ['Documento:', f'{patient.document_type}: {patient.document}'],
        ['Fecha de Nac.:', str(patient.birth_date or 'N/A')],
        ['Edad / Género:', f'{age_str} / {gender_str}'],
        ['Consecutivo:', order.consecutive],
        ['Fecha de orden:', order.date.strftime('%Y-%m-%d %H:%M')],
    ]
    if order.attending_physician:
        data.append(['Médico remitente:', order.attending_physician])
    if order.diagnosis:
        data.append(['Diagnóstico:', order.diagnosis])

    t = Table(data, colWidths=[45 * mm, None])
    t.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#e8f0fe')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]))
    return [t]


def _build_exam_info(result, styles):
    exam = result.exam
    bold = ParagraphStyle('Bold', parent=styles['Normal'], fontName='Helvetica-Bold')
    data = [
        [Paragraph('INFORMACIÓN DEL EXAMEN', bold), ''],
        ['Examen:', f'{exam.code} – {exam.name}'],
    ]
    if exam.technique:
        data.append(['Técnica:', exam.technique])
    if exam.equipment:
        data.append(['Equipo:', exam.equipment])
    if exam.method:
        data.append(['Método:', exam.method])
    if exam.sample_type:
        data.append(['Tipo de muestra:', exam.sample_type])
    data.append(['Fecha resultado:', result.date.strftime('%Y-%m-%d %H:%M')])

    t = Table(data, colWidths=[45 * mm, None])
    t.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#e8f0fe')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]))
    return [t]


def _build_results_table(result, styles):
    """
    Build a table from the exam LayoutCells, substituting result values
    where cell_type == 'result'.
    """
    cells = result.exam.layout_cells.order_by(LayoutCell.row, LayoutCell.col).all()
    pr_map = {pr.parameter_id: pr for pr in result.parameter_results}

    if not cells:
        # Fallback: simple list of parameters and values
        return _build_simple_results_table(result, styles, pr_map)

    max_row = max(c.row + c.rowspan - 1 for c in cells)
    max_col = max(c.col + c.colspan - 1 for c in cells)
    num_cols = max_col + 1

    # Build a matrix
    matrix = [[None] * num_cols for _ in range(max_row + 1)]
    span_cmds = []
    style_cmds = [
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
    ]

    covered = set()
    for cell in sorted(cells, key=lambda c: (c.row, c.col)):
        r, c = cell.row, cell.col
        if (r, c) in covered:
            continue

        # Determine cell content
        if cell.cell_type == 'result' and cell.parameter_id and cell.parameter_id in pr_map:
            pr = pr_map[cell.parameter_id]
            text = pr.value or ''
            if pr.out_of_range or pr.flagged:
                text = f'*{text}*'
                style_cmds.append(('TEXTCOLOR', (c, r), (c, r), colors.red))
            if pr.units:
                text = f'{text} {pr.units}'
        elif cell.cell_type == 'fixed' and cell.parameter_id and cell.parameter_id in pr_map:
            pr = pr_map[cell.parameter_id]
            text = pr.value or cell.content or ''
        else:
            text = cell.content or ''

        # Apply cell styles
        style_d = cell.style_dict
        if style_d.get('bold') or cell.cell_type in ('header',):
            style_cmds.append(('FONTNAME', (c, r), (c, r), 'Helvetica-Bold'))
        if style_d.get('align') == 'center' or cell.cell_type == 'header':
            style_cmds.append(('ALIGNMENT', (c, r), (c, r), 'CENTER'))
        if cell.cell_type == 'header':
            style_cmds.append(('BACKGROUND', (c, r), (c, r), colors.HexColor('#d0e4ff')))

        matrix[r][c] = Paragraph(text, styles['Normal'])

        # Span commands
        if cell.rowspan > 1 or cell.colspan > 1:
            end_r = r + cell.rowspan - 1
            end_c = c + cell.colspan - 1
            span_cmds.append(('SPAN', (c, r), (end_c, end_r)))
            for rr in range(r, end_r + 1):
                for cc in range(c, end_c + 1):
                    covered.add((rr, cc))
        else:
            covered.add((r, c))

    # Fill remaining None cells with ''
    for r in range(max_row + 1):
        for c in range(num_cols):
            if matrix[r][c] is None:
                matrix[r][c] = ''

    t = Table(matrix)
    t.setStyle(TableStyle(style_cmds + span_cmds))
    return [t]


def _build_simple_results_table(result, styles, pr_map):
    """Fallback table when no grid layout is defined."""
    bold = ParagraphStyle('Bold', parent=styles['Normal'], fontName='Helvetica-Bold')
    normal = styles['Normal']

    data = [[
        Paragraph('Parámetro', bold),
        Paragraph('Resultado', bold),
        Paragraph('Unidades', bold),
        Paragraph('Referencia', bold),
    ]]

    for pr in result.parameter_results:
        param = pr.parameter
        value_text = pr.value or ''
        if pr.out_of_range or pr.flagged:
            value_para = Paragraph(f'<font color="red">*{value_text}*</font>', normal)
        else:
            value_para = Paragraph(value_text, normal)

        ref_desc = ''
        for rv in param.reference_values.all():
            if rv.ref_type == 'range':
                parts = []
                if rv.min_value is not None:
                    parts.append(str(rv.min_value))
                if rv.max_value is not None:
                    parts.append(str(rv.max_value))
                ref_desc = ' – '.join(parts)
            elif rv.ref_type == 'exact':
                ref_desc = str(rv.exact_value or '')
            else:
                ref_desc = rv.text_value or ''
            break

        data.append([
            Paragraph(param.name, normal),
            value_para,
            Paragraph(pr.units or '', normal),
            Paragraph(ref_desc, normal),
        ])

    t = Table(data, colWidths=[None, 35 * mm, 30 * mm, 40 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d0e4ff')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    return [t]


def _build_signatures(result, styles, page_size, margin_left, margin_right):
    usable_width = page_size[0] - margin_left - margin_right
    col_w = usable_width / 2

    def sig_block(user):
        items = []
        sig_path = None
        if user and user.signature_image:
            full = os.path.join(current_app.config['UPLOAD_FOLDER'], user.signature_image)
            if os.path.exists(full):
                sig_path = full
        if sig_path:
            items.append(Image(sig_path, width=50 * mm, height=20 * mm))
        else:
            items.append(Spacer(1, 20 * mm))
        items.append(HRFlowable(width=col_w - 10 * mm, thickness=0.5, color=colors.black))
        if user:
            items.append(Paragraph(
                user.name,
                ParagraphStyle('SigName', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER)
            ))
            if user.professional_id:
                items.append(Paragraph(
                    f'Reg. Prof.: {user.professional_id}',
                    ParagraphStyle('SigReg', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER)
                ))
        return items

    bact = result.bacteriologist
    rev = result.reviewer

    if rev:
        data = [[sig_block(bact), sig_block(rev)]]
        t = Table(data, colWidths=[col_w, col_w])
    else:
        data = [[sig_block(bact)]]
        t = Table(data, colWidths=[col_w])

    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    return [t]


def _build_qr(result, cfg, styles):
    """Generate a QR code pointing to the verification URL."""
    try:
        with current_app.test_request_context():
            verify_url = url_for(
                'results.verify', token=result.qr_token, _external=True
            )
    except Exception:
        verify_url = f'/results/verify/{result.qr_token}'

    qr = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(verify_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    qr_img = Image(buf, width=25 * mm, height=25 * mm)
    label = Paragraph(
        'Escanea para verificar autenticidad',
        ParagraphStyle('QRLabel', parent=styles['Normal'], fontSize=7, alignment=TA_CENTER)
    )
    container = Table([[qr_img], [label]], colWidths=[30 * mm])
    container.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return [container]
