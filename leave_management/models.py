from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.validators import MinLengthValidator
from django.utils import timezone
from datetime import datetime, date
from django.core.exceptions import ValidationError

# Create your models here.

DEPARTMENT_CHOICES = [
    ('CSE', 'Computer Science'),
    ('ECE', 'Electronics and Communication'),
    ('EEE', 'Electrical and Electronics'),
    ('MECH', 'Mechanical'),
    ('CIVIL', 'Civil'),
    ('AI', 'Artificial Intelligence'),
    ('NON_TEACHING', 'Non Teaching'),
    ('MATH', 'Mathematics'),
    ('ENGLISH', 'English'),
]

class EmployeeManager(UserManager):
    def create_superuser(self, employee_id, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_admin', True)
        extra_fields.setdefault('department', 'CSE')  # Default department
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
            
        return self._create_user(employee_id, password, **extra_fields)
    
    def _create_user(self, employee_id, password, **extra_fields):
        if not employee_id:
            raise ValueError('The Employee ID must be set')
        
        user = self.model(
            username=employee_id.upper(),
            employee_id=employee_id,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

class Employee(AbstractUser):
    DEPARTMENT_CHOICES = [
        ('CSE', 'Computer Science'),
        ('ECE', 'Electronics'),
        ('MECH', 'Mechanical'),
        ('CIVIL', 'Civil'),
        ('AI', 'Artificial Intelligence'),
        ('NON_TEACHING', 'Non Teaching'),
        ('MATH', 'Mathematics'),
        ('ENGLISH', 'English'),
    ]
    
    username = models.CharField(max_length=150, null=True, blank=True)
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES, default='CSE')
    is_admin = models.BooleanField(default=False)
    casual_leaves_remaining = models.IntegerField(default=1)
    extra_leaves_taken = models.IntegerField(default=0)
    summer_leaves_remaining = models.IntegerField(default=5)
    last_leave_increment = models.DateField(default=timezone.now)
    phone_number = models.CharField(max_length=15, blank=True, null=True)

    objects = EmployeeManager()

    USERNAME_FIELD = 'employee_id'
    REQUIRED_FIELDS = ['department']

    class Meta:
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'
        constraints = [
            models.UniqueConstraint(
                fields=['employee_id'],
                name='unique_employee_id_case_insensitive',
                condition=models.Q(employee_id__isnull=False)
            )
        ]

    def clean(self):
        if self.employee_id:
            # Check for case-insensitive uniqueness
            if Employee.objects.filter(employee_id__iexact=self.employee_id).exclude(pk=self.pk).exists():
                raise ValidationError({'employee_id': 'Employee ID already exists (case-insensitive)'})
            self.employee_id = self.employee_id.strip()
        super().clean()

    def save(self, *args, **kwargs):
        if self.employee_id:
            # Store username in uppercase for consistency
            self.username = self.employee_id.upper()
            # Keep employee_id in original case
            self.employee_id = self.employee_id.strip()
            # Run validation before saving
            self.full_clean()
        super().save(*args, **kwargs)

    def get_username(self):
        """Override get_username to return employee_id in original case"""
        return self.employee_id

    def __str__(self):
        return f"{self.employee_id} - {self.get_full_name() or self.employee_id}"

    def get_academic_year(self):
        today = timezone.now().date()
        if today.month < 6:  # Before June
            return today.year - 1
        return today.year
    
    def update_leaves(self):
        today = timezone.now().date()
        current_academic_year = self.get_academic_year()
        
        # Reset leaves if we're in a new academic year
        if self.last_leave_increment.year < current_academic_year:
            self.casual_leaves_remaining = 1  # Start with 1 in June
            self.extra_leaves_taken = 0
            self.summer_leaves_remaining = 5
            self.last_leave_increment = date(current_academic_year, 6, 1)
        else:
            # Don't increment leaves for May (summer vacation month)
            if today.month != 5:
                # Calculate months since last increment
                months_diff = (today.year - self.last_leave_increment.year) * 12 + today.month - self.last_leave_increment.month
                if months_diff > 0:
                    # For new employees starting mid-academic year, 
                    # ensure they only get leaves from their start month
                    if self.date_joined.date() > date(current_academic_year, 6, 1):
                        start_month = self.date_joined.date().replace(day=1)
                        months_since_joining = (today.year - start_month.year) * 12 + today.month - start_month.month
                        months_diff = min(months_diff, months_since_joining)
                    
                    self.casual_leaves_remaining += months_diff
                    self.last_leave_increment = today.replace(day=1)
        
        self.save()

class Holiday(models.Model):
    name = models.CharField(max_length=100)
    date = models.DateField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        unique_together = ['date', 'name']

    def __str__(self):
        return f"{self.name} - {self.date}"

    @staticmethod
    def is_holiday(date):
        """Check if a given date is a holiday"""
        # Check if it's Sunday
        if date.weekday() == 6:  # Sunday is 6 in Python's weekday
            return True
        # Check if it's a registered holiday
        return Holiday.objects.filter(date=date).exists()

class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    LEAVE_TYPES = [
        ('CASUAL', 'Casual Leave'),
        ('SUMMER', 'Summer Leave'),
        ('EXTRA', 'Extra Leave'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    leave_type = models.CharField(max_length=10, choices=LEAVE_TYPES, default='CASUAL')
    number_of_days = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.employee.employee_id} - {self.start_date} to {self.end_date}"

    def calculate_working_days(self):
        """Calculate the number of working days excluding holidays and Sundays"""
        working_days = 0
        current_date = self.start_date
        while current_date <= self.end_date:
            if not Holiday.is_holiday(current_date):
                working_days += 1
            current_date += timezone.timedelta(days=1)
        return working_days

    def save(self, *args, **kwargs):
        # Calculate working days before saving
        self.number_of_days = self.calculate_working_days()
        super().save(*args, **kwargs)

class LeaveHistory(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    month = models.IntegerField()
    year = models.IntegerField()
    casual_leaves_taken = models.IntegerField(default=0)
    extra_leaves_taken = models.IntegerField(default=0)
    summer_leaves_taken = models.IntegerField(default=0)

    class Meta:
        unique_together = ('employee', 'month', 'year')

    def __str__(self):
        return f"{self.employee.employee_id} - {self.month}/{self.year}"

class Attendance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField()
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-check_in_time']
        unique_together = ['employee', 'date']

    def __str__(self):
        return f"{self.employee.employee_id} - {self.date}"

    def get_duration(self):
        if self.check_in_time and self.check_out_time:
            check_in = datetime.combine(self.date, self.check_in_time)
            check_out = datetime.combine(self.date, self.check_out_time)
            duration = check_out - check_in
            hours = duration.total_seconds() / 3600
            return round(hours, 2)
        return None

class LoginAttempt(models.Model):
    username = models.CharField(max_length=100)
    attempted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.CharField(max_length=45, blank=True, null=True)
    role = models.CharField(max_length=20)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-attempted_at']

    def __str__(self):
        return f"{self.username} - {self.attempted_at}"
