from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('leave_management', '0011_populate_employee_salaries'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaverequest',
            name='cancellation_reason',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='leaverequest',
            name='cancelled_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]