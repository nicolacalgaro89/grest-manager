import datetime
from decimal import Decimal

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
        attivo = Subscription.objects.create(date=timezone.now(),
            related_to=self.person, to_event=_make_event("Attivo", active=True))
        evento_spento = Subscription.objects.create(date=timezone.now(),
            related_to=self.person, to_event=_make_event("Spento", active=False))
        finestra_chiusa = Subscription.objects.create(date=timezone.now(),
            related_to=self.person, to_event=_make_event("Chiuso", active=True, opens_days_ago=10, closes_in_days=-5))
        self.assertTrue(attivo.is_active())
        self.assertFalse(evento_spento.is_active())
        self.assertFalse(finestra_chiusa.is_active())

    def test_subscription_was_issued_recently(self):
        ev = _make_event()
        recente = Subscription.objects.create(date=timezone.now(),
            related_to=self.person, to_event=ev)
        vecchia = Subscription.objects.create(
            date=timezone.now() - datetime.timedelta(days=2),
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
            date=timezone.now(), related_to=cls.person, to_event=cls.event,
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

    # Colonna "Gestito da" (solo per lo staff)
    def test_staff_vede_colonna_gestito_da(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("grestmanager:persons"))
        self.assertContains(r, "Gestito da")               # intestazione colonna
        self.assertContains(r, self.owner.username)         # username del gestore

    def test_non_staff_non_vede_colonna_gestito_da(self):
        self.client.force_login(self.owner)
        r = self.client.get(reverse("grestmanager:persons"))
        self.assertNotContains(r, "Gestito da")

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
        cls.attiva = Subscription.objects.create(date=timezone.now(),
            related_to=cls.person, to_event=_make_event("Attivo", active=True))
        cls.non_attiva = Subscription.objects.create(date=timezone.now(),
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
        Subscription.objects.create(date=timezone.now(),
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
        cls.event = _make_event("Grest Estate")
        cls.entry = TimeEntry.objects.create(entry_type=EntryType.IN, remarks="ingresso",
            related_to=cls.person, to_event=cls.event)

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

    # Evento sulla presenza
    def test_dropdown_evento_solo_attivi(self):
        evento_spento = _make_event("Spento", active=False)
        self.client.force_login(self.owner)
        r = self.client.get(reverse("grestmanager:time_entry_create", kwargs={"person_id": self.person.id}))
        eventi = list(r.context["form"].fields["to_event"].queryset)
        self.assertIn(self.event, eventi)
        self.assertNotIn(evento_spento, eventi)

    def test_parametro_event_preseleziona_evento(self):
        self.client.force_login(self.owner)
        url = reverse("grestmanager:time_entry_create", kwargs={"person_id": self.person.id})
        r = self.client.get(url + f"?event={self.event.id}")
        self.assertEqual(str(r.context["form"].initial.get("to_event")), str(self.event.id))

    def test_creazione_presenza_salva_evento(self):
        self.client.force_login(self.owner)
        url = reverse("grestmanager:time_entry_create", kwargs={"person_id": self.person.id})
        r = self.client.post(url, {"entry_type": EntryType.IN, "to_event": self.event.id, "remarks": "prova"})
        self.assertEqual(r.status_code, 302)
        creata = TimeEntry.objects.filter(related_to=self.person, remarks="prova").first()
        self.assertIsNotNone(creata)
        self.assertEqual(creata.to_event, self.event)


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
        # Anche le view con controllo di proprietà reindirizzano l'anonimo al login (non 403)
        urls = [
            reverse("grestmanager:person_create"),
            reverse("grestmanager:person_detail", kwargs={"person_id": self.person.id}),
            reverse("grestmanager:person_update", kwargs={"person_id": self.person.id}),
            reverse("grestmanager:person_delete", kwargs={"person_id": self.person.id}),
        ]
        for url in urls:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn("/accounts/login/", r.url, url)

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


# ----------------------------------------------------------------------------
# Export CSV delle anagrafiche (solo staff)
# ----------------------------------------------------------------------------
class CsvExportTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("staff", password="pw", is_staff=True)
        cls.owner = User.objects.create_user("owner", password="pw")
        # due anagrafiche di gestori diversi: l'export staff deve contenerle entrambe
        cls.p1 = Person.objects.create(name="Anna", surname="Neri", birth_date=timezone.now(),
            tax_code="NRINNA80A01F205Z", managed_by=cls.owner)
        cls.p2 = Person.objects.create(name="Bruno", surname="Verdi", birth_date=timezone.now(),
            tax_code="VRDBRN70B02F205Y", managed_by=cls.staff)

    def test_staff_scarica_csv_con_tutte_le_anagrafiche(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("grestmanager:persons_export_csv"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "text/csv")
        self.assertIn("anagrafiche.csv", r["Content-Disposition"])
        body = r.content.decode("utf-8")
        self.assertIn("Nome,Cognome,Data di Nascita,Codice Fiscale,Gestito da", body)
        self.assertIn("NRINNA80A01F205Z", body)   # anagrafica di owner
        self.assertIn("VRDBRN70B02F205Y", body)   # anagrafica di staff
        self.assertIn("owner", body)              # colonna "Gestito da"

    def test_non_staff_403_su_export(self):
        self.client.force_login(self.owner)
        r = self.client.get(reverse("grestmanager:persons_export_csv"))
        self.assertEqual(r.status_code, 403)


# ----------------------------------------------------------------------------
# Badge presenze con QR (persona + evento)
# ----------------------------------------------------------------------------
class PresenceBadgeTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("staff", password="pw", is_staff=True)
        cls.owner = User.objects.create_user("owner", password="pw")
        cls.other = User.objects.create_user("other", password="pw")
        cls.person = Person.objects.create(name="Anna", surname="Neri", birth_date=timezone.now(),
            tax_code="NRINNA80A01F205Z", managed_by=cls.owner)
        cls.event = _make_event("Grest Estate")
        cls.subscription = Subscription.objects.create(date=timezone.now(),
            related_to=cls.person, to_event=cls.event)

    def _url(self):
        return reverse("grestmanager:presence_badge",
                       kwargs={"person_id": self.person.id, "event_id": self.event.id})

    def test_owner_apre_il_badge(self):
        self.client.force_login(self.owner)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)

    def test_staff_apre_il_badge(self):
        self.client.force_login(self.staff)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)

    def test_estraneo_403_sul_badge(self):
        self.client.force_login(self.other)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 403)

    def test_badge_contiene_link_assoluti_in_out_e_qr(self):
        self.client.force_login(self.owner)
        body = self.client.get(self._url()).content.decode()
        # URL assoluti (host della richiesta) con i parametri corretti
        self.assertIn("http://testserver", body)
        self.assertIn(f"entry_type=IN&amp;event={self.event.id}", body)
        self.assertIn(f"entry_type=OUT&amp;event={self.event.id}", body)
        # etichette e QR (due SVG)
        self.assertIn("ENTRATA", body)
        self.assertIn("USCITA", body)
        self.assertGreaterEqual(body.count("<svg"), 2)

    def test_pulsante_badge_presente_in_person_detail(self):
        self.client.force_login(self.owner)
        r = self.client.get(reverse("grestmanager:person_detail", kwargs={"person_id": self.person.id}))
        self.assertContains(r, self._url())


# ----------------------------------------------------------------------------
# Iscrizione: prezzi, conferma, saldo, revisione (fase 1)
# ----------------------------------------------------------------------------
class SubscriptionPricingTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("staff", password="pw", is_staff=True)
        cls.owner = User.objects.create_user("owner", password="pw")
        cls.person = Person.objects.create(name="Anna", surname="Neri", birth_date=timezone.now(),
            tax_code="NRINNA80A01F205Z", managed_by=cls.owner)
        cls.event = Event.objects.create(
            name="Grest", active=True,
            subscription_opening_date=timezone.now() - datetime.timedelta(days=1),
            subscription_closing_date=timezone.now() + datetime.timedelta(days=30),
            price_morning=Decimal("10"), price_lunch=Decimal("5"),
            price_afternoon=Decimal("8"), price_trip=Decimal("15"),
        )

    def _sub(self, **flags):
        return Subscription.objects.create(date=timezone.now(),
            related_to=self.person, to_event=self.event, **flags)

    def test_calculate_price_somma_fasce_e_gite(self):
        sub = self._sub(week1_morning=True, week1_afternoon=True,
                        week2_morning=True, week2_lunch=True, week2_afternoon=True, week2_trip=True)
        # sett1: 10+8=18 ; sett2: 10+5+8+15=38 ; tot 56
        self.assertEqual(sub.calculate_price(), Decimal("56"))

    def test_calculate_price_zero_senza_fasce(self):
        self.assertEqual(self._sub().calculate_price(), Decimal("0"))

    def test_requires_review_pranzo_senza_giornata_intera(self):
        self.assertTrue(self._sub(week1_morning=True, week1_lunch=True).requires_review())
        self.assertTrue(self._sub(week1_afternoon=True, week1_lunch=True).requires_review())

    def test_requires_review_false_full_day_o_senza_pranzo(self):
        self.assertFalse(self._sub(week1_morning=True, week1_lunch=True, week1_afternoon=True).requires_review())
        self.assertFalse(self._sub(week1_morning=True, week1_afternoon=True).requires_review())
        self.assertFalse(self._sub().requires_review())

    def test_current_price_dinamico_prima_della_conferma(self):
        sub = self._sub(week1_morning=True)  # 10
        self.assertFalse(sub.confirmed)
        self.assertEqual(sub.current_price(), Decimal("10"))
        self.assertTrue(sub.is_editable())

    def test_confirm_congela_prezzo_e_registra_chi_quando(self):
        sub = self._sub(week1_morning=True, week1_lunch=True, week1_afternoon=True)  # 23
        sub.confirm(self.staff)
        sub.refresh_from_db()
        self.assertTrue(sub.confirmed)
        self.assertEqual(sub.confirmed_by, self.staff)
        self.assertIsNotNone(sub.confirmed_at)
        self.assertEqual(sub.confirmed_price, Decimal("23"))
        self.assertFalse(sub.is_editable())
        # i prezzi dell'evento cambiano ma il prezzo confermato resta congelato
        self.event.price_morning = Decimal("100"); self.event.save()
        sub.refresh_from_db()
        self.assertEqual(sub.current_price(), Decimal("23"))

    def test_mark_paid_registra_chi_quando(self):
        sub = self._sub(week1_morning=True)
        sub.mark_paid(self.staff)
        sub.refresh_from_db()
        self.assertTrue(sub.paid)
        self.assertEqual(sub.paid_by, self.staff)
        self.assertIsNotNone(sub.paid_at)
