from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Authentication URLs
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.custom_logout, name='logout'),
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
    path('leave-details/', views.leave_details_by_date, name='leave_details_by_date'),
    
    # API endpoints
    path('approve-leave/<int:leave_id>/', views.approve_leave, name='approve_leave'),
    path('reject-leave/<int:leave_id>/', views.reject_leave, name='reject_leave'),
]
