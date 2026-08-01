import json
import uuid
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager


# ---------------------------------------------------------------------------
# User / Authentication
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='bacteriologist')
    # role options: 'admin', 'bacteriologist', 'reviewer'
    professional_id = db.Column(db.String(50))   # registration / license number
    signature_image = db.Column(db.Text)          # file path relative to uploads
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    results_as_bacteriologist = db.relationship(
        'Result', foreign_keys='Result.bacteriologist_id', backref='bacteriologist', lazy='dynamic'
    )
    results_as_reviewer = db.relationship(
        'Result', foreign_keys='Result.reviewer_id', backref='reviewer', lazy='dynamic'
    )
    pdf_configs = db.relationship('PDFConfig', backref='owner', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# Patient
# ---------------------------------------------------------------------------

class Patient(db.Model):
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)
    document_type = db.Column(db.String(20), default='CC')
    document = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    birth_date = db.Column(db.Date)
    gender = db.Column(db.String(10))   # 'M' or 'F'
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    address = db.Column(db.String(300))
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('Order', backref='patient', lazy='dynamic')

    @property
    def age(self):
        if not self.birth_date:
            return None
        today = date.today()
        return (today - self.birth_date).days // 365

    def __repr__(self):
        return f'<Patient {self.document} – {self.name}>'


# ---------------------------------------------------------------------------
# Order  (consecutive / attention)
# ---------------------------------------------------------------------------

class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    consecutive = db.Column(db.String(50), unique=True, nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    attending_physician = db.Column(db.String(200))
    diagnosis = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)

    results = db.relationship('Result', backref='order', lazy='dynamic')

    def __repr__(self):
        return f'<Order {self.consecutive}>'


# ---------------------------------------------------------------------------
# Exam catalog
# ---------------------------------------------------------------------------

class Exam(db.Model):
    __tablename__ = 'exams'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), default='human')  # 'human', 'veterinary', 'other'
    description = db.Column(db.Text)
    technique = db.Column(db.String(300))
    equipment = db.Column(db.String(300))
    method = db.Column(db.String(300))
    sample_type = db.Column(db.String(100))
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parameters = db.relationship(
        'Parameter', backref='exam', lazy='dynamic',
        cascade='all, delete-orphan', order_by='Parameter.order_index'
    )
    layout_cells = db.relationship(
        'LayoutCell', backref='exam', lazy='dynamic',
        cascade='all, delete-orphan'
    )
    results = db.relationship('Result', backref='exam', lazy='dynamic')

    def __repr__(self):
        return f'<Exam {self.code} – {self.name}>'


# ---------------------------------------------------------------------------
# Parameter
# ---------------------------------------------------------------------------

RESULT_TYPES = ('integer', 'decimal', 'text')


class Parameter(db.Model):
    __tablename__ = 'parameters'

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    result_type = db.Column(db.String(20), nullable=False, default='decimal')
    # 'integer' | 'decimal' | 'text'
    default_units = db.Column(db.String(50))
    is_fixed = db.Column(db.Boolean, default=False)
    fixed_value = db.Column(db.String(200))
    order_index = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)

    reference_values = db.relationship(
        'ReferenceValue', backref='parameter', lazy='dynamic',
        cascade='all, delete-orphan'
    )
    parameter_results = db.relationship(
        'ParameterResult', backref='parameter', lazy='dynamic'
    )

    def __repr__(self):
        return f'<Parameter {self.name} ({self.exam_id})>'


# ---------------------------------------------------------------------------
# Reference Values
# ---------------------------------------------------------------------------

