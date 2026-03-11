import logging
import os
from io import BytesIO
from reportlab.pdfgen import canvas
from pathlib import Path

from django.utils.translation import gettext_lazy as _
from jinja2 import Template

from titulus_utility.titulus_ws.protocollo import Protocollo
from titulus_utility.titulus_ws.utils import get_protocol_dict
from . import conf as titulus_settings

logger = logging.getLogger(__name__)


def _assicura_formato_pdf(contenuto):
    """
    Verifica se il contenuto è un PDF. Se è una semplice stringa/testo,
    lo converte in un PDF valido in memoria.
    """
    # Se arriva come stringa, la codifichiamo in byte
    if isinstance(contenuto, str):
        contenuto = contenuto.encode('utf-8')

    # Controlliamo i "magic bytes": un PDF inizia sempre con %PDF
    if contenuto.startswith(b'%PDF'):
        return contenuto  # È già un PDF valido, non facciamo nulla!

    # Se non è un PDF, creiamo un PDF al volo con il testo ricevuto
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

    return buffer.getvalue()

def _esegui_flusso_protocollo(
        tipo,
        azione,
        bozza,
        subject,
        rif_esterno_data,
        valid_conf,
        invia_notifica,
        credential_ws_protocollo,
        configuration_ws_protocollo,
        prot_template,
        principal_file_name,
        principal_file,
        attachments_folder,
        attachments,
        test,
        label_notifica,
        method_notifica,
        voce_indice=None
):
    """
    Funzione core fattorizzata per gestire l'intero flusso di comunicazione con Titulus
    (protocollazione base o attivazione iter con notifica).
    """
    if attachments_folder is None:
        attachments_folder = titulus_settings.FOLDER_FILE_PATH

    if prot_template is None:
        with open(titulus_settings.TEMPLATE_DOCUMENT_JINJAXML, 'r',
                  encoding=titulus_settings.PROT_DOC_ENCODING) as f:
            prot_template = f.read()

    # fix zeep key words issue
    subject = subject.upper()

    if test:
        prot_url = titulus_settings.PROTOCOL_TEST_URL
        prot_login = titulus_settings.PROTOCOL_TEST_LOGIN
        prot_passw = titulus_settings.PROTOCOL_TEST_PASSW
        prot_aoo = titulus_settings.PROTOCOL_TEST_AOO
        prot_agd = titulus_settings.PROTOCOL_TEST_AGD
        prot_uo = titulus_settings.PROTOCOL_TEST_UO
        prot_uo_rpa = titulus_settings.PROTOCOL_TEST_UO_RPA
        prot_uo_rpa_username = ""
        prot_uo_rpa_matricola = ""
        prot_send_email = titulus_settings.PROTOCOL_SEND_MAIL_DEBUG
        prot_email = titulus_settings.PROTOCOL_EMAIL_DEFAULT
        prot_titolario = titulus_settings.PROTOCOL_TEST_TITOLARIO
        prot_fascicolo_num = titulus_settings.PROTOCOL_TEST_FASCICOLO
        prot_fascicolo_anno = titulus_settings.PROTOCOL_TEST_FASCICOLO_ANNO

        if titulus_settings.PROTOCOL_TEST_XML:
            with open(titulus_settings.PROTOCOL_TEST_XML, 'r', encoding=titulus_settings.PROT_DOC_ENCODING) as f:
                prot_template = f.read()

        principal_file = principal_file or b"Test"
        principal_file_name = principal_file_name or "test name"
        notification_endpoint = getattr(titulus_settings, 'NOTIFICATION_ENDPOINT_TEST',
                                        None) if invia_notifica else None

    elif not test and valid_conf:
        prot_url = titulus_settings.PROTOCOL_URL
        prot_login = credential_ws_protocollo.protocollo_username
        prot_passw = credential_ws_protocollo.protocollo_password
        prot_aoo = credential_ws_protocollo.protocollo_aoo
        prot_agd = credential_ws_protocollo.protocollo_agd
        prot_uo = configuration_ws_protocollo.protocollo_uo
        prot_uo_rpa = configuration_ws_protocollo.protocollo_uo_rpa
        prot_uo_rpa_username = configuration_ws_protocollo.protocollo_uo_rpa_username
        prot_uo_rpa_matricola = configuration_ws_protocollo.protocollo_uo_rpa_matricola
        prot_send_email = configuration_ws_protocollo.protocollo_send_email
        prot_email = configuration_ws_protocollo.protocollo_email or titulus_settings.PROTOCOL_EMAIL_DEFAULT
        prot_titolario = configuration_ws_protocollo.protocollo_cod_titolario
        prot_fascicolo_num = configuration_ws_protocollo.protocollo_fascicolo_numero
        prot_fascicolo_anno = configuration_ws_protocollo.protocollo_fascicolo_anno
        notification_endpoint = getattr(titulus_settings, 'NOTIFICATION_ENDPOINT', None) if invia_notifica else None

    else:
        raise Exception(_("Missing XML configuration or notification endpoint for production"))

    uo_nome = dict(titulus_settings.UO_DICT).get(prot_uo, prot_uo)

    # Costruiamo il dizionario base combinandolo con i riferimenti esterni (che dipendono da arrivo/partenza)
    protocol_kwargs = dict(
        tipo=tipo,
        bozza=bozza,
        oggetto=subject,
        autore=titulus_settings.TITULUS_AUTORE,
        aoo=prot_aoo,
        agd=prot_agd,
        destinatario=prot_uo_rpa,
        destinatario_username=prot_uo_rpa_username,
        destinatario_code=prot_uo_rpa_matricola,
        send_email=prot_send_email,
        uo_nome=uo_nome,
        uo=prot_uo,
        email_ufficio=prot_email,
        titolario="",
        cod_titolario=prot_titolario,
        num_allegati=1 + len(attachments),
        fascicolo_num=prot_fascicolo_num,
        fascicolo_anno=prot_fascicolo_anno,
        voce_indice=voce_indice,
        label_notifica=label_notifica,
        method_notifica=method_notifica,
        **rif_esterno_data
    )

    if invia_notifica:
        protocol_kwargs['invia_notifica_protocollazione'] = True
        protocol_kwargs['endpoint_notifica'] = notification_endpoint

    protocol_data = get_protocol_dict(**protocol_kwargs)

    wsclient = Protocollo(
        wsdl_url=prot_url,
        username=prot_login,
        password=prot_passw,
        template_xml_flusso=prot_template,
        **protocol_data,
    )

    logger.info(f"Protocollazione richiesta {subject}")
    # --- GESTIONE FLESSIBILE DEL FILE PRINCIPALE ---
    if hasattr(principal_file, 'read'):
        # CASO 1: Oggetto "file-like"
        # (es. request.FILES['doc'], un campo FileField di Django, o un file aperto)
        docPrinc = principal_file
        if hasattr(docPrinc, 'seek'):
            docPrinc.seek(0)

    elif isinstance(principal_file, (str, Path)):
        # CASO 2: Percorso del file (Stringa classica o oggetto pathlib.Path)
        file_path = str(principal_file)
        if os.path.isfile(file_path):
            with open(file_path, 'rb') as f:
                docPrinc = BytesIO(f.read())
        else:
            raise FileNotFoundError(f"Il file specificato non esiste: {file_path}")

    elif isinstance(principal_file, bytes):
        # CASO 3: Byte crudi generati al volo
        docPrinc = BytesIO(principal_file)

    else:
        raise ValueError(
            "Il parametro 'principal_file' deve essere un oggetto file (es. Django File/UploadedFile), "
            "un percorso valido (str o Path) o dei byte crudi."
        )
    # -----------------------------------------------
    # --- TRASFORMAZIONE AUTOMATICA IN PDF ---
    # Leggiamo i primi 4 byte per verificare la firma binaria del file
    magic_bytes = docPrinc.read(4)
    docPrinc.seek(0)  # Riportiamo il puntatore all'inizio

    if magic_bytes != b'%PDF':
        # Non è un PDF (es. è b"Test" o un file di testo semplice).
        # Leggiamo tutto il contenuto grezzo...
        contenuto_grezzo = docPrinc.read()

        # ...lo trasformiamo in un VERO file PDF...
        pdf_bytes = _assicura_formato_pdf(contenuto_grezzo)

        # ...e rimpiazziamo docPrinc con il nuovo PDF in memoria!
        docPrinc = BytesIO(pdf_bytes)
    # -----------------------------------------------
    wsclient.aggiungi_docPrinc(
        fopen=docPrinc, nome_doc=f"{principal_file_name}.pdf", tipo_doc=f"{principal_file_name}.pdf"
    )

    # attachments
    if attachments:
        for v in attachments:
            # 1. Costruiamo il percorso in modo sicuro e cross-platform
            file_path = os.path.join(attachments_folder, v)

            # 2. Apriamo il file e lo passiamo direttamente al client
            with open(file_path, "rb") as f:
                wsclient.aggiungi_allegato(
                    nome=v,
                    descrizione=subject,
                    fopen=f,
                    test=test
                )

    # Esecuzione dell'azione specifica
    if azione == 'protocolla':
        wsclient.protocolla(test=test)
        assert getattr(wsclient, 'numero', None)
        result_key = "numero"
        result_val = wsclient.numero
    elif azione == 'attiva_iter':
        wsclient.salva_bozza_e_attiva_iter(test=test)
        assert getattr(wsclient, 'nrecord', None)
        result_key = "nrecord"
        result_val = wsclient.nrecord

    principal_file_result = {result_key: result_val}

    # Fascicolazione separata
    if titulus_settings.FASCICOLAZIONE_SEPARATA and prot_fascicolo_num:
        # Recupera sia il numero (se protocollato) che nrecord (se bozza/iter)
        doc_num_prot = getattr(wsclient, 'numero', '')
        doc_nrecord = getattr(wsclient, 'nrecord', '')

        try:
            with open(titulus_settings.FASCICOLO_PATH, "r", encoding=titulus_settings.PROT_DOC_ENCODING) as file:
                fasc_template_str = file.read()

            jinja_fasc_template = Template(fasc_template_str)

            fasc = jinja_fasc_template.render(
                fascicolo_physdoc="",
                fascicolo_nrecord="",
                fascicolo_numero=prot_fascicolo_num,
                doc_physdoc="",
                doc_nrecord=doc_nrecord,
                doc_num_prot=doc_num_prot,
                doc_minuta="no"
            )

            wsclient.fascicolaDocumento(fasc)

            # Identificativo per i log: usa il numero se presente, altrimenti nrecord
            doc_id_for_log = doc_num_prot if doc_num_prot else doc_nrecord
            msg = f"Fascicolazione avvenuta: {prot_fascicolo_num} in {doc_id_for_log}"

        except Exception as e:
            doc_id_for_log = doc_num_prot if doc_num_prot else doc_nrecord
            msg = f"Fascicolazione fallita: {prot_fascicolo_num} in {doc_id_for_log} - {e}"

        principal_file_result["message"] = msg
        logger.info(msg)

    return principal_file_result


