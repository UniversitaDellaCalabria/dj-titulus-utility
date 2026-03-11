import os
from pathlib import Path


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'yout_secret_key'

DEBUG = True #or False
DEV = True # or False
ALLOWED_HOSTS = []



INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'titulus_utility'
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'your_root_url_conf'

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'it-it'

TIME_ZONE = 'Europe/Rome'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = 'data/static/'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =========================================================
# ================= TITULUS UTILITY CONFIG ================
# =========================================================

# ---------------------------------------------------------
# VARIABILI OBBLIGATORIE
# ---------------------------------------------------------
# Cartella (relativa a MEDIA_ROOT) dove vengono temporaneamente
# salvati/letti i documenti da protocollare o allegare.
TITULUS_DOCUMENT_FOLDER = "protocollo_attachments"


# ---------------------------------------------------------
# PARAMETRI DI PRODUZIONE (Usati se test=False nel client)
# ---------------------------------------------------------
if DEV:
    TITULUS_PROTOCOL_URL = 'https://titulus-preprod.dominio.it/ws'
    TITULUS_NAMESPACE_NS2 = '{titulus pre-prod URL namespace}'
else:
    TITULUS_PROTOCOL_URL = 'https://titulus-prod.dominio.it/ws'
    TITULUS_NAMESPACE_NS2 = '{titulus prod URL namespace}'

# Autore di default inserito nel documento (Se non definito,
# la libreria tenta di dedurlo dal nome app e dominio).
# TITULUS_AUTORE = "Sistema Django"

# Email di default per le comunicazioni di protocollazione
# TITULUS_PROTOCOL_EMAIL_DEFAULT = 'protocollo@example.pec.it'


# ---------------------------------------------------------
# PARAMETRI DI TEST E DEBUG (Usati se test=True nel client)
# ---------------------------------------------------------
# TITULUS_PROTOCOL_TEST_URL = 'https://titulus-test.dominio.it/ws'
# TITULUS_PROTOCOL_TEST_LOGIN = 'utente_test'
# TITULUS_PROTOCOL_TEST_PASSW = 'password_test'

# Dati strutturali per l'ambiente di test
# TITULUS_PROTOCOL_TEST_AOO = 'AOO_TEST'
# TITULUS_PROTOCOL_TEST_AGD = 'AGD_TEST'
# TITULUS_PROTOCOL_TEST_UO = 'UO_TEST'
# TITULUS_PROTOCOL_TEST_UO_RPA = 'RPA_TEST'

# Classificazione e fascicolazione di test
# TITULUS_PROTOCOL_TEST_TITOLARIO = 'I/1'
# TITULUS_PROTOCOL_TEST_FASCICOLO = '2025-I/1.1'
# TITULUS_PROTOCOL_TEST_FASCICOLO_ANNO = '2025'

# Flag per inviare effettivamente email durante il test
# TITULUS_PROTOCOL_SEND_MAIL_DEBUG = False

# Testare l'endpoint di avvenuta protocollazione : url pubblicamente accessibile che restituisce 200 ok
# TITULUS_TEST_NOTIFICATION_ENDPOINT='https://tuo.dominio.it/webhook'

# Utente usato come rif esterno /interno per i test (dipendente)
# TITULUS_FIRST_NAME_USER_TEST='Mario'
# TITULUS_LAST_NAME_USER_TEST='Rossi'
# TITULUS_FISCAL_CODE_USER_TEST='RSSMRA...'
# TITULUS_EMAIL_USER_TEST='mario.rossi@tuaistituzione.it'
# TITULUS_ATTACHMENT_FOLDER_TEST=a folder in mediaroot
# ---------------------------------------------------------
# TEMPLATE JINJA2 PERSONALIZZATI (Opzionali)
# ---------------------------------------------------------
# Se vuoi sovrascrivere l'XML di default per la protocollazione
# o la fascicolazione, decommenta e punta ai tuoi file Jinja2.
# TITULUS_TEMPLATE_DOCUMENT_JINJAXML = BASE_DIR / 'custom_templates' / 'document.jinja2.xml'
# TITULUS_FASCICOLO_PATH = BASE_DIR / 'custom_templates' / 'fascicolo.jinja2.xml'

# Template XML specifico usato solo quando si lancia in test=True
# TITULUS_PROTOCOL_TEST_XML = BASE_DIR / 'custom_templates' / 'test_document.jinja2.xml'


# ---------------------------------------------------------
# DIZIONARI E LOGICHE APPLICATIVE (Opzionali)
# ---------------------------------------------------------
# Dizionario per mappare i codici UO a nomi leggibili
# TITULUS_UO_DICT = {
#     'UO_01': 'Segreteria Didattica',
#     'UO_02': 'Risorse Umane',
# }

# Se True, abilita la logica di fascicolazione successiva alla protocollazione
# TITULUS_FASCICOLAZIONE_SEPARATA = False

# Sovrascrittura completa dei namespace SOAP/XML (Sconsigliato a meno di major update di Titulus)
# TITULUS_PROTOCOL_NAMESPACES = {
#     'xsd': '{http://www.w3.org/2001/XMLSchema}',
#     'ns0': '{http://www.kion.it/titulus}',
#     'ns1': '{http://schemas.xmlsoap.org/soap/encoding/}',
#     'ns2': TITULUS_NAMESPACE_NS2,
# }