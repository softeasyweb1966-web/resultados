from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, jsonify, send_file,
)
from flask_login import login_required, current_user
from app.models import Order, Exam, Result, ParameterResult, Parameter, LayoutCell, User
from app.services.reference_checker import check_parameter_value
from app.services.pdf_generator import generate_result_pdf
from app import db
import io

results_bp = Blueprint('results', __name__)


# ---------------------------------------------------------------------------
# Search / entry point
# ---------------------------------------------------------------------------

@results_bp.route('/')
@login_required
def search():
    consecutive = request.args.get('consecutive', '').strip()
    exam_code = request.args.get('exam_code', '').strip()
    order = None
    exam = None

    if consecutive:
        order = Order.query.filter_by(consecutive=consecutive).first()
        if not order:
            flash('No se encontró la orden con ese consecutivo.', 'warning')

    if order and exam_code:
        exam = Exam.query.filter_by(code=exam_code.upper(), active=True).first()
        if not exam:
            flash('Código de examen no encontrado.', 'warning')

    if order and exam:
        return redirect(url_for('results.register', order_id=order.id, exam_id=exam.id))

    exams = Exam.query.filter_by(active=True).order_by(Exam.name).all()
    return render_template(
        'results/search.html',
        order=order,
        exams=exams,
        consecutive=consecutive,
        exam_code=exam_code,
    )


# ---------------------------------------------------------------------------
# Register result
# ---------------------------------------------------------------------------

@results_bp.route('/register/<int:order_id>/<int:exam_id>', methods=['GET', 'POST'])
@login_required
def register(order_id, exam_id):
    order = Order.query.get_or_404(order_id)
    exam = Exam.query.get_or_404(exam_id)
    patient = order.patient
    params = exam.parameters.filter_by(active=True).order_by(Parameter.order_index).all()
    cells = exam.layout_cells.order_by(LayoutCell.row, LayoutCell.col).all()

    # Previous results for same patient & exam
    prev_results = (
        Result.query
        .join(Order)
        .filter(
            Order.patient_id == patient.id,
            Result.exam_id == exam_id,
            Result.status == 'final',
        )
        .order_by(Result.date.desc())
        .limit(5)
        .all()
    )

    bacteriologists = User.query.filter(
        User.active == True,
        User.role.in_(['bacteriologist', 'admin'])
    ).order_by(User.name).all()
    reviewers = User.query.filter(
        User.active == True,
        User.role.in_(['reviewer', 'admin'])
    ).order_by(User.name).all()

    # Existing draft
    existing = (
        Result.query
        .filter_by(order_id=order_id, exam_id=exam_id, status='draft')
        .first()
    )

    if request.method == 'POST':
        action = request.form.get('action', 'save')

        if existing:
            result = existing
        else:
            result = Result(order_id=order_id, exam_id=exam_id)
            result.generate_qr_token()
            db.session.add(result)

        result.bacteriologist_id = int(request.form.get('bacteriologist_id', current_user.id))
        rev_id = request.form.get('reviewer_id', '')
        result.reviewer_id = int(rev_id) if rev_id else None
        result.notes = request.form.get('notes', '').strip()

        if action == 'finalize':
            result.status = 'final'
        elif action == 'approve':
            result.status = 'approved'

        # Save parameter results
        ParameterResult.query.filter_by(result_id=result.id).delete()
        db.session.flush()

        alarms = []
        for param in params:
            if param.is_fixed:
                continue
            value = request.form.get(f'param_{param.id}', '').strip()
            units = request.form.get(f'units_{param.id}', param.default_units or '').strip()
            out_of_range, alarm_desc = check_parameter_value(
                param, value, patient.age, patient.gender
            )
            flagged = bool(request.form.get(f'flag_{param.id}'))
            pr = ParameterResult(
                result_id=result.id,
                parameter_id=param.id,
                value=value,
                units=units,
                out_of_range=out_of_range,
                flagged=flagged or out_of_range,
            )
            db.session.add(pr)
            if out_of_range:
                alarms.append({'param': param.name, 'desc': alarm_desc, 'value': value})

        db.session.commit()

        if alarms and action == 'save':
            alarm_msgs = '; '.join(f"{a['param']}: {a['value']} (ref: {a['desc']})" for a in alarms)
            flash(f'⚠️ Valores fuera de rango: {alarm_msgs}', 'warning')

        if action in ('finalize', 'approve'):
            flash('Resultado guardado exitosamente.', 'success')
            return redirect(url_for('results.result_detail', result_id=result.id))

        flash('Borrador guardado.', 'info')
        return redirect(url_for('results.register', order_id=order_id, exam_id=exam_id))

    # Build grid
    grid = _cells_to_grid(cells)
    # Load existing values if draft
    existing_values = {}
    existing_units = {}
    if existing:
        for pr in existing.parameter_results:
            existing_values[pr.parameter_id] = pr.value
            existing_units[pr.parameter_id] = pr.units

    return render_template(
        'results/form.html',
        order=order,
        exam=exam,
        patient=patient,
        params=params,
        grid=grid,
        prev_results=prev_results,
        bacteriologists=bacteriologists,
        reviewers=reviewers,
        existing=existing,
        existing_values=existing_values,
        existing_units=existing_units,
    )


