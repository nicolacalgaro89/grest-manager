import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User, Permission, Group

from .models import Person, Event, Subscription, TimeEntry, EntryType


def _make_event(name="Evento", *, active=True, opens_days_ago=1, closes_in_days=30):
    """Crea un evento con finestra iscrizioni configurabile."""
    now = timezone.now()
    return Event.objects.create(
        name=name, active=active,
        subscription_opening_date=now - datetime.timedelta(days=opens_days_ago),
        subscription_closing_date=now + datetime.timedelta(days=closes_in_days),
    )


# ----------------------------------------------------------------------------
# 1. Metodi dei modelli (logica di dominio sulle date)
# ----------------------------------------------------------------------------
class ModelMethodTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("u", password="pw")
        cls.person = Person.objects.create(
            name="Anna", surname="Neri", birth_date=timezone.now(),
            tax_code="NRINNA80A01F205Z", managed_by=cls.user,
        )

    def test_event_is_subscription_open(self):
        now = timezone.now()
        aperto = _make_event("Aperto", opens_days_ago=1, closes_in_days=1)
        futuro = Event.objects.create(
            name="Futuro", active=True,
            subscription_opening_date=now + datetime.timedelta(days=1),
            subscription_closing_date=now + datetime.timedelta(days=2),
        )
        passato = Event.objects.create(
            name="Passato", active=True,
            subscription_opening_date=now - datetime.timedelta(days=2),
            subscription_closing_date=now - datetime.timedelta(days=1),
        )
        self.assertTrue(aperto.is_subscription_open())
        self.assertFalse(futuro.is_subscription_open())
        self.assertFalse(passato.is_subscription_open())

    def test_subscription_is_active(self):
        attivo = Subscription.objects.create(date=timezone.now(), price="0",
            related_to=self.person, to_event=_make_event("Attivo", active=True))
        evento_spento = Subscription.objects.create(date=timezone.now(), price="0",
            related_to=self.person, to_event=_make_event("Spento", active=False))
        finestra_chiusa = Subscription.objects.create(date=timezone.now(), price="0",
            related_to=self.person, to_event=_make_event("Chiuso", active=True, opens_days_ago=10, closes_in_days=-5))
        self.assertTrue(attivo.is_active())
        self.assertFalse(evento_spento.is_active())
        self.assertFalse(finestra_chiusa.is_active())

    def test_subscription_was_issued_recently(self):
        ev = _make_event()
        recente = Subscription.objects.create(date=timezone.now(), price="0",
            related_to=self.person, to_event=ev)
        vecchia = Subscription.objects.create(
            date=timezone.now() - datetime.timedelta(days=2), price="0",
            related_to=self.person, to_event=_make_event("Altro"))
        self.assertTrue(recente.was_issued_recently())
        self.assertFalse(vecchia.was_issued_recently())


