from django.db import migrations
import random

def populate_random_salaries(apps, schema_editor):
    Employee = apps.get_model('leave_management', 'Employee')
    for employee in Employee.objects.all():
        employee.current_salary = round(random.uniform(25000.0, 99999.99), 2)
        employee.save()

def reverse_populate_salaries(apps, schema_editor):
    Employee = apps.get_model('leave_management', 'Employee')
    Employee.objects.all().update(current_salary=0.0)

class Migration(migrations.Migration):
    dependencies = [
        ('leave_management', '0010_employee_current_salary'),
    ]

    operations = [
        migrations.RunPython(populate_random_salaries, reverse_populate_salaries),
    ]