class ReferenceValue(db.Model):
    __tablename__ = 'reference_values'

    id = db.Column(db.Integer, primary_key=True)
    parameter_id = db.Column(db.Integer, db.ForeignKey('parameters.id'), nullable=False)

    # Condition segmentation
    gender = db.Column(db.String(10))      # 'M', 'F', or None (all)
    min_age = db.Column(db.Integer)        # inclusive, in years
    max_age = db.Column(db.Integer)        # inclusive, in years

    # Reference type: 'range' | 'exact' | 'text'
    ref_type = db.Column(db.String(10), nullable=False, default='range')
    min_value = db.Column(db.Float)
    max_value = db.Column(db.Float)
    exact_value = db.Column(db.Float)
    text_value = db.Column(db.String(300))
    units = db.Column(db.String(50))

    def matches(self, age, gender):
        """Return True if this reference value applies to the given age/gender."""
        if self.gender and gender and self.gender != gender:
            return False
        if self.min_age is not None and age is not None and age < self.min_age:
            return False
        if self.max_age is not None and age is not None and age > self.max_age:
            return False
        return True

    def check_value(self, value):
        """
        Returns (out_of_range: bool, description: str).
        value is numeric (float) for 'range'/'exact', string for 'text'.
        """
        if self.ref_type == 'range':
            try:
                v = float(value)
            except (TypeError, ValueError):
                return False, ''
            low = self.min_value if self.min_value is not None else float('-inf')
            high = self.max_value if self.max_value is not None else float('inf')
            out = not (low <= v <= high)
            desc = f'{low} – {high} {self.units or ""}'.strip()
            return out, desc
        elif self.ref_type == 'exact':
            try:
                v = float(value)
            except (TypeError, ValueError):
                return False, ''
            out = (self.exact_value is not None and v != self.exact_value)
            desc = f'{self.exact_value} {self.units or ""}'.strip()
            return out, desc
        return False, self.text_value or ''

    def __repr__(self):
        return f'<ReferenceValue param={self.parameter_id}>'


# ---------------------------------------------------------------------------
# Exam Layout  (grid / spreadsheet-like design)
# ---------------------------------------------------------------------------

CELL_TYPES = ('header', 'label', 'result', 'fixed', 'blank', 'units')


class LayoutCell(db.Model):
    __tablename__ = 'layout_cells'

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    row = db.Column(db.Integer, nullable=False)
    col = db.Column(db.Integer, nullable=False)
    rowspan = db.Column(db.Integer, default=1)
    colspan = db.Column(db.Integer, default=1)
    cell_type = db.Column(db.String(20), default='label')
    content = db.Column(db.Text)               # static text / header label
    parameter_id = db.Column(db.Integer, db.ForeignKey('parameters.id'))
    style = db.Column(db.Text)                 # JSON: {"bold": true, "align": "center", ...}

    parameter = db.relationship('Parameter')

    @property
    def style_dict(self):
        if self.style:
            try:
                return json.loads(self.style)
            except Exception:
                return {}
        return {}

    def __repr__(self):
        return f'<LayoutCell exam={self.exam_id} r={self.row} c={self.col}>'


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

class Result(db.Model):
    __tablename__ = 'results'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    bacteriologist_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='draft')  # 'draft' | 'final' | 'approved'
    qr_token = db.Column(db.String(100), unique=True, index=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parameter_results = db.relationship(
        'ParameterResult', backref='result', lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def generate_qr_token(self):
        self.qr_token = str(uuid.uuid4()).replace('-', '')

    @property
    def has_alarms(self):
        return any(pr.out_of_range for pr in self.parameter_results)

    def __repr__(self):
        return f'<Result order={self.order_id} exam={self.exam_id}>'


class ParameterResult(db.Model):
    __tablename__ = 'parameter_results'

    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.Integer, db.ForeignKey('results.id'), nullable=False)
    parameter_id = db.Column(db.Integer, db.ForeignKey('parameters.id'), nullable=False)
    value = db.Column(db.Text)
    units = db.Column(db.String(50))
    out_of_range = db.Column(db.Boolean, default=False)
    flagged = db.Column(db.Boolean, default=False)  # confirmed out-of-range and saved anyway

    def __repr__(self):
        return f'<ParameterResult result={self.result_id} param={self.parameter_id}>'


# ---------------------------------------------------------------------------
# PDF Configuration
# ---------------------------------------------------------------------------

class PDFConfig(db.Model):
    __tablename__ = 'pdf_configs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(100), nullable=False, default='Default')
    is_default = db.Column(db.Boolean, default=False)

    logo_path = db.Column(db.String(500))
    header_text = db.Column(db.Text)
    footer_text = db.Column(db.Text)
    institution_name = db.Column(db.String(200))
    institution_address = db.Column(db.String(400))
    institution_phone = db.Column(db.String(100))

    page_size = db.Column(db.String(20), default='A4')  # 'A4', 'Letter'
    margin_top = db.Column(db.Float, default=20.0)
    margin_bottom = db.Column(db.Float, default=20.0)
    margin_left = db.Column(db.Float, default=20.0)
    margin_right = db.Column(db.Float, default=20.0)
    show_qr = db.Column(db.Boolean, default=True)
    show_watermark = db.Column(db.Boolean, default=False)
    watermark_text = db.Column(db.String(100))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<PDFConfig {self.name}>'
