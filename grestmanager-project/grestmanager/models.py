import datetime
from django.conf import settings
from django.db import models
from django.utils import timezone

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
    
class Subscription(models.Model):
    date = models.DateTimeField("issuance date")
    price = models.CharField(max_length=200)
    related_to = models.ForeignKey(
        "Person", 
        on_delete=models.DO_NOTHING, 
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
    