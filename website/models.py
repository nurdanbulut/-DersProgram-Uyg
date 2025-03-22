from peewee import SqliteDatabase, Model, IntegerField, CharField, BooleanField, ForeignKeyField, DateField

from datetime import date

from werkzeug.security import generate_password_hash

db = SqliteDatabase("database/db.sqlite")

class BaseModel(Model):
    class Meta:
        database = db


class Department(BaseModel):
    name = CharField(max_length=255)
    short_name = CharField(max_length=5, unique=True)
    max_hour = IntegerField()

    class Meta:
        table_name = 'departments'

class User(BaseModel):
    name = CharField(max_length=255)
    department = ForeignKeyField(Department, backref='users',
                                 null=True)  # Eğer kullanıcı öğrenci değilse, boş olabilir.
    grade = IntegerField(null=True)  # Öğrenci değilse boş olabilir.
    type = IntegerField()  # 0: Öğrenci, 1: Öğretim Görevlisi, 2: Yönetici
    password = CharField(max_length=255) # Şifre

    class Meta:
        table_name = 'users'

class LessonType(BaseModel):
    name = CharField(max_length=255)
    code = CharField(max_length=10)
    teacher = ForeignKeyField(User, backref='lessons', null=True)  # Bir öğretmene bağlı olabilir
    online = BooleanField(default=False)  # Dersin online olup olmadığını belirtir.

    def __dict__(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'teacher': {
                'name': self.teacher.name,
            },
            'online': self.online,
        }

    def __str__(self):
        rslt = f"{ self.name } - { self.code } - { self.teacher.name } - "

        if self.online:
            rslt += "Online"
        else:
            rslt += "Yüzyüze"

        return rslt

    class Meta:
        table_name = 'lesson_types'

class SyllabusOptions(BaseModel):
    lesson_type = ForeignKeyField(LessonType, backref='syllabus_options')
    hpw = IntegerField()  # Haftalık saat
    department = ForeignKeyField(Department, backref='syllabus_options')
    grade = IntegerField()
    shareable = BooleanField(default=False)

    class Meta:
        table_name = 'syllabus_options'

class Syllabus(BaseModel):
    excel_folder = CharField(null=True)
    created_at = DateField(default=date.today)

    class Meta:
        table_name = 'syllabuses'

class Excel(BaseModel):
    department = ForeignKeyField(Department, backref='excels')
    filename = CharField(null=True)
    syllabus = ForeignKeyField(Syllabus, backref='excels')

    class Meta:
        table_name = 'excels'

class Lesson(BaseModel):
    day = IntegerField()  # 1: Pazartesi, 2: Salı, vs.
    start_hour = IntegerField()  # Başlangıç saati
    type = ForeignKeyField(LessonType, backref='lessons')  # normal veya online
    teacher = ForeignKeyField(User, backref='teachers')  # Öğretmen
    grade = IntegerField()  # Hangi sınıf seviyesi
    options = ForeignKeyField(SyllabusOptions, backref='lessons')
    syllabus = ForeignKeyField(Syllabus, backref='syllabuses')
    shared = BooleanField(default=False)

    class Meta:
        table_name = 'lessons'

db.create_tables([Department, User, Lesson, SyllabusOptions, LessonType, Syllabus, Excel],safe=True)

if User.select().count() == 0: # Eğer hiçbir kullanıcı yok ise bir yönetici kullanıcı oluştur.
    User(name="Admin", type=2, password=generate_password_hash('admin')).save()
