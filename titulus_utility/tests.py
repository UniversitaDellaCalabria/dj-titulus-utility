import os
from datetime import datetime
from django.test import TestCase
from django.conf import settings
from unittest.mock import MagicMock

from titulus_utility import services
from titulus_utility import conf as titulus_settings
from titulus_utility.conf import TitulusIdType
from titulus_utility.models import Repertorio
from titulus_utility.titulus_ws.protocollo import WSTitulusClient, WSTitulusQueryClient, WSTitulusConnector


class TitulusIntegrationTests(TestCase):

    def setUp(self):
        # 1. Creiamo un finto utente Django da passare alle funzioni
        self.mock_user = MagicMock()
        self.mock_user.first_name = titulus_settings.FIRST_NAME_USER_TEST
        self.mock_user.last_name = titulus_settings.LAST_NAME_USER_TEST
        self.mock_user.taxpayer_id = titulus_settings.FISCAL_CODE_USER_TEST
        self.mock_user.email = titulus_settings.EMAIL_USER_TEST

        # 2. Mockiamo le configurazioni DB
        self.mock_cred = MagicMock()
        self.mock_conf = MagicMock()

        # 3. Creiamo un file temporaneo reale da usare come allegato principale
        self.test_file_content = b"Contenuto del file di test generato automaticamente."
        self.test_file_name = "documento_test.pdf"
        self.attachment_folder = titulus_settings.ATTACHMENT_FOLDER_TEST
        self.test_repertorio = Repertorio(repertorio="Contratti di Lavoro ARU", code="RCARU")

        # 4. Generiamo la data e ora corrente per appenderla dinamicamente ai subject/infos
        self.current_time = datetime.now().strftime("%d/%m/%Y %H:%M")

    def test_01_connessione_diretta_client(self):
        """
        Testa la connessione base a Zeep usando le credenziali di test.
        Se questo fallisce, l'URL o le credenziali nel localsettings sono errate.
        """
        client = WSTitulusConnector(
            wsdl_url=titulus_settings.PROTOCOL_TEST_URL,
            username=titulus_settings.PROTOCOL_TEST_LOGIN,
            password=titulus_settings.PROTOCOL_TEST_PASSW,
        )
        # Tenta di connettersi e scaricare il WSDL
        client.assure_connection()
        self.assertTrue(client.is_connected(), "Il client non è riuscito a connettersi a Titulus.")

    def _get_test_attachments(self):
        """
        Legge tutti i file presenti nella cartella di test e restituisce
        la lista dei nomi file da passare ai services.
        """
        folder_path = os.path.join(settings.MEDIA_ROOT, self.attachment_folder)
        if os.path.exists(folder_path):
            # Filtriamo solo i file reali, ignorando eventuali sottocartelle
            return [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
        return []

    # ==========================================
    # CASI ARRIVO - PROTOCOLLO DIRETTO
    # ==========================================

    def test_01_arrivo_protocollo_senza_allegati(self):
        risultato = services.protocolla_arrivo(
            user=self.mock_user,
            subject=f"TEST INTEGRAZIONE 1 - Arrivo, Protocollo, No Allegati - {self.current_time}",
            credential_ws_protocollo=self.mock_cred,
            configuration_ws_protocollo=self.mock_conf,
            principal_file_name=self.test_file_name,
            principal_file=self.test_file_content,
            test=True,
            linked_nrecord="000065145-EXAMPLE-503f1b3f-a4a6-4e4f-83e7-e0418a263274"
        )
        self.assertIn("numero", risultato)
        self.assertIsNotNone(risultato["numero"])

    def test_02_arrivo_protocollo_con_allegati(self):
        attachments = self._get_test_attachments()
        self.assertTrue(len(attachments) > 0, "Nessun file trovato in ATTACHMENT_FOLDER_TEST per il test.")

        risultato = services.protocolla_arrivo(
            user=self.mock_user,
            subject=f"TEST INTEGRAZIONE 2 - Arrivo, Protocollo, Con Allegati + zip - {self.current_time}",
            credential_ws_protocollo=self.mock_cred,
            configuration_ws_protocollo=self.mock_conf,
            principal_file_name=self.test_file_name,
            principal_file=self.test_file_content,
            attachments=attachments,
            attachments_folder=self.attachment_folder,
            test=True,
            linked_nrecord="000065145-EXAMPLE-503f1b3f-a4a6-4e4f-83e7-e0418a263274"
        )
        self.assertIn("numero", risultato)
        self.assertIsNotNone(risultato["numero"])

    def test_02_b_arrivo_protocollo_con_zip_principale(self):
        """
        Variante del test_02 in cui il file ZIP reale viene impostato
        come documento principale del protocollo.
        """
        import os
        from django.conf import settings

        # 1. Recuperiamo gli allegati secondari come nel test originale
        attachments = self._get_test_attachments()

        # 2. Costruiamo il percorso sicuro verso lo ZIP da usare come principale
        zip_path = os.path.join(settings.BASE_DIR, "media", "attachment_test", "ziptesst.zip")
        self.assertTrue(os.path.exists(zip_path), f"File ZIP principale non trovato: {zip_path}")

        # 3. Leggiamo lo ZIP in modalità binaria
        with open(zip_path, "rb") as f:
            zip_principal_content = f.read()

        risultato = services.protocolla_arrivo(
            user=self.mock_user,
            subject=f"TEST INTEGRAZIONE 2B - Arrivo, ZIP principale + Allegati - {self.current_time}",
            credential_ws_protocollo=self.mock_cred,
            configuration_ws_protocollo=self.mock_conf,
            principal_file_name="ziptesst.zip",
            principal_file=zip_principal_content,  # Passiamo i byte dello ZIP
            attachments=attachments,
            attachments_folder=self.attachment_folder,
            test=True,
            # Manteniamo il tuo parametro del flusso d'esempio
            linked_nrecord="000065145-EXAMPLE-503f1b3f-a4a6-4e4f-83e7-e0418a263274"
        )

        self.assertIn("numero", risultato)
        self.assertIsNotNone(risultato["numero"])

    # ==========================================
    # CASI PARTENZA - PROTOCOLLO DIRETTO
    # ==========================================

    def test_03_partenza_protocollo_senza_allegati(self):
        risultato = services.protocolla_partenza(
            subject=f"TEST INTEGRAZIONE 3 - Partenza, Protocollo, No Allegati - {self.current_time}",
            credential_ws_protocollo=self.mock_cred,
            configuration_ws_protocollo=self.mock_conf,
            principal_file_name=self.test_file_name,
            principal_file=self.test_file_content,
            test=True,
        )
        self.assertIn("numero", risultato)
        self.assertIsNotNone(risultato["numero"])

    def test_04_partenza_protocollo_con_allegati(self):
        attachments = self._get_test_attachments()

        risultato = services.protocolla_partenza(
            subject=f"TEST INTEGRAZIONE 4 - Partenza, Protocollo, Con Allegati - {self.current_time}",
            credential_ws_protocollo=self.mock_cred,
            configuration_ws_protocollo=self.mock_conf,
            principal_file_name=self.test_file_name,
            principal_file=self.test_file_content,
            attachments=attachments,
            attachments_folder=self.attachment_folder,
            test=True,
        )
        self.assertIn("numero", risultato)
        self.assertIsNotNone(risultato["numero"])

    # ==========================================
    # CASI ARRIVO - BOZZA E ITER
    # ==========================================

    def test_05_arrivo_bozza_iter_senza_allegati(self):
        risultato = services.avvia_iter_arrivo(
            user=self.mock_user,
            subject=f"TEST INTEGRAZIONE 5 - Arrivo, Bozza/Iter, No Allegati - {self.current_time}",
            voce_indice="Iter Approva e Firma",
            credential_ws_protocollo=self.mock_cred,
            configuration_ws_protocollo=self.mock_conf,
            principal_file_name=self.test_file_name,
            principal_file=self.test_file_content,
            test=True
        )
        # Nelle bozze ci aspettiamo l'nrecord, non il numero di protocollo
        self.assertIn("nrecord", risultato)
        self.assertIsNotNone(risultato["nrecord"])

    def test_05_arrivo_bozza_iter_senza_allegati_notifica(self):
        risultato = services.avvia_iter_arrivo(
            user=self.mock_user,
            subject=f"TEST INTEGRAZIONE 5 - Arrivo, Bozza/Iter, No Allegati e Notifica - {self.current_time}",
            voce_indice="Iter Approva e Firma",
            credential_ws_protocollo=self.mock_cred,
            configuration_ws_protocollo=self.mock_conf,
            principal_file_name=self.test_file_name,
            principal_file=self.test_file_content,
            test=True,
            invia_notifica=True
        )
        # Nelle bozze ci aspettiamo l'nrecord, non il numero di protocollo
        self.assertIn("nrecord", risultato)
        self.assertIsNotNone(risultato["nrecord"])

    def test_06_arrivo_bozza_iter_con_allegati(self):
        attachments = self._get_test_attachments()

        risultato = services.avvia_iter_arrivo(
            user=self.mock_user,
            subject=f"TEST INTEGRAZIONE 6 - Arrivo, Bozza/Iter, Con Allegati - {self.current_time}",
            voce_indice="Iter Approva e Firma",
            credential_ws_protocollo=self.mock_cred,
            configuration_ws_protocollo=self.mock_conf,
            principal_file_name=self.test_file_name,
            principal_file=self.test_file_content,
            attachments=attachments,
            attachments_folder=self.attachment_folder,
            test=True
        )
        self.assertIn("nrecord", risultato)
        self.assertIsNotNone(risultato["nrecord"])

    def test_06_arrivo_bozza_iter_con_allegati_notifica(self):
        attachments = self._get_test_attachments()

        risultato = services.avvia_iter_arrivo(
            user=self.mock_user,
            subject=f"TEST INTEGRAZIONE 6 - Arrivo, Bozza/Iter, Con Allegati e Notifica - {self.current_time}",
            voce_indice="Iter Approva e Firma",
            credential_ws_protocollo=self.mock_cred,
            configuration_ws_protocollo=self.mock_conf,
            principal_file_name=self.test_file_name,
            principal_file=self.test_file_content,
            attachments=attachments,
            attachments_folder=self.attachment_folder,
            test=True,
            invia_notifica=True
        )
        self.assertIn("nrecord", risultato)
        self.assertIsNotNone(risultato["nrecord"])

    # ==========================================
    # CASI PARTENZA - BOZZA E ITER
    # ==========================================

    def test_07_partenza_bozza_iter_senza_allegati(self):
        risultato = services.avvia_iter_partenza(
            subject=f"TEST INTEGRAZIONE 7 - Partenza, Bozza/Iter, No Allegati - {self.current_time}",
            voce_indice="Iter Approva e Firma",
            credential_ws_protocollo=self.mock_cred,
            configuration_ws_protocollo=self.mock_conf,
            principal_file_name=self.test_file_name,
            principal_file=self.test_file_content,
            test=True,
            invia_notifica=False,
        )
        self.assertIn("nrecord", risultato)
        self.assertIsNotNone(risultato["nrecord"])

    def test_07_1_partenza_bozza_iter_senza_allegati(self):
        risultato = services.avvia_iter_partenza(
            subject=f"TEST INTEGRAZIONE 7 - Partenza, Bozza/Iter, No Allegati REPERTORIO - {self.current_time}",
            voce_indice="Iter Approva e Firma",
            credential_ws_protocollo=self.mock_cred,
            configuration_ws_protocollo=self.mock_conf,
            principal_file_name=self.test_file_name,
            principal_file=self.test_file_content,
            test=True,
            invia_notifica=False,
            repertorio=self.test_repertorio,
        )
        self.assertIn("nrecord", risultato)
        self.assertIsNotNone(risultato["nrecord"])

    def test_07_partenza_bozza_iter_senza_allegati_notifica(self):
        risultato = services.avvia_iter_partenza(
            subject=f"TEST INTEGRAZIONE 7 - Partenza, Bozza/Iter, No Allegati e Notifica - {self.current_time}",
            voce_indice="Iter Approva e Firma",
            credential_ws_protocollo=self.mock_cred,
            configuration_ws_protocollo=self.mock_conf,
            principal_file_name=self.test_file_name,
            principal_file=self.test_file_content,
            test=True,
            invia_notifica=True,
        )
        self.assertIn("nrecord", risultato)
        self.assertIsNotNone(risultato["nrecord"])

    def test_08_partenza_bozza_iter_con_allegati(self):
        attachments = self._get_test_attachments()

        risultato = services.avvia_iter_partenza(
            subject=f"TEST INTEGRAZIONE 8 - Partenza, Bozza/Iter, Con Allegati - {self.current_time}",
            voce_indice="Iter Approva e Firma",
            credential_ws_protocollo=self.mock_cred,
            configuration_ws_protocollo=self.mock_conf,
            principal_file_name=self.test_file_name,
            principal_file=self.test_file_content,
            attachments=attachments,
            attachments_folder=self.attachment_folder,
            test=True,
            invia_notifica=False,
        )
        self.assertIn("nrecord", risultato)
        self.assertIsNotNone(risultato["nrecord"])

    def test_08_partenza_bozza_iter_con_allegati_notifica(self):
        attachments = self._get_test_attachments()

        risultato = services.avvia_iter_partenza(
            subject=f"TEST INTEGRAZIONE 8 - Partenza, Bozza/Iter, Con Allegati e Notifica - {self.current_time}",
            voce_indice="Iter Approva e Firma",
            credential_ws_protocollo=self.mock_cred,
            configuration_ws_protocollo=self.mock_conf,
            principal_file_name=self.test_file_name,
            principal_file=self.test_file_content,
            attachments=attachments,
            attachments_folder=self.attachment_folder,
            test=True,
            invia_notifica=True,
        )
        self.assertIn("nrecord", risultato)
        self.assertIsNotNone(risultato["nrecord"])

    def test_09_recupera_numero_protocollo(self):
        risultato = services.recupera_numero_protocollo(
            credential_ws_protocollo=self.mock_cred,
            nrecord="000063688-EXAMPLE-d37b386c-c10a-4ba3-8e27-e7020d995b47",
            test=True,
        )
        self.assertIsNotNone(risultato)

    def test_10_get_attachments(self):
        risultato = services.recupera_documenti(credential_ws_protocollo=self.mock_cred,
                                                nrecord="000063964-EXAMPLE-d70b4a6e-694b-4cb2-b4d5-8c69b2f746b4",
                                                attachments=["MSTLNE94M46C710M.pdf"], test=True)
        self.assertIsNotNone(risultato)
        print(risultato)

    # ==========================================
    # CASI MESSAGE BROKER - RICEVUTE
    # ==========================================

    def test_11_registra_ricevuta_documento(self):
        """
        Testa la sottomissione di una ricevuta/notifica associata a un record esistente.
        Verifica il funzionamento end-to-end del modulo WSTitulusMessageBroker.
        """
        # Utilizziamo lo stesso nrecord di test valido e già presente nell'ambiente CINECA
        test_nrecord = "000065145-EXAMPLE-503f1b3f-a4a6-4e4f-83e7-e0418a263274"

        # Generiamo al volo un XML di ricevuta simulato in byte
        dummy_receipt_content = b"<notifica><stato>CONSEGNATO</stato><operazione>TEST-INTEGRAZIONE</operazione></notifica>"
        dummy_receipt_name = "ricevuta_consegna_pec.xml"

        risultato = services.registra_ricevuta_documento(
            nrecord=test_nrecord,
            infos=f"Notifica di Consegna PEC - Test Automatico Integrazione - {self.current_time}",
            type="messaggio_ricezione_flusso",
            esito="OK",
            receipt_file_name=dummy_receipt_name,
            receipt_file=dummy_receipt_content,
            credential_ws_protocollo=self.mock_cred,
            test=True,
            extract_cades=False
        )

        # Ci aspettiamo che il service restituisca True a seguito della chiamata SOAP andata a buon fine
        self.assertTrue(risultato, "La registrazione della ricevuta tramite MessageBroker è fallita su Titulus.")

    def test_12_registra_ricevuta_documento_pdf(self):
        """
        Testa la sottomissione di una ricevuta in formato PDF binario.
        Verifica che il MessageBroker carichi e associ correttamente il documento.
        """
        # Utilizziamo l'nrecord di test valido sul server CINECA
        test_nrecord = "000065145-EXAMPLE-503f1b3f-a4a6-4e4f-83e7-e0418a263274"


        # Generiamo una struttura minima ma binariamente valida di un file PDF
        # Questo evita che i validatori di Titulus scartino il file
        dummy_pdf_content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
            b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000056 00000 n\n0000000111 00000 n\n"
            b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
            b"startxref\n190\n"
            b"%%EOF"
        )
        dummy_pdf_name = "ricevuta_notifica_firmata.pdf"

        risultato = services.registra_ricevuta_documento(
            nrecord=test_nrecord,
            infos=f"Notifica di Avvenuta Consegna - Allegato PDF - {self.current_time}",
            type="messaggi_esito_applicativo",
            esito="OK",
            receipt_file_name=dummy_pdf_name,
            receipt_file=dummy_pdf_content,  # Passiamo i byte del PDF appena generato
            credential_ws_protocollo=self.mock_cred,
            test=True,
            extract_cades=False
        )

        # Verifica che il server risponda con successo (True)
        self.assertTrue(risultato, "Il MessageBroker ha fallito l'invio della ricevuta in formato PDF.")

    def test_13_registra_ricevuta_eml_documento(self):
        """
        Testa la generazione dinamica di una ricevuta in formato .eml (testo + allegato)
        e il suo corretto caricamento e associazione su un documento Titulus esistente.
        """
        # Utilizziamo lo stesso nrecord di test valido sul server sandbox CINECA
        test_nrecord = "000065145-EXAMPLE-503f1b3f-a4a6-4e4f-83e7-e0418a263274"



        # 1. Il file (es. dati XML) che vogliamo si trovi DENTRO l'email come allegato
        inner_xml_content = b"<ricevuta><id>12345</id><esito>CONSEGNATO</esito></ricevuta>"
        inner_xml_name = "dati_notifica_core.xml"

        # 2. Il corpo del testo dell'email (.eml)
        testo_corpo_email = (
            "Buongiorno,\n\n"
            "Si trasmette la notifica telematica prodotta automaticamente dai sistemi centrali.\n"
            "I dettagli strutturati dell'esito sono disponibili nel file XML allegato.\n\n"
            "Cordiali saluti,\nServizio Integrazione Message Broker Unical."
        )


        # Invochiamo il nuovo service wrapper
        risultato = services.registra_ricevuta_eml_documento(
            nrecord=test_nrecord,
            infos=f"Messaggio di Notifica PEC Complesso (.eml) - {self.current_time}",
            type="messaggio_ricezione_flusso",
            esito="OK",
            receipt_file=inner_xml_content,  # Diventa l'allegato interno dell'EML
            attachment_name=inner_xml_name,  # Nome dell'allegato interno
            email_body=testo_corpo_email,  # Corpo dell'EML
            eml_filename="notifica_pec_completa.eml",  # Nome dell'EML registrato su Titulus
            credential_ws_protocollo=self.mock_cred,
            test=True,
            extract_cades=False,
            # Se vuoi, qui puoi testare il passaggio opzionale delle intestazioni personalizzate:
            email_subject="[NOTIFICA AUTOMATICA] Esito Ricezione Flusso",
            email_from="notifiche-automatiche@unical.it"
            # email_to viene omesso appositamente per testare il fallback di default
        )

        # Ci aspettiamo che il server di test di Titulus risponda con successo
        self.assertTrue(risultato, "Il service registra_ricevuta_eml_documento ha fallito la sottomissione.")

    def test_14_registra_ricevuta_eml_documento_con_pdf_reale(self):
        """
        Testa la generazione di una ricevuta .eml leggendo un file PDF reale
        presente sul disco (media/attachment_test/Questo allegato di test 1.pdf).
        """
        import os
        from django.conf import settings

        # Utilizziamo l'nrecord valido dell'ambiente sandbox CINECA
        test_nrecord = "000065145-EXAMPLE-503f1b3f-a4a6-4e4f-83e7-e0418a263274"

        # Costruiamo il percorso assoluto in modo sicuro.
        # Se 'media' si trova nella radice del tuo progetto Django:
        file_path = os.path.join(settings.BASE_DIR, "media", "attachment_test", "Questo allegato di test 1.pdf")

        # Se invece usi la configurazione standard di Django per i media:
        # file_path = os.path.join(settings.MEDIA_ROOT, "attachment_test", "Questo allegato di test 1.pdf")

        # Controllo preventivo per assicurarsi che il file esista e non fallire alla cieca
        self.assertTrue(os.path.exists(file_path), f"Attenzione, file non trovato al percorso: {file_path}")

        # Leggiamo il contenuto binario del file reale dal disco
        with open(file_path, "rb") as f:
            real_pdf_content = f.read()

        inner_pdf_name = "Questo allegato di test 1.pdf"

        corpo_email_testo = (
            "Gentile Utente,\n\n"
            "si trasmette in allegato a questa comunicazione il documento PDF reale "
            "recuperato direttamente dal file system del server.\n\n"
            "Cordiali saluti,\nSistemi Informativi - Università della Calabria."
        )


        # Invochiamo il service passandogli i byte del file reale appena letti
        risultato = services.registra_ricevuta_eml_documento(
            nrecord=test_nrecord,
            infos=f"Notifica Mail EML con PDF reale prelevato da disco - {self.current_time}",
            type="messaggi_esito_applicativo",
            esito="OK",
            receipt_file=real_pdf_content,
            attachment_name=inner_pdf_name,
            email_body=corpo_email_testo,
            eml_filename="notifica_con_pdf_reale.eml",
            credential_ws_protocollo=self.mock_cred,
            test=True,
            extract_cades=False,
            email_subject="[REPORT SYSTEM] Invio Documento Reale da Disco",
            email_from="servizi-web-ws@unical.it"
        )

        # Verifica che Titulus accetti l'EML contenente il tuo PDF reale
        self.assertTrue(risultato, "Il service ha fallito l'invio dell'EML con il PDF reale.")

    # ==========================================
    # CASI CON FILE ZIP (DIRETTO E INGLOBATO)
    # ==========================================

    def test_15_registra_ricevuta_zip_diretto(self):
        """
        Testa la sottomissione diretta di un file ZIP reale (ziptesst.zip)
        come ricevuta associata a un record esistente su Titulus.
        """
        import os
        from django.conf import settings

        # Utilizziamo l'nrecord valido dell'ambiente sandbox CINECA
        test_nrecord = "000065145-EXAMPLE-503f1b3f-a4a6-4e4f-83e7-e0418a263274"

        # Costruzione del percorso sicuro verso il file ZIP su disco
        file_path = os.path.join(settings.BASE_DIR, "media", "attachment_test", "ziptesst.zip")

        # Verifica preventiva dell'esistenza del file per un feedback immediato nei log di test
        self.assertTrue(os.path.exists(file_path), f"File ZIP non trovato al percorso richiesto: {file_path}")

        # Lettura binaria dello ZIP
        with open(file_path, "rb") as f:
            zip_content = f.read()

        zip_file_name = "ziptesst.zip"


        # Invocazione del servizio di registrazione diretta
        risultato = services.registra_ricevuta_documento(
            nrecord=test_nrecord,
            infos=f"Archivio ZIP di Log - Sottomissione Diretta - {self.current_time}",
            type="messaggi_esito_applicativo",
            esito="OK",
            receipt_file_name=zip_file_name,
            receipt_file=zip_content,  # Passiamo i byte dello ZIP
            credential_ws_protocollo=self.mock_cred,
            test=True,
            extract_cades=False
        )

        # Ci aspettiamo che Titulus accetti il file ZIP e ritorni True
        self.assertTrue(risultato, "Il service ha fallito l'invio diretto del file ZIP.")

    def test_16_registra_ricevuta_eml_con_zip_inglobato(self):
        """
        Testa la generazione di una ricevuta .eml che contiene un corpo testo
        e un file allegato in formato ZIP binario (ziptesst.zip), registrandola su Titulus.
        """
        import os
        from django.conf import settings

        # Utilizziamo lo stesso nrecord valido dell'ambiente sandbox CINECA
        test_nrecord = "000065145-EXAMPLE-503f1b3f-a4a6-4e4f-83e7-e0418a263274"

        # Costruzione del percorso sicuro verso il file ZIP su disco
        file_path = os.path.join(settings.BASE_DIR, "media", "attachment_test", "ziptesst.zip")

        # Verifica preventiva dell'esistenza del file
        self.assertTrue(os.path.exists(file_path), f"File ZIP non trovato per incapsulamento EML: {file_path}")

        # Lettura binaria dello ZIP
        with open(file_path, "rb") as f:
            zip_content = f.read()

        inner_zip_name = "ziptesst.zip"

        corpo_email_testo = (
            "Spettabile Assistenza,\n\n"
            "si trasmette in allegato l'archivio compresso ZIP contenente i file di log "
            "e i dettagli strutturati estratti a sistema per la verifica del flusso.\n\n"
            "Messaggio automatico inviato da Message Broker Unical."
        )


        # Invocazione del servizio che incapsula lo ZIP nell'EML
        risultato = services.registra_ricevuta_eml_documento(
            nrecord=test_nrecord,
            infos=f"Notifica Mail EML con allegato archivio ZIP di log - {self.current_time}",
            type="messaggio_ricezione_flusso",
            esito="OK",
            receipt_file=zip_content,  # I byte del file ZIP finiranno dentro l'EML
            attachment_name=inner_zip_name,  # Nome del file compresso dentro l'email
            email_body=corpo_email_testo,  # Corpo testo del file .eml
            eml_filename="notifica_con_allegato_zip.eml",  # Nome del file .eml finale su Titulus
            credential_ws_protocollo=self.mock_cred,
            test=True,
            extract_cades=False,
            # Passaggio opzionale di metadati personalizzati per l'EML:
            email_subject="[BACKUP SYSTEM] Invio Archivio Log Compresso",
            email_from="servizi-web-ws@unical.it"
        )

        # Verifica che il server SOAP di Titulus accetti il pacchetto MIME (.eml) contenente lo ZIP
        self.assertTrue(risultato, "Il service ha fallito l'invio della ricevuta EML con ZIP inglobato.")

    # ==========================================
    # CASI CON ANNIDAMENTO EML (1 E 2 LIVELLI)
    # ==========================================

    def test_17_registra_ricevuta_eml_con_eml_allegato(self):
        """
        Testa la generazione di una ricevuta .eml che contiene a sua volta
        un file .eml come allegato (il quale possiede un suo testo indipendente).
        """
        from email.message import EmailMessage

        # Utilizziamo l'nrecord valido dell'ambiente sandbox CINECA
        test_nrecord = "000065145-EXAMPLE-503f1b3f-a4a6-4e4f-83e7-e0418a263274"

        # 1. Costruiamo l'email INTERNA (l'allegato .eml) con il proprio testo indipendente
        inner_msg = EmailMessage()
        inner_msg['Subject'] = 'Dettaglio Notifica Interna - Originaria'
        inner_msg['From'] = 'sistema-sorgente@unical.it'
        inner_msg['To'] = 'audit-log@unical.it'
        inner_msg.set_content(
            "Questo è il corpo del testo dell'email ALLEGATA (interna).\n"
            "Contiene i metadati originari estratti dalla transazione di rete."
        )
        # Seralizziamo l'email interna in byte crudi
        inner_eml_bytes = inner_msg.as_bytes()

        corpo_email_esterna = (
            "Si trasmette in allegato la notifica telematica inoltrata.\n"
            "Il file .eml allegato contiene i dettagli nativi del messaggio originario."
        )


        # Invochiamo il servizio: prenderà i byte dell'email interna e li incapsulerà nell'email principale
        risultato = services.registra_ricevuta_eml_documento(
            nrecord=test_nrecord,
            infos=f"Notifica Mail EML contenente allegato EML interno - {self.current_time}",
            type="messaggio_ricezione_flusso",
            esito="OK",
            receipt_file=inner_eml_bytes,                     # Byte dell'email interna
            attachment_name="messaggio_originale_allegato.eml", # Nome dell'allegato dentro l'email
            email_body=corpo_email_esterna,                   # Testo dell'email contenitore
            eml_filename="notifica_principale_con_eml_dentro.eml", # Nome del file .eml finale registrato
            credential_ws_protocollo=self.mock_cred,
            test=True,
            extract_cades=False,
            email_subject="[CONTAINER] Notifica Principale - Invio Involucro EML"
        )

        # Verifica che il server di test di Titulus accetti il pacchetto MIME
        self.assertTrue(risultato, "Il service ha fallito l'invio della ricevuta EML contenente un EML allegato.")


    def test_18_registra_ricevuta_eml_annidato_due_livelli(self):
        """
        Testa la sottomissione di una struttura ad annidamento profondo (2 livelli di nesting):
        Email Esterna (Livello 0) -> contiene Email Intermedia (Livello 1) -> contiene Email Interna (Livello 2).
        """
        from email.message import EmailMessage

        test_nrecord = "000065145-EXAMPLE-503f1b3f-a4a6-4e4f-83e7-e0418a263274"


        # --- LIVELLO 2: L'email più profonda (Interna) ---
        inner_msg = EmailMessage()
        inner_msg['Subject'] = 'Livello 2 - Core Log Originario'
        inner_msg['From'] = 'kernel-broker@unical.it'
        inner_msg['To'] = 'dev-null@unical.it'
        inner_msg.set_content("Testo critico generato dal core del Message Broker (Livello 2 - Più interno).")
        inner_eml_bytes = inner_msg.as_bytes()

        # --- LIVELLO 1: L'email intermedia che ingloba il livello 2 ---
        middle_msg = EmailMessage()
        middle_msg['Subject'] = 'Livello 1 - Involucro Intermedio di Smistamento'
        middle_msg['From'] = 'dispatch-service@unical.it'
        middle_msg['To'] = 'buffer-routing@unical.it'
        middle_msg.set_content(
            "Testo del livello intermedio (Livello 1).\n"
            "Trovate l'email nativa di livello 2 in allegato all'interno."
        )
        # Agganciamo l'email interna a quella intermedia impostando il tipo rfc822
        middle_msg.add_attachment(
            inner_eml_bytes,
            maintype="message",
            subtype="rfc822",
            filename="email_livello_2_interna.eml"
        )
        middle_eml_bytes = middle_msg.as_bytes()

        # --- LIVELLO 0: Il testo dell'email ESTERNA (Radice) generata dal Service ---
        corpo_email_esterna = (
            "Attenzione: rilevato flusso ad incapsulamento multiplo (Nesting Profondo).\n"
            "In allegato viene inoltrato l'involucro intermedio di livello 1.\n"
            "Procedere con il parsing ricorsivo se necessario."
        )


        # Il service prenderà middle_eml_bytes (che ha già dentro il livello 2) e lo impacchetterà nel livello 0
        risultato = services.registra_ricevuta_eml_documento(
            nrecord=test_nrecord,
            infos=f"Notifica Mail EML con 2 livelli di annidamento EML ricorsivi - {self.current_time}",
            type="messaggio_ricezione_flusso",
            esito="OK",
            receipt_file=middle_eml_bytes,                 # Passiamo l'involucro intermedio (Livello 1)
            attachment_name="involucro_livello_1.eml",       # Nome dell'allegato dentro la mail radice
            email_body=corpo_email_esterna,                 # Testo della mail radice (Livello 0)
            eml_filename="notifica_radice_livello_0.eml",   # File .eml finale salvato su Titulus
            credential_ws_protocollo=self.mock_cred,
            test=True,
            extract_cades=False,
            email_subject="[ROOT-LEVEL 0] Analisi Flusso Multi-Incapsulato"
        )

        # Verifica che Titulus accetti l'annidamento ricorsivo rfc822 senza sollevare eccezioni
        self.assertTrue(risultato, "Il server ha rifiutato la struttura EML ad annidamento ricorsivo a 2 livelli.")

    def test_19_arrivo_protocollo_formati_frequenti_da_cartella(self):
        """
        Testa la protocollazione in arrivo iterando su tutti i file reali
        presenti nella cartella 'media/principal_file_test'.
        Verifica che il motore di normalizzazione riconosca e accetti
        correttamente i formati fisici (docx, xml, p7m, png, ecc.).
        """
        import os
        from django.conf import settings

        # Definiamo il percorso della cartella contenente i file fisici
        folder_path = os.path.join(settings.BASE_DIR, "media", "principal_file_test")

        # Controllo preventivo: verifichiamo che la cartella esista
        self.assertTrue(os.path.exists(folder_path), f"Cartella non trovata al percorso: {folder_path}")

        # Recuperiamo la lista di tutti i file al suo interno
        test_files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]

        # Assicuriamoci che ci sia almeno un file su cui iterare
        self.assertTrue(len(test_files) > 0, "Nessun file trovato nella cartella 'principal_file_test'.")

        # Iniziamo l'iterazione su ogni file
        for filename in test_files:
            file_path = os.path.join(folder_path, filename)

            # Leggiamo i byte grezzi del file reale
            with open(file_path, "rb") as f:
                file_content = f.read()

            # Inviamo il file a Titulus
            risultato = services.protocolla_arrivo(
                user=self.mock_user,
                subject=f"TEST INTEGRAZIONE 19 - Formato {filename} - {self.current_time}",
                credential_ws_protocollo=self.mock_cred,
                configuration_ws_protocollo=self.mock_conf,
                principal_file_name=filename,
                principal_file=file_content,
                test=True,
                linked_nrecord="000065145-EXAMPLE-503f1b3f-a4a6-4e4f-83e7-e0418a263274"
            )

            # Verifichiamo che Titulus abbia accettato questo specifico formato senza corrompersi
            self.assertIn("numero", risultato, f"Protocollazione fallita per il file: {filename}")
            self.assertIsNotNone(risultato["numero"], f"Numero di protocollo nullo per il file: {filename}")

    # ==========================================
    # CASI RECUPERO INFORMAZIONI MASSIVO
    # ==========================================

    def test_20_recupera_nrecord_da_num_prot(self):
        """
        Testa il recupero massivo dell'nrecord per due documenti distinti,
        utilizzando il loro numero di protocollo (num_prot) come chiave di ricerca.
        Stampa a terminale il dizionario risultante.
        """
        # Se li hai definiti in altri file, assicurati di averli importati in cima!
        # Esempio: from mio_modulo.enums import TitulusIdType, TitulusDocNodeAttribs

        # 1. Definiamo i due numeri di protocollo di test
        # (Uso quelli presenti nel tuo XML precedente come esempio)
        protocolli_da_cercare = [
            "2026-EXAMPLE-0000545",
            "2026-EXAMPLE-0000320"
        ]

        # 2. Definiamo le informazioni che vogliamo farci restituire (in questo caso 'nrecord')
        info_richieste = ["nrecord"]

        # 3. Invochiamo il wrapper che abbiamo creato
        risultati = services.recupera_info_documenti(
            id_type=TitulusIdType.NUM_PROT,  # Assicurati di usare l'Enum corretto
            ids=protocolli_da_cercare,
            required_infos=info_richieste,
            credential_ws_protocollo=self.mock_cred,
            test=True
        )

        # 4. Verifica di base per il test
        self.assertIsNotNone(risultati, "Il wrapper ha restituito None invece di un dizionario.")
        self.assertTrue(len(risultati) > 0, "Il dizionario dei risultati è vuoto.")

        # 5. Stampa a video dei risultati estratti (come da te richiesto)
        print("\n" + "=" * 50)
        print("RISULTATI RICERCA NRECORD DA NUM_PROT")
        print("=" * 50)
        for doc_id, infos in risultati.items():
            nrecord_trovato = infos.get("nrecord", "NON TROVATO")
            print(f"Num. Protocollo cercato: {doc_id}")
            print(f"Nrecord estratto:        {nrecord_trovato}")
            print("-" * 50)