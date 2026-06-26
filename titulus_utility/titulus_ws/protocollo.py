import base64
import logging
import mimetypes
import xml.etree.ElementTree as ET
from email.message import EmailMessage
from io import BytesIO

from jinja2 import Template
from requests import Session
from requests.auth import HTTPBasicAuth
from zeep import Client, Settings, xsd
from zeep.transports import Transport

from titulus_utility import conf as titulus_settings
from titulus_utility.conf import TitulusIdType, TitulusDocNodeAttribs
from titulus_utility.titulus_ws.attachment_bean_utility import SOAPPayloadMixin

logger = logging.getLogger(__name__)


class WSTitulusConnector(object):
    """
    Gestisce esclusivamente la connessione di basso livello al Web Service
    SOAP di Titulus tramite Zeep.
    """

    def __init__(self, wsdl_url, username, password):
        self.wsdl_url = wsdl_url
        self.username = username
        self.password = password

        # Inizializzazione variabili zeep
        self.client = None
        self.service = None
        self.namespaces = titulus_settings.PROTOCOL_NAMESPACES

    def connect(self):
        """Stabilisce la connessione con il Web Service SOAP tramite Zeep."""
        logger.debug(f"Tentativo di connessione al WSDL: {self.wsdl_url}")
        try:
            session = Session()
            settings_zeep = Settings(strict=False, xml_huge_tree=True)
            session.auth = HTTPBasicAuth(self.username, self.password)
            transport = Transport(session=session)

            self.client = Client(self.wsdl_url,
                                 transport=transport,
                                 settings=settings_zeep)
            self.service = self.client.bind('Titulus4Service', 'Titulus4')
            return self.client
        except Exception as e:
            logger.exception(f"Errore durante la connessione al Web Service: {e}")
            raise

    def is_connected(self):
        """Ritorna True se il client Zeep è stato inizializzato."""
        return True if self.client else False

    def assure_connection(self):
        """Verifica lo stato della connessione e la avvia se assente."""
        if not self.is_connected():
            self.connect()


