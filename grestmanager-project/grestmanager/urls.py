from django.urls import path, include

from . import views
from django.contrib.auth import views as auth_views

app_name = "grestmanager"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("events/<int:event_id>/", views.EventDetailView.as_view(), name="event_detail"),
    path("persons/<int:person_id>/", views.PersonDetailView.as_view(), name="person_detail"),
    path("persons/", views.PersonsListView.as_view(), name="persons"),
    path("persons/create/", views.PersonCreateView.as_view(), name="person_create"),
    path("persons/<int:person_id>/update/", views.PersonUpdateView.as_view(), name="person_update"),
    path("persons/<int:person_id>/delete/", views.PersonDeleteView.as_view(), name="person_delete"),
    path("persons/<int:person_id>/subscriptions/", views.subscriptions, name="subscriptions"),
    path("persons/<int:person_id>/subscriptions/create/", views.SubscriptionCreateView.as_view(), name="subscription_create"),
    path("persons/<int:person_id>/subscriptions/<int:subscription_id>/delete/", views.SubscriptionDeleteView.as_view(), name="subscription_delete"),

    path("accounts/register/", views.RegisterView.as_view(), name="register"),

]