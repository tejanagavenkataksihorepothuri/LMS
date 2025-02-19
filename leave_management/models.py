from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator
from django.utils import timezone
from datetime import datetime, date

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

class Employee(AbstractUser):
    DEPARTMENT_CHOICES = [
        ('CSE', 'Computer Science'),
        ('ECE', 'Electronics'),
        ('MECH', 'Mechanical'),
        ('CIVIL', 'Civil'),
        
    ]
    
    employee_id = models.CharField(max_length=20, unique=True, validators=[MinLengthValidator(1)])
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES)
    is_admin = models.BooleanField(default=False)
    casual_leaves_remaining = models.IntegerField(default=1)  # Start with 1 leave
    extra_leaves_taken = models.IntegerField(default=0)
    summer_leaves_remaining = models.IntegerField(default=5)  # Summer leaves for May
    last_leave_increment = models.DateField(default=timezone.now)  # Track last leave increment
    
    def save(self, *args, **kwargs):
        if self.employee_id:
            self.employee_id = self.employee_id.upper()
        
        # If this is a new employee (no pk means it's not saved to db yet)
        if not self.pk:
            # Set initial casual leave to 1 for current month
            self.casual_leaves_remaining = 1
            # Set last_leave_increment to first day of current month
            today = timezone.now().date()
            self.last_leave_increment = today.replace(day=1)
            
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.employee_id} - {self.get_full_name()}"
    
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

class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    number_of_days = models.IntegerField()
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee.employee_id} - {self.start_date} to {self.end_date}"

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

class LoginAttempt(models.Model):
    employee_id = models.CharField(max_length=10)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    login_type = models.CharField(max_length=20)
    status = models.CharField(max_length=20)
    message = models.CharField(max_length=255)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.employee_id} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {self.status}"
