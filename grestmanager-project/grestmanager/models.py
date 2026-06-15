import datetime
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class Person(models.Model):
    name = models.CharField(max_length=200)
    surname = models.CharField(max_length=200)
    birth_date = models.DateTimeField("birth date")
    tax_code = models.CharField(max_length=200)
    managed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="persons")
    def __str__(self):
        return self.name + " - " + self.birth_date.strftime("%Y-%m-%d %H:%M:%S")
    
class Event(models.Model):
    name = models.CharField(max_length=200)
    active = models.BooleanField(default=True)
    subscription_opening_date = models.DateTimeField("subscription opening date")
    subscription_closing_date = models.DateTimeField("subscription closing date")
    # Prezzi applicati all'iscrizione: per settimana (mattino/pranzo/pomeriggio) e per gita
    price_morning = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    price_lunch = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    price_afternoon = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    price_trip = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    def __str__(self):
        return self.name
    def is_subscription_open(self):
        now = timezone.now()
        return self.subscription_opening_date <= now <= self.subscription_closing_date
    
class Subscription(models.Model):
    date = models.DateTimeField("issuance date")  # storico: data di emissione dell'iscrizione
    related_to = models.ForeignKey(
        "Person",
        on_delete=models.CASCADE,
        related_name="subscriptions")
    to_event = models.ForeignKey(
        "Event",
        on_delete=models.CASCADE,
        related_name="subscriptions")

    # Partecipazione: per ognuna delle 4 settimane, le fasce (mattino/pranzo/pomeriggio) e la gita del venerdì
    week1_morning = models.BooleanField(default=False)
    week1_lunch = models.BooleanField(default=False)
    week1_afternoon = models.BooleanField(default=False)
    week1_trip = models.BooleanField(default=False)
    week2_morning = models.BooleanField(default=False)
    week2_lunch = models.BooleanField(default=False)
    week2_afternoon = models.BooleanField(default=False)
    week2_trip = models.BooleanField(default=False)
    week3_morning = models.BooleanField(default=False)
    week3_lunch = models.BooleanField(default=False)
    week3_afternoon = models.BooleanField(default=False)
    week3_trip = models.BooleanField(default=False)
    week4_morning = models.BooleanField(default=False)
    week4_lunch = models.BooleanField(default=False)
    week4_afternoon = models.BooleanField(default=False)
    week4_trip = models.BooleanField(default=False)

    # Stato/storico di conferma e saldo (gestiti dallo staff)
    confirmed = models.BooleanField(default=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="confirmed_subscriptions")
    confirmed_price = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="paid_subscriptions")

    def __str__(self):
        return self.date.strftime("%Y-%m-%d %H:%M:%S") + " - " + self.to_event.name

    def was_issued_recently(self):
        return self.date >= timezone.now() - datetime.timedelta(days=1)

    def is_active(self):
        now = timezone.now()
        return self.to_event.active and self.to_event.subscription_opening_date <= now <= self.to_event.subscription_closing_date

    def calculate_price(self):
        """Prezzo calcolato dinamicamente dalle fasce scelte e dai prezzi dell'evento."""
        event = self.to_event
        total = Decimal("0")
        for week in range(1, 5):
            if getattr(self, f"week{week}_morning"):
                total += event.price_morning
            if getattr(self, f"week{week}_lunch"):
                total += event.price_lunch
            if getattr(self, f"week{week}_afternoon"):
                total += event.price_afternoon
            if getattr(self, f"week{week}_trip"):
                total += event.price_trip
        return total

    def current_price(self):
        """Prezzo da mostrare: lo snapshot se confermata, altrimenti il calcolo dinamico."""
        return self.confirmed_price if self.confirmed else self.calculate_price()

    def is_editable(self):
        """Una volta confermata, l'iscrizione non è più modificabile."""
        return not self.confirmed

    def requires_review(self):
        """Segnala le settimane col pranzo ma senza giornata intera (mattino+pomeriggio):
        combinazioni consentite ma normalmente non accettate, da rivedere per dare
        priorità a chi partecipa l'intera giornata."""
        for week in range(1, 5):
            lunch = getattr(self, f"week{week}_lunch")
            morning = getattr(self, f"week{week}_morning")
            afternoon = getattr(self, f"week{week}_afternoon")
            if lunch and not (morning and afternoon):
                return True
        return False

    def confirm(self, by_user):
        """Conferma l'iscrizione (staff): congela il prezzo e registra chi/quando."""
        self.confirmed = True
        self.confirmed_at = timezone.now()
        self.confirmed_by = by_user
        self.confirmed_price = self.calculate_price()
        self.save()

    def mark_paid(self, by_user):
        """Segna l'iscrizione come saldata (staff): registra chi/quando."""
        self.paid = True
        self.paid_at = timezone.now()
        self.paid_by = by_user
        self.save()
    
class EntryType(models.TextChoices):
    IN = 'IN', _('Inbound')
    OUT = 'OUT', _('Outbound')
    
class TimeEntry(models.Model):

    timestamp = models.DateTimeField(auto_now_add=True)
    
    # L'attributo che salva il tipo di timbratura
    entry_type = models.CharField(
        max_length=3,
        choices=EntryType.choices,
        default=EntryType.IN,
    )
    
    remarks = models.CharField(max_length=200, blank=True)
    
    related_to = models.ForeignKey(
        "Person",
        on_delete=models.CASCADE,
        related_name="time_entries")
    # Evento a cui si riferisce la presenza
    to_event = models.ForeignKey(
        "Event",
        on_delete=models.CASCADE,
        related_name="time_entries",
        verbose_name="Evento")
    def __str__(self):
        return self.timestamp.strftime("%Y-%m-%d %H:%M:%S") + " - " + self.remarks
