from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from datetime import date
import json
from .models import Employee, LeaveRequest, LeaveHistory, LoginAttempt
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django import forms
from django.db.models import Q
import csv
from io import TextIOWrapper
from django.http import HttpResponse

def is_admin(user):
    return user.is_admin

class EmployeeForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput())
    
    class Meta:
        model = Employee
        fields = ['first_name', 'last_name', 'employee_id', 'department', 'password']

class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

class CustomLoginView(LoginView):
    template_name = 'leave_management/login.html'
    
    def form_valid(self, form):
        username = form.cleaned_data.get('username', '').upper()
        password = form.cleaned_data.get('password')
        role = self.request.POST.get('role')
        
        if not role:
            messages.error(self.request, 'Please select a role')
            return self.form_invalid(form)
            
        # Convert username to lowercase for case-insensitive comparison
        user = Employee.objects.filter(employee_id__iexact=username).first()
        
        if user and user.check_password(password):
            # Validate role selection
            if (role == 'employer' and not user.is_admin) or (role == 'employee' and user.is_admin):
                self._record_failed_attempt(username, role)
                messages.error(self.request, 'Invalid credentials or incorrect role selected')
                return self.form_invalid(form)
            
            # Set the user for authentication
            form.cleaned_data['username'] = user.username
            return super().form_valid(form)
        else:
            self._record_failed_attempt(username, role)
            messages.error(self.request, 'Invalid credentials or incorrect role selected')
            return self.form_invalid(form)

    def _record_failed_attempt(self, username, role):
        LoginAttempt.objects.create(
            username=username,
            role=role,
            ip_address=self.request.META.get('REMOTE_ADDR', '')
        )
    
    def get_success_url(self):
        if self.request.user.is_admin:
            return reverse_lazy('admin_home')
        return reverse_lazy('home')

class ChangePasswordView(LoginRequiredMixin, PasswordChangeView):
    template_name = 'leave_management/change_password.html'
    success_url = reverse_lazy('home')

@login_required
def home(request):
    if request.user.is_admin:
        return redirect('admin_home')
    return render(request, 'leave_management/home.html')

@login_required
def apply_leave(request):
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave_request = form.save(commit=False)
            leave_request.employee = request.user
            
            # Update employee's leave balance
            request.user.update_leaves()
            
            # Validate dates
            today = timezone.now().date()
            if leave_request.start_date <= today:
                messages.error(request, 'Cannot apply leave for today or previous days')
                return render(request, 'leave_management/apply_leave.html', {'form': form})
            
            # Check if dates overlap with existing leave requests
            existing_leaves = LeaveRequest.objects.filter(
                employee=request.user,
                status__in=['PENDING', 'APPROVED'],
                start_date__lte=leave_request.end_date,
                end_date__gte=leave_request.start_date
            )
            if existing_leaves.exists():
                messages.error(request, 'You already have a leave request for these dates')
                return render(request, 'leave_management/apply_leave.html', {'form': form})
            
            # Calculate number of days
            leave_request.number_of_days = (leave_request.end_date - leave_request.start_date).days + 1
            
            # Check if it's a May leave (summer vacation)
            if leave_request.start_date.month == 5:
                if leave_request.number_of_days > request.user.summer_leaves_remaining:
                    messages.error(request, f'You only have {request.user.summer_leaves_remaining} summer leaves remaining')
                    return render(request, 'leave_management/apply_leave.html', {'form': form})
            else:
                # Regular month leave logic
                if leave_request.number_of_days > request.user.casual_leaves_remaining:
                    extra_days_needed = leave_request.number_of_days - request.user.casual_leaves_remaining
                    leave_request.is_extra_leave = True
                
            leave_request.save()
            messages.success(request, 'Leave request submitted successfully!')
            return redirect('leave_history')
    else:
        form = LeaveRequestForm()
        
        # Get today's date
        today = timezone.now().date()
        
        # Disable dates that have pending or approved leaves
        existing_leaves = LeaveRequest.objects.filter(
            employee=request.user,
            status__in=['PENDING', 'APPROVED']
        ).values_list('start_date', 'end_date')
        
        disabled_dates = []
        for start_date, end_date in existing_leaves:
            current_date = start_date
            while current_date <= end_date:
                disabled_dates.append(current_date.strftime('%Y-%m-%d'))
                current_date += timezone.timedelta(days=1)
                
        return render(request, 'leave_management/apply_leave.html', {
            'form': form,
            'disabled_dates': json.dumps(disabled_dates),
            'today': today,
        })

@login_required
def leave_history(request):
    leaves = LeaveRequest.objects.filter(employee=request.user).order_by('-created_at')
    monthly_history = LeaveHistory.objects.filter(employee=request.user).order_by('-year', '-month')
    return render(request, 'leave_management/leave_history.html', {
        'leaves': leaves,
        'monthly_history': monthly_history
    })

