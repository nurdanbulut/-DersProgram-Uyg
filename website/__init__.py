from flask import Flask, request, flash, url_for, redirect, session

from pathlib import Path

from datetime import timedelta

from .models import *
from .auth import auth
from .dashboard import dashboard
from .website import website

def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "B1zdkpOQ3AbJBvSaJrlCWMITM1uQwwmIbTImjIRFGkSr74J1TDp6J3Yzzl4a3Qgq96vMNf0hSSD0fouM"
    app.config['ROOT_URL'] = Path(__file__).parent.parent

    print(f"Proje {app.config['ROOT_URL']} dizininde çalıştırılıyor")

    @app.before_request
    def login_required():
        if not ((session.get('id', None)) or
                (request.endpoint and request.endpoint in ('auth.login', 'static'))):
            flash('Önce Giriş Yapın', 'danger'),
            return redirect(url_for('auth.login', next=request.url))

    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(dashboard, url_prefix='/dashboard')
    app.register_blueprint(website)

    return app