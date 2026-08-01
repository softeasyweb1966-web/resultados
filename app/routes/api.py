from flask import Blueprint, jsonify, request
from flask_login import login_required
from app.models import Exam, Parameter, Order, Patient, Result, ParameterResult
from app import db

api_bp = Blueprint('api', __name__)


@api_bp.route('/exams/search')
@login_required
def exam_search():
    q = request.args.get('q', '').strip()
    exams = Exam.query.filter(
        Exam.active == True,
        Exam.name.ilike(f'%{q}%') | Exam.code.ilike(f'%{q}%')
    ).order_by(Exam.name).limit(20).all()
    return jsonify([{'id': e.id, 'code': e.code, 'name': e.name} for e in exams])


@api_bp.route('/patients/search')
@login_required
def patient_search():
    q = request.args.get('q', '').strip()
    patients = Patient.query.filter(
        Patient.active == True,
        Patient.name.ilike(f'%{q}%') | Patient.document.ilike(f'%{q}%')
    ).order_by(Patient.name).limit(20).all()
    return jsonify([
        {'id': p.id, 'document': p.document, 'name': p.name, 'gender': p.gender, 'age': p.age}
        for p in patients
    ])


@api_bp.route('/orders/search')
@login_required
def order_search():
    q = request.args.get('q', '').strip()
    orders = (
        Order.query.join(Patient)
        .filter(
            Order.consecutive.ilike(f'%{q}%') |
            Patient.name.ilike(f'%{q}%') |
            Patient.document.ilike(f'%{q}%')
        )
        .order_by(Order.date.desc())
        .limit(20)
        .all()
    )
    return jsonify([
        {
            'id': o.id,
            'consecutive': o.consecutive,
            'patient_name': o.patient.name,
            'patient_document': o.patient.document,
            'date': o.date.strftime('%Y-%m-%d'),
        }
        for o in orders
    ])


@api_bp.route('/results/<int:result_id>/parameter-values')
@login_required
def parameter_values(result_id):
    """Return parameter results for a given result (used to show previous results)."""
    result = Result.query.get_or_404(result_id)
    data = []
    for pr in result.parameter_results:
        data.append({
            'parameter_id': pr.parameter_id,
            'parameter_name': pr.parameter.name,
            'value': pr.value,
            'units': pr.units,
            'out_of_range': pr.out_of_range,
            'flagged': pr.flagged,
        })
    return jsonify({'date': result.date.strftime('%Y-%m-%d'), 'values': data})


@api_bp.route('/parameters/<int:param_id>/units-suggestions')
@login_required
def units_suggestions(param_id):
    """Return common units for a parameter based on reference values."""
    param = Parameter.query.get_or_404(param_id)
    units_set = set()
    if param.default_units:
        units_set.add(param.default_units)
    for rv in param.reference_values:
        if rv.units:
            units_set.add(rv.units)
    return jsonify(list(units_set))