class WSTitulusMessageBroker(WSTitulusConnector, SOAPPayloadMixin):
    """
    Gestisce le operazioni di messaggistica e notifica di secondo livello
    sul Web Service SOAP di Titulus (es. registrazione ricevute PECh/Flussi).
    """

    def __init__(self, wsdl_url, username, password, email_subject=None, email_from=None, email_to=None):
        """
        Inizializza il broker di messaggistica Titulus.
        """
        # Inizializza la classe base (WSTitulusConnector) che definisce self.namespaces
        super().__init__(wsdl_url=wsdl_url, username=username, password=password)
        self.receipt = None
        self.email_subject = email_subject or 'Notifica Sistema - Registrazione Ricevuta'
        self.email_from = email_from or 'titulus-broker@unical.it'
        self.email_to = email_to or 'titulus-protocollo@unical.it'

    def encode_eml_doc_receipt(self, fopen, attachment_name, email_body, eml_filename="ricevuta.eml",
                               description="Notifica EML"):
        """
        Genera in memoria un file .eml contenente un corpo testo e un file allegato,
        lo codifica in Base64 e lo imposta come `self.receipt`.

        Args:
            fopen (file-like/bytes): Il file (ricevuta originale, PDF, XML) da allegare all'EML.
            attachment_name (str): Nome del file allegato dentro l'email (es. 'dati.xml').
            email_body (str): Il testo che comporrà il corpo dell'email.
            eml_filename (str, optional): Nome del file .eml finale che vedrà Titulus. Defaults to "ricevuta.eml".
            description (str, optional): Descrizione per l'AttachmentBean. Defaults to "Notifica EML".
        """
        logger.info(f"Avvio generazione file EML in memoria: {eml_filename}")
        self.assure_connection()

        try:
            # 1. Risoluzione polimorfica del file da allegare (legge sia bytes che file-like)
            if hasattr(fopen, 'read'):
                if hasattr(fopen, 'seek'):
                    fopen.seek(0)
                attachment_bytes = fopen.read()
            elif isinstance(fopen, bytes):
                attachment_bytes = fopen
            else:
                raise ValueError("Il parametro 'fopen' deve essere un oggetto file-like o bytes crudi.")

            # 2. Costruzione della struttura MIME dell'email
            msg = EmailMessage()
            msg['Subject'] = self.email_subject
            msg['From'] = self.email_from
            msg['To'] = self.email_to

            # Imposta il corpo del messaggio (Text/Plain)
            msg.set_content(email_body)

            # 3. Rilevamento automatico del MimeType dell'allegato
            mime_type, _ = mimetypes.guess_type(attachment_name)
            if mime_type is None:
                mime_type = 'application/octet-stream'
            main_type, sub_type = mime_type.split('/', 1)

            # Aggiunge l'allegato all'email
            msg.add_attachment(
                attachment_bytes,
                maintype=main_type,
                subtype=sub_type,
                filename=attachment_name
            )

            # 4. Serializzazione dell'intera email in un flusso di Byte (Formato .eml standard)
            eml_bytes = msg.as_bytes()
            logger.debug(f"File EML generato con successo. Dimensione: {len(eml_bytes)} byte.")

            # 5. Passaggio dei byte generati al mixin di codifica standard
            eml_stream = BytesIO(eml_bytes)
            self.receipt = self.encode_file_base64(self.client, eml_stream, eml_filename, description)
            logger.info(f"File EML '{eml_filename}' codificato in Base64 e caricato in self.receipt.")

        except Exception as e:
            logger.exception(f"Errore fatale durante la creazione o codifica del file EML {eml_filename}: {e}")
            raise

    def encode_doc_receipt(self, fopen, name, description):
        """
        Prepara e codifica in Base64 il file di notifica/ricevuta da inviare.
        Il risultato viene memorizzato nell'attributo di istanza `self.receipt`.
        """
        logger.info(f"Avvio codifica payload per la ricevuta: {name}")
        self.assure_connection()
        try:
            self.receipt = self.encode_file_base64(self.client, fopen, name, description)
            logger.debug(f"Ricevuta '{name}' codificata e caricata in memoria.")
        except Exception as e:
            logger.exception(f"Errore fatale durante la conversione del file {name} in Base64: {e}")
            raise

    def register_doc_receipt_to_titulus(self, nrecord, infos, type, esito, extract_cades=False):
        """
        Associa il file di notifica precedentemente codificato a un documento Titulus.

        Invia la richiesta al servizio SOAP `receiveMsgForDocument`. Se al record
        sono legate delle copie, la notifica viene propagata automaticamente da Titulus.

        Args:
            nrecord (str): Identificativo univoco (id/nrecord) del documento in Titulus.
            infos (str): Informazioni descrittive della notifica (es. 'notifica-ordinativo-xml').
            type (str): Tipo di notifica (es. 'messaggi_esito_applicativo').
            esito (str): Esito dell'operazione da registrare sul sistema.
            extract_cades (bool, optional): Se True, estrae l'eventuale busta CAdES.
                                            Defaults to False.

        Returns:
            bool: true in caso di successo
        """
        logger.info(f"[{nrecord}] Tentativo di registrazione notifica. Tipo: '{type}', Esito: '{esito}'")
        self.assure_connection()

        if self.receipt is None:
            error_msg = f"[{nrecord}] Errore: nessuna ricevuta in memoria. Chiamare 'encode_doc_receipt' prima."
            logger.error(error_msg)
            raise Exception(error_msg)

        ns0 = self.namespaces["ns0"]

        try:
            logger.debug(f"[{nrecord}] Recupero del tipo complesso {ns0}AttachmentBean")
            attachment_bean_type = self.client.get_type(f'{ns0}AttachmentBean')
            abean_to_send = attachment_bean_type(
                content=self.receipt['content'],
                fileName=self.receipt['filename'],
                description=self.receipt['description']
            )

            logger.debug(f"[{nrecord}] Invocazione servizio SOAP receiveMsgForDocument")
            receive_msg_response = self.service.receiveMsgForDocument(
                id=nrecord,
                notifyFile=abean_to_send,
                infos=infos,
                type=type,
                esito=esito,
                extractCades=extract_cades
            )

            if receive_msg_response:
                xml_string = receive_msg_response if isinstance(receive_msg_response,
                                                                str) else receive_msg_response._value_1
                logger.info(f"[{nrecord}] Notifica registrata con successo su Titulus.")
                logger.debug(f"[{nrecord}] Risposta raw da receiveMsgForDocument:\n{xml_string}")
                return True
            else:
                logger.warning(f"[{nrecord}] La chiamata ha restituito una risposta vuota dal server.")
                return None

        except Exception as e:
            logger.exception(f"[{nrecord}] Errore fatale durante l'esecuzione di receiveMsgForDocument: {e}")
            raise


