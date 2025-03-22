import shutil

from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, send_file, session

from . import LessonType, Excel
from .func import generate_password, get_student_count_of_department, parse_options, format_options, get_shared_lessons, place_lesson, get_lessons, get_day, create_excel
from .models import User, Department, LessonType, SyllabusOptions, Syllabus, Lesson

from werkzeug.security import generate_password_hash

from uuid import uuid4
from os import makedirs
from pathlib import Path

dashboard = Blueprint('dashboard', __name__, template_folder='templates/dashboard/')

@dashboard.before_request
def before_request():
    if session.get('type', 0) != 2:
        flash("Yönetici değilsiniz!", "danger")
        return redirect(url_for('auth.login'))

# ! Ders Programı Başlangıç

# Anasayfa
@dashboard.route('/')
def index(): # Anasayfa ve bazı verilerin gösterileceği kısım
    departments = Department.select()

    for department in departments:
        department.is_options_set = [False, False, False, False]

        for option in SyllabusOptions.select(SyllabusOptions.grade).where(SyllabusOptions.department == department).distinct():
            department.is_options_set[option.grade-1] = True

    syllabus_options = SyllabusOptions.select()

    syllabuses = Syllabus.select()

    return render_template('syllabus/index.html', departments=departments, enumerate=enumerate, syllabus_options=syllabus_options, SyllabusOptions=SyllabusOptions, syllabuses=syllabuses, str=str)


@dashboard.route('/syllabus-options/add/<int:department>/<int:grade>', methods=['GET', 'POST'])
def syllabus_options_add(department, grade):
    department = Department.select().where(Department.id == department).get_or_none()
    if not department:
        flash("Bölüm bulunamadı!", "danger")
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        options = parse_options(request)

        lesson_types = []

        online_hours_sum = 0
        for lesson_type, hour, shareable in options:
            lesson_type = LessonType.select().where(LessonType.id == lesson_type).get_or_none()

            if not lesson_type:
                flash("Ders tipi bulunamadı" "danger")
                return redirect(url_for('dashboard.syllabus_options_add', department=department.id, grade=grade))

            if lesson_type.online:
                online_hours_sum += hour
                if online_hours_sum > 10:
                    flash("Online derslerin saatinin toplamı 10'u geçemez", "danger")
                    return redirect(url_for('dashboard.syllabus_options_add', department=department.id, grade=grade))

            lesson_type.hour = hour
            lesson_type.shareable = shareable
            lesson_types.append(lesson_type)

        SyllabusOptions.delete().where(SyllabusOptions.department == department, SyllabusOptions.grade == grade).execute()
        for lesson_type in lesson_types:

            option = SyllabusOptions(
                lesson_type=lesson_type,
                hpw=lesson_type.hour,
                department=department,
                grade=grade,
                shareable=lesson_type.shareable,
            )
            option.save()

        flash("Başarıyla kaydedildi.", "success")
        return redirect(url_for('dashboard.index'))

    else:
        lessons = LessonType.select()
        lessons = [lesson.__dict__() for lesson in lessons]

        options = format_options(department, grade)

        return render_template('syllabus_options/add.html', department=department, grade=grade, lessons=lessons, options=options)


