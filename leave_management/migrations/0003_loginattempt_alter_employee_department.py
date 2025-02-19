# Generated by Django 5.0.1 on 2025-02-19 06:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leave_management', '0002_alter_employee_department'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoginAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=100)),
                ('attempted_at', models.DateTimeField(auto_now_add=True)),
                ('ip_address', models.CharField(blank=True, max_length=45, null=True)),
                ('role', models.CharField(max_length=20)),
            ],
            options={
                'ordering': ['-attempted_at'],
            },
        ),
        migrations.AlterField(
            model_name='employee',
            name='department',
            field=models.CharField(choices=[('CSE', 'Computer Science'), ('ECE', 'Electronics'), ('MECH', 'Mechanical'), ('CIVIL', 'Civil'), ('AI', 'Artificial Intelligence'), ('NON_TEACHING', 'Non Teaching'), ('MATH', 'Mathematics'), ('ENGLISH', 'English')], max_length=20),
        ),
    ]
