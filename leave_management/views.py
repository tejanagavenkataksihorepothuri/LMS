from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from datetime import date, datetime, timedelta
import json
from .models import Employee, LeaveRequest, LeaveHistory, LoginAttempt, Holiday, Attendance, CompensatoryLeave
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django import forms
from django.db.models import Q
import csv
from io import TextIOWrapper
from django.http import HttpResponse
from .utils import export_to_excel, export_to_pdf
from openpyxl import Workbook
from django.template.loader import get_template
from io import BytesIO
from xhtml2pdf import pisa
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.db.models import Count, Avg
from django.db.models.functions import ExtractMonth
from .forms import HolidayForm

def is_admin(user):
    return user.is_admin

def admin_required(view_func):
    decorated_view = user_passes_test(is_admin)(view_func)
    return decorated_view

def is_staff(user):
    return user.is_staff

class EmployeeForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'id': 'password'
        })
    )
    phone_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter 10-digit phone number',
            'pattern': '[0-9]{10}',
            'title': 'Phone number must be exactly 10 digits',
            'onkeypress': 'return (event.charCode >= 48 && event.charCode <= 57)',
            'maxlength': '10',
            'minlength': '10',
            'type': 'number',
            'oninput': 'javascript: if (this.value.length > this.maxLength) this.value = this.value.slice(0, this.maxLength);'
        })
    )
    date_of_joining = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    current_salary = forms.FloatField(
        required=True,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter current salary',
            'min': '0',
            'step': '0.01'
        })
    )

    class Meta:
        model = Employee
        fields = ['first_name', 'last_name', 'employee_id', 'department', 'phone_number', 'date_of_joining', 'current_salary', 'password']

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Remove any non-digit characters
            phone_number = ''.join(filter(str.isdigit, str(phone_number)))
            if not phone_number.isdigit():
                raise forms.ValidationError("Phone number must contain only digits")
            if len(phone_number) != 10:
                raise forms.ValidationError("Phone number must be exactly 10 digits")
            # Additional check to ensure no letters
            if any(c.isalpha() for c in str(phone_number)):
                raise forms.ValidationError("Phone number cannot contain letters")
        return phone_number

class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ['start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

@method_decorator(ensure_csrf_cookie, name='dispatch')
class CustomLoginView(LoginView):
    template_name = 'leave_management/login.html'
    
    def form_valid(self, form):
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')
        role = self.request.POST.get('role')
        
        # Add rate limiting check with case-insensitive filter
        recent_attempts = LoginAttempt.objects.filter(
            username__iexact=username,
            attempted_at__gte=timezone.now() - timezone.timedelta(minutes=15)
        ).count()
        
        if recent_attempts >= 5:
            messages.error(
                self.request,
                'Your account has been temporarily locked due to too many failed login attempts. '
                'Please try again after 15 minutes or contact your administrator.'
            )
            return self.form_invalid(form)
        
        if not role:
            messages.error(self.request, 'Please select your role (Employee or Employer) to continue.')
            return self.form_invalid(form)
            
        # Use iexact for case-insensitive comparison but keep original case
        user = Employee.objects.filter(employee_id__iexact=username).first()
        if user is None:
            self._record_failed_attempt(username, role)
            messages.error(
                self.request,
                'Invalid Employee ID or password. Please check your credentials and try again.'
            )
            return self.form_invalid(form)
            
        if user and user.check_password(password):
            # Validate role selection
            if (role == 'employer' and not user.is_admin) or (role == 'employee' and user.is_admin):
                self._record_failed_attempt(username, role)
                messages.error(
                    self.request,
                    'Access denied. The selected role does not match your account permissions. '
                    'Please choose the correct role and try again.'
                )
                return self.form_invalid(form)
            
            # Use the original employee_id case for display
            form.cleaned_data['username'] = user.employee_id
            response = super().form_valid(form)
            
            # Add success message
            messages.success(
                self.request,
                f'Welcome back, {user.get_full_name() or user.employee_id}! You have successfully logged in.'
            )
            
            # Ensure CSRF cookie is set
            response.csrf_cookie_set = True
            return response
        else:
            self._record_failed_attempt(username, role)
            remaining_attempts = 5 - (recent_attempts + 1)
            messages.error(
                self.request,
                f'Invalid Employee ID or password. You have {remaining_attempts} {"attempt" if remaining_attempts == 1 else "attempts"} '
                'remaining before your account is temporarily locked.'
            )
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f'{error}')
        response = super().form_invalid(form)
        response.csrf_cookie_set = True
        return response
    
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

    def form_valid(self, form):
        messages.success(self.request, 'Your password was successfully updated!')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)

@login_required
def home(request):
    if request.user.is_admin:
        return redirect('admin_home')
    return render(request, 'leave_management/home.html')

def calculate_summer_leaves(employee):
    """Calculate summer leaves based on employee experience"""
    if not employee.date_of_joining:
        return 3  # Default to minimum if no joining date
        
    today = date.today()
    experience = (today - employee.date_of_joining).days / 365.0  # Experience in years
    
    if experience < 1:
        return 3
    elif experience < 2:
        return 6
    else:
        return 12

