# Generated by Django 5.0.1 on 2025-03-06 09:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leave_management', '0007_alter_employee_department'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaverequest',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
