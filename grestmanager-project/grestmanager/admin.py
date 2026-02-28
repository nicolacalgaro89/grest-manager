from django.contrib import admin

# Register your models here.
from .models import Person, Subscription

admin.site.register(Person)
admin.site.register(Subscription)
