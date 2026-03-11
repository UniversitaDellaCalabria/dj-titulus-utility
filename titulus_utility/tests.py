import os
from django.test import TestCase
from django.conf import settings
from unittest.mock import MagicMock

from titulus_utility import services
from titulus_utility import conf as titulus_settings
from titulus_utility.titulus_ws.protocollo import Protocollo


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
        self.test_file_name = "documento_test"
        self.attachment_folder = titulus_settings.ATTACHMENT_FOLDER_TEST

    def test_01_connessione_diretta_client(self):
        """
        Testa la connessione base a Zeep usando le credenziali di test.
        Se questo fallisce, l'URL o le credenziali nel localsettings sono errate.
        """
        client = Protocollo(
            wsdl_url=titulus_settings.PROTOCOL_TEST_URL,
            username=titulus_settings.PROTOCOL_TEST_LOGIN,
            password=titulus_settings.PROTOCOL_TEST_PASSW,
            template_xml_flusso="<doc><test/></doc>"  # Un template fittizio per inizializzare
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
            subject="TEST INTEGRAZIONE 1 - Arrivo, Protocollo, No Allegati",
            credential_ws_protocollo=self.mock_cred,
            configuration_ws_protocollo=self.mock_conf,
            principal_file_name=self.test_file_name,
            principal_file=self.test_file_content,
            test=True
        )
        self.assertIn("numero", risultato)
        self.assertIsNotNone(risultato["numero"])

    def test_02_arrivo_protocollo_con_allegati(self):
        attachments = self._get_test_attachments()
        self.assertTrue(len(attachments) > 0, "Nessun file trovato in ATTACHMENT_FOLDER_TEST per il test.")

        risultato = services.protocolla_arrivo(
            user=self.mock_user,
            subject="TEST INTEGRAZIONE 2 - Arrivo, Protocollo, Con Allegati",
            credential_ws_protocollo=self.mock_cred,
            configuration_ws_protocollo=self.mock_conf,
            principal_file_name=self.test_file_name,
            principal_file=self.test_file_content,
            attachments=attachments,
            attachments_folder=self.attachment_folder,
            test=True
        )
        self.assertIn("numero", risultato)
        self.assertIsNotNone(risultato["numero"])

    # ==========================================
    # CASI PARTENZA - PROTOCOLLO DIRETTO
    # ==========================================

    def test_03_partenza_protocollo_senza_allegati(self):
        risultato = services.protocolla_partenza(
            subject="TEST INTEGRAZIONE 3 - Partenza, Protocollo, No Allegati",
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
            subject="TEST INTEGRAZIONE 4 - Partenza, Protocollo, Con Allegati",
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
            subject="TEST INTEGRAZIONE 5 - Arrivo, Bozza/Iter, No Allegati",
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
            subject="TEST INTEGRAZIONE 5 - Arrivo, Bozza/Iter, No Allegati e Notifica",
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
            subject="TEST INTEGRAZIONE 6 - Arrivo, Bozza/Iter, Con Allegati",
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
            subject="TEST INTEGRAZIONE 6 - Arrivo, Bozza/Iter, Con Allegati e Notifica",
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
            subject="TEST INTEGRAZIONE 7 - Partenza, Bozza/Iter, No Allegati",
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

    def test_07_partenza_bozza_iter_senza_allegati_notifica(self):
        risultato = services.avvia_iter_partenza(
            subject="TEST INTEGRAZIONE 7 - Partenza, Bozza/Iter, No Allegati e Notifica",
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
            subject="TEST INTEGRAZIONE 8 - Partenza, Bozza/Iter, Con Allegati",
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
            subject="TEST INTEGRAZIONE 8 - Partenza, Bozza/Iter, Con Allegati e Notifica",
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