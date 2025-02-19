from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.utils import timezone
from datetime import datetime
from .models import Employee, LeaveRequest, LeaveHistory
from django import forms

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
        username = form.cleaned_data.get('username')
        password = form.cleaned_data.get('password')
        
        # Convert username to lowercase for case-insensitive comparison
        user = Employee.objects.filter(employee_id__iexact=username).first()
        
        if user and user.check_password(password):
            # Set the user for authentication
            form.cleaned_data['username'] = user.username
            return super().form_valid(form)
        else:
            form.add_error(None, 'Invalid Employee ID or password')
            return self.form_invalid(form)
    
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
            leave_request.number_of_days = (leave_request.end_date - leave_request.start_date).days + 1
            leave_request.save()
            messages.success(request, 'Leave request submitted successfully!')
            return redirect('leave_history')
    else:
        form = LeaveRequestForm()
    return render(request, 'leave_management/apply_leave.html', {'form': form})

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
    employee_id = request.GET.get('employee_id')
    employee = None
    history = None
    
    if employee_id:
        # Use case-insensitive lookup for employee_id
        employee = get_object_or_404(Employee, employee_id__iexact=employee_id)
        history = LeaveHistory.objects.filter(employee=employee).order_by('-year', '-month')
    
    return render(request, 'leave_management/employee_leave_history.html', {
        'employee': employee,
        'history': history
    })

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
        employee_id = request.POST.get('employee_id')
        admin_password = request.POST.get('password')
        
        if request.user.check_password(admin_password):
            try:
                employee = Employee.objects.get(employee_id=employee_id)
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
        if employee.casual_leaves_remaining >= leave_request.number_of_days:
            employee.casual_leaves_remaining -= leave_request.number_of_days
            history.casual_leaves_taken += leave_request.number_of_days
        else:
            extra_leaves = leave_request.number_of_days - employee.casual_leaves_remaining
            history.casual_leaves_taken += employee.casual_leaves_remaining
            history.extra_leaves_taken += extra_leaves
            employee.casual_leaves_remaining = 0
            employee.extra_leaves_taken += extra_leaves
        
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
