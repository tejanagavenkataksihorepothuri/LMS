# Generated by Django 5.0.1 on 2025-03-06 08:08

import django.db.models.deletion
import django.utils.timezone
import leave_management.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
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
                ('is_read', models.BooleanField(default=False)),
            ],
            options={
                'ordering': ['-attempted_at'],
            },
        ),
        migrations.CreateModel(
            name='Employee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('first_name', models.CharField(blank=True, max_length=150, verbose_name='first name')),
                ('last_name', models.CharField(blank=True, max_length=150, verbose_name='last name')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='email address')),
                ('is_staff', models.BooleanField(default=False, help_text='Designates whether the user can log into this admin site.', verbose_name='staff status')),
                ('is_active', models.BooleanField(default=True, help_text='Designates whether this user should be treated as active. Unselect this instead of deleting accounts.', verbose_name='active')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('username', models.CharField(blank=True, max_length=150, null=True)),
                ('employee_id', models.CharField(max_length=20, unique=True)),
                ('department', models.CharField(choices=[('CSE', 'Computer Science'), ('ECE', 'Electronics'), ('MECH', 'Mechanical'), ('CIVIL', 'Civil'), ('AI', 'Artificial Intelligence'), ('NON_TEACHING', 'Non Teaching'), ('MATH', 'Mathematics'), ('ENGLISH', 'English')], default='CSE', max_length=20)),
                ('is_admin', models.BooleanField(default=False)),
                ('date_of_joining', models.DateField(default=django.utils.timezone.now)),
                ('experience', models.DurationField(blank=True, null=True)),
                ('casual_leaves_remaining', models.IntegerField(default=1)),
                ('extra_leaves_taken', models.IntegerField(default=0)),
                ('summer_leaves_remaining', models.IntegerField(default=5)),
                ('last_leave_increment', models.DateField(default=django.utils.timezone.now)),
                ('phone_number', models.CharField(blank=True, max_length=15, null=True)),
                ('groups', models.ManyToManyField(blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.', related_name='user_set', related_query_name='user', to='auth.group', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(blank=True, help_text='Specific permissions for this user.', related_name='user_set', related_query_name='user', to='auth.permission', verbose_name='user permissions')),
            ],
            options={
                'verbose_name': 'Employee',
                'verbose_name_plural': 'Employees',
            },
            managers=[
                ('objects', leave_management.models.EmployeeManager()),
            ],
        ),
        migrations.CreateModel(
            name='Attendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('check_in_time', models.TimeField(blank=True, null=True)),
                ('check_out_time', models.TimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-date', '-check_in_time'],
            },
        ),
        migrations.CreateModel(
            name='Holiday',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('date', models.DateField()),
                ('description', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-date'],
                'unique_together': {('date', 'name')},
            },
        ),
        migrations.CreateModel(
            name='LeaveHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month', models.IntegerField()),
                ('year', models.IntegerField()),
                ('casual_leaves_taken', models.IntegerField(default=0)),
                ('extra_leaves_taken', models.IntegerField(default=0)),
                ('summer_leaves_taken', models.IntegerField(default=0)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='LeaveRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('reason', models.TextField()),
                ('status', models.CharField(choices=[('PENDING', 'Pending'), ('APPROVED', 'Approved'), ('REJECTED', 'Rejected')], default='PENDING', max_length=10)),
                ('leave_type', models.CharField(choices=[('CASUAL', 'Casual Leave'), ('SUMMER', 'Summer Leave'), ('EXTRA', 'Extra Leave')], default='CASUAL', max_length=10)),
                ('number_of_days', models.IntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name='employee',
            constraint=models.UniqueConstraint(condition=models.Q(('employee_id__isnull', False)), fields=('employee_id',), name='unique_employee_id_case_insensitive'),
        ),
        migrations.AlterUniqueTogether(
            name='attendance',
            unique_together={('employee', 'date')},
        ),
        migrations.AlterUniqueTogether(
            name='leavehistory',
            unique_together={('employee', 'month', 'year')},
        ),
    ]
