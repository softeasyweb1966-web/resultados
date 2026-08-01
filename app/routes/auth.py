from urllib.parse import urlsplit
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request,
)
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app import db


def _is_safe_url(target):
    """Return True only if *target* is a relative URL (no host / scheme)."""
    if not target:
        return False
    parsed = urlsplit(target)
    return not parsed.netloc and not parsed.scheme

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(username=username, active=True).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            return redirect(url_for('main.index'))
        flash('Usuario o contraseña incorrectos.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.name = request.form.get('name', current_user.name).strip()
        current_user.professional_id = request.form.get('professional_id', '').strip()
        new_pw = request.form.get('new_password', '')
        if new_pw:
            current_user.set_password(new_pw)
        db.session.commit()
        flash('Perfil actualizado.', 'success')
    return render_template('auth/profile.html')


# ---------------------------------------------------------------------------
# User management  (admin only)
# ---------------------------------------------------------------------------

@auth_bp.route('/users')
@login_required
def users_list():
    if current_user.role != 'admin':
        flash('Acceso restringido.', 'danger')
        return redirect(url_for('main.index'))
    users = User.query.order_by(User.name).all()
    return render_template('auth/users.html', users=users)


@auth_bp.route('/users/new', methods=['GET', 'POST'])
@login_required
def user_new():
    if current_user.role != 'admin':
        flash('Acceso restringido.', 'danger')
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        if User.query.filter_by(username=username).first():
            flash('El usuario ya existe.', 'warning')
        else:
            u = User(
                username=username,
                name=request.form.get('name', '').strip(),
                role=request.form.get('role', 'bacteriologist'),
                professional_id=request.form.get('professional_id', '').strip(),
            )
            u.set_password(request.form.get('password', 'changeme'))
            db.session.add(u)
            db.session.commit()
            flash('Usuario creado correctamente.', 'success')
            return redirect(url_for('auth.users_list'))
    return render_template('auth/user_form.html', user=None)


@auth_bp.route('/users/<int:uid>/edit', methods=['GET', 'POST'])
@login_required
def user_edit(uid):
    if current_user.role != 'admin':
        flash('Acceso restringido.', 'danger')
        return redirect(url_for('main.index'))
    u = User.query.get_or_404(uid)
    if request.method == 'POST':
        u.name = request.form.get('name', u.name).strip()
        u.role = request.form.get('role', u.role)
        u.professional_id = request.form.get('professional_id', '').strip()
        u.active = bool(request.form.get('active'))
        new_pw = request.form.get('password', '')
        if new_pw:
            u.set_password(new_pw)
        db.session.commit()
        flash('Usuario actualizado.', 'success')
        return redirect(url_for('auth.users_list'))
    return render_template('auth/user_form.html', user=u)
