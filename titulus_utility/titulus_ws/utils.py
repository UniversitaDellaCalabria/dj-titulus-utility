import logging
import os
from io import BytesIO
from reportlab.pdfgen import canvas

logger = logging.getLogger(__name__)

def get_protocol_dict(**kwargs):
    """
        Costruisce e normalizza il dizionario dei dati per la protocollazione.

        Questa funzione fa da ponte tra i wrapper di alto livello in `services.py` e
        il client SOAP di `protocollo.py`. Prende in input i parametri (kwargs) estratti
        dai modelli e dalle chiamate, validando quelli obbligatori, e restituisce un
        dizionario formattato esattamente per il rendering del template `document.jinja2.xml`.

        Args:
            **kwargs: Variabili di contesto (tipo, oggetto, aoo, destinatario, rif_esterno, ecc.).

        Returns:
            dict: Dizionario normalizzato pronto per essere passato a `Protocollo()`.

        Raises:
            ValueError: Se mancano parametri obbligatori come 'tipo' o 'oggetto'.
        """
    if 'tipo' not in kwargs or not kwargs['tipo']:
        error_msg = "Il parametro 'tipo' (es. 'arrivo', 'partenza') è obbligatorio."
        logger.error(error_msg)
        raise ValueError(error_msg)

    if 'oggetto' not in kwargs or not kwargs['oggetto']:
        error_msg = "Il parametro 'oggetto' è obbligatorio."
        logger.error(error_msg)
        raise ValueError(error_msg)

    protocol_data = {
        # --- Variabili base ---
        'tipo_documento': kwargs['tipo'],
        'bozza': kwargs.get('bozza', 'no'),
        'oggetto': '{:<20}'.format(kwargs['oggetto']),
        'autore': kwargs.get('autore'),
        'cod_repertorio': kwargs.get('cod_repertorio',None),
        'cod_amm_aoo': kwargs.get('aoo'),

        # --- Variabili Opzionali Base ---
        'voce_indice': kwargs.get('voce_indice'),

        # --- Riferimento interno ---
        'nome_persona_rif_interno': kwargs.get('destinatario'),
        'destinatario_username': kwargs.get('destinatario_username'),
        'destinatario_code': kwargs.get('destinatario_code'),
        'nome_uff_rif_interno': kwargs.get('uo_nome'),
        'cod_uff_rif_interno': kwargs.get('uo'),
        'cod_persona': kwargs.get('cod_persona'),
        'rif_interni_cc': kwargs.get('rif_interni_cc', []),
        'rif_interno_op': kwargs.get('rif_interno_op',None),
        'send_email': kwargs.get('send_email'),

        # --- Riferimento esterno (Refattorizzato, neutrale rispetto al verso) ---
        'nome_rif_esterno': f'{kwargs.get("nome_rif_esterno", "")} {kwargs.get("cognome_rif_esterno", "")}'.strip(),
        'codice_fiscale_rif_esterno': kwargs.get('cod_fis_rif_esterno'),
        'cod_nome_rif_esterno': kwargs.get('cod_fis_rif_esterno'),
        'email_rif_esterno': kwargs.get('email_rif_esterno'),
        'fax_rif_esterno': kwargs.get('fax_rif_esterno', ''),
        'tel_rif_esterno': kwargs.get('tel_rif_esterno', ''),
        'indirizzo': kwargs.get('indirizzo_rif_esterno'),

        # --- Classificazione e Allegati ---
        'classif': kwargs.get('titolario'),
        'cod_classif': kwargs.get('cod_titolario'),
        'allegato': kwargs.get('num_allegati'),

        # --- Notifiche ---
        'invia_notifica_protocollazione': kwargs.get('invia_notifica_protocollazione', False),
        'endpoint_notifica': kwargs.get('endpoint_notifica'),
        'auth_notifica': kwargs.get('auth_notifica',None),
        'label_notifica': kwargs.get('label_notifica','Invio notifica fine ITER'),
        'method_notifica': kwargs.get('method_notifica','POST'),
        'href': kwargs.get('linked_nrecord', None),
    }
    logger.debug(
        f"Dizionario di protocollazione costruito con successo. Tipo: {protocol_data['tipo_documento']}, Bozza: {protocol_data['bozza']}")
    return protocol_data
