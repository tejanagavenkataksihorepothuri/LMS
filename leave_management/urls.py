from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from .views import cancel_leave

urlpatterns = [
    # Authentication URLs
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    
    # Notifications URLs
    path('notifications/', views.notifications, name='notifications'),
    path('get_login_attempts/', views.get_login_attempts, name='get_login_attempts'),
    path('delete_login_attempt/<int:attempt_id>/', views.delete_login_attempt, name='delete_login_attempt'),
    
    # Employee URLs
    path('', views.home, name='home'),
    path('apply-leave/', views.apply_leave, name='apply_leave'),
    path('leave-history/', views.leave_history, name='leave_history'),
    path('employee-list/', views.employee_list, name='employee_list'),
    path('employees-on-date/', views.employees_on_date, name='employees_on_date'),
    path('my-compensatory-leaves/', views.my_compensatory_leaves, name='my_compensatory_leaves'),
    
    # Admin URLs
    path('admin-home/', views.admin_home, name='admin_home'),
    path('leave-applications/', views.leave_applications, name='leave_applications'),
    path('employee-leave-history/', views.employee_leave_history, name='employee_leave_history'),
    path('employee-details/<str:employee_id>/', views.employee_leave_detail, name='employee_detail'),
    path('employee-leave-report/', views.employee_leave_report, name='employee_leave_report'),
    path('register-employee/', views.register_employee, name='register_employee'),
    path('bulk-register/', views.bulk_register, name='bulk_register'),
    path('download-csv-template/', views.download_csv_template, name='download_csv_template'),
    path('delete-employee/', views.delete_employee, name='delete_employee'),
    path('bulk-delete-employees/', views.bulk_delete_employees, name='bulk_delete_employees'),
    path('todays-leave/', views.todays_leave, name='todays_leave'),
    path('admin-change-password/', views.admin_change_user_password, name='admin_change_user_password'),
    path('bulk-holiday-register/', views.bulk_holiday_register, name='bulk_holiday_register'),
    path('download-holiday-csv-template/', views.download_holiday_csv_template, name='download_holiday_csv_template'),
    
    # Attendance URLs
    path('attendance/', views.user_attendance, name='user_attendance'),
    path('admin-attendance/', views.admin_attendance, name='admin_attendance'),
    
    # API endpoints
    path('approve-leave/<int:leave_id>/', views.approve_leave, name='approve_leave'),
    path('reject-leave/<int:leave_id>/', views.reject_leave, name='reject_leave'),
    path('manage-holidays/', views.manage_holidays, name='manage_holidays'),
    path('delete-holiday/<int:holiday_id>/', views.delete_holiday, name='delete_holiday'),
    path('compensatory-leave/', views.manage_compensatory_leave, name='manage_compensatory_leave'),
    path('compensatory-leave/delete/<int:comp_leave_id>/', views.delete_compensatory_leave, name='delete_compensatory_leave'),
    path('reports/', views.reports, name='reports'),
    path('cancel-leave/<int:leave_id>/', cancel_leave, name='cancel_leave'),
]
