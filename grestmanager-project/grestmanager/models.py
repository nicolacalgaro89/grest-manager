import datetime
from django.conf import settings
from django.db import models
from django.utils import timezone

class Person(models.Model):
    name = models.CharField(max_length=200)
    birth_date = models.DateTimeField("birth date")
    def __str__(self):
        return self.name + " - " + self.birth_date.strftime("%Y-%m-%d %H:%M:%S")
    
class Subscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="subscriptions"
    )
    date = models.DateTimeField("issuance date")
    price = models.CharField(max_length=200)
    related_to = models.ForeignKey(
        "Person", 
        on_delete=models.DO_NOTHING, 
        related_name="subscriptions")
    def __str__(self):
        return self.date.strftime("%Y-%m-%d %H:%M:%S") + " - " + self.price
    def was_issued_recently(self):
        return self.date >= timezone.now() - datetime.timedelta(days=1)