# ==============================================================================================
# WRAPPERS PUBBLICI (Semplificati e Rinominati)
# ==============================================================================================

def protocolla_arrivo(
        user,
        subject,
        credential_ws_protocollo=None,
        configuration_ws_protocollo=None,
        prot_template=None,
        principal_file_name="",
        principal_file=b"",
        attachments_folder=None,
        attachments=[],
        test=False,
        label_notifica=None, method_notifica=None):
    """
    Protocolla un documento in arrivo.
    """
    valid_conf = credential_ws_protocollo and configuration_ws_protocollo

    rif_esterno_data = {
        'nome_rif_esterno': user.first_name,
        'cognome_rif_esterno': user.last_name,
        'cod_fis_rif_esterno': user.taxpayer_id,
        'email_rif_esterno': user.email,
    }

    return _esegui_flusso_protocollo(
        tipo='arrivo',
        azione='protocolla',
        bozza='no',
        subject=subject,
        rif_esterno_data=rif_esterno_data,
        valid_conf=valid_conf,
        invia_notifica=False,
        credential_ws_protocollo=credential_ws_protocollo,
        configuration_ws_protocollo=configuration_ws_protocollo,
        prot_template=prot_template,
        principal_file_name=principal_file_name,
        principal_file=principal_file,
        attachments_folder=attachments_folder,
        attachments=attachments,
        test=test,
        label_notifica=label_notifica,
        method_notifica=method_notifica
    )


