# Generated by Django 5.0.1 on 2025-03-06 09:26

from django.db import migrations

def migrate_departments(apps, schema_editor):
    Employee = apps.get_model('leave_management', 'Employee')
    CompensatoryLeave = apps.get_model('leave_management', 'CompensatoryLeave')
    
    # Department mapping
    department_mapping = {
        'AI': 'CSE',
        'NON_TEACHING': 'CSE',
        'MATH': 'CSE',
        'ENGLISH': 'CSE'
    }
    
    # Update Employee departments
    for old_dept, new_dept in department_mapping.items():
        Employee.objects.filter(department=old_dept).update(department=new_dept)
        CompensatoryLeave.objects.filter(department=old_dept).update(department=new_dept)

def reverse_migrate(apps, schema_editor):
    # No reverse migration needed as we can't determine original departments
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('leave_management', '0005_compensatoryleave'),
    ]

    operations = [
        migrations.RunPython(migrate_departments, reverse_migrate),
    ]