@login_required
def apply_leave(request):
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave_request = form.save(commit=False)
            
            # Add validation for end date being after start date
            if leave_request.end_date < leave_request.start_date:
                messages.error(request, 'End date cannot be before start date')
                return render(request, 'leave_management/apply_leave.html', {'form': form})
            
            leave_request.employee = request.user
            
            # Calculate working days (excluding Sundays and holidays)
            working_days = leave_request.calculate_working_days()
            
            if working_days == 0:
                messages.error(request, 'Selected dates only include holidays and/or Sundays. Please select valid working days.')
                return render(request, 'leave_management/apply_leave.html', {'form': form})
            
            # Add validation for maximum leave duration
            if working_days > 30:
                messages.error(request, 'Leave request cannot exceed 30 working days')
                return render(request, 'leave_management/apply_leave.html', {'form': form})
            
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
            
            # Set number of working days
            leave_request.number_of_days = working_days
            
            # Check if it's a May leave (summer vacation)
            if leave_request.start_date.month == 5:
                summer_leaves_allowed = calculate_summer_leaves(request.user)
                if working_days > request.user.summer_leaves_remaining:
                    messages.error(request, f'You only have {request.user.summer_leaves_remaining} summer leaves remaining (Based on {summer_leaves_allowed} total summer leaves for your experience)')
                    return render(request, 'leave_management/apply_leave.html', {'form': form})
                leave_request.leave_type = 'SUMMER'
            else:
                # Regular month leave logic
                if working_days > request.user.casual_leaves_remaining:
                    extra_days_needed = working_days - request.user.casual_leaves_remaining
                    leave_request.is_extra_leave = True
                    leave_request.leave_type = 'EXTRA'
                else:
                    leave_request.leave_type = 'CASUAL'
            
            # Explicitly set status to PENDING
            leave_request.status = 'PENDING'
            leave_request.save()
            messages.success(request, f'Leave request submitted successfully for {working_days} working days! (Excluding Sundays and holidays)')
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
    # Get all leave requests for the user
    leave_requests = LeaveRequest.objects.filter(employee=request.user).order_by('-created_at')
    
    # Get the current academic year's monthly history
    current_date = timezone.now().date()
    current_year = current_date.year
    
    # Get all leave history for current year
    monthly_history = LeaveHistory.objects.filter(
        employee=request.user,
        year=current_year
    ).order_by('month')
    
    # Create monthly report for all months
    monthly_data = []
    for month in range(1, 13):
        history = monthly_history.filter(month=month).first()
        if history:
            monthly_data.append({
                'month': datetime(2000, month, 1).strftime('%B'),  # Month name
                'year': current_year,
                'casual_leaves_taken': history.casual_leaves_taken,
                'extra_leaves_taken': history.extra_leaves_taken,
                'summer_leaves_taken': history.summer_leaves_taken
            })
        else:
            monthly_data.append({
                'month': datetime(2000, month, 1).strftime('%B'),  # Month name
                'year': current_year,
                'casual_leaves_taken': 0,
                'extra_leaves_taken': 0,
                'summer_leaves_taken': 0
            })
    
    # Pagination for leave requests
    page = request.GET.get('page', 1)
    paginator = Paginator(leave_requests, 10)  # Show 10 records per page
    
    try:
        leave_page = paginator.page(page)
    except PageNotAnInteger:
        leave_page = paginator.page(1)
    except EmptyPage:
        leave_page = paginator.page(paginator.num_pages)
    
    context = {
        'leaves': leave_page,
        'monthly_history': monthly_data,
        'user': request.user
    }
    
    return render(request, 'leave_management/leave_history.html', context)

@login_required
@user_passes_test(is_admin)
def admin_home(request):
    return render(request, 'leave_management/admin_home.html')

@login_required
@user_passes_test(is_admin)
def leave_applications(request):
    leave_requests = LeaveRequest.objects.filter(status='PENDING').order_by('-created_at')
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(leave_requests, 10)  # Show 10 records per page
    
    try:
        leave_page = paginator.page(page)
    except PageNotAnInteger:
        leave_page = paginator.page(1)
    except EmptyPage:
        leave_page = paginator.page(paginator.num_pages)
        
    return render(request, 'leave_management/leave_applications.html', {'leave_requests': leave_page})

