from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse
from django.views import generic
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.forms import UserCreationForm
# from django.template import loader

from django.urls import reverse, reverse_lazy   
from django.utils import timezone
from .models import Person, Subscription


# def index(request):
#     return HttpResponse("Hello, world. You're at the grest manager index.")

# def index(request):
#     person_list = Person.objects.order_by("-birth_date")[:5]
#     output = ", ".join([q.name for q in person_list])
#     return HttpResponse(output)

# def index(request):
#     person_list = Person.objects.order_by("-birth_date")[:5]
#     template = loader.get_template("grestmanager/index.html")
#     context = {"person_list": person_list}
#     return HttpResponse(template.render(context, request))


def index(request):
    person_list = Person.objects.order_by("-birth_date")[:5]
    context = {"person_list": person_list}
    return render(request, "grestmanager/index.html", context)


# def detail(request, person_id):
#     return HttpResponse("You're looking at person %s." % person_id)

# def detail(request, person_id):
#     try:
#         person = Person.objects.get(pk=person_id)
#     except Person.DoesNotExist:
#         raise Http404("Person does not exist")
#     return render(request, "grestmanager/detail.html", {"person": person})

@login_required
def detail(request, person_id):
    person = get_object_or_404(Person, pk=person_id)
    return render(request, "grestmanager/detail.html", {"person": person})

class SubscriptionsView(generic.ListView):
    template_name = "grestmanager/subscriptions.html"
    context_object_name = "subscriptions_list"

    def get_queryset(self):
        """Return the last five issued subscriptions."""
        return Subscription.objects.order_by("-date")[:5]
    
# @login_required
# @permission_required("grestmanager.add_person", raise_exception=True) Non funziona con le class based view, per questo uso i mixin
# class PersonsView(generic.ListView):
#     template_name = "grestmanager/persons.html"
#     context_object_name = "persons_list"

#     def get_queryset(self):
#         """Return the list of persons ordered by birth date."""
#         return Person.objects.order_by("-birth_date")
    
# Mixins MUST come before the generic view in the inheritance list
class PersonsView(LoginRequiredMixin, PermissionRequiredMixin, generic.ListView):
    template_name = "grestmanager/persons.html"
    context_object_name = "persons_list"
    
    # Permission settings for PermissionRequiredMixin
    permission_required = "grestmanager.add_person"
    raise_exception = True
    
    # permission_denied_message = "You do not have permission to view this page." # Only for log purose, not for the message shown to the user

    def get_queryset(self):
        return Person.objects.order_by("-birth_date")

def subscribe(request):
    try:
        selected_person = Person.objects.get(pk=request.POST["subscribe"])
    except (KeyError, Person.DoesNotExist):
        # Redisplay the question voting form.
        return render(
            request,
            "grestmanager/index.html",
            {
                "person_list": Person.objects.all(),
                "error_message": "You didn't select a person.",
            },
        )
    else:
        # create a new subscription
        subscription = Subscription(date=timezone.now(), related_to=selected_person, price="0")
        subscription.save()
        return HttpResponseRedirect(reverse("grestmanager:detail", args=(selected_person.id,)))  #Uso reverse per non avere l'url hardcoded
    
class SubscriptionCreateView(LoginRequiredMixin, generic.CreateView):
    model = Subscription
    fields = ['related_to'] # Non mettiamo 'user' qui, lo aggiungiamo noi via codice
    template_name = "grestmanager/create_subscription.html"
    
    # Questo dice a Django dove andare dopo il salvataggio
    success_url = reverse_lazy('grestmanager:index')

    def form_valid(self, form):
        # Assegniamo l'utente loggato all'istanza della sottoscrizione
        form.instance.user = self.request.user
        form.instance.date = timezone.now()  # Impostiamo la data di creazione
        form.instance.price = "0"  # Impostiamo un prezzo di default
        return super().form_valid(form)
    
#------Gestione account------
    
class RegisterView(SuccessMessageMixin, generic.CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("grestmanager:index")  # Dopo la registrazione, manda al login
    template_name = "registration/register.html"
    success_message = "Il tuo account è stato creato con successo! Ora puoi effettuare il login."
    
    def form_valid(self, form):
        print("DEBUG: Form valida! Sto per creare il messaggio.")
        response = super().form_valid(form)
        print(f"DEBUG: Success URL è: {self.get_success_url()}")
        return response