class WSTitulusFileClient(WSTitulusConnector, SOAPPayloadMixin):
    def __init__(self,
                 wsdl_url,
                 username,
                 password):
        # Inizializza la classe base (WSTitulusConnector)
        super().__init__(wsdl_url=wsdl_url, username=username, password=password)
        self.document = None
        self.nrecord = None

    def load_document(self, nrecord):
        logger.info(f"Caricamento del documento con nrecord: {nrecord}")
        self.nrecord = nrecord
        self.assure_connection()

        try:
            logger.debug(f"[{nrecord}] Invocazione servizio loadDocument")
            raw_response = self.service.loadDocument(id=nrecord, lock=False)

            if raw_response:
                xml_string = raw_response if isinstance(raw_response, str) else raw_response._value_1
                logger.debug(f"[{nrecord}] Risposta raw da loadDocument ricevuta con successo \n{xml_string}")
                self.document = ET.fromstring(xml_string)
                return True
            else:
                self.document = None
                return False

        except Exception as e:
            logger.exception(f"[{nrecord}] Errore fatale durante load_document: {e}")
            raise

    def get_attachment(self, filename):

        # Ora verifichiamo che self.document non sia None
        if self.document is None:
            raise Exception(
                f"Impossibile scaricare l'allegato richiesto, documento non caricato in memoria, chiamare load_document prima")

        logger.info(f"[{self.nrecord}] Richiesta allegato: {filename}")

        self.assure_connection()

        try:
            logger.debug(f"[{self.nrecord}] Ricerca del fileId nell'albero XML in memoria")

            # Definizione del namespace usato per i tag dei file in Titulus
            namespaces = {'xw': 'http://www.kion.it/ns/xw'}

            # 1. Cerca direttamente su self.document
            target_file_node = None
            files_node = self.document.find('.//files')

            if files_node is not None:
                for f_node in files_node.findall('xw:file', namespaces=namespaces):
                    if f_node.attrib.get('title') == filename:
                        target_file_node = f_node
                        break

            if target_file_node is None:
                raise Exception(f"[{self.nrecord}] File con titolo '{filename}' non trovato nel documento.")

            # 2. Ciclo per trovare il nodo xw:file più annidato (l'ultima versione/modifica)
            current_node = target_file_node
            while True:
                child_node = current_node.find('xw:file', namespaces=namespaces)
                if child_node is not None:
                    current_node = child_node
                else:
                    break

            # 3. Estrazione del fileId definitivo
            file_id = current_node.attrib.get('name')

            if not file_id:
                raise Exception(f"[{self.nrecord}] Attributo 'name' (fileId) non trovato per il file '{filename}'.")

            logger.info(f"[{self.nrecord}] Trovato fileId dell'ultima versione: {file_id}")

            # 4. Invocazione servizio getAttachment
            logger.debug(f"[{self.nrecord}] Invocazione servizio getAttachment per {file_id}")
            attachment_bean = self.service.getAttachment(fileId=file_id)

            if attachment_bean:
                logger.debug(f"[{self.nrecord}] Risposta da getAttachment ricevuta. Tento l'estrazione del payload.")

                try:
                    file_content = attachment_bean.content._value_1

                except AttributeError:
                    logger.warning(
                        f"[{self.nrecord}] Struttura AttachmentBean inattesa. Tento il recupero dal dizionario o XML grezzo.")

                    if isinstance(attachment_bean, dict) and 'content' in attachment_bean:
                        file_content = attachment_bean['content']
                        if hasattr(file_content, '_value_1'):
                            file_content = file_content._value_1

                    elif isinstance(attachment_bean, str):
                        root = ET.fromstring(attachment_bean)
                        content_node = root.find('.//content')
                        file_content = content_node.text if content_node is not None else None

                    else:
                        raise Exception(f"[{self.nrecord}] Impossibile estrarre 'content' dall'AttachmentBean.")

                # --- Verifiche finali e decodifica ---
                if not file_content:
                    raise Exception(f"[{self.nrecord}] Il contenuto estratto dal Web Service è vuoto.")

                if isinstance(file_content, str):
                    logger.debug(f"[{self.nrecord}] Decodifica manuale del contenuto da Base64 a Bytes")
                    return base64.b64decode(file_content)

                elif isinstance(file_content, bytes):
                    logger.debug(f"[{self.nrecord}] Il contenuto è già in formato Bytes")
                    return file_content

                else:
                    raise Exception(
                        f"[{self.nrecord}] Tipo di dato non previsto per il contenuto del file: {type(file_content)}")

        except Exception as e:
            logger.exception(f"[{self.nrecord}] Errore fatale durante get_attachment: {e}")
            raise


