import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor inicie sesión para continuar.'
login_manager.login_message_category = 'warning'


def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    from app.routes.auth import auth_bp
    from app.routes.exams import exams_bp
    from app.routes.designer import designer_bp
    from app.routes.results import results_bp
    from app.routes.orders import orders_bp
    from app.routes.pdf_config import pdf_config_bp
    from app.routes.main import main_bp
    from app.routes.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(exams_bp, url_prefix='/exams')
    app.register_blueprint(designer_bp, url_prefix='/designer')
    app.register_blueprint(results_bp, url_prefix='/results')
    app.register_blueprint(orders_bp, url_prefix='/orders')
    app.register_blueprint(pdf_config_bp, url_prefix='/pdf-config')
    app.register_blueprint(api_bp, url_prefix='/api')

    return app
