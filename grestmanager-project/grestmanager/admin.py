from django.contrib import admin

# Register your models here.
from .models import Person, Subscription, Event

admin.site.register(Person)
admin.site.register(Subscription)
admin.site.register(Event)
admin.site.site_header = "Grest Manager Admin"
admin.site.site_title = "Grest Manager Admin Portal"
admin.site.index_title = "Welcome to the Grest Manager Admin Portal"
