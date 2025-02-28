from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta, time
import random
from leave_management.models import Employee, Attendance, LeaveRequest, Holiday

class Command(BaseCommand):
    help = 'Generate dummy attendance data for all employees from May 2024'

    def handle(self, *args, **kwargs):
        # Get all employees
        employees = Employee.objects.all()
        
        # Set start date to May 1, 2024
        start_date = datetime(2024, 5, 1).date()
        # Get current date
        today = timezone.now().date()
        
        # Get all holidays
        holidays = Holiday.objects.filter(
            date__range=[start_date, today]
        ).values_list('date', flat=True)
        holidays = set(holidays)
        
        for employee in employees:
            self.stdout.write(f'Generating attendance for employee: {employee.employee_id}')
            
            # Get approved leaves for this employee
            approved_leaves = LeaveRequest.objects.filter(
                employee=employee,
                status='APPROVED',
                start_date__gte=start_date,
                end_date__lte=today
            )
            
            # Create a set of leave dates
            leave_dates = set()
            for leave in approved_leaves:
                current_date = leave.start_date
                while current_date <= leave.end_date:
                    leave_dates.add(current_date)
                    current_date += timedelta(days=1)
            
            # Generate attendance for each day
            current_date = start_date
            while current_date <= today:
                # Skip weekends and holidays
                if current_date.weekday() in [5, 6] or current_date in holidays:  # 5 is Saturday, 6 is Sunday
                    current_date += timedelta(days=1)
                    continue
                
                # Skip if it's a leave day
                if current_date in leave_dates:
                    # Create attendance record with no check-in/out times for leave days
                    Attendance.objects.get_or_create(
                        employee=employee,
                        date=current_date,
                        defaults={
                            'check_in_time': None,
                            'check_out_time': None
                        }
                    )
                    current_date += timedelta(days=1)
                    continue
                
                # Generate random attendance patterns
                attendance_type = random.choices(
                    ['regular', 'late', 'early_leave', 'absent'],
                    weights=[85, 5, 5, 5]
                )[0]
                
                if attendance_type == 'absent':
                    # Create attendance record with no check-in/out times
                    Attendance.objects.get_or_create(
                        employee=employee,
                        date=current_date,
                        defaults={
                            'check_in_time': None,
                            'check_out_time': None
                        }
                    )
                else:
                    # Base check-in and check-out times
                    if attendance_type == 'regular':
                        check_in_hour = random.randint(8, 9)
                        check_in_minute = random.randint(0, 30)
                        check_out_hour = random.randint(16, 17)
                        check_out_minute = random.randint(30, 59)
                    elif attendance_type == 'late':
                        check_in_hour = random.randint(9, 10)
                        check_in_minute = random.randint(31, 59)
                        check_out_hour = random.randint(16, 17)
                        check_out_minute = random.randint(30, 59)
                    else:  # early_leave
                        check_in_hour = random.randint(8, 9)
                        check_in_minute = random.randint(0, 30)
                        check_out_hour = random.randint(15, 16)
                        check_out_minute = random.randint(0, 29)
                    
                    check_in = time(check_in_hour, check_in_minute)
                    check_out = time(check_out_hour, check_out_minute)
                    
                    # Create attendance record
                    Attendance.objects.get_or_create(
                        employee=employee,
                        date=current_date,
                        defaults={
                            'check_in_time': check_in,
                            'check_out_time': check_out
                        }
                    )
                
                current_date += timedelta(days=1)
            
        self.stdout.write(self.style.SUCCESS('Successfully generated attendance data'))
