from django.contrib import admin
from titulus_utility.models import CredentialWSProtocollo, ConfigurationWSProtocollo, VoceIndice, \
    ConfigurationWSProtocolloCC, Repertorio


# admin.site.register(ConfigurationWSProtocollo)
# admin.site.register(CredentialWSProtocollo)
# admin.site.register(VoceIndice)

class ConfigurationWSProtocolloCCInline(admin.TabularInline):
    model = ConfigurationWSProtocolloCC
    extra = 1  # Mostra sempre una riga vuota extra per aggiungere un nuovo CC
    classes = ['collapse']  # Rende il blocco collassabile per risparmiare spazio
    verbose_name = "Destinatario in Copia Conoscenza (CC)"
    verbose_name_plural = "Destinatari in Copia Conoscenza (CC)"


@admin.register(ConfigurationWSProtocollo)
class ConfigurationWSProtocolloAdmin(admin.ModelAdmin):
    # Colonne visibili nella lista generale
    list_display = ('name', 'content_type', 'object_id', 'is_active', 'created')
    list_filter = ('is_active', 'content_type')
    search_fields = ('name', 'object_id', 'protocollo_uo_rpa')

    # Inseriamo i CC dentro la pagina della configurazione!
    inlines = [ConfigurationWSProtocolloCCInline]

    # Raggruppiamo i campi in sezioni ordinate
    fieldsets = (
        (None, {
            'fields': ('name', 'is_active')
        }),
        ('Legame Oggetto Django', {
            'fields': ('content_type', 'object_id'),
            'description': "Riferimento generico all'oggetto (es. Struttura o Categoria)"
        }),
        ('Parametri Protocollo (RPA)', {
            'fields': (
                'protocollo_uo',
                'protocollo_uo_rpa',
                'protocollo_uo_rpa_username',
                'protocollo_uo_rpa_matricola'
            )
        }),
        ('Classificazione e Fascicolazione', {
            'fields': (
                'protocollo_cod_titolario',
                'protocollo_fascicolo_numero',
                'protocollo_fascicolo_anno'
            )
        }),
        ('Notifiche e Email', {
            'fields': ('protocollo_send_email', 'protocollo_email')
        }),
    )

    def save_model(self, request, obj, form, change):
        """Richiama il tuo metodo per disattivare le altre configurazioni se questa è attiva"""
        if obj.is_active:
            obj.disable_other_configurations()
        super().save_model(request, obj, form, change)


@admin.register(CredentialWSProtocollo)
class CredentialWSProtocolloAdmin(admin.ModelAdmin):
    list_display = ('name', 'content_type', 'is_active', 'protocollo_username')

    def save_model(self, request, obj, form, change):
        if obj.is_active:
            obj.disable_other_configurations()
        super().save_model(request, obj, form, change)



admin.site.register(VoceIndice)
admin.site.register(Repertorio)