# ---------------------------------------------------------------------------
# Result detail / view
# ---------------------------------------------------------------------------

@results_bp.route('/<int:result_id>')
@login_required
def result_detail(result_id):
    result = Result.query.get_or_404(result_id)
    order = result.order
    exam = result.exam
    cells = exam.layout_cells.order_by(LayoutCell.row, LayoutCell.col).all()
    grid = _cells_to_grid(cells)
    pr_map = {pr.parameter_id: pr for pr in result.parameter_results}
    return render_template(
        'results/detail.html',
        result=result,
        order=order,
        exam=exam,
        grid=grid,
        pr_map=pr_map,
    )


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

@results_bp.route('/<int:result_id>/pdf')
@login_required
def result_pdf(result_id):
    result = Result.query.get_or_404(result_id)
    pdf_bytes = generate_result_pdf(result)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=False,
        download_name=f'resultado_{result.id}.pdf',
    )


# ---------------------------------------------------------------------------
# Verify by QR token (public)
# ---------------------------------------------------------------------------

@results_bp.route('/verify/<token>')
def verify(token):
    result = Result.query.filter_by(qr_token=token).first_or_404()
    return render_template('results/verify.html', result=result)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@results_bp.route('/list')
@login_required
def list_results():
    q = request.args.get('q', '').strip()
    query = Result.query.join(Order).join(Order.patient.__class__)
    if q:
        from app.models import Patient
        query = (
            Result.query
            .join(Order)
            .join(Patient, Order.patient_id == Patient.id)
            .filter(
                Order.consecutive.ilike(f'%{q}%') |
                Patient.name.ilike(f'%{q}%')
            )
        )
    results = query.order_by(Result.date.desc()).limit(100).all()
    return render_template('results/list.html', results=results, q=q)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cells_to_grid(cells):
    """Build a 2D structure for HTML table rendering, skipping merged positions."""
    if not cells:
        return []
    max_row = max(c.row + c.rowspan - 1 for c in cells)
    max_col = max(c.col + c.colspan - 1 for c in cells)

    covered = set()
    grid_map = {}
    for c in sorted(cells, key=lambda x: (x.row, x.col)):
        grid_map[(c.row, c.col)] = c
        for r in range(c.row, c.row + c.rowspan):
            for cc in range(c.col, c.col + c.colspan):
                covered.add((r, cc))

    rows = []
    for r in range(max_row + 1):
        row = []
        for c in range(max_col + 1):
            if (r, c) in grid_map:
                row.append(grid_map[(r, c)])
            elif (r, c) not in covered:
                row.append(None)
            # covered but not origin → skip (merged)
        rows.append(row)
    return rows
