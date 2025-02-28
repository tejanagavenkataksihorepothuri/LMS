from django.contrib import admin
from .models import Employee, LeaveRequest, LeaveHistory, LoginAttempt
# Register your models here.
admin.site.register(Employee) 
admin.site.register(LeaveRequest)
admin.site.register(LeaveHistory)
admin.site.register(LoginAttempt)
