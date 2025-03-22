from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash

from .models import User

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('id', None):
        if session.get('type') == 2:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('website.index'))

    if request.method == 'GET':
        return render_template('auth/login.html')
    else:
        id = request.form.get('id')
        password = request.form.get('password')

        user = User.select().where(User.id == id).get_or_none()

        if user is None:
            flash('Girdiğiniz kullanıcı bulunamamıştır', 'danger')
            return redirect(url_for('auth.login'))

        if not check_password_hash(user.password, password):
            flash("Şifreniz yanlış", "danger")
            return redirect(url_for('auth.login'))

        session['id'] = user.id
        session['name'] = user.name
        session['type'] = user.type
        session['grade'] = user.grade

        if user.type == 2:
            return redirect(url_for('dashboard.index'))

        return redirect(url_for('website.index'))

@auth.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

@auth.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if not session.get('id', None):
        flash("Henüz giriş yapmadınız", "danger")
        return redirect(url_for('auth.login'))

    user = User.select().where(User.id == session.get('id', None)).get_or_none()
    if not user:
        flash("Kullanıcı bulunamadı", "danger")
        logout()

    if request.method == 'GET':
        return render_template("auth/change_password.html")

    else:
        old_password = request.form.get('old_password')
        password = request.form.get('password')
        confirm = request.form.get('confirm')

        if check_password_hash(user.password, old_password):
            if password != confirm:
                flash("Şifreler uyuşmuyor", "danger")
                return redirect(url_for('auth.change_password'))

            user.password = generate_password_hash(password)
            user.save()

            flash("Başarıyla şifreniz değiştirildi", "warning")
            session.clear()
            return redirect(url_for('auth.login'))
        else:
            flash("Şifreniz yanlış", "danger")
            return redirect(url_for('auth.change_password'))
