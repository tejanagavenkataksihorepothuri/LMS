from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Employee, LeaveRequest, LeaveHistory, LoginAttempt

class EmployeeAdmin(UserAdmin):
    list_display = ('employee_id', 'first_name', 'last_name', 'department', 'current_salary', 'date_of_joining')
    list_filter = ('department', 'is_admin')
    search_fields = ('employee_id', 'first_name', 'last_name', 'email')
    ordering = ('employee_id',)
    
    fieldsets = (
        (None, {'fields': ('employee_id', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'current_salary')}),
        ('Department info', {'fields': ('department', 'date_of_joining')}),
        ('Leave info', {'fields': ('casual_leaves_remaining', 'summer_leaves_remaining', 'extra_leaves_taken')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_admin', 'groups', 'user_permissions')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('employee_id', 'password1', 'password2', 'department', 'current_salary'),
        }),
    )

# Register your models here
admin.site.register(Employee, EmployeeAdmin)
admin.site.register(LeaveRequest)
admin.site.register(LeaveHistory)
admin.site.register(LoginAttempt)
