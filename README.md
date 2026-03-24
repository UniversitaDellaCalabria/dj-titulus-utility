# dj-titulus-utility 🏛️

Una reusable app per Django che fornisce strumenti, utility e template XML per l'integrazione semplice e veloce con il protocollo SOAP di Titulus (tramite Zeep).

## 📦 Installazione

Attualmente l'app è in fase **Beta**. Puoi installarla direttamente dal repository GitHub tramite `pip`:

```bash
pip install git+https://github.com/UniversitaDellaCalabria/dj-titulus-utility.git@v0.1.0-beta.1
```

## ⚙️ Configurazione Base

Aggiungi l'app al file `settings.py` del tuo progetto Django, all'interno della lista `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ... altre app ...
    'titulus_utility',
]
```

## 🛠️ Configurazione Avanzata (Settings)

L'app è dotata di configurazioni di default, ma puoi (e devi) sovrascriverle nel `settings.py` (o `localsettings.py`) del tuo progetto principale. 

Ecco un esempio completo di tutte le variabili a disposizione. Copia quelle che ti servono nel tuo file di configurazione:

```python
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
# PARAMETRI DI PRODUZIONE E SVILUPPO (Usati se test=False)
# ---------------------------------------------------------
# Esempio per gestire ambienti diversi in base a una variabile DEV
if DEV:
    TITULUS_PROTOCOL_URL = 'https://titulus-preprod.dominio.it/ws'
    TITULUS_NAMESPACE_NS2 = '{titulus pre-prod URL namespace}'
else:
    TITULUS_PROTOCOL_URL = 'https://titulus-prod.dominio.it/ws'
    TITULUS_NAMESPACE_NS2 = '{titulus prod URL namespace}'

# Autore di default inserito nel documento. 
# (Se non definito, tenta di dedurlo dal nome app e dominio).
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

# Utente usato come rif esterno/interno per i test
# TITULUS_FIRST_NAME_USER_TEST='Mario'
# TITULUS_LAST_NAME_USER_TEST='Rossi'
# TITULUS_FISCAL_CODE_USER_TEST='RSSMRA...'
# TITULUS_EMAIL_USER_TEST='mario.rossi@tuaistituzione.it'

# Altre utility di test
# TITULUS_ATTACHMENT_FOLDER_TEST = 'cartella_allegati_di_test'
# TITULUS_PROTOCOL_SEND_MAIL_DEBUG = False
# TITULUS_TEST_NOTIFICATION_ENDPOINT='https://tuo.dominio.it/webhook'

# ---------------------------------------------------------
# TEMPLATE JINJA2 PERSONALIZZATI (Opzionali)
# ---------------------------------------------------------
# Decommenta per usare i tuoi XML custom invece di quelli di default dell'app.
# TITULUS_TEMPLATE_DOCUMENT_JINJAXML = BASE_DIR / 'custom_templates' / 'document.jinja2.xml'
# TITULUS_FASCICOLO_PATH = BASE_DIR / 'custom_templates' / 'fascicolo.jinja2.xml'
# TITULUS_PROTOCOL_TEST_XML = BASE_DIR / 'custom_templates' / 'test_document.jinja2.xml'
```

## 🚀 Esempi di Utilizzo

Il modulo `services.py` permette di gestire facilmente le casistiche principali. Le funzioni accettano il parametro opzionale `test=True`, ideale per puntare all'ambiente di collaudo usando le variabili `TITULUS_*_TEST` definite nei settings.

### 1. Protocollo in Arrivo (Diretto)
```python
from titulus_utility import services

risultato = services.protocolla_arrivo(
    user=request.user, 
    subject="Oggetto del protocollo in arrivo",
    credential_ws_protocollo=cred,
    configuration_ws_protocollo=conf,
    principal_file_name="documento_principale.pdf",
    principal_file=b"Contenuto binario...",
    # attachments=["allegato1.pdf"],
    # attachments_folder="percorso/cartella/allegati"
)

print(f"Protocollo: {risultato.get('numero')}")
```

### 2. Protocollo in Partenza (Diretto)
```python
from titulus_utility import services

risultato = services.protocolla_partenza(
    subject="Oggetto del protocollo in partenza",
    credential_ws_protocollo=cred,
    configuration_ws_protocollo=conf,
    principal_file_name="lettera_partenza.pdf",
    principal_file=b"Contenuto binario...",
)

print(f"Protocollo: {risultato.get('numero')}")
```

### 3. Avvio Iter / Creazione Bozza
Titulus restituirà un **nrecord** (numero di record) invece di un numero di protocollo definitivo.

```python
from titulus_utility import services

risultato_iter = services.avvia_iter_arrivo(
    user=request.user,
    subject="Documento in arrivo da approvare",
    voce_indice="Iter Approva e Firma",  
    credential_ws_protocollo=cred,
    configuration_ws_protocollo=conf,
    principal_file_name="bozza_arrivo.pdf",
    principal_file=b"Contenuto binario...",
    invia_notifica=True 
)

print(f"Bozza creata! ID Record: {risultato_iter.get('nrecord')}")
```

## 🛠️ Sviluppo Locale e Testing

Per contribuire allo sviluppo dell'app:

1. Clona il repository.
2. Crea un ambiente virtuale e installa le dipendenze.
3. Lancia i test Django (assicurati di aver configurato il file `localsettings.py` con le credenziali):
   ```bash
   python manage.py test titulus_utility
   ```