def avvia_iter_arrivo(
        user,
        subject,
        voce_indice=None,
        credential_ws_protocollo=None,
        configuration_ws_protocollo=None,
        prot_template=None,
        principal_file_name="",
        principal_file=b"",
        attachments_folder=None,
        attachments=[],
        test=False,
        invia_notifica=False,
        label_notifica='Invio notifica fine ITER',
        method_notifica='POST'):
    """
    Salva la bozza in entrata e attiva l'iter.
    Se invia_notifica=True, inserisce anche l'endpoint di notifica nel payload.
    """
    valid_conf = credential_ws_protocollo and configuration_ws_protocollo and voce_indice
    if invia_notifica:
        valid_conf = valid_conf and titulus_settings.NOTIFICATION_ENDPOINT

    rif_esterno_data = {
        'nome_rif_esterno': user.first_name,
        'cognome_rif_esterno': user.last_name,
        'cod_fis_rif_esterno': user.taxpayer_id,
        'email_rif_esterno': user.email,
    }

    return _esegui_flusso_protocollo(
        tipo='arrivo',
        azione='attiva_iter',
        bozza='si',
        subject=subject,
        rif_esterno_data=rif_esterno_data,
        valid_conf=valid_conf,
        invia_notifica=invia_notifica,
        credential_ws_protocollo=credential_ws_protocollo,
        configuration_ws_protocollo=configuration_ws_protocollo,
        prot_template=prot_template,
        principal_file_name=principal_file_name,
        principal_file=principal_file,
        attachments_folder=attachments_folder,
        attachments=attachments,
        test=test,
        voce_indice=voce_indice,
        label_notifica=label_notifica,
        method_notifica=method_notifica
    )