@dashboard.route('/syllabus/create')
def syllabus_create():
    syllabus = Syllabus() # Ders programını oluşturuyorum
    syllabus.save() # İçine ders ekleyebilmek için kaydediyorum

    all_options = {option:option.hpw for option in (SyllabusOptions.select())}
    shared_options = get_shared_lessons()

    # Ortak derslerin eklenmesi
    current_option = None # En son eklenen ayar
    saved_lessons = [] # Aynı ayarları diğer bölümlere de eklemek için kaydediyorum
    for shared_option in shared_options:
        # Eğer son eklenen ayar var ise şimdikinden farklı bir ayarı ve aynı ders tipini belirtiyorsa o zaman daha önce
        # eklenmiş seçeneklere göre işlem yapılacak
        if current_option and shared_option != current_option and shared_option.lesson_type == current_option.lesson_type:
            """
            Kayıtlı seçenekler içinde geziniyor(İlk kaydedilen seçenek ortak olan ders sayısının en küçüğünü aldığı için
            otomatik olarak kalan eğer ortak olmayan ders varsa ayrılıyor). Gezindiği her dersin ayarını diğer bölüme ve
            sınıfa ekliyor ve eklediği her dersi de all_options'un saat sayısından düşüyor            
            
            """
            for lesson in saved_lessons:
                Lesson(
                    day=lesson.day,
                    start_hour=lesson.start_hour,
                    type=lesson.type,
                    teacher=lesson.teacher,
                    grade=shared_option.grade,
                    options=shared_option,
                    syllabus=syllabus,
                    shared=True
                ).save()

                all_options[shared_option] -= 1
        else:
            # Yeni eklenen ayar daha önce eklenenden farklıysa
            current_option = shared_option
            saved_lessons.clear()
            # ders sayısı kadar ekleme yapılıyor
            for _ in range(shared_option.hpw):
                state, lesson = place_lesson(
                    shared_option,
                    syllabus,
                    shared=True
                )

                # Eğer herhangi bir hata varsa durduruluyor
                if not state:
                    flash(lesson, "danger")
                    return redirect(url_for('dashboard.index'))

                saved_lessons.append(lesson)

                all_options[shared_option] -= 1

    # Diğer dersleri ekleme
    for option, hour in all_options.items():
        for _ in range(hour):
            state, lesson = place_lesson(
                option,
                syllabus,
                shared=False
            )

            if not state:
                flash(lesson, "danger")
                return redirect(url_for('dashboard.index'))

            all_options[option] -= 1

    try:
        syllabus.excel_folder = str(uuid4())
        folder_path = (current_app.config["ROOT_URL"] / "excels" / "output" / syllabus.excel_folder).resolve()
        makedirs(folder_path, exist_ok=True)

        for department in Department.select():
            create_excel((current_app.config.get('ROOT_URL') / "excels").resolve(), syllabus.excel_folder, syllabus, department)

        syllabus.save()
    except Exception as e:
        flash(f"Excel oluşturulamadı: {e}", "danger")
        return redirect(url_for('dashboard.index'))

    flash("Başarıyla oluşturuldu.", "success")
    return redirect(url_for('dashboard.index'))

@dashboard.route('/syllabus/<int:id>')
def syllabus_view(id):
    syllabus = Syllabus.select().where(Syllabus.id == id).get_or_none()

    if not syllabus:
        flash("Ders programı bulunamadı!", "danger")
        return redirect(url_for('dashboard.index'))

    departments = {department: [None for _ in range(4)] for department in  Department.select()}

    for department, tables in departments.items():
        for grade, table in enumerate(tables):
            departments[department][grade] = get_lessons(syllabus, department, grade + 1)

    return render_template('syllabus/view.html', departments=departments, enumerate=enumerate, get_day=get_day, str=str, syllabus=syllabus)

@dashboard.route('/syllabus/delete/<int:id>')

def syllabus_delete(id):
    syllabus = Syllabus.select().where(Syllabus.id == id).get_or_none()
    if not syllabus:
        flash("Ders programı bulunamadı", "danger")
        return redirect(url_for('dashboard.index'))

    # ROOT_URL kontrolü
    root_url = current_app.config.get('ROOT_URL')
    if not root_url:
        flash("ROOT_URL tanımlı değil! Lütfen yapılandırmayı kontrol edin.", "danger")
        return redirect(url_for('dashboard.index'))

    # Excel ve Ders kayıtlarını sil
    Excel.delete().where(Excel.syllabus == syllabus).execute()
    Lesson.delete().where(Lesson.syllabus == syllabus).execute()

    # Dosya yolunu oluştur
    folder_path = Path(root_url) / 'excels' / 'output' / (syllabus.excel_folder or '')

    # Klasör var mı kontrol et ve sil
    if folder_path.exists() and folder_path.is_dir():
        try:
            shutil.rmtree(folder_path)
        except Exception as e:
            flash(f"Klasör silinirken hata oluştu: {e}", "danger")

    # Veritabanından sil
    syllabus.delete_instance(recursive=False)

    flash("Başarıyla silindi!", "warning")
    return redirect(url_for('dashboard.index'))


