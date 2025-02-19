from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator

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
    casual_leaves_remaining = models.IntegerField(default=11)  # Annual casual leaves
    extra_leaves_taken = models.IntegerField(default=0)
    summer_leaves_remaining = models.IntegerField(default=5)  # Summer holidays
    
    def save(self, *args, **kwargs):
        # Convert employee_id to uppercase before saving
        if self.employee_id:
            self.employee_id = self.employee_id.upper()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.employee_id} - {self.get_full_name()}"

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
