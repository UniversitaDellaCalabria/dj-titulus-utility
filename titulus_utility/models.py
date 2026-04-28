import sys

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from . import conf as titulus_settings

_protocollo_titolario_list = titulus_settings.TITOLARIO_DICT
_protocollo_uo_list = titulus_settings.UO_DICT
if 'makemigrations' in sys.argv or 'migrate' in sys.argv:  # pragma: no cover
    _protocollo_titolario_list = [('', '-')]
    _protocollo_uo_list = [('', '-')]


class TimeStampedModel(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CredentialWSProtocollo(TimeStampedModel):
    """
        Modello per l'archiviazione delle credenziali di accesso al WS Titulus.

        Usa una GenericForeignKey per legarsi in modo lasso a qualsiasi modello
        del progetto Django genitore. Le istanze recuperate da questo modello
        (assieme a ConfigurationWSProtocollo) vengono passate ai servizi di
        `services.py` per autorizzare le chiamate SOAP inoltrate da `protocollo.py`.
    """
    # 1. Puntatore al modello
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    # 2. ID dell'oggetto (manteniamo CharField per flessibilità PK)
    object_id = models.CharField(max_length=125)
    # 3. La GenericForeignKey "virtuale"
    content_object = GenericForeignKey('content_type', 'object_id')
    """
    Note: These fields (above) implement a loose-coupled generic relationship. 
    They allow the application to reference external objects without importing 
    their specific models, preventing circular dependencies and keeping 
    the app model-agnostic.
    """
    name = models.CharField(_("Denominazione configurazione"), max_length=255)
    is_active = models.BooleanField(default=False)

    protocollo_username = models.CharField("Username", max_length=255)
    protocollo_password = models.CharField("Password", max_length=255)
    protocollo_aoo = models.CharField("AOO", max_length=12)
    protocollo_agd = models.CharField(
        "AGD", max_length=12, default="", blank=True)

    # protocollo_template = models.TextField('XML template',
    # help_text=_('Template XML che '
    # 'descrive il flusso'))
    @classmethod
    def create_for_object(cls, obj, **kwargs):
        """
        Creates a CredentialWSProtocollo instance linked to a generic source object.
        equivalent to:
            CredentialWSProtocollo.objects.create(
                content_object=mio_ticket,
                name="Config 1",
                ...
            )
        """
        return cls.objects.create(content_object=obj, **kwargs)

    class Meta:
        ordering = ["-created"]
        verbose_name = _("Configurazione WS Protocollo Struttura")
        verbose_name_plural = _("Configurazioni WS Protocollo Strutture")

    def disable_other_configurations(self):
        others = CredentialWSProtocollo.objects.filter(
            content_type=self.content_type,
            object_id=self.object_id
        ).exclude(pk=self.pk)
        for other in others:
            other.is_active = False
            other.save(update_fields=["is_active", "modified"])

    @staticmethod
    def get_active_protocol_credential(obj):
        conf = CredentialWSProtocollo.objects.filter(
            content_type=ContentType.objects.get_for_model(obj),  # La traduzione avviene qui dentro
            object_id=str(obj.pk),
            is_active=True
        ).first()
        return conf if conf else False

    def __str__(self):
        return "{} - {} ({})".format(self.name, self.content_type, self.object_id)


class ConfigurationWSProtocollo(TimeStampedModel):
    """
        Modello per l'archiviazione dei parametri di rete/ufficio (UO, RPA, titolario).

        Accoppiato al modello `CredentialWSProtocollo`, fornisce i metadati necessari a
        `utils.get_protocol_dict()` per formattare l'XML e a `protocollo.py` per fascicolare
        il documento. Viene consumato dai wrappers di `services.py`.
    """
    # 1. Puntatore al modello
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    # 2. ID dell'oggetto (manteniamo CharField per flessibilità PK)
    object_id = models.CharField(max_length=125)
    # 3. La GenericForeignKey "virtuale"
    content_object = GenericForeignKey('content_type', 'object_id')
    """
    Note: These fields (above) implement a loose-coupled generic relationship. 
    They allow the application to reference external objects without importing 
    their specific models, preventing circular dependencies and keeping 
    the app model-agnostic.
    """
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=False)
    protocollo_uo = models.CharField("UO", max_length=12, choices=_protocollo_uo_list)
    protocollo_uo_rpa = models.CharField(
        "RPA", max_length=255, default="", blank=True, help_text=_("Nominativo RPA")
    )
    protocollo_uo_rpa_username = models.CharField(
        "RPA username",
        max_length=255,
        default="",
        blank=True,
        help_text=_("Username RPA sul sistema di protocollo"),
    )
    protocollo_uo_rpa_matricola = models.CharField(
        "RPA matricola",
        max_length=255,
        default="",
        blank=True,
        help_text=_("Matricola RPA sul sistema di protocollo"),
    )
    protocollo_send_email = models.BooleanField(
        _("Invia e-mail a RPA"), default=True)
    protocollo_email = models.EmailField(
        "E-mail",
        max_length=255,
        blank=True,
        null=True,
        help_text="default: settings.PROTOCOL_EMAIL_DEFAULT",
    )
    protocollo_cod_titolario = models.CharField(
        _("Codice titolario"), max_length=12, choices=_protocollo_titolario_list
    )
    protocollo_fascicolo_numero = models.CharField(
        _("Fascicolo numero"), max_length=255, default="", blank=True
    )
    protocollo_fascicolo_anno = models.IntegerField(
        _("Fascicolo anno"), null=True, blank=True
    )

    @classmethod
    def create_for_object(
            cls,
            obj,
            **kwargs):
        """
        Extracts model metadata from the source object and creates a new configuration instance.

        Args:
            obj (models.Model): The Django model instance to link (e.g., TicketCategory, OrganizationalStructure).
            name (str): Display name for this configuration.
            protocollo_uo (str): Organizational Unit (UO) code.
            protocollo_cod_titolario (str): Classification scheme (Titolario) code.
            is_active (bool, optional): Whether this configuration is active. Defaults to False.
            protocollo_uo_rpa (str, optional): Name of the RPA official. Defaults to "".
            protocollo_uo_rpa_username (str, optional): RPA username on protocol system. Defaults to "".
            protocollo_uo_rpa_matricola (str, optional): RPA employee ID. Defaults to "".
            protocollo_send_email (bool, optional): Whether to send email to RPA. Defaults to True.
            protocollo_email (str, optional): Specific email for protocol notifications. Defaults to None.
            protocollo_fascicolo_numero (str, optional): Folder number. Defaults to "".
            protocollo_fascicolo_anno (int, optional): Folder year. Defaults to None.

        Returns:
            ConfigurationWSProtocollo: The created configuration instance.
        """
        return cls.objects.create(content_object=obj, **kwargs)

    class Meta:
        ordering = ["-created"]
        verbose_name = _("Configurazione WS Protocollo Categoria")
        verbose_name_plural = _("Configurazioni WS Protocollo Categorie")

    def disable_other_configurations(self):
        others = ConfigurationWSProtocollo.objects.filter(
            content_type=self.content_type,
            object_id=self.object_id
        ).exclude(pk=self.pk)
        for other in others:
            other.is_active = False
            other.save(update_fields=["is_active", "modified"])

    @staticmethod
    def get_active_protocol_configuration(obj):
        conf = ConfigurationWSProtocollo.objects.filter(
            content_type=ContentType.objects.get_for_model(obj),  # La traduzione avviene qui dentro
            object_id=str(obj.pk),
            is_active=True
        ).first()
        return conf if conf else False

    def __str__(self):
        return "{} - {} ({})".format(self.name, self.content_type, self.object_id)

