from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, jsonify,
)
from flask_login import login_required
from app.models import Order, Patient
from app import db

orders_bp = Blueprint('orders', __name__)


@orders_bp.route('/')
@login_required
def list_orders():
    q = request.args.get('q', '').strip()
    query = Order.query.join(Patient)
    if q:
        query = query.filter(
            Order.consecutive.ilike(f'%{q}%') |
            Patient.name.ilike(f'%{q}%') |
            Patient.document.ilike(f'%{q}%')
        )
    orders = query.order_by(Order.date.desc()).limit(100).all()
    return render_template('orders/list.html', orders=orders, q=q)


@orders_bp.route('/new', methods=['GET', 'POST'])
@login_required
def order_new():
    if request.method == 'POST':
        # Resolve or create patient
        patient = _resolve_patient(request.form)
        if not patient:
            return redirect(url_for('orders.order_new'))

        consecutive = request.form.get('consecutive', '').strip()
        if Order.query.filter_by(consecutive=consecutive).first():
            flash('Ya existe una orden con ese consecutivo.', 'warning')
            return redirect(url_for('orders.order_new'))

        order = Order(
            consecutive=consecutive,
            patient_id=patient.id,
            attending_physician=request.form.get('attending_physician', '').strip(),
            diagnosis=request.form.get('diagnosis', '').strip(),
            notes=request.form.get('notes', '').strip(),
        )
        db.session.add(order)
        db.session.commit()
        flash('Orden creada.', 'success')
        return redirect(url_for('orders.order_detail', order_id=order.id))
    patients = Patient.query.filter_by(active=True).order_by(Patient.name).all()
    return render_template('orders/form.html', order=None, patients=patients)


@orders_bp.route('/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    return render_template('orders/detail.html', order=order)


# ---------------------------------------------------------------------------
# Patient management
# ---------------------------------------------------------------------------

@orders_bp.route('/patients')
@login_required
def patients_list():
    q = request.args.get('q', '').strip()
    query = Patient.query.filter_by(active=True)
    if q:
        query = query.filter(
            Patient.name.ilike(f'%{q}%') | Patient.document.ilike(f'%{q}%')
        )
    patients = query.order_by(Patient.name).limit(100).all()
    return render_template('orders/patients.html', patients=patients, q=q)


@orders_bp.route('/patients/new', methods=['GET', 'POST'])
@login_required
def patient_new():
    if request.method == 'POST':
        patient = _patient_from_form(Patient())
        if Patient.query.filter_by(document=patient.document).first():
            flash('Ya existe un paciente con ese documento.', 'warning')
            return redirect(url_for('orders.patient_new'))
        db.session.add(patient)
        db.session.commit()
        flash('Paciente registrado.', 'success')
        return redirect(url_for('orders.patients_list'))
    return render_template('orders/patient_form.html', patient=None)


@orders_bp.route('/patients/<int:patient_id>/edit', methods=['GET', 'POST'])
@login_required
def patient_edit(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    if request.method == 'POST':
        _patient_from_form(patient)
        db.session.commit()
        flash('Paciente actualizado.', 'success')
        return redirect(url_for('orders.patients_list'))
    return render_template('orders/patient_form.html', patient=patient)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_patient(form):
    patient_id = form.get('patient_id', '').strip()
    if patient_id:
        patient = Patient.query.get(int(patient_id))
        if not patient:
            flash('Paciente no encontrado.', 'danger')
        return patient
    # inline patient creation
    document = form.get('patient_document', '').strip()
    if not document:
        flash('Se requiere el documento del paciente.', 'danger')
        return None
    patient = Patient.query.filter_by(document=document).first()
    if not patient:
        patient = _patient_from_form(Patient(), prefix='patient_')
        db.session.add(patient)
        db.session.flush()
    return patient


def _patient_from_form(patient, prefix=''):
    patient.document_type = request.form.get(f'{prefix}document_type', 'CC')
    patient.document = request.form.get(f'{prefix}document', '').strip()
    patient.name = request.form.get(f'{prefix}name', '').strip()
    birth = request.form.get(f'{prefix}birth_date', '').strip()
    if birth:
        from datetime import date
        try:
            patient.birth_date = date.fromisoformat(birth)
        except ValueError:
            pass
    patient.gender = request.form.get(f'{prefix}gender', '')
    patient.phone = request.form.get(f'{prefix}phone', '').strip()
    patient.email = request.form.get(f'{prefix}email', '').strip()
    patient.address = request.form.get(f'{prefix}address', '').strip()
    return patient