@login_required
@user_passes_test(is_admin)
def employee_leave_history(request):
    # Get search query and department filter
    search_query = request.GET.get('search', '')
    selected_department = request.GET.get('department', '')
    export_format = request.GET.get('export', '')
    
    # Start with all non-admin employees
    employees = Employee.objects.filter(is_admin=False)
    
    # Apply search filter if provided (case-insensitive)
    if search_query:
        employees = employees.filter(
            Q(employee_id__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
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
        
        # Get current month's leaves
        monthly_leaves = approved_leaves.filter(
            start_date__month=current_date.month
        )
        
        # Calculate monthly casual vs extra leaves
        monthly_casual = 0
        monthly_extra = 0
        for leave in monthly_leaves:
            if leave.leave_type == 'EXTRA':
                monthly_extra += leave.number_of_days
            else:
                monthly_casual += leave.number_of_days
        
        employee_list.append({
            'employee_id': emp.employee_id,
            'name': emp.get_full_name(),
            'department': emp.get_department_display(),
            'casual_leaves_used': casual_leaves_used,
            'casual_leaves_available': emp.casual_leaves_remaining,
            'extra_leaves_total': emp.extra_leaves_taken,
            'monthly_extra_leaves': monthly_extra,
            'monthly_casual_leaves': monthly_casual,
            'summer_leaves': summer_leaves,
            'summer_leaves_remaining': emp.summer_leaves_remaining
        })

    # Handle export
    if export_format:
        if export_format == 'excel':
            # Prepare data for Excel export
            data = [{
                'Employee ID': emp['employee_id'],
                'Name': emp['name'],
                'Department': emp['department'],
                'Casual Leaves Used': emp['casual_leaves_used'],
                'Casual Leaves Available': emp['casual_leaves_available'],
                'Extra Leaves Total': emp['extra_leaves_total'],
                'Monthly Extra Leaves': emp['monthly_extra_leaves'],
                'Monthly Casual Leaves': emp['monthly_casual_leaves'],
                'Summer Leaves Taken': emp['summer_leaves'],
                'Summer Leaves Remaining': emp['summer_leaves_remaining']
            } for emp in employee_list]
            
            headers = [
                'Employee ID', 'Name', 'Department', 
                'Casual Leaves Used', 'Casual Leaves Available',
                'Extra Leaves Total', 'Monthly Extra Leaves',
                'Monthly Casual Leaves', 'Summer Leaves Taken',
                'Summer Leaves Remaining'
            ]
            return export_to_excel(data, 'employee_leave_history', headers)
            
        elif export_format == 'pdf':
            context = {
                'employee_list': employee_list,
                'current_date': timezone.now().strftime('%B %d, %Y'),
                'title': 'Employee Leave History'
            }
            return export_to_pdf(
                'leave_management/pdf/employee_leave_history.html',
                context,
                'employee_leave_history'
            )
    
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
    # Use case-insensitive lookup
    employee = get_object_or_404(Employee, employee_id__iexact=employee_id)
    
    # Get all leave requests ordered by applied date
    leave_requests = LeaveRequest.objects.filter(employee=employee).order_by('-created_at')
    
    # Initialize monthly data
    monthly_data = {}
    
    for leave in leave_requests:
        leave_type = 'Summer' if leave.start_date.month == 5 else 'Regular'
        month_key = leave.created_at.strftime('%B %Y')
        
        if month_key not in monthly_data:
            monthly_data[month_key] = {
                'month': month_key,
                'list': [],
                'total_days': 0,
                'approved_count': 0,
                'pending_count': 0,
                'rejected_count': 0
            }
        
        # Add leave to monthly data
        leave_data = {
            'start_date': leave.start_date.strftime('%Y-%m-%d'),
            'end_date': leave.end_date.strftime('%Y-%m-%d'),
            'number_of_days': leave.number_of_days,
            'type': leave_type,
            'reason': leave.reason,
            'status': leave.status,
            'applied_date': leave.created_at.strftime('%Y-%m-%d %H:%M'),
            'approved_date': leave.updated_at.strftime('%Y-%m-%d %H:%M') if leave.status != 'PENDING' and hasattr(leave, 'updated_at') and leave.updated_at else '-'
        }
        
        monthly_data[month_key]['list'].append(leave_data)
        monthly_data[month_key]['total_days'] += leave.number_of_days
        
        # Update status counts
        if leave.status == 'APPROVED':
            monthly_data[month_key]['approved_count'] += 1
        elif leave.status == 'PENDING':
            monthly_data[month_key]['pending_count'] += 1
        else:  # REJECTED
            monthly_data[month_key]['rejected_count'] += 1
    
    # Convert to list and sort by date (most recent first)
    monthly_leaves = list(monthly_data.values())
    monthly_leaves.sort(key=lambda x: datetime.strptime(x['month'], '%B %Y'), reverse=True)
    
    context = {
        'employee': employee,
        'monthly_leaves': monthly_leaves,
        'casual_leaves_remaining': employee.casual_leaves_remaining,
        'summer_leaves_remaining': employee.summer_leaves_remaining,
        'extra_leaves_taken': employee.extra_leaves_taken
    }
    
    return render(request, 'leave_management/employee_details.html', context)

@login_required
def employee_list(request):
    # Get sort parameters
    sort_by = request.GET.get('sort_by', 'employee_id')
    sort_order = request.GET.get('order', 'asc')
    search_query = request.GET.get('search', '')
    
    # Start with all non-admin employees
    employees = Employee.objects.filter(is_admin=False)
    
    # Apply search if provided
    if search_query:
        employees = employees.filter(
            Q(employee_id__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )
    
    # Calculate experience for each employee
    from datetime import date
    today = date.today()
    
    employee_data = []
    for emp in employees:
        if emp.date_of_joining:
            experience = today - emp.date_of_joining
            years = experience.days // 365
            months = (experience.days % 365) // 30
            experience_str = f"{years} years, {months} months"
        else:
            experience_str = "N/A"
            
        employee_data.append({
            'employee': emp,
            'experience': experience_str
        })
    
    # Apply sorting
    if sort_by == 'department':
        employee_data.sort(key=lambda x: x['employee'].get_department_display())
    else:  # sort by employee_id
        employee_data.sort(key=lambda x: x['employee'].employee_id)
    
    # Reverse if descending order
    if sort_order == 'desc':
        employee_data.reverse()
    
    # Export functionality
    export_format = request.GET.get('export')
    if export_format:
        if export_format == 'excel':
            data = [{
                'Employee ID': emp['employee'].employee_id,
                'Name': emp['employee'].get_full_name(),
                'Department': emp['employee'].get_department_display(),
                'Phone': emp['employee'].phone_number or '-',
                'Experience': emp['experience']
            } for emp in employee_data]
            
            headers = ['Employee ID', 'Name', 'Department', 'Phone', 'Experience']
            return export_to_excel(data, 'employee_list', headers)
            
        elif export_format == 'pdf':
            context = {
                'employees': employee_data,
                'title': 'Employee List',
                'today': today.strftime('%B %d, %Y')
            }
            return export_to_pdf(
                'leave_management/pdf/employee_list.html',
                context,
                'employee_list'
            )
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(employee_data, 10)  # Show 10 records per page
    
    try:
        employee_page = paginator.page(page)
    except PageNotAnInteger:
        employee_page = paginator.page(1)
    except EmptyPage:
        employee_page = paginator.page(paginator.num_pages)
    
    context = {
        'employees': employee_page,
        'sort_by': sort_by,
        'sort_order': sort_order,
        'search_query': search_query,
        'departments': dict(Employee.DEPARTMENT_CHOICES)
    }
        
    return render(request, 'leave_management/employee_list.html', context)

@login_required
@user_passes_test(is_admin)
def register_employee(request):
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save(commit=False)
            # Keep original case for employee_id
            employee_id = form.cleaned_data['employee_id']
            
            # Check if employee exists (case-insensitive)
            if Employee.objects.filter(employee_id__iexact=employee_id).exists():
                messages.error(request, 'Employee ID already exists')
                return render(request, 'leave_management/register_employee.html', {'form': form})
            
            employee.username = employee_id  # Will be converted to uppercase in save method
            employee.employee_id = employee_id  # Keep original case
            employee.set_password(form.cleaned_data['password'])
            
            # Set initial summer leaves based on experience
            summer_leaves = calculate_summer_leaves(employee)
            employee.summer_leaves_remaining = summer_leaves
            
            employee.save()
            
            messages.success(request, f'Employee registered successfully with {summer_leaves} summer leaves based on experience!')
            return redirect('employee_list')
    else:
        form = EmployeeForm()
    return render(request, 'leave_management/register_employee.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def delete_employee(request):
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id', '')
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
    try:
        leave_request = get_object_or_404(LeaveRequest, id=leave_id)
        if leave_request.status != 'PENDING':
            messages.error(request, 'This leave request has already been processed')
            return redirect('leave_applications')
            
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
                    employee.casual_leaves_remaining = 0
                    extra_leaves_needed = leave_request.number_of_days - employee.casual_leaves_remaining
                    history.extra_leaves_taken += extra_leaves_needed
                    employee.extra_leaves_taken += extra_leaves_needed
                else:
                    # If no casual leaves remaining, all are extra
                    history.extra_leaves_taken += leave_request.number_of_days
                    employee.extra_leaves_taken += leave_request.number_of_days
        
        employee.save()
        history.save()
        
        return redirect('leave_applications')
    except Exception as e:
        messages.error(request, 'An error occurred while processing the leave request')
        # You might want to log the error here
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
def cancel_leave(request, leave_id):
    leave_request = get_object_or_404(LeaveRequest, id=leave_id)
    
    # Verify that the leave request belongs to the user
    if leave_request.employee != request.user:
        messages.error(request, 'You can only cancel your own leave requests.')
        return redirect('my_leaves')
    
    # Check if the leave request is pending and hasn't started
    if leave_request.status != 'PENDING':
        messages.error(request, 'Only pending leave requests can be cancelled.')
        return redirect('my_leaves')
    
    from datetime import date
    if leave_request.start_date <= date.today():
        messages.error(request, 'Cannot cancel a leave that has already started or passed.')
        return redirect('my_leaves')
    
    # Cancel the leave request
    leave_request.status = 'CANCELLED'
    leave_request.cancelled_at = timezone.now()
    leave_request.save()
    
    messages.success(request, 'Leave request cancelled successfully.')
    return redirect('my_leaves')

@login_required
@user_passes_test(is_admin)
def notifications(request):
    # Mark all notifications as read when visiting the page
    LoginAttempt.objects.filter(is_read=False).update(is_read=True)
    return render(request, 'leave_management/notifications.html')

@login_required
@user_passes_test(is_admin)
def get_login_attempts(request):
    attempts = LoginAttempt.objects.all().order_by('-attempted_at')
    unread_count = LoginAttempt.objects.filter(is_read=False).count()
    
    data = [{
        'id': attempt.id,
        'username': attempt.username,
        'attempted_at': attempt.attempted_at.strftime('%Y-%m-%d %H:%M:%S'),
        'ip_address': attempt.ip_address,
        'role': attempt.role,
        'is_read': attempt.is_read
    } for attempt in attempts]
    
    return JsonResponse({
        'data': data,
        'unread_count': unread_count
    })

@login_required
@user_passes_test(is_admin)
@require_POST
def delete_login_attempt(request, attempt_id):
    attempt = get_object_or_404(LoginAttempt, id=attempt_id)
    attempt.delete()
    return JsonResponse({'status': 'success'})

def calculate_yearly_totals(employee):
    """Calculate yearly totals for an employee's leave history"""
    current_year = timezone.now().year
    
    # Get all leave history records for the current year
    leave_histories = LeaveHistory.objects.filter(
        employee=employee,
        year=current_year
    )
    
    # Initialize yearly totals
    yearly_totals = {
        'casual_leaves': 0,
        'extra_leaves': 0,
        'summer_leaves': 0,
        'total_days': 0
    }
    
    # Calculate totals from leave history
    for history in leave_histories:
        yearly_totals['casual_leaves'] += history.casual_leaves_taken
        yearly_totals['extra_leaves'] += history.extra_leaves_taken
        yearly_totals['summer_leaves'] += history.summer_leaves_taken
        
    yearly_totals['total_days'] = (
        yearly_totals['casual_leaves'] + 
        yearly_totals['extra_leaves'] + 
        yearly_totals['summer_leaves']
    )
    
    return yearly_totals

@login_required
@user_passes_test(is_admin)
def employee_leave_report(request):
    context = {
        'current_year': datetime.now().year
    }
    
    search_query = request.GET.get('employee_id', '')
    if search_query:
        try:
            employee = Employee.objects.get(employee_id__iexact=search_query)
            
            # Get all leave requests for the employee
            leave_history = LeaveRequest.objects.filter(
                employee=employee
            ).order_by('-created_at')  # Most recent first
            
            # Get all leave history for current year
            current_year = datetime.now().year
            leave_histories = LeaveHistory.objects.filter(
                employee=employee,
                year=current_year
            ).order_by('month')
            
            # Create monthly report
            monthly_report = []
            for month in range(1, 13):
                history = leave_histories.filter(month=month).first()
                monthly_report.append({
                    'month': datetime(2025, month, 1).strftime('%B'),  # Month name
                    'casual_leaves': history.casual_leaves_taken if history else 0,
                    'extra_leaves': history.extra_leaves_taken if history else 0,
                    'summer_leaves': history.summer_leaves_taken if history else 0,
                    'total_days': (
                        (history.casual_leaves_taken + 
                         history.extra_leaves_taken + 
                         history.summer_leaves_taken) if history else 0
                    )
                })
            
            # Calculate yearly totals
            yearly_totals = calculate_yearly_totals(employee)
            
            # Update context with all data
            context.update({
                'employee': employee,
                'monthly_report': monthly_report,
                'search_id': search_query,
                'total_casual_leaves': yearly_totals['casual_leaves'],
                'total_extra_leaves': yearly_totals['extra_leaves'],
                'total_summer_leaves': yearly_totals['summer_leaves'],
                'total_days': yearly_totals['total_days'],
                'casual_leaves_available': employee.casual_leaves_remaining,
                'summer_leaves_available': employee.summer_leaves_remaining,
                'extra_leaves_taken': employee.extra_leaves_taken,
                'leave_history': leave_history
            })
            
            if search_query and 'export' in request.GET:
                export_format = request.GET.get('export')
                if export_format == 'excel':
                    data = [{
                        'Month': month['month'],
                        'Casual Leaves': month['casual_leaves'],
                        'Extra Leaves': month['extra_leaves'],
                        'Summer Leaves': month['summer_leaves'],
                        'Total Days': month['total_days']
                    } for month in monthly_report]
                    
                    headers = ['Month', 'Casual Leaves', 'Extra Leaves', 'Summer Leaves', 'Total Days']
                    return export_to_excel(data, f'leave_report_{employee.employee_id}', headers)
                    
                elif export_format == 'pdf':
                    return export_to_pdf(
                        'leave_management/pdf/leave_report.html',
                        context,
                        f'leave_report_{employee.employee_id}'
                    )
        except Employee.DoesNotExist:
            messages.error(request, f'No employee found with ID: {search_query}')
            context['search_id'] = search_query
    
    return render(request, 'leave_management/employee_leave_report.html', context)

@login_required
@user_passes_test(is_admin)
def bulk_register(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = TextIOWrapper(request.FILES['csv_file'].file, encoding='utf-8')
        reader = csv.DictReader(csv_file)
        preview_data = []
        success_count = 0
        
        required_fields = ['employee_id', 'first_name', 'last_name', 'department', 'password', 'date_of_joining', 'current_salary']
        
        # Get valid departments from model choices
        valid_departments = [dept[0] for dept in Employee.DEPARTMENT_CHOICES]
        
        # Validate CSV headers
        headers = reader.fieldnames
        if not headers or not all(field in headers for field in required_fields):
            messages.error(request, 'CSV file must contain all required fields: ' + ', '.join(required_fields))
            return render(request, 'leave_management/bulk_register.html')
        
        for row in reader:
            try:
                # Validate required fields
                if not all(row.get(field) for field in required_fields):
                    raise ValueError(f"All fields are required. Missing data in row.")
                
                # Validate department
                if row['department'] not in valid_departments:
                    raise ValueError(f"Invalid department: {row['department']}. Valid departments are: {', '.join(valid_departments)}")
                
                # Validate password length
                if len(row['password']) < 8:
                    raise ValueError("Password must be at least 8 characters long")

                # Validate current salary
                try:
                    current_salary = float(row['current_salary'])
                    if current_salary < 0:
                        raise ValueError("Salary cannot be negative")
                except ValueError:
                    raise ValueError("Current salary must be a valid number")

                # Validate phone number if provided
                phone_number = row.get('phone_number', '').strip()
                if phone_number:
                    # Remove any non-digit characters
                    phone_number = ''.join(filter(str.isdigit, str(phone_number)))
                    # Check for letters
                    if any(c.isalpha() for c in str(phone_number)):
                        raise ValueError("Phone number cannot contain letters")
                    # Check for digits only
                    if not phone_number.isdigit():
                        raise ValueError("Phone number must contain only digits")
                    # Check length
                    if len(phone_number) != 10:
                        raise ValueError("Phone number must be exactly 10 digits")
                
                # Validate and parse date of joining
                try:
                    date_of_joining = datetime.strptime(row['date_of_joining'], '%Y-%m-%d').date()
                    if date_of_joining > date.today():
                        raise ValueError("Date of joining cannot be in the future")
                except ValueError as e:
                    if "cannot be in the future" in str(e):
                        raise e
                    raise ValueError("Invalid date format. Use YYYY-MM-DD format for date of joining")
                
                # Check if employee_id already exists
                if Employee.objects.filter(employee_id__iexact=row['employee_id']).exists():
                    raise ValueError(f"Employee ID already exists: {row['employee_id']}")
                
                # Create the employee
                employee = Employee(
                    username=row['employee_id'].upper(),
                    employee_id=row['employee_id'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    department=row['department'],
                    phone_number=phone_number,
                    date_of_joining=date_of_joining,
                    is_admin=False
                )
                
                # Set password before saving
                employee.set_password(row['password'])
                
                # Calculate summer leaves based on experience
                summer_leaves = calculate_summer_leaves(employee)
                employee.summer_leaves_remaining = summer_leaves
                
                employee.save()
                
                preview_data.append({
                    'employee_id': employee.employee_id,
                    'first_name': employee.first_name,
                    'last_name': employee.last_name,
                    'department': employee.get_department_display(),
                    'phone_number': employee.phone_number,
                    'date_of_joining': employee.date_of_joining.strftime('%Y-%m-%d'),
                    'summer_leaves': summer_leaves,
                    'status': 'success'
                })
                success_count += 1
                
            except Exception as e:
                preview_data.append({
                    'employee_id': row.get('employee_id', 'N/A'),
                    'first_name': row.get('first_name', 'N/A'),
                    'last_name': row.get('last_name', 'N/A'),
                    'department': row.get('department', 'N/A'),
                    'phone_number': row.get('phone_number', 'N/A'),
                    'date_of_joining': row.get('date_of_joining', 'N/A'),
                    'summer_leaves': 'N/A',
                    'status': 'error',
                    'error': str(e)
                })
        
        if success_count > 0:
            messages.success(request, f'Successfully registered {success_count} employees.')
        if len(preview_data) - success_count > 0:
            messages.warning(request, f'Failed to register {len(preview_data) - success_count} employees. Please check the preview below.')
        
        return render(request, 'leave_management/bulk_register.html', {'preview_data': preview_data})
    
    return render(request, 'leave_management/bulk_register.html')

@login_required
@user_passes_test(is_admin)
def download_csv_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="employee_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['employee_id', 'first_name', 'last_name', 'department', 'password', 'phone_number', 'date_of_joining'])
    
    # Add example rows with different departments
    writer.writerow(['CS01', 'John', 'Doe', 'CSE', 'welcome123', '9876543210', '2024-01-01'])
    writer.writerow(['EC01', 'Jane', 'Smith', 'ECE', 'welcome123', '9876543211', '2024-01-01'])
    writer.writerow(['EE01', 'Alice', 'Johnson', 'EEE', 'welcome123', '9876543212', '2024-01-01'])
    writer.writerow(['ME01', 'Bob', 'Wilson', 'MECH', 'welcome123', '9876543213', '2024-01-01'])
    writer.writerow(['CV01', 'Carol', 'Brown', 'CIVIL', 'welcome123', '9876543214', '2024-01-01'])
    writer.writerow(['AI01', 'David', 'Lee', 'AI', 'welcome123', '9876543215', '2024-01-01'])
    writer.writerow(['NT01', 'Emma', 'Davis', 'NON_TEACHING', 'welcome123', '9876543216', '2024-01-01'])
    writer.writerow(['MT01', 'Frank', 'Miller', 'MATH', 'welcome123', '9876543217', '2024-01-01'])
    writer.writerow(['EN01', 'Grace', 'Taylor', 'ENGLISH', 'welcome123', '9876543218', '2024-01-01'])
    
    return response

@login_required
@user_passes_test(is_admin)
def todays_leave(request):
    today = timezone.now().date()
    todays_leaves = LeaveRequest.objects.filter(start_date__lte=today, end_date__gte=today, status='APPROVED')
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(todays_leaves, 10)  # Show 10 records per page
    
    try:
        todays_leaves_page = paginator.page(page)
    except PageNotAnInteger:
        todays_leaves_page = paginator.page(1)
    except EmptyPage:
        todays_leaves_page = paginator.page(paginator.num_pages)
        
    return render(request, 'leave_management/todays_leave.html', {'todays_leaves': todays_leaves_page})

@login_required
@user_passes_test(is_admin)
def employees_on_date(request):
    if request.method == 'POST':
        selected_date = request.POST.get('date')
        if selected_date:
            leaves_on_date = LeaveRequest.objects.filter(
                start_date__lte=selected_date,
                end_date__gte=selected_date,
                status='APPROVED'
            ).select_related('employee')
            
            # Pagination
            page = request.GET.get('page', 1)
            paginator = Paginator(leaves_on_date, 10)  # Show 10 records per page
            
            try:
                leaves_on_date_page = paginator.page(page)
            except PageNotAnInteger:
                leaves_on_date_page = paginator.page(1)
            except EmptyPage:
                leaves_on_date_page = paginator.page(paginator.num_pages)
                
            return render(request, 'leave_management/employees_on_date.html', {
                'leaves_on_date': leaves_on_date_page,
                'selected_date': selected_date
            })
    
    return render(request, 'leave_management/employees_on_date.html')

@login_required
def my_leaves(request):
    """View function to display the leave history for the logged-in employee"""
    from datetime import date
    leaves = LeaveRequest.objects.filter(employee=request.user).order_by('-created_at')
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(leaves, 10)  # Show 10 records per page
    
    try:
        leave_page = paginator.page(page)
    except PageNotAnInteger:
        leave_page = paginator.page(1)
    except EmptyPage:
        leave_page = paginator.page(paginator.num_pages)
        
    context = {
        'leaves': leave_page,
        'today': date.today()
    }
    return render(request, 'leave_management/leave_history.html', context)

@login_required
@admin_required
def manage_holidays(request):
    if request.method == 'POST':
        form = HolidayForm(request.POST)
        if form.is_valid():
            holiday = form.save()
            messages.success(request, f'Holiday "{holiday.name}" has been added successfully!')
            return redirect('manage_holidays')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{error}')
    else:
        form = HolidayForm()
    
    # Get all holidays ordered by date
    holidays = Holiday.objects.all().order_by('-date')
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(holidays, 10)  # Show 10 records per page
    
    try:
        holidays_page = paginator.page(page)
    except PageNotAnInteger:
        holidays_page = paginator.page(1)
    except EmptyPage:
        holidays_page = paginator.page(paginator.num_pages)
    
    context = {
        'form': form,
        'holidays': holidays_page,
        'today': timezone.now().date()
    }
    
    return render(request, 'leave_management/manage_holidays.html', context)

@login_required
@admin_required
def delete_holiday(request, holiday_id):
    try:
        # Get the holiday object
        holiday = get_object_or_404(Holiday, id=holiday_id)
        
        # Get all approved leave requests that overlap with this holiday date
        affected_leaves = LeaveRequest.objects.filter(
            start_date__lte=holiday.date,
            end_date__gte=holiday.date,
            status='APPROVED'
        )
        
        # Store holiday info for message
        holiday_name = holiday.name
        holiday_date = holiday.date
        
        # Delete the holiday
        holiday.delete()
        
        # Update leave counts for affected requests
        for leave in affected_leaves:
            # Store old values
            old_days = leave.number_of_days
            old_type = leave.leave_type
            
            # Recalculate working days
            new_days = leave.calculate_working_days()
            difference = new_days - old_days  # New days will be more since holiday is removed
            
            if difference > 0:
                # Update leave counts based on leave type
                employee = leave.employee
                
                # Get all affected months
                current_date = leave.start_date
                while current_date <= leave.end_date:
                    month = current_date.month
                    year = current_date.year
                    
                    # Get or create leave history for this month
                    history, created = LeaveHistory.objects.get_or_create(
                        employee=employee,
                        month=month,
                        year=year
                    )
                    
                    # Calculate days in this month
                    month_start = max(current_date, leave.start_date)
                    month_end = min(current_date.replace(day=1).replace(month=month % 12 + 1) - timezone.timedelta(days=1), leave.end_date)
                    days_in_month = (month_end - month_start).days + 1
                    
                    # Calculate proportion of difference for this month
                    month_difference = int(round(difference * (days_in_month / old_days)))
                    
                    if old_type == 'CASUAL':
                        if employee.casual_leaves_remaining >= month_difference:
                            history.casual_leaves_taken += month_difference
                            employee.casual_leaves_remaining -= month_difference
                        else:
                            # If not enough casual leaves, use extra leaves
                            casual_leaves_available = employee.casual_leaves_remaining
                            if casual_leaves_available > 0:
                                history.casual_leaves_taken += casual_leaves_available
                                employee.casual_leaves_remaining = 0
                                extra_leaves_needed = month_difference - casual_leaves_available
                                history.extra_leaves_taken += extra_leaves_needed
                                employee.extra_leaves_taken += extra_leaves_needed
                            else:
                                history.extra_leaves_taken += month_difference
                                employee.extra_leaves_taken += month_difference
                    elif old_type == 'SUMMER':
                        history.summer_leaves_taken += month_difference
                        employee.summer_leaves_remaining -= month_difference
                    else:  # EXTRA
                        history.extra_leaves_taken += month_difference
                        employee.extra_leaves_taken += month_difference
                    
                    history.save()
                    
                    # Move to next month
                    if month == 12:
                        current_date = current_date.replace(year=year + 1, month=1, day=1)
                    else:
                        current_date = current_date.replace(month=month + 1, day=1)
                
                employee.save()
            
            # Update leave request days
            leave.number_of_days = new_days
            leave.save()
        
        messages.success(
            request,
            f'Holiday "{holiday_name}" on {holiday_date} deleted successfully. '
            f'{len(affected_leaves)} leave requests were updated.'
        )
    except Exception as e:
        messages.error(request, f'Error deleting holiday: {str(e)}')
    
    return redirect('manage_holidays')

@login_required
@user_passes_test(is_admin)
def admin_change_user_password(request):
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        try:
            if new_password != confirm_password:
                messages.error(request, 'Passwords do not match!')
                return redirect('admin_change_user_password')
            
            # Case-insensitive query for employee ID
            employee = Employee.objects.filter(employee_id__iexact=employee_id).first()
            if not employee:
                raise Employee.DoesNotExist()
                
            employee.set_password(new_password)
            employee.save()
            
            messages.success(request, f'Password successfully changed for employee {employee_id}')
            return redirect('admin_change_user_password')
            
        except Employee.DoesNotExist:
            messages.error(request, f'Employee with ID {employee_id} not found!')
            return redirect('admin_change_user_password')
    
    return render(request, 'leave_management/admin_change_password.html')

@login_required
@user_passes_test(is_admin)
def bulk_holiday_register(request):
    if request.method == 'POST':
        if 'csv_file' not in request.FILES:
            messages.error(request, 'Please upload a CSV file')
            return redirect('bulk_holiday_register')
        
        csv_file = request.FILES['csv_file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a valid CSV file')
            return redirect('bulk_holiday_register')
            
        try:
            decoded_file = TextIOWrapper(csv_file.file, encoding='utf-8-sig')
            csv_reader = csv.DictReader(decoded_file)
            
            success_count = 0
            error_count = 0
            errors = []
            
            for row in csv_reader:
                try:
                    # Parse the date string to date object
                    holiday_date = datetime.strptime(row['date'], '%Y-%m-%d').date()
                    
                    # Create holiday if it doesn't exist
                    holiday, created = Holiday.objects.get_or_create(
                        date=holiday_date,
                        name=row['name'],
                        defaults={'description': row.get('description', '')}
                    )
                    
                    if created:
                        success_count += 1
                    else:
                        error_count += 1
                        errors.append(f"Holiday already exists for date {row['date']}")
                        
                except Exception as e:
                    error_count += 1
                    errors.append(f"Error in row {csv_reader.line_num}: {str(e)}")
            
            if success_count > 0:
                messages.success(request, f'Successfully added {success_count} holidays')
            if error_count > 0:
                messages.warning(request, f'Failed to add {error_count} holidays')
                for error in errors[:5]:  # Show first 5 errors
                    messages.error(request, error)
                    
        except Exception as e:
            messages.error(request, f'Error processing CSV file: {str(e)}')
            
        return redirect('manage_holidays')
        
    return render(request, 'leave_management/bulk_holiday_register.html')

def download_holiday_csv_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="holiday_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['name', 'date', 'description'])
    writer.writerow(['New Year', '2024-01-01', 'New Year Celebration'])  # Example row
    
    return response

@login_required
def user_attendance(request):
    today = timezone.now().date()
    current_month = today.month
    current_year = today.year
    
    # Get month and year from request
    month = int(request.GET.get('month', current_month))
    year = int(request.GET.get('year', current_year))
    
    # Get attendance records for the selected month
    attendance_records = Attendance.objects.filter(
        employee=request.user,
        date__year=year,
        date__month=month
    ).order_by('-date')
    
    # Export functionality
    if 'export' in request.GET:
        format = request.GET.get('format', 'excel')
        if format == 'excel':
            return export_attendance_to_excel(attendance_records, f"attendance_{year}_{month}")
        elif format == 'pdf':
            return export_attendance_to_pdf(attendance_records, f"attendance_{year}_{month}")
    
    # Create a list of month tuples (number, name)
    months = [(i, datetime(2000, i, 1).strftime('%B')) for i in range(1, 13)]
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(attendance_records, 10)  # Show 10 records per page
    
    try:
        attendance_page = paginator.page(page)
    except PageNotAnInteger:
        attendance_page = paginator.page(1)
    except EmptyPage:
        attendance_page = paginator.page(paginator.num_pages)
    
    context = {
        'attendance_records': attendance_page,
        'current_month': month,
        'current_year': year,
        'months': months,
        'years': range(today.year - 2, today.year + 1),
    }
    return render(request, 'leave_management/user_attendance.html', context)

@login_required
@user_passes_test(is_admin)
def admin_attendance(request):
    today = timezone.now().date()
    
    # Get filter parameters
    filter_type = request.GET.get('filter_type', 'day')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    employee_id = request.GET.get('employee_id', '')
    
    # Base query
    attendance_query = Attendance.objects.all().order_by('-date')
    
    # Apply filters
    if employee_id:
        attendance_query = attendance_query.filter(employee__employee_id__iexact=employee_id)
    if start_date:
        attendance_query = attendance_query.filter(date__gte=start_date)
    if end_date:
        attendance_query = attendance_query.filter(date__lte=end_date)
        
    # Export functionality
    if 'export' in request.GET:
        format = request.GET.get('format', 'excel')
        if format == 'excel':
            return export_attendance_to_excel(attendance_query, "attendance_report")
        elif format == 'pdf':
            return export_attendance_to_pdf(attendance_query, "attendance_report")
            
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(attendance_query, 10)  # Show 10 records per page
    
    try:
        attendance_page = paginator.page(page)
    except PageNotAnInteger:
        attendance_page = paginator.page(1)
    except EmptyPage:
        attendance_page = paginator.page(paginator.num_pages)
    
    context = {
        'attendance_records': attendance_page,
        'employee_id': employee_id,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'leave_management/admin_attendance.html', context)

def export_attendance_to_excel(queryset, filename):
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance Report"
    
    # Headers
    headers = ['Date', 'Employee ID', 'Name', 'Check-in Time', 'Check-out Time', 'Duration (Hours)']
    ws.append(headers)
    
    # Data
    for record in queryset:
        ws.append([
            record.date,
            record.employee.employee_id,
            record.employee.get_full_name(),
            record.check_in_time.strftime('%H:%M') if record.check_in_time else 'N/A',
            record.check_out_time.strftime('%H:%M') if record.check_out_time else 'N/A',
            record.get_duration() or 'N/A'
        ])
    
    wb.save(response)
    return response

def export_attendance_to_pdf(queryset, filename):
    template_path = 'leave_management/pdf/attendance_report.html'
    context = {'attendance_records': queryset}
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)
    
    # Create PDF
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('PDF generation error')
    return response

@login_required
@user_passes_test(is_admin)
def manage_compensatory_leave(request):
    if request.method == 'POST':
        grant_type = request.POST.get('grant_type')
        number_of_days = int(request.POST.get('number_of_days', 0))
        reason = request.POST.get('reason', '')
        
        if number_of_days <= 0:
            messages.error(request, 'Number of days must be greater than 0')
            return redirect('manage_compensatory_leave')
            
        try:
            comp_leave = CompensatoryLeave(
                grant_type=grant_type,
                number_of_days=number_of_days,
                reason=reason,
                granted_by=request.user
            )
            
            if grant_type == 'INDIVIDUAL':
                employee_id = request.POST.get('employee_id')
                employee = Employee.objects.filter(employee_id__iexact=employee_id).first()
                if not employee:
                    messages.error(request, f'Employee with ID {employee_id} not found')
                    return redirect('manage_compensatory_leave')
                comp_leave.employee = employee
                
            else:  # DEPARTMENT
                department = request.POST.get('department')
                if not department:
                    messages.error(request, 'Please select a department')
                    return redirect('manage_compensatory_leave')
                comp_leave.department = department
            
            comp_leave.save()
            messages.success(request, 'Compensatory leave granted successfully')
            
        except Exception as e:
            messages.error(request, f'Error granting compensatory leave: {str(e)}')
            
        return redirect('manage_compensatory_leave')
    
    # Get search query
    search_query = request.GET.get('search', '')
    
    # Get compensatory leave history with search filter
    comp_leaves = CompensatoryLeave.objects.all()
    
    if search_query:
        comp_leaves = comp_leaves.filter(
            Q(employee__employee_id__icontains=search_query) |
            Q(employee__first_name__icontains=search_query) |
            Q(employee__last_name__icontains=search_query)
        )
    
    comp_leaves = comp_leaves.order_by('-granted_date')
    
    # Get list of departments and employees for the form
    departments = dict(Employee.DEPARTMENT_CHOICES)
    employees = Employee.objects.filter(is_admin=False).order_by('employee_id')
    
    context = {
        'comp_leaves': comp_leaves,
        'departments': departments,
        'employees': employees,
        'search_query': search_query
    }
    
    return render(request, 'leave_management/manage_compensatory_leave.html', context)

@login_required
@user_passes_test(is_admin)
def delete_compensatory_leave(request, comp_leave_id):
    comp_leave = get_object_or_404(CompensatoryLeave, id=comp_leave_id)
    
    try:
        # Reduce casual leaves for affected employees
        if comp_leave.grant_type == 'INDIVIDUAL' and comp_leave.employee:
            comp_leave.employee.casual_leaves_remaining -= comp_leave.number_of_days
            comp_leave.employee.save()
        elif comp_leave.grant_type == 'DEPARTMENT' and comp_leave.department:
            employees = Employee.objects.filter(department=comp_leave.department)
            for emp in employees:
                emp.casual_leaves_remaining -= comp_leave.number_of_days
                emp.save()
        
        comp_leave.delete()
        messages.success(request, 'Compensatory leave deleted successfully')
        
    except Exception as e:
        messages.error(request, f'Error deleting compensatory leave: {str(e)}')
    
    return redirect('manage_compensatory_leave')

@login_required
def my_compensatory_leaves(request):
    """View function to display compensatory leaves for the logged-in employee"""
    # Get search query
    search_query = request.GET.get('search', '')
    
    # Get individual compensatory leaves
    individual_leaves = CompensatoryLeave.objects.filter(
        grant_type='INDIVIDUAL',
        employee=request.user
    )
    
    # Get department-wide compensatory leaves
    department_leaves = CompensatoryLeave.objects.filter(
        grant_type='DEPARTMENT',
        department=request.user.department
    )
    
    # Apply search if provided
    if search_query:
        individual_leaves = individual_leaves.filter(
            Q(reason__icontains=search_query) |
            Q(granted_date__icontains=search_query)
        )
        department_leaves = department_leaves.filter(
            Q(reason__icontains=search_query) |
            Q(granted_date__icontains=search_query)
        )
    
    # Order by granted date
    individual_leaves = individual_leaves.order_by('-granted_date')
    department_leaves = department_leaves.order_by('-granted_date')
    
    # Combine both types of leaves
    all_leaves = list(individual_leaves) + list(department_leaves)
    all_leaves.sort(key=lambda x: x.granted_date, reverse=True)
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(all_leaves, 10)  # Show 10 records per page
    
    try:
        leaves_page = paginator.page(page)
    except PageNotAnInteger:
        leaves_page = paginator.page(1)
    except EmptyPage:
        leaves_page = paginator.page(paginator.num_pages)
    
    context = {
        'compensatory_leaves': leaves_page,
        'search_query': search_query
    }
    return render(request, 'leave_management/my_compensatory_leaves.html', context)

@login_required
@user_passes_test(is_admin)
def bulk_delete_employees(request):
    if request.method == 'POST':
        employee_ids = request.POST.getlist('employee_ids')
        admin_password = request.POST.get('password')
        
        if not employee_ids:
            messages.error(request, 'No employees selected for deletion')
            return redirect('employee_list')
            
        if not request.user.check_password(admin_password):
            messages.error(request, 'Invalid admin password')
            return redirect('employee_list')
            
        try:
            # Filter out admin users and delete selected employees
            deleted_count = 0
            for emp_id in employee_ids:
                try:
                    employee = Employee.objects.get(employee_id__iexact=emp_id)
                    if not employee.is_admin:
                        employee.delete()
                        deleted_count += 1
                except Employee.DoesNotExist:
                    continue
            
            if deleted_count > 0:
                messages.success(request, f'Successfully deleted {deleted_count} employee(s)')
            else:
                messages.warning(request, 'No employees were deleted')
                
        except Exception as e:
            messages.error(request, f'Error deleting employees: {str(e)}')
            
        return redirect('employee_list')
    
    # Get all non-admin employees for the template
    employees = Employee.objects.filter(is_admin=False).order_by('employee_id')
    return render(request, 'leave_management/bulk_delete_employees.html', {'employees': employees})

@login_required
@user_passes_test(is_staff)
def reports(request):
    # Get filter parameters
    department = request.GET.get('department', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    # Base queryset
    leave_requests = LeaveRequest.objects.all()
    
    # Apply date filters if provided
    if start_date:
        leave_requests = leave_requests.filter(start_date__gte=start_date)
    if end_date:
        leave_requests = leave_requests.filter(end_date__lte=end_date)
    
    # Calculate summary statistics
    total_leaves = leave_requests.count()
    pending_leaves = leave_requests.filter(status='PENDING').count()
    approved_leaves = leave_requests.filter(status='APPROVED').count()
    rejected_leaves = leave_requests.filter(status='REJECTED').count()
    
    # Department-wise statistics
    if department:
        # If specific department is selected
        department_stats = leave_requests.filter(
            employee__department=department
        ).values('employee__department').annotate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='APPROVED')),
            pending=Count('id', filter=Q(status='PENDING')),
            rejected=Count('id', filter=Q(status='REJECTED')),
            avg_duration=Avg('number_of_days')
        )
    else:
        # Show all departments
        department_stats = leave_requests.values('employee__department').annotate(
            total=Count('id'),
            approved=Count('id', filter=Q(status='APPROVED')),
            pending=Count('id', filter=Q(status='PENDING')),
            rejected=Count('id', filter=Q(status='REJECTED')),
            avg_duration=Avg('number_of_days')
        )
    
    # Convert department codes to names and format the stats
    departments_dict = dict(Employee.DEPARTMENT_CHOICES)
    formatted_dept_stats = []
    for stat in department_stats:
        dept_code = stat['employee__department']
        formatted_dept_stats.append({
            'name': departments_dict.get(dept_code, dept_code),
            'total': stat['total'],
            'approved': stat['approved'],
            'pending': stat['pending'],
            'rejected': stat['rejected'],
            'avg_duration': round(stat['avg_duration'], 1) if stat['avg_duration'] else 0
        })
    
    # Leave type distribution with month analysis
    leave_type_stats = []
    for leave_type in ['CASUAL', 'EXTRA', 'SUMMER']:
        type_requests = leave_requests.filter(leave_type=leave_type)
        if type_requests.exists():
            # Get the most common month for this leave type
            common_month = type_requests.annotate(
                month=ExtractMonth('start_date')
            ).values('month').annotate(
                count=Count('id')
            ).order_by('-count').first()
            
            month_name = datetime(2000, common_month['month'], 1).strftime('%B') if common_month else 'N/A'
            
            leave_type_stats.append({
                'name': leave_type.capitalize(),
                'total': type_requests.count(),
                'approved': type_requests.filter(status='APPROVED').count(),
                'avg_duration': round(type_requests.aggregate(avg=Avg('number_of_days'))['avg'] or 0, 1),
                'common_month': month_name
            })
    
    context = {
        'total_leaves': total_leaves,
        'pending_leaves': pending_leaves,
        'approved_leaves': approved_leaves,
        'rejected_leaves': rejected_leaves,
        'department_stats': formatted_dept_stats,
        'leave_type_stats': leave_type_stats,
        'selected_department': department,
        'start_date': start_date,
        'end_date': end_date,
        'departments': dict(Employee.DEPARTMENT_CHOICES),
    }
    
    return render(request, 'leave_management/reports.html', context)

def logout_view(request):
    if request.user.is_authenticated:
        # Clear any messages
        storage = messages.get_messages(request)
        for _ in storage:
            pass  # Iterate through messages to mark them as read
        
        # Perform logout
        logout(request)
        messages.success(request, 'You have been successfully logged out.')
    
    # Redirect to login page
    return redirect('login')

@login_required
@require_POST
def cancel_leave(request, leave_id):
    leave_request = get_object_or_404(LeaveRequest, id=leave_id, employee=request.user)
    
    if leave_request.status != 'PENDING' or leave_request.start_date <= timezone.now().date():
        messages.error(request, 'This leave request cannot be cancelled.')
        return redirect('leave_history')
    
    leave_request.status = 'CANCELLED'
    leave_request.cancelled_at = timezone.now()
    leave_request.cancellation_reason = 'Cancelled by employee'
    leave_request.save()
    
    messages.success(request, 'Leave request has been cancelled successfully.')
    return redirect('leave_history')
