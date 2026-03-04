from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse
from django.views import generic
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import PermissionDenied
# from django.template import loader

from django.urls import reverse, reverse_lazy   
from django.utils import timezone
from .models import Person, Subscription
from .forms import PersonForm
from django.contrib.auth.models import Group          


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

# def index(request):
#     person_list = Person.objects.order_by("-birth_date")[:5]
#     context = {"person_list": person_list}
#     return render(request, "grestmanager/index.html", context)

# E' solo una landing page, non ha bisogno di dati dinamici, quindi non passo nessun contesto
def index(request):
     return render(request, "grestmanager/index.html")
 
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

  
# @login_required
# @permission_required("grestmanager.add_person", raise_exception=True) Non funziona con le class based view, per questo uso i mixin
# class PersonsView(generic.ListView):
#     template_name = "grestmanager/persons.html"
#     context_object_name = "persons_list"

#     def get_queryset(self):
#         """Return the list of persons ordered by birth date."""
#         return Person.objects.order_by("-birth_date")
    
# Mixins MUST come before the generic view in the inheritance list
class PersonsListView(LoginRequiredMixin, PermissionRequiredMixin, generic.ListView):
    template_name = "grestmanager/persons.html"
    context_object_name = "persons_list"
    
    # Permission settings for PermissionRequiredMixin
    permission_required = "grestmanager.add_person"
    raise_exception = True
    
    # permission_denied_message = "You do not have permission to view this page." # Only for log purose, not for the message shown to the user

    def get_queryset(self):
        return Person.objects.order_by("-birth_date").filter(managed_by=self.request.user) # Mostro solo le persone gestite dall'utente loggato

class PersonCreateView(LoginRequiredMixin, generic.CreateView):
    model = Person
    template_name = "grestmanager/person_create.html"
    form_class = PersonForm # Se voglio personalizzare il form, altrimenti Django lo genera da solo in base ai campi specificati sopra
    
    # Questo dice a Django dove andare dopo il salvataggio
    success_url = reverse_lazy('grestmanager:persons')

    def form_valid(self, form):
        # Assegniamo l'utente loggato all'istanza della persona
        form.instance.managed_by = self.request.user
        return super().form_valid(form)

class PersonUpdateView(LoginRequiredMixin, generic.UpdateView):
    model = Person
    template_name = "grestmanager/person_update.html"
    form_class = PersonForm
    # Verifichiamo che l'utente loggato è il gestore della persona che vuole eliminare
    def dispatch(self, request, *args, **kwargs):
        person = self.get_object()
        if person.managed_by != request.user:
            raise PermissionDenied("You do not have permission to update this person.")
        return super().dispatch(request, *args, **kwargs)
    # Questo dice a Django dove andare dopo il salvataggio
    success_url = reverse_lazy('grestmanager:persons')   

class PersonDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = Person
    template_name = "grestmanager/person_delete.html"
    # Verifichiamo che l'utente loggato è il gestore della persona che vuole eliminare
    def dispatch(self, request, *args, **kwargs):
        person = self.get_object()
        if person.managed_by != request.user:
            raise PermissionDenied("You do not have permission to delete this person.")
        return super().dispatch(request, *args, **kwargs)
    # Questo dice a Django dove andare dopo il salvataggio
    success_url = reverse_lazy('grestmanager:persons')    


# class SubscriptionsListView(LoginRequiredMixin, PermissionRequiredMixin, generic.ListView):
#     template_name = "grestmanager/subscriptions.html"
#     context_object_name = "subscriptions_list"
#     permission_required = "grestmanager.add_subscription"

#     def get_queryset(self):
#         """Return the last five issued subscriptions."""
#         return Subscription.objects.order_by("-date").filter(related_to__managed_by=self.request.user, related_to__pk=self.kwargs["person_id"]) # Filtro le sottoscrizioni per mostrare solo quelle relative alla persona specificata nell'url e gestite dall'utente loggato

# Sono costretto a usare una function based view per poter usare i decoratori di login e permission, altrimenti con le class based view dovrei usare i mixin, ma non riesco a farli funzionare insieme alla logica di filtraggio delle sottoscrizioni per persona e utente loggato, quindi preferisco questa soluzione più semplice
@login_required
@permission_required("grestmanager.add_subscription", raise_exception=True) #Non funziona con le class based view, per questo uso i mixin
def subscriptions(request, person_id):
    person = get_object_or_404(Person, id=person_id) # Recuperi la persona dall'URL
    subscription_list = Subscription.objects.order_by("-date").filter(related_to__managed_by=request.user, related_to=person) # Filtro le sottoscrizioni per mostrare solo quelle relative alla persona specificata nell'url e gestite dall'utente loggato
    context = {"subscription_list": subscription_list, "person": person} # Passo anche la persona al contesto per poterla mostrare nella pagina
    return render(request, "grestmanager/subscriptions.html", context)

class SubscriptionCreateView(LoginRequiredMixin, generic.CreateView):
    model = Subscription
    fields = ['to_event'] # Non mettiamo 'user' qui, lo aggiungiamo noi via codice
    template_name = "grestmanager/subscription_create.html"

    # passo person_id al contesto per poterlo usare nel template
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        person_id = self.kwargs.get('person_id')
        person = get_object_or_404(Person, id=person_id)
        context['person'] = person
        return context

    def form_valid(self, form):
        # 1. Recupera l'ID della persona dall'URL (URLconf)
        person_id = self.kwargs.get('person_id')
        
        # 2. Recupera l'oggetto Person o restituisce 404
        person = get_object_or_404(Person, id=person_id)

        if person.subscriptions.count() > 1:
            form.add_error(None, "Questa persona è già iscritta.")
            return self.form_invalid(form)
        
        # 3. Collega la persona all'istanza della sottoscrizione che sta per essere creata
        form.instance.related_to = person
        form.instance.date = timezone.now()  # Impostiamo la data di creazione
        form.instance.price = "0"  # Impostiamo un prezzo di default
        
        # 4. Chiama il metodo originale per salvare i dati
        return super().form_valid(form)

    def get_success_url(self):
        # Dopo il salvataggio, torna alla lista delle iscrizioni di quella persona
        return reverse_lazy('grestmanager:subscriptions', kwargs={'person_id': self.kwargs['person_id']})

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
    
#------Gestione account------
    
class RegisterView(SuccessMessageMixin, generic.CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy("grestmanager:index")  # Dopo la registrazione, manda al login
    template_name = "registration/register.html"
    success_message = "Il tuo account è stato creato con successo! Ora puoi effettuare il login."
    
    def form_valid(self, form):
        print("DEBUG: Form valida! Sto per creare il messaggio.")
        form.instance.username = form.cleaned_data.get("username")  # Imposta il nome utente prima di salvare
        response = super().form_valid(form)
        try:
            base_group = Group.objects.get(name='BaseUsers')
            self.object.groups.add(base_group)
        except Group.DoesNotExist:
            # Gestisci il caso in cui il gruppo non esista ancora nel DB
            print("ERRORE: Il gruppo 'BaseUsers' non esiste!")
        print(f"DEBUG: Success URL è: {self.get_success_url()}")
        return response