# ----------------------------------------------------------------------------
# 2-3-6. Confine di proprietà / staff su Person e Subscription
# ----------------------------------------------------------------------------
class OwnershipAuthorizationTests(TestCase):
    """managed_by come confine, con eccezione per gli utenti staff."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("staff", password="pw", is_staff=True)
        cls.owner = User.objects.create_user("owner", password="pw")
        cls.other = User.objects.create_user("other", password="pw")
        perms = Permission.objects.filter(content_type__app_label="grestmanager")
        for user in (cls.staff, cls.owner, cls.other):
            user.user_permissions.set(perms)

        cls.person = Person.objects.create(
            name="Anna", surname="Neri",
            birth_date=timezone.now() - datetime.timedelta(days=9000),
            tax_code="NRINNA80A01F205Z", managed_by=cls.owner,
        )
        cls.event = _make_event("Grest Estate")
        cls.subscription = Subscription.objects.create(
            date=timezone.now(), price="0", related_to=cls.person, to_event=cls.event,
        )

    # Lista anagrafiche
    def test_owner_vede_solo_le_proprie_in_lista(self):
        self.client.force_login(self.owner)
        r = self.client.get(reverse("grestmanager:persons"))
        self.assertEqual(r.status_code, 200)
        self.assertIn(self.person, r.context["persons_list"])

    def test_estraneo_non_vede_anagrafiche_altrui_in_lista(self):
        self.client.force_login(self.other)
        r = self.client.get(reverse("grestmanager:persons"))
        self.assertNotIn(self.person, r.context["persons_list"])

    def test_staff_vede_tutte_le_anagrafiche_in_lista(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("grestmanager:persons"))
        self.assertIn(self.person, r.context["persons_list"])

    # Dettaglio
    def test_proprietario_apre_la_propria_anagrafica(self):
        self.client.force_login(self.owner)
        r = self.client.get(reverse("grestmanager:person_detail", kwargs={"person_id": self.person.id}))
        self.assertEqual(r.status_code, 200)

    def test_estraneo_403_su_anagrafica_altrui(self):
        self.client.force_login(self.other)
        r = self.client.get(reverse("grestmanager:person_detail", kwargs={"person_id": self.person.id}))
        self.assertEqual(r.status_code, 403)

    def test_staff_apre_anagrafica_altrui(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("grestmanager:person_detail", kwargs={"person_id": self.person.id}))
        self.assertEqual(r.status_code, 200)

    # Modifica / eliminazione
    def test_estraneo_403_su_modifica_ed_eliminazione(self):
        self.client.force_login(self.other)
        for name in ("person_update", "person_delete"):
            r = self.client.get(reverse(f"grestmanager:{name}", kwargs={"person_id": self.person.id}))
            self.assertEqual(r.status_code, 403, name)

    def test_staff_accede_a_modifica_ed_eliminazione(self):
        self.client.force_login(self.staff)
        for name in ("person_update", "person_delete"):
            r = self.client.get(reverse(f"grestmanager:{name}", kwargs={"person_id": self.person.id}))
            self.assertEqual(r.status_code, 200, name)

    # Iscrizioni (confine via related_to.managed_by)
    def test_estraneo_403_su_dettaglio_iscrizione(self):
        self.client.force_login(self.other)
        r = self.client.get(reverse("grestmanager:subscription_detail",
            kwargs={"person_id": self.person.id, "subscription_id": self.subscription.id}))
        self.assertEqual(r.status_code, 403)

    def test_staff_apre_dettaglio_iscrizione(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("grestmanager:subscription_detail",
            kwargs={"person_id": self.person.id, "subscription_id": self.subscription.id}))
        self.assertEqual(r.status_code, 200)

    def test_estraneo_non_vede_iscrizioni_altrui_in_lista(self):
        self.client.force_login(self.other)
        r = self.client.get(reverse("grestmanager:subscriptions", kwargs={"person_id": self.person.id}))
        self.assertNotIn(self.subscription, r.context["subscription_list"])

    def test_staff_vede_iscrizioni_altrui_in_lista(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("grestmanager:subscriptions", kwargs={"person_id": self.person.id}))
        self.assertIn(self.subscription, r.context["subscription_list"])


# ----------------------------------------------------------------------------
# 3. person_detail mostra solo le iscrizioni attive
# ----------------------------------------------------------------------------
class PersonDetailActiveSubscriptionsTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("owner", password="pw")
        cls.owner.user_permissions.set(Permission.objects.filter(content_type__app_label="grestmanager"))
        cls.person = Person.objects.create(name="Anna", surname="Neri",
            birth_date=timezone.now(), tax_code="NRINNA80A01F205Z", managed_by=cls.owner)
        cls.attiva = Subscription.objects.create(date=timezone.now(), price="0",
            related_to=cls.person, to_event=_make_event("Attivo", active=True))
        cls.non_attiva = Subscription.objects.create(date=timezone.now(), price="0",
            related_to=cls.person, to_event=_make_event("Spento", active=False))

    def test_detail_mostra_solo_iscrizioni_attive(self):
        self.client.force_login(self.owner)
        r = self.client.get(reverse("grestmanager:person_detail", kwargs={"person_id": self.person.id}))
        attive = r.context["active_subscriptions"]
        self.assertIn(self.attiva, attive)
        self.assertNotIn(self.non_attiva, attive)


# ----------------------------------------------------------------------------
# 2 + 6. Regole di SubscriptionCreateView: una sola iscrizione, controllo proprietà
# ----------------------------------------------------------------------------
class SubscriptionCreateRulesTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("staff", password="pw", is_staff=True)
        cls.owner = User.objects.create_user("owner", password="pw")
        cls.other = User.objects.create_user("other", password="pw")
        cls.person = Person.objects.create(name="Anna", surname="Neri",
            birth_date=timezone.now(), tax_code="NRINNA80A01F205Z", managed_by=cls.owner)
        cls.event1 = _make_event("Evento 1")
        cls.event2 = _make_event("Evento 2")

    def _url(self):
        return reverse("grestmanager:subscription_create", kwargs={"person_id": self.person.id})

    def test_prima_iscrizione_consentita(self):
        self.client.force_login(self.owner)
        r = self.client.post(self._url(), {"to_event": self.event1.id})
        self.assertEqual(r.status_code, 302)  # redirect dopo il salvataggio
        self.assertEqual(self.person.subscriptions.count(), 1)

    def test_seconda_iscrizione_rifiutata(self):
        # la persona ha già un'iscrizione
        Subscription.objects.create(date=timezone.now(), price="0",
            related_to=self.person, to_event=self.event1)
        self.client.force_login(self.owner)
        r = self.client.post(self._url(), {"to_event": self.event2.id})
        self.assertEqual(r.status_code, 200)  # form ri-renderizzato con errore
        self.assertEqual(self.person.subscriptions.count(), 1)  # nessuna seconda iscrizione

    def test_estraneo_non_puo_iscrivere_persona_altrui(self):
        self.client.force_login(self.other)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 403)

    def test_staff_puo_iscrivere_persona_altrui(self):
        self.client.force_login(self.staff)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)


# ----------------------------------------------------------------------------
# 8. Parità del confine su TimeEntry
# ----------------------------------------------------------------------------
class TimeEntryAccessTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("staff", password="pw", is_staff=True)
        cls.owner = User.objects.create_user("owner", password="pw")
        cls.other = User.objects.create_user("other", password="pw")
        cls.person = Person.objects.create(name="Anna", surname="Neri",
            birth_date=timezone.now(), tax_code="NRINNA80A01F205Z", managed_by=cls.owner)
        cls.entry = TimeEntry.objects.create(entry_type=EntryType.IN, remarks="ingresso", related_to=cls.person)

    def test_estraneo_non_vede_presenze_altrui(self):
        self.client.force_login(self.other)
        r = self.client.get(reverse("grestmanager:time_entries", kwargs={"person_id": self.person.id}))
        self.assertNotIn(self.entry, r.context["time_entry_list"])

    def test_staff_vede_presenze_altrui(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("grestmanager:time_entries", kwargs={"person_id": self.person.id}))
        self.assertIn(self.entry, r.context["time_entry_list"])

    def test_estraneo_403_su_creazione_presenza_altrui(self):
        self.client.force_login(self.other)
        r = self.client.get(reverse("grestmanager:time_entry_create", kwargs={"person_id": self.person.id}))
        self.assertEqual(r.status_code, 403)

    def test_staff_accede_a_creazione_presenza_altrui(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("grestmanager:time_entry_create", kwargs={"person_id": self.person.id}))
        self.assertEqual(r.status_code, 200)


# ----------------------------------------------------------------------------
# 4-5-7. Autenticazione, permessi di modello, assegnazione di managed_by
# ----------------------------------------------------------------------------
class AuthAndPermissionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("owner", password="pw")
        cls.person = Person.objects.create(name="Anna", surname="Neri",
            birth_date=timezone.now(), tax_code="NRINNA80A01F205Z", managed_by=cls.owner)
        # utente loggato ma senza permessi di modello
        cls.senza_permessi = User.objects.create_user("nopermessi", password="pw")

    def test_utente_non_autenticato_reindirizzato_al_login(self):
        # person_create usa il solo LoginRequiredMixin: l'anonimo viene mandato al login
        r = self.client.get(reverse("grestmanager:person_create"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r.url)

    def test_utente_senza_permesso_403_sulla_lista(self):
        self.client.force_login(self.senza_permessi)
        r = self.client.get(reverse("grestmanager:persons"))
        self.assertEqual(r.status_code, 403)

    def test_person_create_assegna_managed_by_all_utente(self):
        self.client.force_login(self.senza_permessi)  # create richiede solo il login
        r = self.client.post(reverse("grestmanager:person_create"), {
            "name": "Marco", "surname": "Rossi",
            "birth_date": "2010-05-01", "tax_code": "RSSMRC10E41F205A",
        })
        self.assertEqual(r.status_code, 302)
        creata = Person.objects.get(tax_code="RSSMRC10E41F205A")
        self.assertEqual(creata.managed_by, self.senza_permessi)


# ----------------------------------------------------------------------------
# 9. RegisterView aggiunge il nuovo utente al gruppo BaseUsers
# ----------------------------------------------------------------------------
class RegisterViewTests(TestCase):

    def _register(self):
        return self.client.post(reverse("grestmanager:register"), {
            "username": "nuovo",
            "password1": "Grest!2026xyz",
            "password2": "Grest!2026xyz",
            "usable_password": "true",  # campo presente in Django 5.1+, ignorato altrimenti
        })

    def test_nuovo_utente_aggiunto_a_baseusers(self):
        gruppo = Group.objects.create(name="BaseUsers")
        r = self._register()
        self.assertEqual(r.status_code, 302)
        utente = User.objects.get(username="nuovo")
        self.assertIn(gruppo, utente.groups.all())

    def test_registrazione_non_crasha_senza_gruppo_baseusers(self):
        # Senza il gruppo l'utente viene comunque creato (l'errore è solo loggato)
        r = self._register()
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username="nuovo").exists())
