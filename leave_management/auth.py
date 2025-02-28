from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from .models import Employee

class CaseInsensitiveAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Case insensitive lookup using employee_id
            employee = Employee.objects.get(Q(employee_id__iexact=username))
            if employee.check_password(password):
                return employee
        except Employee.DoesNotExist:
            return None
        
    def get_user(self, user_id):
        try:
            return Employee.objects.get(pk=user_id)
        except Employee.DoesNotExist:
            return None 