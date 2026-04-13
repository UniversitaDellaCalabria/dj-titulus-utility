import logging
import os
import xml.etree.ElementTree as ET

from jinja2 import Template
from requests import Session
from requests.auth import HTTPBasicAuth
from zeep import Client, Settings, xsd
from zeep.transports import Transport

from titulus_utility import conf as titulus_settings

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
            logger.debug(f"Invocazione servizio getRecordInfos")
            record_info = self.service.getRecordInfos(id=nrecord)

            if record_info:
                logger.debug(f"Risposta raw da getRecordInfos: {record_info._value_1}")
                root = ET.fromstring(record_info._value_1)

                doc_node = root.find('.//doc')

                if doc_node is not None:
                    attribs = doc_node.attrib

                    if 'num_prot' in attribs:
                        self.numero = attribs['num_prot']
                        logger.info(f"Record recuperato. Assegnato Num Prot: {self.numero}")

                    if 'nrecord' in attribs:
                        self.nrecord = attribs['nrecord']
                        logger.info(f"Record recuperato. Assegnato Nrecord: {self.nrecord}")
                else:
                    logger.error("Attenzione: Nodo <doc> non trovato nella risposta XML!")

                return True
        except Exception as e:
            logger.exception(f"Errore fatale durante _get_record_infos: {e}")
            raise

    def cercaDocumento(self, key, value):
        """Ricerca un documento in Titulus in base a chiave e valore."""
        self.assure_connection()
        query = f'[{key}]={value}'
        logger.debug(f"Esecuzione ricerca in Titulus. Query: {query}")
        return self.service.search(query=query,
                                   orderby=xsd.SkipValue,
                                   params=xsd.SkipValue)


class WSTitulusClient(WSTitulusQueryClient):
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
        if kwargs.get('nrecord'):
            self.nrecord = kwargs.get('nrecord')

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
        namespaces = titulus_settings.PROTOCOL_NAMESPACES

        if not force:
            if not is_bozza and (self.numero or self.anno):
                error_msg = f'Tentativo di protocollare un\'istanza con numero/anno già assegnati: {self.numero}/{self.anno}'
                logger.error(error_msg)
                raise Exception(error_msg)
            if is_bozza and self.nrecord:
                error_msg = f'Tentativo di salvare in bozza un\'istanza con nrecord già assegnato: {self.nrecord}'
                logger.error(error_msg)
                raise Exception(error_msg)

        ns0 = namespaces["ns0"]
        ns2 = namespaces["ns2"]
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

                if 'num_prot' in attribs:
                    self.numero = attribs['num_prot']
                    logger.info(f"Salvataggio completato. Assegnato Num Prot: {self.numero}")

                if 'nrecord' in attribs:
                    self.nrecord = attribs['nrecord']
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

    def aggiungi_allegato(self,
                          fopen,
                          nome,
                          descrizione,
                          is_doc_princ=False,
                          test=False):
        """
            Codifica un file in Base64 e lo aggiunge alla lista degli allegati SOAP.

            Args:
                fopen (file-like): Il file aperto in modalità binaria (rb).
                nome (str): Nome del file con estensione.
                descrizione (str): Descrizione dell'allegato.
                is_doc_princ (bool): Se True, l'allegato viene inserito in posizione 0 (Documento Principale).

            Returns:
                dict: L'allegato codificato pronto per Titulus.
        """
        logger.debug(f"Elaborazione allegato: {nome} (Principale: {is_doc_princ})")
        namespaces = titulus_settings.PROTOCOL_NAMESPACES
        ns1 = namespaces["ns1"]

        ext = os.path.splitext(nome)[1]
        if not ext:
            error_msg = ("'nome' deve avere l'estensione (es: .pdf) per evitare l'errore xml -201 da Titulus!")
            logger.error(error_msg)
            raise Exception(error_msg)

        self.assure_connection()
        try:
            content_type = self.client.get_type(f'{ns1}base64Binary')
            content = content_type(fopen.read())
            allegato_dict = self._get_allegato_dict()
            allegato_dict['content'] = content
            allegato_dict['description'] = descrizione
            allegato_dict['filename'] = nome

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

        if self.rpa_username:
            logger.debug(f"Impostazione impersonificazione WSUser: {self.rpa_username}")
            self.service.setWSUser(
                user=self.rpa_username,
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