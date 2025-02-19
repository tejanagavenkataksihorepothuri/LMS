import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lms_project.settings')
django.setup()

from leave_management.models import Employee

# Create admin user if it doesn't exist
if not Employee.objects.filter(username='admin').exists():
    admin = Employee.objects.create_superuser(
        username='admin',
        password='URCE',
        employee_id='admin',
        department='CSE',
        is_admin=True,
        first_name='Admin',
        last_name='User'
    )
    print("Admin user created successfully!")