def protocolla_partenza(
        subject,
        credential_ws_protocollo=None,
        configuration_ws_protocollo=None,
        nome_rif_esterno=None,
        cognome_rif_esterno=None,
        cod_fis_rif_esterno=None,
        email_rif_esterno=None,
        prot_template=None,
        principal_file_name="",
        principal_file=b"",
        attachments_folder=None,
        attachments=[],
        test=False
        , label_notifica=None, method_notifica=None):
    """
    Protocolla un documento in partenza.
    """
    valid_conf = credential_ws_protocollo and configuration_ws_protocollo and cognome_rif_esterno and cod_fis_rif_esterno

    rif_esterno_data = {
        'nome_rif_esterno': nome_rif_esterno,
        'cognome_rif_esterno': cognome_rif_esterno,
        'cod_fis_rif_esterno': cod_fis_rif_esterno,
        'email_rif_esterno': email_rif_esterno,
    }

    return _esegui_flusso_protocollo(
        tipo='partenza',
        azione='protocolla',
        bozza='no',
        subject=subject,
        rif_esterno_data=rif_esterno_data,
        valid_conf=valid_conf,
        invia_notifica=False,
        credential_ws_protocollo=credential_ws_protocollo,
        configuration_ws_protocollo=configuration_ws_protocollo,
        prot_template=prot_template,
        principal_file_name=principal_file_name,
        principal_file=principal_file,
        attachments_folder=attachments_folder,
        attachments=attachments,
        test=test, label_notifica=label_notifica,
        method_notifica=method_notifica

    )


def avvia_iter_partenza(
        subject,
        voce_indice=None,
        credential_ws_protocollo=None,
        configuration_ws_protocollo=None,
        nome_rif_esterno=None,
        cognome_rif_esterno=None,
        cod_fis_rif_esterno=None,
        email_rif_esterno=None,
        prot_template=None,
        principal_file_name="",
        principal_file=b"",
        attachments_folder=None,
        attachments=[],
        test=False,
        invia_notifica=False,
        label_notifica='Invio notifica fine ITER',
        method_notifica='POST'
):
    """
    Salva la bozza in uscita e attiva l'iter.
    Se invia_notifica=True, inserisce anche l'endpoint di notifica nel payload.
    """
    valid_conf = credential_ws_protocollo and configuration_ws_protocollo and cognome_rif_esterno and cod_fis_rif_esterno and voce_indice
    if invia_notifica:
        valid_conf = valid_conf and titulus_settings.NOTIFICATION_ENDPOINT

    rif_esterno_data = {
        'nome_rif_esterno': nome_rif_esterno,
        'cognome_rif_esterno': cognome_rif_esterno,
        'cod_fis_rif_esterno': cod_fis_rif_esterno,
        'email_rif_esterno': email_rif_esterno,
    }

    return _esegui_flusso_protocollo(
        tipo='partenza',
        azione='attiva_iter',
        bozza='si',
        subject=subject,
        rif_esterno_data=rif_esterno_data,
        valid_conf=valid_conf,
        invia_notifica=invia_notifica,
        credential_ws_protocollo=credential_ws_protocollo,
        configuration_ws_protocollo=configuration_ws_protocollo,
        prot_template=prot_template,
        principal_file_name=principal_file_name,
        principal_file=principal_file,
        attachments_folder=attachments_folder,
        attachments=attachments,
        test=test,
        voce_indice=voce_indice,
        label_notifica=label_notifica,
        method_notifica=method_notifica
    )
