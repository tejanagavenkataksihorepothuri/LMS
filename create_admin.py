import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lms_project.settings')
django.setup()

from leave_management.models import Employee

# Create admin user if it doesn't exist
if not Employee.objects.filter(username='admin').exists():
    admin = Employee.objects.create_superuser(
        employee_id='admin',
        password='URCE',
        department='CSE',
        is_admin=True,
        first_name='Admin',
        last_name='User'
    )
    print("Admin user created successfully!")