def _assicura_formato_pdf(contenuto):
    """
    Verifica se il contenuto è un PDF. Se è una semplice stringa/testo,
    lo converte in un PDF valido in memoria usando ReportLab.

    Utile per prevenire l'errore "ISO 32000-1" di Titulus che si verifica
    quando si forza l'estensione '.pdf' su file che binariamente non lo sono.
    """
    logger.debug("Verifica della conformità del contenuto al formato PDF.")
    # Se arriva come stringa, la codifichiamo in byte
    if isinstance(contenuto, str):
        contenuto = contenuto.encode('utf-8')

    # Controlliamo i "magic bytes": un PDF inizia sempre con %PDF
    if contenuto.startswith(b'%PDF'):
        logger.debug("Magic bytes '%PDF' rilevati. Il contenuto è un file PDF valido.")
        return contenuto  # È già un PDF valido, non facciamo nulla!

    # Se non è un PDF, creiamo un PDF al volo con il testo ricevuto
    logger.warning("Il file non è un PDF. Avvio conversione automatica in memoria tramite canvas.")
    testo_str = contenuto.decode('utf-8', errors='ignore')

    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    testo_pdf = p.beginText()
    testo_pdf.setTextOrigin(50, 800)  # Margini x, y
    testo_pdf.setFont("Helvetica", 12)

    # Scriviamo riga per riga per supportare gli "a capo"
    for linea in testo_str.split('\n'):
        testo_pdf.textLine(linea)

    p.drawText(testo_pdf)
    p.showPage()
    p.save()

    logger.debug("Conversione da testo a PDF completata con successo.")
    return buffer.getvalue()


