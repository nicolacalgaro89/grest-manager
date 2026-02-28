from django.urls import path, include

from . import views
from django.contrib.auth import views as auth_views

app_name = "grestmanager"
urlpatterns = [
    path("", views.index, name="index"),
    # ex: /grestmanager/5/
    path("person/<int:person_id>/", views.detail, name="detail"),
    # ex: /grestmanager/5/subscriptions/
    path("subscriptions/", views.SubscriptionsView.as_view(), name="subscriptions"),
    path("persons/", views.PersonsView.as_view(), name="persons"),

    path("subscribe/", views.subscribe, name="subscribe"),
    path("create_subscription/", views.SubscriptionCreateView.as_view(), name="create_subscription"),

    #path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/register/", views.RegisterView.as_view(), name="register"),

]