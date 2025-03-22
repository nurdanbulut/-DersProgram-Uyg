from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from .models import User, Lesson, Syllabus

from .func import get_lessons, get_day, get_lessons_for_teacher

website = Blueprint('website', __name__, template_folder='templates/website/')

@website.before_request
def before_request():
    if session.get('type') == 2:
        return redirect(url_for('dashboard.index'))

@website.route('/')
def index():
    if session.get('type', None) == 0:
        student = User.select().where(User.id == session['id']).get()
        syllabus = Syllabus.select().order_by(Syllabus.created_at.desc()).get()

        table = get_lessons(syllabus, student.department, student.grade)

        return render_template('website/student/index.html', table=table, department=student.department, get_day=get_day, enumerate=enumerate, str=str)
    elif session.get('type', None) == 1:
        teacher = User.select().where(User.id == session['id']).get()
        table = get_lessons_for_teacher(Syllabus.select().order_by(Syllabus.created_at.desc()).get(), teacher)

        return render_template('website/teacher/index.html', table=table, get_day=get_day, enumerate=enumerate, str=str, len=len)
    else:
        flash("Lütfen giriş yapın", "danger")
        return redirect(url_for('auth.login'))