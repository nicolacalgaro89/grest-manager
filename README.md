# Grest Manager
Gestionale GREST

# Concetti base
La view è l'oggetto che gestisce le informazioni da e per il client. Alcune view rispondono a chiamate GET e restituiscono un template popolato con i valori delle variabili in esso contenuti esplicitate. Altre view sono progettate per rispondere a richieste POST che vanno ad agire sul sistema (database, ...) e non renderizzano alcun template ma eventualmente ridirezionano il client verso un'altra pagina.
Le view si possono definire da zero gestendo la reazione alla richiesta in maniera specifica e customizzata per la particolare situazione oppure si può basare su view standar (sono classi in questo caso) che possono essere estese o per le quali si fa l'override di qualche parametro per customizzarne alcuni aspetti.

Gli url definiti in grestmanager-project/grestmanager/urls.py fanno il mapping tra un percorso e una view. Gli url hanno un nome che li svincola dal percorso stesso che quindi può essere cambiato a piacimento senza dover riportare la modifica in tutto il software. Se la variabile app_name viene valorizzata nel resto dell'applicazione bisogna fare riferimento all'url tramite la designazione app_name:url_name.

Esitono pacchetti di url come quando si aggiunge `path("accounts/", include("django.contrib.auth.urls"))` che hanno delle view preconfigurate, le quali a loro volta cercano i template da restituire in determinate posizioni. Se non li trovano in quelle posizioni fanno il fallback su altre cartelle specifiche. Per far funzionare questi url è necessario che siano aggiunti a livello core e non nell'applicazione. Anche i template vanno messi nel percorso definito nei settings nella variabile TEMPLATE.DIRS+/registration. Quando si aggiungono applicazioni terze questa è una situazione tipica.

# Comandi base di Django
```
python manage.py makemigrations grestmanager
python manage.py sqlmigrate grestmanager 0003
python manage.py migrate
```

# Come usare django-registration per migliorare il sistema di registrazione
- Si installa l'applicazione con
```
    pip install django-registration
```
- Si aggiunge alle INSTALLED_APPS in grestmanager-project/core/settings.py:
```
INSTALLED_APPS = [
    'grestmanager.apps.GrestmanagerConfig',
    ...
```
- Si migra il database:
```
python manage.py migrate
```
- Si usano i template nella cartella predefinita grestmanager-project/templates/django_registration. Le views dell'applicazione puntano ai templates con questi nomi e in questa posizione. I templates sono molto semplice e in pratica hanno il solo scopo di visualizzare le form quando ci sono. Ci sono anche dei template .txt per definire il corpo delle mails che utilizzanod delle variabili specifiche. Le mail vengono utilizzate per attivare gli accounts.
- In grestmanager-project/core/urls.py si inseriscono gli urlpatterns 
```
    path("accounts/", include("django_registration.backends.activation.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
```
- Per far si che la cartella predefinita per i templates sia vista da django è necessario inserirla in grestmanager-project/core/settings.py
```
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        ...
```
- In grestmanager-project/core/settings.py è necessario inserire almeno i seguenti settings:
```
    ACCOUNT_ACTIVATION_DAYS = 7 # One-week activation window
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```
Per utilizzare django-registration al meglio bisognerebbe configurare un server smtp con un servizio che non vada a finire direttamente nella spam. Di solito questi servizi sono costosi (tipo sendgrid.com) e quindi per il momento ci si accontenta di una autenticazione senza verifica della mail.
Un'applicazione alternativa che comprende anche alcuni SSO è django-allauth. 

# Gestire il database

La sequenza perfetta per un reset totale di un'app è:
```
python manage.py migrate nome_app zero (Svuota il DB)
```
Opzionale: Cancella i file dentro la cartella migrations/ (tranne __init__.py) se vuoi ricominciare la cronologia da 0001.
```
python manage.py makemigrations nome_app (Crea il nuovo schema dai modelli attuali)
```
```
python manage.py migrate nome_app (Applica lo schema al DB)
```

C'è un dettaglio fondamentale: migrate non guarda direttamente i models.py, ma guarda i file dentro la cartella migrations/ che sono stati costruiti man mano con makemigrations. Se non vengono rimossi si rischia di non ripulire il database come si vorrebbe da un reset completo.

Nel caso in cui si siano installate app di terze parti che hanno modificato il database invece non si può far altro che cancellare il database, rimuovere tutti i file e la cache nella cartella grestmanager-project/grestmanager/migrations e grestmanager-project/core e quindi ripartire con i comandi:
```
python manage.py makemigrations grestmanager
python manage.py migrate
```  
A quel punto il database viene rigenerato completamente.

# Per usare .env in Django
Esempio .env:
```
DEBUG=True
SECRET_KEY=tua-chiave-segreta-molto-lunga
DATABASE_URL=sqlite:///db.sqlite3
# Esempio per Postgres: postgres://user:password@localhost:5432/dbname
```
## Usando django-environ
```
pip install django-environ
```
All'inizio di settings.py
```
import environ

# 1. Inizializza environ
env = environ.Env(
    # imposta i valori di default (opzionale)
    DEBUG=(bool, False)
)

# 2. Leggi il file .env
environ.Env.read_env(BASE_DIR / '.env')

# 3. Usa le variabili
SECRET_KEY = env('SECRET_KEY')

DEBUG = env('DEBUG')

Per il Database è ancora più comodo
DATABASES = {
    'default': env.db(), # Legge automaticamente DATABASE_URL
}
```

## Usando os.environ
```
import os
from dotenv import load_dotenv # Opzionale, vedi sotto

load_dotenv(BASE_DIR / '.env')  # Carica le variabili d'ambiente dal file .env (opzionale, se usi un file .env)

# Set default values for the environment variables if they’re not already set
os.environ.setdefault("PGDATABASE", "example")
os.environ.setdefault("PGUSER", "username")
os.environ.setdefault("PGPASSWORD", "")
os.environ.setdefault("PGHOST", "localhost")
os.environ.setdefault("PGPORT", "5432")
os.environ.setdefault("SECRET_KEY", "your-secret-key")
os.environ.setdefault("DEBUG", "False")
os.environ.setdefault("ALLOWED_HOSTS", "*")

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
```

# Gestione file statici
In settings.py settare la variabile:
```
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
```
e lanciare
```
python manage.py collectstatic
```
Questo raccoglie tutti i file statici di tutte le cartelle e le mette nella cartella definita. Whitenoise servirà i file statici da quella cartella.