class WSTitulusQueryClient(WSTitulusConnector):
    """
    Client leggero per le sole operazioni di lettura (Query, Ricerca).
    """

    def __init__(self,
                 wsdl_url,
                 username,
                 password):
        # Inizializza la classe base (WSTitulusConnector)
        super().__init__(wsdl_url=wsdl_url, username=username, password=password)

        # Inizializziamo questi attributi poiché get_record_infos va a popolarli
        self.numero = None
        self.nrecord = None

    def get_record_infos(self, nrecord):
        """
        Recupera le informazioni di un record Titulus (Metodo Core).

        Args:
            nrecord (string): l'identificativo del record registrato in titulus

        Returns:
            bool: True se la chiamata va a buon fine, assegnando a `self.numero` o `self.nrecord` la risposta.
        """
        logger.info(f"Richiesta info per il record {nrecord}")
        self.assure_connection()

        try:
            logger.debug(f"[{nrecord}] Invocazione servizio getRecordInfos")
            record_info = self.service.getRecordInfos(id=nrecord)

            if record_info:
                logger.debug(f"[{nrecord}] Risposta raw da getRecordInfos: {record_info._value_1}")
                root = ET.fromstring(record_info._value_1)

                doc_node = root.find('.//doc')

                if doc_node is not None:
                    attribs = doc_node.attrib

                    if TitulusDocNodeAttribs.NUM_PROT in attribs:
                        self.numero = attribs[TitulusDocNodeAttribs.NUM_PROT]
                        logger.info(f"[{nrecord}] Record recuperato. Assegnato Num Prot: {self.numero}")

                    if TitulusDocNodeAttribs.NRECORD in attribs:
                        self.nrecord = attribs[TitulusDocNodeAttribs.NRECORD]
                        logger.info(f"[{nrecord}] Record recuperato. Assegnato Nrecord: {self.nrecord}")
                else:
                    logger.error(f"[{nrecord}] Attenzione: Nodo <doc> non trovato nella risposta XML!")

                return True
        except Exception as e:
            logger.exception(f"[{nrecord}] Errore fatale durante _get_record_infos: {e}")
            raise

    def cercaDocumento(self, key, value):
        """Ricerca un documento in Titulus in base a chiave e valore."""
        self.assure_connection()
        query = f'[{key}]={value}'
        logger.debug(f"Esecuzione ricerca in Titulus. Query: {query}")
        return self.service.search(query=query,
                                   orderby=xsd.SkipValue,
                                   params=xsd.SkipValue)

    def get_document_infos(self, id_type, value, required_infos):
        """
        Cerca un documento e ne estrae un set specifico di attributi XML.

        Utilizza `cercaDocumento` per trovare il documento e parsa il nodo `<doc>`
        restituendo solo gli attributi richiesti. Include una validazione del tipo
        di identificatore passato.

        Args:
            id_type (TitulusIdType): Il tipo di identificatore usato per la ricerca.
            value (str): Il valore dell'identificatore da cercare.
            required_infos (list of str): Lista dei nomi degli attributi XML che si
                                          desidera estrarre dal nodo <doc>.

        Returns:
            dict: Un dizionario contenente le chiavi presenti in `required_infos`
                  che sono state trovate negli attributi del nodo XML, con i
                  rispettivi valori.

        Raises:
            TypeError: Se `id_type` non è un'istanza dell'enum `TitulusIdType`.
        """
        if not isinstance(id_type, TitulusIdType):
            raise TypeError(f"id_type deve essere di tipo TitulusIdType, ricevuto {type(id_type).__name__}")
        document_infos = self.cercaDocumento(id_type.value, value)
        root = ET.fromstring(document_infos._value_1)
        to_return = {}
        doc_node = root.find('.//doc')
        if doc_node is not None:
            attribs = doc_node.attrib
            for required_info in required_infos:
                if required_info in attribs:
                    to_return[required_info] = attribs[required_info]
        return to_return


