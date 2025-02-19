from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Authentication URLs
    path('login/', views.login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    
    # Employee URLs
    path('', views.home, name='home'),
    path('apply-leave/', views.apply_leave, name='apply_leave'),
    path('leave-history/', views.leave_history, name='leave_history'),
    
    # Admin URLs
    path('admin-home/', views.admin_home, name='admin_home'),
    path('leave-applications/', views.leave_applications, name='leave_applications'),
    path('employee-leave-history/', views.employee_leave_history, name='employee_leave_history'),
    path('employee-details/<str:employee_id>/', views.employee_leave_detail, name='employee_detail'),
    path('employee-leave-report/', views.employee_leave_report, name='employee_leave_report'),
    path('register-employee/', views.register_employee, name='register_employee'),
    path('delete-employee/', views.delete_employee, name='delete_employee'),
    path('admin-notifications/', views.admin_notifications, name='admin_notifications'),
    
    # Notifications URLs
    path('notifications/', views.notifications, name='notifications'),
    path('get_login_attempts/', views.get_login_attempts, name='get_login_attempts'),
    path('delete_login_attempt/<int:attempt_id>/', views.delete_login_attempt, name='delete_login_attempt'),
    
    # API endpoints
    path('approve-leave/<int:leave_id>/', views.approve_leave, name='approve_leave'),
    path('reject-leave/<int:leave_id>/', views.reject_leave, name='reject_leave'),
]
