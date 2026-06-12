from django.db import models
from django.contrib.auth.models import User
import datetime


class Present(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(default=datetime.date.today)
    present = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']

    def __str__(self):
        status = 'Present' if self.present else 'Absent'
        return f'{self.user.username} — {self.date} — {status}'


class Time(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='time_records')
    date = models.DateField(default=datetime.date.today)
    time = models.DateTimeField(null=True, blank=True)
    out = models.BooleanField(default=False)

    class Meta:
        ordering = ['time']

    def __str__(self):
        action = 'Out' if self.out else 'In'
        return f'{self.user.username} — {action} — {self.time}'