class WSTitulusClient(WSTitulusQueryClient, SOAPPayloadMixin):
    """
    Client per la logica di business del Web Service Titulus.

    Eredita da WSTitulusQueryClient per la gestione della connessione SOAP e delle ricerche.
    Si occupa di renderizzare il template JinjaXML, gestire l'upload degli
    allegati (AttachmentBean) e inviare le richieste operative (SaveDocument, ecc).
    """

    def __init__(self,
                 wsdl_url,
                 username,
                 password,
                 template_xml_flusso=None,
                 **kwargs):

        # Inizializza la classe base (WSTitulusQueryClient -> WSTitulusConnector)
        super().__init__(wsdl_url=wsdl_url, username=username, password=password)

        if template_xml_flusso is None:
            logger.debug("Caricamento del template XML di default per Titulus.")
            with open(titulus_settings.TEMPLATE_DOCUMENT_JINJAXML, 'r', encoding='utf-8') as f:
                self.template_xml_flusso = f.read()
        else:
            self.template_xml_flusso = template_xml_flusso

        jinja_template = Template(self.template_xml_flusso)
        self.doc = jinja_template.render(**kwargs)

        logger.info(f"Inizializzazione WSTitulusClient completata per l'oggetto: {kwargs.get('oggetto', 'N/D')}")
        logger.debug(f"XML Renderizzato (Doc): {self.doc}")

        # RPA username and code (per impersonificare RPA in fascicolazione)
        self.rpa_username = kwargs.get('destinatario_username')
        self.rpa_code = kwargs.get('destinatario_code', None)

        # send email
        self.send_email = kwargs.get('send_email', False)

        # Gestione numero/anno da kwargs (sovrascrive eventuali None del super().__init__)
        if kwargs.get('numero') and kwargs.get('anno'):
            self.numero = kwargs.get('numero')
            self.anno = kwargs.get('anno')
        else:
            self.anno = None

        # Gestione nrecord da kwargs
        if kwargs.get(TitulusDocNodeAttribs.NRECORD):
            self.nrecord = kwargs.get(TitulusDocNodeAttribs.NRECORD)

        # attachments
        self.allegati = []

    def _esegui_salvataggio(self, is_bozza=False, force=False):
        """
        Invia il payload e gli allegati a Titulus (Metodo Core).

        Viene invocato dai wrapper `protocolla` e `salva_bozza_e_attiva_iter`.
        Richiede ed elabora i tipi complessi definiti nel WSDL (SaveParams, AttachmentBean).

        Args:
            is_bozza (bool): Se True, il documento viene salvato senza assegnare un numero di protocollo.
            force (bool): Se True, forza il salvataggio ignorando eventuali controlli di presenza di un numero pregresso.

        Returns:
            bool: True se la chiamata va a buon fine, assegnando a `self.numero` o `self.nrecord` la risposta.
        """
        logger.info(f"Esecuzione salvataggio (bozza: {is_bozza}, force: {force})")
        self.assure_connection()

        if not force:
            if not is_bozza and (self.numero or self.anno):
                error_msg = f'Tentativo di protocollare un\'istanza con numero/anno già assegnati: {self.numero}/{self.anno}'
                logger.error(error_msg)
                raise Exception(error_msg)
            if is_bozza and self.nrecord:
                error_msg = f'Tentativo di salvare in bozza un\'istanza con nrecord già assegnato: {self.nrecord}'
                logger.error(error_msg)
                raise Exception(error_msg)

        ns0 = self.namespaces["ns0"]
        ns2 = self.namespaces["ns2"]
        try:
            self.client.get_type(f'{ns0}AttachmentBean')
            attachmentBeans_type = self.client.get_type(f'{ns2}ArrayOf_tns1_AttachmentBean')
            saveParams = self.client.get_type(f'{ns0}SaveParams')()

            attachmentBeans = attachmentBeans_type(self.allegati)

            saveParams.pdfConversion = True
            saveParams.sendEMail = self.send_email

            logger.debug(f"Invocazione servizio saveDocument. Allegati totali: {len(self.allegati)}")
            saveDocumentResponse = self.service.saveDocument(document=self.doc,
                                                             attachmentBeans=attachmentBeans,
                                                             params=saveParams)

            if saveDocumentResponse:
                logger.debug(f"Risposta raw da saveDocument: {saveDocumentResponse._value_1}")
                root = ET.fromstring(saveDocumentResponse._value_1)
                attribs = root[1][0].attrib

                if TitulusDocNodeAttribs.NUM_PROT in attribs:
                    self.numero = attribs[TitulusDocNodeAttribs.NUM_PROT]
                    logger.info(f"Salvataggio completato. Assegnato Num Prot: {self.numero}")

                if TitulusDocNodeAttribs.NRECORD in attribs:
                    self.nrecord = attribs[TitulusDocNodeAttribs.NRECORD]
                    logger.info(f"Salvataggio completato. Assegnato Nrecord: {self.nrecord}")

                return True
        except Exception as e:
            logger.exception(f"Errore fatale durante _esegui_salvataggio: {e}")
            raise

    def protocolla(self, test=False, force=False):
        """Wrapper per la protocollazione diretta"""
        return self._esegui_salvataggio(is_bozza=False, force=force)

    def salva_bozza_e_attiva_iter(self, test=False, force=False):
        """Wrapper per il salvataggio in bozza e iter"""
        return self._esegui_salvataggio(is_bozza=True, force=force)

    def _get_allegato_dict(self):
        return {'content': None,
                'description': None,
                'filename': None}

    def aggiungi_allegato(self, fopen, nome, descrizione, is_doc_princ=False, test=False):
        self.assure_connection()
        try:
            allegato_dict = self.encode_file_base64(self.client, fopen, nome, descrizione)

            if is_doc_princ:
                self.allegati.insert(0, allegato_dict)
            else:
                self.allegati.append(allegato_dict)

            logger.debug(f"Allegato {nome} elaborato correttamente in base64.")
            return allegato_dict
        except Exception as e:
            logger.exception(f"Errore durante l'elaborazione dell'allegato {nome}: {e}")
            raise

    def aggiungi_docPrinc(self, fopen, nome_doc, tipo_doc):
        """Helper che richiama `aggiungi_allegato` forzando is_doc_princ a True."""
        return self.aggiungi_allegato(fopen=fopen,
                                      nome=nome_doc,
                                      descrizione=tipo_doc,
                                      is_doc_princ=True)

    def fascicolaDocumento(self, fascicolo):
        """Fascicola un documento esistente sfruttando il template fascicolo.jinja2.xml."""
        logger.info("Richiesta di fascicolazione documento inviata.")
        self.assure_connection()

        if self.rpa_code:
            logger.debug(
                f"Impostazione impersonificazione WSUser: {self.rpa_username}, usando la sua matricola {self.rpa_code}")
            self.service.setWSUser(
                user=self.rpa_code,
                pnumber=self.rpa_code
            )
        try:
            response = self.service.addInFolder(fascicolo)
            if response:
                logger.info("Fascicolazione avvenuta con successo tramite addInFolder.")
                return True
        except Exception as e:
            logger.exception(f"Errore durante la fascicolazione: {e}")
            raise
