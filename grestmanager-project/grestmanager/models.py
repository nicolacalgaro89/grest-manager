import datetime
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class Person(models.Model):
    name = models.CharField(max_length=200)
    surname = models.CharField(max_length=200)
    birth_date = models.DateTimeField("birth date")
    tax_code = models.CharField(max_length=200)
    managed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="persons")
    def __str__(self):
        return self.name + " - " + self.birth_date.strftime("%Y-%m-%d %H:%M:%S")
    
class Event(models.Model):
    name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    subscription_opening_date = models.DateTimeField("subscription opening date")
    subscription_closing_date = models.DateTimeField("subscription closing date")
    def __str__(self):
        return self.name
    def is_subscription_open(self):
        now = timezone.now()
        return self.subscription_opening_date <= now <= self.subscription_closing_date
    
class Subscription(models.Model):
    date = models.DateTimeField("issuance date")
    price = models.CharField(max_length=200)
    related_to = models.ForeignKey(
        "Person", 
        on_delete=models.CASCADE, 
        related_name="subscriptions")
    to_event = models.ForeignKey(
        "Event", 
        on_delete=models.CASCADE, 
        related_name="subscriptions")
    def __str__(self):
        return self.date.strftime("%Y-%m-%d %H:%M:%S") + " - " + self.price
    def was_issued_recently(self):
        return self.date >= timezone.now() - datetime.timedelta(days=1)
    def is_active(self):
        now = timezone.now()
        return self.to_event.active and self.to_event.subscription_opening_date <= now <= self.to_event.subscription_closing_date
    
class TimeEntry(models.Model):
    class EntryType(models.TextChoices):
        IN = 'IN', _('Inbound')
        OUT = 'OUT', _('Outbound')

    timestamp = models.DateTimeField(auto_now_add=True)
    
    # L'attributo che salva il tipo di timbratura
    entry_type = models.CharField(
        max_length=3,
        choices=EntryType.choices,
        default=EntryType.IN,
    )
    
    remarks = models.CharField(max_length=200, blank=True)
    
    related_to = models.ForeignKey(
        "Person", 
        on_delete=models.CASCADE, 
        related_name="time_entries")
    def __str__(self):
        return self.date.strftime("%Y-%m-%d %H:%M:%S") + " - " + self.description
