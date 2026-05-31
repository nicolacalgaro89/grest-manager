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
from .models import Person, Subscription, Event, TimeEntry, EntryType
from .forms import PersonForm
from django.contrib.auth.models import Group          

# E' solo una landing page, non ha bisogno di dati dinamici, quindi non passo nessun contesto
# add events list to the context in the future, so I can show them in the index page
class IndexView(generic.ListView):
    template_name = "grestmanager/index.html"
    context_object_name = "active_events"

    def get_queryset(self):
        return Event.objects.filter(active=True)

class EventDetailView(generic.DetailView):
    model = Event
    template_name = "grestmanager/event_detail.html"
    pk_url_kwarg = "event_id"

class PersonDetailView(LoginRequiredMixin, generic.DetailView):
    model = Person
    template_name = "grestmanager/person_detail.html"
    pk_url_kwarg = "person_id"
    
    # Verify that the logged-in user is the manager of the person being viewed
    def dispatch(self, request, *args, **kwargs):
        person = self.get_object()
        if person.managed_by != request.user:
            raise PermissionDenied("You do not have permission to view this person.")
        return super().dispatch(request, *args, **kwargs)
    
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
    pk_url_kwarg = "person_id"
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
    pk_url_kwarg = "person_id"
    # Verifichiamo che l'utente loggato è il gestore della persona che vuole eliminare
    def dispatch(self, request, *args, **kwargs):
        person = self.get_object()
        if person.managed_by != request.user:
            raise PermissionDenied("You do not have permission to delete this person.")
        return super().dispatch(request, *args, **kwargs)
    # Questo dice a Django dove andare dopo il salvataggio
    success_url = reverse_lazy('grestmanager:persons')    

# Sono costretto a usare una function based view per poter usare i decoratori di login e permission, altrimenti con le class based view dovrei usare i mixin, 
# ma non riesco a farli funzionare insieme alla logica di filtraggio delle sottoscrizioni per persona e utente loggato, quindi preferisco questa soluzione più semplice
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
    
class SubscriptionDeleteView(LoginRequiredMixin, generic.DeleteView):
    model = Subscription
    template_name = "grestmanager/subscription_delete.html"
    pk_url_kwarg = "subscription_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription = self.get_object()
        context['person'] = subscription.related_to
        return context

    # Verifichiamo che l'utente loggato è il gestore della persona che vuole eliminare
    def dispatch(self, request, *args, **kwargs):
        subscription = self.get_object()
        if subscription.related_to.managed_by != request.user:
            raise PermissionDenied("You do not have permission to delete this subscription.")
        return super().dispatch(request, *args, **kwargs)

    # Questo dice a Django dove andare dopo il salvataggio
    def get_success_url(self):
        # Dopo il salvataggio, torna alla lista delle iscrizioni di quella persona
        person_id = self.get_object().related_to.id
        return reverse_lazy('grestmanager:subscriptions', kwargs={'person_id': person_id})
    
@login_required
def time_entries(request, person_id):
    person = get_object_or_404(Person, id=person_id) # Recuperi la persona dall'URL
    time_entry_list = TimeEntry.objects.order_by("-timestamp").filter(related_to__managed_by=request.user, related_to=person) # Filtro le voci di tempo per mostrare solo quelle relative alla persona specificata nell'url e gestite dall'utente loggato
    context = {"time_entry_list": time_entry_list, "person": person} # Passo anche la persona al contesto per poterla mostrare nella pagina
    return render(request, "grestmanager/time_entries.html", context)


class TimeEntryCreateView(LoginRequiredMixin, generic.CreateView):
    model = TimeEntry
    template_name = "grestmanager/time_entry_create.html"
    fields = ['entry_type', 'remarks'] # Campi per la creazione di una nuova voce di tempo

    # passo person_id al contesto per poterlo usare nel template
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        person_id = self.kwargs.get('person_id')
        person = get_object_or_404(Person, id=person_id)
        context['person'] = person
        return context

    def get_initial(self):
        initial = super().get_initial()
        entry_type = self.request.GET.get('entry_type')
        if entry_type in [choice[0] for choice in EntryType.choices]:
            initial['entry_type'] = entry_type
        return initial

    def dispatch(self, request, *args, **kwargs):
        person = get_object_or_404(Person, id=self.kwargs.get('person_id'))
        if person.managed_by != request.user:
            raise PermissionDenied("You do not have permission to add a time entry for this person.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # 1. Recupera l'ID della persona dall'URL (URLconf)
        person_id = self.kwargs.get('person_id')
        
        # 2. Recupera l'oggetto Person o restituisce 404
        person = get_object_or_404(Person, id=person_id)
        
        # 3. Collega la persona all'istanza della presenza che sta per essere creata
        form.instance.related_to = person
        
        # 4. Chiama il metodo originale per salvare i dati
        return super().form_valid(form)

    def get_success_url(self):
        # Dopo il salvataggio, torna alla lista delle iscrizioni di quella persona
        return reverse_lazy('grestmanager:time_entries', kwargs={'person_id': self.kwargs['person_id']})

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