class ConfigurationWSProtocolloOP(TimeStampedModel):
    """
    Modello per l'archiviazione dell'Operatore (OP) incaricato.
    Legato a 1 a 1 con ConfigurationWSProtocollo.
    """
    configurazione = models.OneToOneField(
        ConfigurationWSProtocollo,
        on_delete=models.CASCADE,
        related_name="op_user"
    )
    protocollo_uo = models.CharField("UO", max_length=12, choices=_protocollo_uo_list)
    protocollo_persona = models.CharField(
        "Nominativo OP", max_length=255, default="", blank=True
    )
    protocollo_persona_username = models.CharField(
        "Username OP", max_length=255, default="", blank=True
    )
    protocollo_persona_matricola = models.CharField(
        "Matricola OP", max_length=255, default="", blank=True
    )

    class Meta:
        ordering = ["created"]
        verbose_name = _("Operatore Configurazione WS Protocollo")
        verbose_name_plural = _("Operatori Configurazioni WS Protocollo")

    def __str__(self):
        return f"OP: {self.protocollo_uo} - {self.protocollo_persona} ({self.configurazione.name})"


class ConfigurationWSProtocolloCC(TimeStampedModel):
    """
    Modello per l'archiviazione dei destinatari in Copia Conoscenza (CC).
    Legato a 1 a molti con ConfigurationWSProtocollo.
    """
    configurazione = models.ForeignKey(
        ConfigurationWSProtocollo,
        on_delete=models.CASCADE,
        related_name="cc_list"
    )
    protocollo_uo = models.CharField("UO", max_length=12, choices=_protocollo_uo_list)
    protocollo_persona = models.CharField(
        "Nominativo CC", max_length=255, default="", blank=True
    )
    protocollo_persona_username = models.CharField(
        "Username CC", max_length=255, default="", blank=True
    )
    protocollo_persona_matricola = models.CharField(
        "Matricola CC", max_length=255, default="", blank=True
    )

    class Meta:
        ordering = ["created"]
        verbose_name = _("Destinatario CC Configurazione WS Protocollo")
        verbose_name_plural = _("Destinatari CC Configurazioni WS Protocollo")

    def __str__(self):
        return f"CC: {self.protocollo_uo} - {self.protocollo_persona} ({self.configurazione.name})"


class VoceIndice(models.Model):
    voce_indice = models.CharField(max_length=255)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.voce_indice


class Repertorio(models.Model):
    repertorio = models.CharField(max_length=255)
    code = models.CharField(max_length=15)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.code}-{self.repertorio}"
