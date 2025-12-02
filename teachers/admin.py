# teachers/admin.py

from django.contrib import admin
from .models import Teacher, TeacherWorkRecord, TeacherUnavailable

admin.site.register(Teacher)
admin.site.register(TeacherWorkRecord)
admin.site.register(TeacherUnavailable)