# ! Ders Programı Bitiş

# ! Excel Dosyası
@dashboard.route('/excel/<int:syllabus_id>/<int:department_id>')
def get_excel(syllabus_id, department_id):
    syllabus = Syllabus.select().where(Syllabus.id == syllabus_id).get_or_none()
    if not syllabus:
        flash("Ders Programı Bulunamadı!", "danger")
        return redirect(url_for('dashboard.index'))

    department = Department.select().where(Department.id == department_id).get_or_none()
    if not department:
        flash("Bölüm bulunamadı", "danger")
        return redirect(url_for('dashboard.index'))

    excel_file = Excel.select().where(Excel.syllabus == syllabus, Excel.department == department).get_or_none()

    path = (current_app.config["ROOT_URL"] / "excels" / "output" / syllabus.excel_folder / excel_file.filename).resolve()
    return send_file(path)

# ! Excel Dosyası Bitiş

# ! Öğretim Görevlileri Başlangıç

# Öğretim Görevlileri Anasayfa
@dashboard.route('/teacher')
def teacher_page():
    teachers = User.select().where(User.type == 1)

    return render_template('teacher/index.html', teachers=teachers)

# Öğretim Görevlisi Ekleme
@dashboard.route('/teacher/add', methods=['GET', 'POST'])
def teacher_add():
    if request.method == 'POST':
        name = request.form.get('name')
        is_password_auto = request.form.get('is_password_auto')

        if is_password_auto:
            password = generate_password()
        else:
            password = request.form.get('password')

        User(name=name, password=generate_password_hash(password), type=1).save()
        flash(f"{name} için kullanıcı oluşturuldu. Şifre: {password}", "success")

        return redirect(url_for('dashboard.teacher_page'))
    else:
        return render_template('teacher/add.html')

@dashboard.route('/teacher/delete/<int:id>')
def teacher_delete(id):
    teacher = User.select().where(User.id == id).get()
    if not teacher or teacher.type != 1:
        flash("Öğretmen bulunamadı!", "danger")
        return redirect(url_for('dashboard.teacher_page'))

    Lesson.delete().where(Lesson.teacher == teacher).execute()

    for option in (SyllabusOptions
    .select()
    .join(LessonType)
    .where(SyllabusOptions.lesson_type.teacher == teacher)):
        option.delete_instance(recursive=False)

    LessonType.delete().where(LessonType.teacher == teacher.id).execute()

    teacher.delete_instance(recursive=False)

    flash("Başarıyla silindi", "warning")
    return redirect(url_for('dashboard.teacher_page'))

# ! Öğretim görevlileri bitiş
# ! Öğrenciler başlangıç

# Öğrenciler anasayfa
@dashboard.route('/student')
def student_page():
    students = User.select().where(User.type == 0)

    return render_template('student/index.html', students=students)

# Öğrenci Ekleme Sayfası
@dashboard.route('/student/add', methods=['GET', 'POST'])
def student_add():
    if request.method == 'POST':
        name = request.form.get('name')

        is_password_auto = request.form.get('is_password_auto')
        if is_password_auto:
            password = generate_password()
        else:
            password = request.form.get('password')

        department_id = request.form.get('department', type=int)
        department = Department.select().where(Department.id == department_id).get_or_none()

        grade = request.form.get('grade', type=int)



        user = User(
            name=name,
            password=generate_password_hash(password),
            department=department,
            grade=grade,
            type=0
        )
        user.save()

        flash(f"Kullanıcı başarıyla oluşturuldu! Şifre: \"{password}\", ID:{user.id}", "success")
        return redirect(url_for('dashboard.student_page'))

    else:
        departments = Department.select()

        return render_template('student/add.html', departments=departments)

@dashboard.route('/student/delete/<int:id>')
def student_delete(id):
    student = User.select().where(User.id == id).get_or_none()
    if not student:
        flash("Öğrenci bulunamadı", "danger")
        return redirect(url_for('dashboard.student_page'))

    student.delete_instance(recursive=False)

    flash("Başarıyla silindi", "warning")
    return redirect(url_for('dashboard.student_page'))

# ! Öğrenciler bitiş

# ! Bölümler Başlangıç