@login_required
@user_passes_test(is_admin)
def admin_home(request):
    return render(request, 'leave_management/admin_home.html')

@login_required
@user_passes_test(is_admin)
def leave_applications(request):
    pending_leaves = LeaveRequest.objects.filter(status='PENDING').order_by('-created_at')
    return render(request, 'leave_management/leave_applications.html', {'leaves': pending_leaves})

@login_required
@user_passes_test(is_admin)
def employee_leave_history(request):
    # Get search query and department filter
    search_query = request.GET.get('search', '').lower()
    selected_department = request.GET.get('department', '')
    
    # Start with all non-admin employees
    employees = Employee.objects.filter(is_admin=False)
    
    # Apply search filter if provided
    if search_query:
        employees = employees.filter(employee_id__icontains=search_query)
    
    # Apply department filter if provided
    if selected_department:
        employees = employees.filter(department=selected_department)
    
    # Prepare employee data
    employee_list = []
    current_date = timezone.now().date()
    
    for emp in employees:
        # Get all leave requests for the employee
        leave_requests = LeaveRequest.objects.filter(employee=emp)
        
        # Calculate leave counts for current year
        approved_leaves = leave_requests.filter(
            status='APPROVED',
            start_date__year=current_date.year
        )
        
        # Count casual leaves (excluding May)
        casual_leaves_used = approved_leaves.exclude(
            start_date__month=5
        ).count()
        
        # Count summer leaves (only May)
        summer_leaves = approved_leaves.filter(
            start_date__month=5
        ).count()
        
        # Count extra leaves (after casual leaves are exhausted)
        extra_leaves = max(0, casual_leaves_used - emp.casual_leaves_remaining)
        
        # Get current month's leaves
        monthly_leaves = approved_leaves.filter(
            start_date__month=current_date.month
        ).count()
        
        # Calculate monthly casual vs extra leaves
        monthly_casual = min(monthly_leaves, emp.casual_leaves_remaining)
        monthly_extra = max(0, monthly_leaves - monthly_casual)
        
        employee_list.append({
            'employee_id': emp.employee_id,
            'name': emp.get_full_name(),
            'department': emp.get_department_display(),
            'casual_leaves_used': casual_leaves_used,
            'casual_leaves_available': emp.casual_leaves_remaining,
            'extra_leaves_total': extra_leaves,
            'monthly_extra_leaves': monthly_extra,
            'monthly_casual_leaves': monthly_casual,
            'summer_leaves': summer_leaves,
            'summer_leaves_remaining': emp.summer_leaves_remaining
        })
    
    context = {
        'employees': employee_list,
        'departments': dict(Employee.DEPARTMENT_CHOICES),
        'selected_department': selected_department,
        'search_query': search_query
    }
    
    return render(request, 'leave_management/employee_leave_history.html', context)

@login_required
@user_passes_test(is_admin)
def employee_leave_detail(request, employee_id):
    employee = get_object_or_404(Employee, employee_id=employee_id)
    
    # Get all leave requests
    leave_requests = LeaveRequest.objects.filter(employee=employee).order_by('-created_at')
    
    leave_history = []
    for leave in leave_requests:
        leave_type = 'Summer' if leave.start_date.month == 5 else 'Regular'
        leave_history.append({
            'start_date': leave.start_date.strftime('%Y-%m-%d'),
            'end_date': leave.end_date.strftime('%Y-%m-%d'),
            'number_of_days': (leave.end_date - leave.start_date).days + 1,
            'type': leave_type,
            'reason': leave.reason,
            'status': leave.status,
            'applied_date': leave.created_at.strftime('%Y-%m-%d %H:%M'),
            'approved_date': leave.updated_at.strftime('%Y-%m-%d %H:%M') if leave.status != 'PENDING' else '-'
        })
    
    context = {
        'employee': employee,
        'leave_history': leave_history,
        'casual_leaves_remaining': employee.casual_leaves_remaining,
        'summer_leaves_remaining': employee.summer_leaves_remaining,
        'extra_leaves_taken': max(0, employee.extra_leaves_taken)
    }
    
    return render(request, 'leave_management/employee_details.html', context)

@login_required
@user_passes_test(is_admin)
def employee_list(request):
    employees = Employee.objects.all()
    return render(request, 'leave_management/employee_list.html', {'employees': employees})

