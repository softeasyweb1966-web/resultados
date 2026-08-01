import os
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, current_app,
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models import PDFConfig
from app import db

pdf_config_bp = Blueprint('pdf_config', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg'}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@pdf_config_bp.route('/')
@login_required
def list_configs():
    configs = PDFConfig.query.filter_by(user_id=current_user.id).all()
    default_cfg = PDFConfig.query.filter_by(is_default=True).first()
    return render_template('pdf_config/list.html', configs=configs, default_cfg=default_cfg)


@pdf_config_bp.route('/new', methods=['GET', 'POST'])
@login_required
def config_new():
    if request.method == 'POST':
        cfg = _config_from_form(PDFConfig(user_id=current_user.id))
        cfg.logo_path = _handle_logo_upload(request, current_app.config['UPLOAD_FOLDER'])
        db.session.add(cfg)
        db.session.commit()
        flash('Configuración PDF creada.', 'success')
        return redirect(url_for('pdf_config.list_configs'))
    return render_template('pdf_config/form.html', cfg=None)


@pdf_config_bp.route('/<int:cfg_id>/edit', methods=['GET', 'POST'])
@login_required
def config_edit(cfg_id):
    cfg = PDFConfig.query.get_or_404(cfg_id)
    if cfg.user_id != current_user.id and current_user.role != 'admin':
        flash('Acceso restringido.', 'danger')
        return redirect(url_for('pdf_config.list_configs'))
    if request.method == 'POST':
        _config_from_form(cfg)
        logo_path = _handle_logo_upload(request, current_app.config['UPLOAD_FOLDER'])
        if logo_path:
            cfg.logo_path = logo_path
        db.session.commit()
        flash('Configuración PDF actualizada.', 'success')
        return redirect(url_for('pdf_config.list_configs'))
    return render_template('pdf_config/form.html', cfg=cfg)


@pdf_config_bp.route('/<int:cfg_id>/set-default', methods=['POST'])
@login_required
def set_default(cfg_id):
    # Remove existing default
    PDFConfig.query.filter_by(is_default=True).update({'is_default': False})
    cfg = PDFConfig.query.get_or_404(cfg_id)
    cfg.is_default = True
    db.session.commit()
    flash(f'"{cfg.name}" establecida como configuración predeterminada.', 'success')
    return redirect(url_for('pdf_config.list_configs'))


@pdf_config_bp.route('/<int:cfg_id>/delete', methods=['POST'])
@login_required
def config_delete(cfg_id):
    cfg = PDFConfig.query.get_or_404(cfg_id)
    db.session.delete(cfg)
    db.session.commit()
    flash('Configuración eliminada.', 'warning')
    return redirect(url_for('pdf_config.list_configs'))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _config_from_form(cfg):
    cfg.name = request.form.get('name', 'Default').strip()
    cfg.institution_name = request.form.get('institution_name', '').strip()
    cfg.institution_address = request.form.get('institution_address', '').strip()
    cfg.institution_phone = request.form.get('institution_phone', '').strip()
    cfg.header_text = request.form.get('header_text', '').strip()
    cfg.footer_text = request.form.get('footer_text', '').strip()
    cfg.page_size = request.form.get('page_size', 'A4')
    cfg.margin_top = float(request.form.get('margin_top', 20) or 20)
    cfg.margin_bottom = float(request.form.get('margin_bottom', 20) or 20)
    cfg.margin_left = float(request.form.get('margin_left', 20) or 20)
    cfg.margin_right = float(request.form.get('margin_right', 20) or 20)
    cfg.show_qr = bool(request.form.get('show_qr'))
    cfg.show_watermark = bool(request.form.get('show_watermark'))
    cfg.watermark_text = request.form.get('watermark_text', '').strip()
    return cfg


def _handle_logo_upload(req, upload_folder):
    file = req.files.get('logo_file')
    if file and file.filename and _allowed_file(file.filename):
        filename = secure_filename(file.filename)
        save_path = os.path.join(upload_folder, filename)
        file.save(save_path)
        return filename
    return None
