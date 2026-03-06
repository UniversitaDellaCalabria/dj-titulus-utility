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


class WSTitulusClient(object):
    """
    Client per il Web Service Titulus
    """

    def __init__(self,
                 wsdl_url,
                 username,
                 password,
                 template_xml_flusso=None,
                 **kwargs):

        self.username = username
        self.password = password
        self.wsdl_url = wsdl_url

        if template_xml_flusso is None:
            with open(titulus_settings.TEMPLATE_DOCUMENT_JINJAXML, 'r', encoding='utf-8') as f:
                self.template_xml_flusso = f.read()
        else:
            self.template_xml_flusso = template_xml_flusso

        jinja_template = Template(self.template_xml_flusso)
        self.doc = jinja_template.render(**kwargs)

        logger.info(f"Protocollazione Titulus {self.doc}")

        # RPA username and code
        # (per impersonificare RPA in fascicolazione!)
        self.rpa_username = kwargs.get('destinatario_username')
        self.rpa_code = kwargs.get('destinatario_code', None)

        # send email
        self.send_email = kwargs.get('send_email', False)

        # zeep
        self.client = None
        self.service = None

        # numero viene popolato a seguito di una protocollazione
        if kwargs.get('numero') and kwargs.get('anno'):
            self.numero = kwargs.get('numero')
            self.anno = kwargs.get('anno')
        else:
            self.numero = None
            self.anno = None
            # numero viene popolato a seguito di una protocollazione
        if kwargs.get('nrecord'):
            self.nrecord = kwargs.get('nrecord')
        else:
            self.nrecord = None
        # attachments
        self.allegati = []

    def connect(self):
        """
        """
        session = Session()
        settings_zeep = Settings(strict=False, xml_huge_tree=True)
        session.auth = HTTPBasicAuth(self.username,
                                     self.password)
        transport = Transport(session=session)
        self.client = Client(self.wsdl_url,
                             transport=transport,
                             settings=settings_zeep)
        self.service = self.client.bind('Titulus4Service', 'Titulus4')
        return self.client

    def is_connected(self):
        return True if self.client else False

    def assure_connection(self):
        if not self.is_connected():
            self.connect()

    def _esegui_salvataggio(self, is_bozza=False, force=False):
        """
        Funzione core fattorizzata per l'invio del payload a Titulus.
        """
        self.assure_connection()
        namespaces = titulus_settings.PROTOCOL_NAMESPACES

        if not force:
            if not is_bozza and (self.numero or self.anno):
                raise Exception(('Stai tentando di protocollare '
                                 'una istanza che ha già un '
                                 'numero e un anno: {}/{}').format(self.numero, self.anno))
            if is_bozza and self.nrecord:
                raise Exception(('Stai tentando di salvare in bozza '
                                 'una istanza che ha già un nrecord'
                                 ': {}').format(self.nrecord))

        ns0 = namespaces["ns0"]
        ns2 = namespaces["ns2"]

        self.client.get_type(f'{ns0}AttachmentBean')
        attachmentBeans_type = self.client.get_type(f'{ns2}ArrayOf_tns1_AttachmentBean')
        saveParams = self.client.get_type(f'{ns0}SaveParams')()

        attachmentBeans = attachmentBeans_type(self.allegati)

        saveParams.pdfConversion = True
        saveParams.sendEMail = self.send_email

        saveDocumentResponse = self.service.saveDocument(document=self.doc,
                                                         attachmentBeans=attachmentBeans,
                                                         params=saveParams)

        if saveDocumentResponse:
            root = ET.fromstring(saveDocumentResponse._value_1)
            attribs = root[1][0].attrib

            # Parsing dinamico: popoliamo in modo sicuro le variabili di classe
            if 'num_prot' in attribs:
                self.numero = attribs['num_prot']

            if 'nrecord' in attribs:
                self.nrecord = attribs['nrecord']

            return True

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
        # force PDF
        # 'mimeType': "application/pdf"}

    def aggiungi_allegato(self,
                          fopen,
                          nome,
                          descrizione,
                          is_doc_princ=False,
                          test=False):

        namespaces = titulus_settings.PROTOCOL_NAMESPACES
        ns1 = namespaces["ns1"]

        ext = os.path.splitext(nome)[1]
        if not ext:
            raise Exception(("'nome' deve essere con l'estensione "
                             "esempio: .pdf altrimenti errore xml -201!"))
        self.assure_connection()
        content_type = self.client.get_type(f'{ns1}base64Binary')
        content = content_type(fopen.read())
        allegato_dict = self._get_allegato_dict()
        allegato_dict['content'] = content
        allegato_dict['description'] = descrizione
        allegato_dict['filename'] = nome
        # if it's principal document insert in first position
        if is_doc_princ:
            self.allegati.insert(0, allegato_dict)
        else: self.allegati.append(allegato_dict)
        return allegato_dict

    def aggiungi_docPrinc(self, fopen, nome_doc, tipo_doc):
        return self.aggiungi_allegato(fopen=fopen,
                                      nome=nome_doc,
                                      descrizione=tipo_doc,
                                      is_doc_princ=True)

    def fascicolaDocumento(self, fascicolo):
        self.assure_connection()

        if self.rpa_username:
            self.service.setWSUser(
                user=self.rpa_username,
                pnumber=self.rpa_code
            )

        response = self.service.addInFolder(fascicolo)
        if response:
            return True
            # root = ET.fromstring(response._value_1)

    def cercaDocumento(self, key, value):
        self.assure_connection()
        query = f'[{key}]={value}'
        return self.service.search(query=query,
                                   orderby=xsd.SkipValue,
                                   params=xsd.SkipValue)


class Protocollo(WSTitulusClient):
    pass