@login_required
@user_passes_test(is_admin)
def register_employee(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.username = form.cleaned_data['employee_id']
            employee.set_password(form.cleaned_data['password'])
            employee.save()
            messages.success(request, 'Employee registered successfully!')
            return redirect('admin_home')
    else:
        form = EmployeeForm()
    return render(request, 'leave_management/register_employee.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def delete_employee(request):
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id', '').upper()
        admin_password = request.POST.get('password')
        
        if request.user.check_password(admin_password):
            try:
                employee = Employee.objects.get(employee_id__iexact=employee_id)
                if not employee.is_admin:
                    employee.delete()
                    messages.success(request, 'Employee deleted successfully!')
                else:
                    messages.error(request, 'Cannot delete admin user!')
            except Employee.DoesNotExist:
                messages.error(request, 'Employee not found!')
        else:
            messages.error(request, 'Invalid admin password!')
            
    return render(request, 'leave_management/delete_employee.html')

@login_required
@user_passes_test(is_admin)
def approve_leave(request, leave_id):
    leave_request = get_object_or_404(LeaveRequest, id=leave_id)
    if leave_request.status == 'PENDING':
        leave_request.status = 'APPROVED'
        leave_request.save()
        
        # Update leave history
        month = leave_request.start_date.month
        year = leave_request.start_date.year
        history, created = LeaveHistory.objects.get_or_create(
            employee=leave_request.employee,
            month=month,
            year=year
        )
        
        # Calculate and update leaves
        employee = leave_request.employee
        
        # Update employee's leave balance
        employee.update_leaves()
        
        if month == 5:  # May - Summer leave
            history.summer_leaves_taken += leave_request.number_of_days
            employee.summer_leaves_remaining = max(0, employee.summer_leaves_remaining - leave_request.number_of_days)
        else:
            if employee.casual_leaves_remaining >= leave_request.number_of_days:
                history.casual_leaves_taken += leave_request.number_of_days
                employee.casual_leaves_remaining -= leave_request.number_of_days
            else:
                # If casual leaves are not enough, use them all and mark the rest as extra
                if employee.casual_leaves_remaining > 0:
                    history.casual_leaves_taken += employee.casual_leaves_remaining
                    extra_leaves = leave_request.number_of_days - employee.casual_leaves_remaining
                    history.extra_leaves_taken += extra_leaves
                    employee.extra_leaves_taken += extra_leaves
                    employee.casual_leaves_remaining = 0
                else:
                    # If no casual leaves remaining, all are extra
                    history.extra_leaves_taken += leave_request.number_of_days
                    employee.extra_leaves_taken += leave_request.number_of_days
        
        employee.save()
        history.save()
        
    return redirect('leave_applications')

@login_required
@user_passes_test(is_admin)
def reject_leave(request, leave_id):
    leave_request = get_object_or_404(LeaveRequest, id=leave_id)
    if leave_request.status == 'PENDING':
        leave_request.status = 'REJECTED'
        leave_request.save()
    return redirect('leave_applications')

@login_required
@user_passes_test(is_admin)
def notifications(request):
    return render(request, 'leave_management/notifications.html')

@login_required
@user_passes_test(is_admin)
def get_login_attempts(request):
    attempts = LoginAttempt.objects.all()
    data = [{
        'id': attempt.id,
        'username': attempt.username,
        'attempted_at': attempt.attempted_at.strftime('%Y-%m-%d %H:%M:%S'),
        'ip_address': attempt.ip_address,
        'role': attempt.role
    } for attempt in attempts]
    return JsonResponse({'data': data})

@login_required
@user_passes_test(is_admin)
@require_POST
def delete_login_attempt(request, attempt_id):
    attempt = get_object_or_404(LoginAttempt, id=attempt_id)
    attempt.delete()
    return JsonResponse({'status': 'success'})

@login_required
@user_passes_test(is_admin)
def employee_leave_report(request):
    search_id = request.GET.get('employee_id', '').upper()
    current_year = timezone.now().year
    context = {'search_id': search_id}
    
    if search_id:
        try:
            employee = Employee.objects.get(employee_id__iexact=search_id)
            leave_requests = LeaveRequest.objects.filter(
                employee=employee,
                start_date__year=current_year,
                status='APPROVED'
            )
            
            # Initialize monthly report
            monthly_report = []
            months = {
                1: 'January', 2: 'February', 3: 'March', 4: 'April',
                5: 'May', 6: 'June', 7: 'July', 8: 'August',
                9: 'September', 10: 'October', 11: 'November', 12: 'December'
            }
            
            # Initialize yearly totals
            yearly_totals = {
                'casual_leaves': 0,
                'extra_leaves': 0,
                'summer_leaves': 0,
                'total_days': 0
            }
            
            # Get leave history records for the year
            leave_histories = LeaveHistory.objects.filter(
                employee=employee,
                year=current_year
            )
            
            # Calculate monthly totals from leave history
            for month_num in range(1, 13):
                month_history = leave_histories.filter(month=month_num).first()
                
                if month_history:
                    casual_leaves = month_history.casual_leaves_taken
                    extra_leaves = month_history.extra_leaves_taken
                    summer_leaves = month_history.summer_leaves_taken
                else:
                    casual_leaves = 0
                    extra_leaves = 0
                    summer_leaves = 0
                
                total_days = casual_leaves + extra_leaves + summer_leaves
                
                monthly_report.append({
                    'month_name': months[month_num],
                    'casual_leaves': casual_leaves,
                    'extra_leaves': extra_leaves,
                    'summer_leaves': summer_leaves,
                    'total_days': total_days
                })
                
                # Update yearly totals
                yearly_totals['casual_leaves'] += casual_leaves
                yearly_totals['extra_leaves'] += extra_leaves
                yearly_totals['summer_leaves'] += summer_leaves
                yearly_totals['total_days'] += total_days
            
            # Prepare leave history
            leave_history = []
            for leave in leave_requests:
                leave_type = 'Summer' if leave.start_date.month == 5 else 'Regular'
                leave_history.append({
                    'start_date': leave.start_date.strftime('%Y-%m-%d'),
                    'end_date': leave.end_date.strftime('%Y-%m-%d'),
                    'number_of_days': (leave.end_date - leave.start_date).days + 1,
                    'type': leave_type,
                    'reason': leave.reason,
                    'status': leave.status,
                    'applied_date': leave.created_at.strftime('%Y-%m-%d %H:%M')
                })
            
            context.update({
                'employee': employee,
                'monthly_report': monthly_report,
                'yearly_totals': yearly_totals,
                'leave_history': leave_history,
                'casual_leaves_remaining': employee.casual_leaves_remaining,
                'summer_leaves_remaining': employee.summer_leaves_remaining,
                'total_extra_leaves': yearly_totals['extra_leaves'],
                'current_year': current_year
            })
        except Employee.DoesNotExist:
            messages.error(request, f'No employee found with ID: {search_id}')
    
    return render(request, 'leave_management/employee_leave_report.html', context)

@login_required
@user_passes_test(is_admin)
def bulk_register(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = TextIOWrapper(request.FILES['csv_file'].file, encoding='utf-8')
        reader = csv.DictReader(csv_file)
        preview_data = []
        
        for row in reader:
            try:
                # Validate department
                if row['department'] not in dict(Employee.DEPARTMENT_CHOICES):
                    raise ValueError(f"Invalid department: {row['department']}")
                
                # Check if employee_id already exists
                if Employee.objects.filter(employee_id__iexact=row['employee_id']).exists():
                    raise ValueError(f"Employee ID already exists: {row['employee_id']}")
                
                # Create the employee
                employee = Employee.objects.create(
                    username=row['employee_id'].upper(),
                    employee_id=row['employee_id'].upper(),
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    department=row['department'],
                    is_admin=False
                )
                employee.set_password(row['password'])
                employee.save()
                
                preview_data.append({
                    'employee_id': employee.employee_id,
                    'first_name': employee.first_name,
                    'last_name': employee.last_name,
                    'department': employee.get_department_display(),
                    'status': 'success'
                })
                
                messages.success(request, f'Successfully registered {len(preview_data)} employees.')
                
            except Exception as e:
                preview_data.append({
                    'employee_id': row.get('employee_id', 'N/A'),
                    'first_name': row.get('first_name', 'N/A'),
                    'last_name': row.get('last_name', 'N/A'),
                    'department': row.get('department', 'N/A'),
                    'status': 'error',
                    'error': str(e)
                })
                messages.error(request, f'Error registering some employees. Please check the preview below.')
        
        return render(request, 'leave_management/bulk_register.html', {'preview_data': preview_data})
    
    return render(request, 'leave_management/bulk_register.html')

@login_required
@user_passes_test(is_admin)
def download_csv_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="employee_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['employee_id', 'first_name', 'last_name', 'department', 'password'])
    
    # Add a sample row
    writer.writerow(['UR01', 'John', 'Doe', 'CSE', 'welcome123'])
    
    return response

@login_required
@user_passes_test(is_admin)
def todays_leave(request):
    today = timezone.now().date()
    todays_leaves = LeaveRequest.objects.filter(start_date__lte=today, end_date__gte=today, status='APPROVED')
    return render(request, 'leave_management/todays_leave.html', {'todays_leaves': todays_leaves})

@login_required
@user_passes_test(is_admin)
def employees_on_date(request):
    if request.method == 'POST':
        selected_date = request.POST.get('date')
        leaves_on_date = LeaveRequest.objects.filter(start_date__lte=selected_date, end_date__gte=selected_date, status='APPROVED')
        return render(request, 'leave_management/employees_on_date.html', {'leaves_on_date': leaves_on_date, 'selected_date': selected_date})
    return render(request, 'leave_management/employees_on_date.html')
