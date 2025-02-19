from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Authentication URLs
    path('login/', views.CustomLoginView.as_view(), name='login'),
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
    path('register-employee/', views.register_employee, name='register_employee'),
    path('delete-employee/', views.delete_employee, name='delete_employee'),
    
    # API endpoints
    path('approve-leave/<int:leave_id>/', views.approve_leave, name='approve_leave'),
    path('reject-leave/<int:leave_id>/', views.reject_leave, name='reject_leave'),
]