# Bölümler Anasayfa
@dashboard.route('/department')
def department_page():
    departments = Department.select()

    return render_template('department/index.html', departments=departments, count_student=get_student_count_of_department)

# Bölümler Ekleme Sayfası
@dashboard.route('/department/add', methods=['GET', 'POST'])
def department_add():
    if request.method == 'POST':
        name = request.form.get('name')
        short_name = request.form.get('short_name').lstrip().upper()
        max_hour = request.form.get('max_hour')

        if department := Department.select().where(Department.short_name == short_name).get_or_none():
            flash("Bu kod ile daha önce bir bölüm kayıt edilmiş", "danger")
            return redirect(url_for('dashboard.department_add'))

        department = Department(name=name, short_name=short_name, max_hour=max_hour)
        department.save()

        flash("Bölüm başarıyla kaydedildi", "success")
        return redirect(url_for('dashboard.department_page'))
    else:
        return render_template('department/add.html')

# Bölüm Silme
@dashboard.route('/department/delete/<int:id>')
def department_delete(id):
    department = Department.select().where(Department.id == id).get_or_none()
    if not department:
        flash("Bölüm bulunamadı", "danger")
        return redirect(url_for('dashboard.department_page'))

    for excel in Excel.select().where(Excel.department == department):
        try:
            syllabus_delete(excel.syllabus.id)
        except:
            pass

    User.delete().where(User.department==department).execute()
    SyllabusOptions.delete().where(SyllabusOptions.department==department).execute()
    department.delete_instance(recursive=False)

    flash("Bölüm ve öğrenciler başarıyla silindi", "danger")
    return redirect(url_for('dashboard.department_page'))

# ! Bölüm Bitiş
# ! Ders Tipleri Başlangıç

# Ders tipi Anasayfa
@dashboard.route('/lesson-type')
def lesson_type_page():
    lesson_types = LessonType.select().order_by(LessonType.teacher, LessonType.code)

    return render_template('lesson_type/index.html', lesson_types=lesson_types)

# Ders tipi ekleme
@dashboard.route('/lesson-type/add', methods=['GET', 'POST'])
def lesson_type_add():
    if request.method == 'POST':
        name = request.form.get('name')
        code = request.form.get('code').lstrip().upper()

        teacher_id = request.form.get('teacher')
        teacher = User.select().where(User.id == teacher_id).get_or_none()
        if not teacher:
            flash('Öğretim görevlisi bulunamadı', 'danger')
            return redirect(url_for('dashboard.lesson_type_add'))

        online = request.form.get('online', type=bool, default=False)

        if LessonType.select().where(LessonType.code == code, LessonType.teacher == teacher).get_or_none():
            flash("Bu ders koduna kayıtlı bir ders tipi bulunuyor!", "danger")
            return redirect(url_for('dashboard.lesson_type_add'))

        if LessonType.select().where(LessonType.code == code, LessonType.name != name).get_or_none():
            flash("Bu ders koduna kayıtlı farklı isimde bir ders tipi bulunuyor! Lütfen aynı ders ismini giriniz!", "danger")
            return redirect(url_for('dashboard.lesson_type_add'))

        lesson_type = LessonType(
            name=name,
            code=code,
            teacher=teacher,
            online=online
        )

        lesson_type.save()

        flash("Başarıyla kaydedildi!", "success")
        return redirect(url_for('dashboard.lesson_type_page'))
    else:
        teachers = User.select().where(User.type == 1)

        return render_template('lesson_type/add.html', teachers=teachers)

# Ders tipi Silme
@dashboard.route('/lesson-type/delete/<int:id>')
def lesson_type_delete(id):
    lesson_type = LessonType.select().where(LessonType.id == id).get_or_none()
    if not lesson_type:
        flash("Ders tipi bulunamadı!", "danger")
        return redirect(url_for('dashboard.lesson_type_page'))

    SyllabusOptions.delete().where(SyllabusOptions.lesson_type == lesson_type).execute()
    lesson_type.delete_instance(recursive=False)

    flash("Başarıyla silindi", "warning")
    return redirect(url_for('dashboard.lesson_type_page'))

# ! Ders Tipi Bitiş