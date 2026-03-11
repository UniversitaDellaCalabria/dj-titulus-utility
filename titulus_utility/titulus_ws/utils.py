

def get_protocol_dict(**kwargs):
    # Controllo di obbligatorietà senza valori di default
    if 'tipo' not in kwargs or not kwargs['tipo']:
        raise ValueError("Il parametro 'tipo' (es. 'arrivo', 'partenza') è obbligatorio.")

    if 'oggetto' not in kwargs or not kwargs['oggetto']:
        raise ValueError("Il parametro 'oggetto' è obbligatorio.")

    protocol_data = {
        # --- Variabili base ---
        'tipo_documento': kwargs['tipo'],
        'bozza': kwargs.get('bozza', 'no'),
        'oggetto': '{:<20}'.format(kwargs['oggetto']),
        'autore': kwargs.get('autore'),
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
        'label_notifica': kwargs.get('label_notifica','Invio notifica fine ITER'),
        'method_notifica': kwargs.get('method_notifica','POST'),
    }
    return protocol_data