def normalize_attachment(fopen, filename):
    """
    Analizza, valida e normalizza un file allegato destinato a Titulus.
    Esegue un'ispezione profonda (Deep Inspection) dei flussi binari per assegnare
    l'estensione specifica corretta (.docx, .xlsx, .msg, ecc.) anche se il file ne è privo.
    """
    logger.debug(f"Avvio normalizzazione allegato per: '{filename}'")

    # 1. Estrazione dell'estensione dal nome (se presente)
    ext = os.path.splitext(filename)[1].lower()

    ESTENSIONI_PROTETTE = {
        '.zip', '.7z', '.rar', '.tar', '.gz', '.xml', '.json', '.csv',
        '.p7m', '.p7s', '.tsd', '.m7m', '.eml', '.msg',
        '.png', '.jpg', '.jpeg', '.tiff', '.tif',
        '.docx', '.xlsx', '.pptx', '.odt', '.ods', '.odp',
        '.doc', '.xls', '.ppt'
    }

    # Memorizziamo la posizione del puntatore e leggiamo i Magic Bytes iniziali
    if hasattr(fopen, 'seek'):
        fopen.seek(0)
    magic_bytes = fopen.read(4)
    fopen.seek(0)

    # =========================================================================
    # CASO 1: L'estensione è già esplicita e protetta -> Passa inalterato
    # =========================================================================
    if ext in ESTENSIONI_PROTETTE:
        logger.info(f"File '{filename}' ha già un'estensione protetta nota ({ext}). Conversione saltata.")
        return fopen, filename

    # =========================================================================
    # CASO 2: Il file è o dichiara di essere un PDF
    # =========================================================================
    elif ext == '.pdf' or magic_bytes == b'%PDF':
        if magic_bytes != b'%PDF':
            logger.warning(f"Il file '{filename}' ha estensione .pdf ma non è valido. Rigenerazione in corso...")
            contenuto_grezzo = fopen.read()
            pdf_bytes = _assicura_formato_pdf(contenuto_grezzo)
            return BytesIO(pdf_bytes), (filename if filename.lower().endswith('.pdf') else f"{filename}.pdf")
        return fopen, (filename if filename.lower().endswith('.pdf') else f"{filename}.pdf")

    # =========================================================================
    # CASO 3: Il file NON ha estensione (ext == ""). DEEP INSPECTION BINARIA
    # =========================================================================
    elif ext == "":

        # --- 3a. Il file inizia per 'PK' -> Contenitore ZIP (Office Moderno / Archivi) ---
        if magic_bytes.startswith(b'PK\x03\x04'):
            try:
                detected_ext = '.zip'  # Fallback standard
                current_pos = fopen.tell()
                fopen.seek(0)

                # Apriamo l'archivio in memoria senza estrarlo per leggerne l'indice dei file
                with zipfile.ZipFile(fopen, 'r') as z:
                    file_list = z.namelist()

                    if 'word/document.xml' in file_list:
                        detected_ext = '.docx'
                    elif 'xl/workbook.xml' in file_list:
                        detected_ext = '.xlsx'
                    elif 'ppt/presentation.xml' in file_list:
                        detected_ext = '.pptx'
                    elif 'mimetype' in file_list:
                        mimetype_content = z.read('mimetype').decode('utf-8', errors='ignore').strip()
                        if 'opendocument.text' in mimetype_content:
                            detected_ext = '.odt'
                        elif 'opendocument.spreadsheet' in mimetype_content:
                            detected_ext = '.ods'
                        elif 'opendocument.presentation' in mimetype_content:
                            detected_ext = '.odp'

                fopen.seek(current_pos)  # Ripristiniamo il puntatore
                logger.warning(f"Deep Inspection ZIP: Rilevato formato specifico '{detected_ext}' per '{filename}'")
                return fopen, f"{filename}{detected_ext}"
            except Exception as e:
                logger.error(f"Errore durante la deep inspection dello ZIP: {e}")
                if hasattr(fopen, 'seek'):
                    fopen.seek(0)
                return fopen, f"{filename}.zip"

        # --- 3b. Il file inizia per OLE Compound File -> Vecchi formati Office / Outlook MSG ---
        elif magic_bytes.startswith(b'\xd0\xcf\x11\xe0'):
            try:
                detected_ext = '.doc'  # Fallback standard
                current_pos = fopen.tell()
                fopen.seek(0)
                # Analizziamo i primi 4KB alla ricerca dei marker di settore OLE
                header_chunk = fopen.read(4096)
                fopen.seek(current_pos)

                if b'WordDocument' in header_chunk:
                    detected_ext = '.doc'
                elif b'Workbook' in header_chunk or b'Book' in header_chunk:
                    detected_ext = '.xls'
                elif b'__substg1.0' in header_chunk:
                    detected_ext = '.msg'  # File di Outlook Mail
                elif b'PowerPoint' in header_chunk:
                    detected_ext = '.ppt'

                logger.warning(f"Deep Inspection OLE: Rilevato formato specifico '{detected_ext}' per '{filename}'")
                return fopen, f"{filename}{detected_ext}"
            except Exception:
                if hasattr(fopen, 'seek'):
                    fopen.seek(0)
                return fopen, f"{filename}.doc"

        # --- 3c. Buste Crittografiche (.p7m, .tsd, .m7m) ---
        elif magic_bytes.startswith(b'\x30\x82'):
            return fopen, f"{filename}.p7m"

        # --- 3d. Email standard (.eml) ---
        elif magic_bytes.lower().startswith(b'from') or magic_bytes.lower().startswith(b'retu'):
            return fopen, f"{filename}.eml"

        # --- 3e. Immagini e Scansioni (.png, .jpg, .tiff) ---
        elif magic_bytes.startswith(b'\x89PNG'):
            return fopen, f"{filename}.png"
        elif magic_bytes.startswith(b'\xff\xd8\xff'):
            return fopen, f"{filename}.jpg"
        elif magic_bytes.startswith(b'II*\x00') or magic_bytes.startswith(b'MM\x00*'):
            return fopen, f"{filename}.tiff"

        # --- 3f. File di testo strutturati (.xml, .json) ---
        elif magic_bytes.startswith(b'<?xm'):
            return fopen, f"{filename}.xml"
        elif magic_bytes.startswith(b'{') or magic_bytes.startswith(b'['):
            return fopen, f"{filename}.json"

    # =========================================================================
    # CASO 4 (FALLBACK): Testo semplice o stringhe fittizie dei test
    # =========================================================================
    logger.info(f"Il file '{filename}' è testo semplice o non riconosciuto. Conversione in PDF.")
    contenuto_grezzo = fopen.read()
    pdf_bytes = _assicura_formato_pdf(contenuto_grezzo)
    return BytesIO(pdf_bytes), f"{filename}.pdf"