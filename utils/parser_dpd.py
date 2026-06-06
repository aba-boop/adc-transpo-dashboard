"""
Parser BCF DPD — Structure validée sur BCF client (même format tous clients)
Contrat ADC : poids réel (volumétrique barré), SGO sur barème seul
"""
import pandas as pd
from io import BytesIO
from collections import defaultdict
from utils.tarifs import (
    DPD_FR, DPD_EU, PAYS_ZONE_DPD, PAYS_GARDER_GLS,
    DPD_SURETE, DPD_LOG, get_sgo_mois
)

def to_f(s):
    try:
        return float(str(s).replace(',', '.').replace(' ', '').strip())
    except:
        return 0.0

# ─── ALERTES CONTRACTUELLES ───────────────────────────────────────────────────
ALERTES_CONTRACTUELLES = {
    'solution_etiquetage': {
        'label': 'Solution étiquetage / Location Zebra',
        'montant_ref': 60.0,
        'message': '⚠️ 60€/mois facturé pour solution étiquetage — injustifié si vous avez votre propre Zebra',
        'colonne': None,  # détecté sur le montant fixe dans frais
    },
    'poids_volumetrique': {
        'label': 'Refacturation au poids volumétrique',
        'message': '🔴 Colis refacturé au poids volumétrique — cette clause est BARRÉE dans votre contrat ADC',
        'colonne': 'Colis refacturé',
    },
    'consignation_edi': {
        'label': 'Consignation EDI manquante',
        'message': '🟡 EDI manquant — problème d\'intégration technique à corriger (0,50€/colis)',
        'colonne': 'Nombre Consignation EDI manquante ou incomplète',
    },
    'avis_eleve': {
        'label': 'Taux d\'avisés élevé',
        'message': '⚠️ Taux d\'avisés > 5% — vérifier que le Predict (tél + email) est bien transmis',
        'colonne': 'Nombre statuts Absents Avisés',
    },
}

def get_dpd_bareme(poids, pays='FR'):
    """Retourne le barème DPD selon poids et pays."""
    if pays == 'FR':
        grille = DPD_FR
        for k in sorted(grille.keys()):
            if poids <= k:
                return grille[k]
        return grille[20] + (poids - 20) * 0.30
    else:
        zone = PAYS_ZONE_DPD.get(pays, 3)
        grille = DPD_EU.get(zone, DPD_EU[3])
        for k in sorted(grille.keys()):
            if poids <= k:
                return grille[k]
        return grille[20]

def parse_bcf_dpd(file_obj, config=None, annee=None, mois=None,
                   sgo_dpd_manuel=None):
    """
    Parse un BCF DPD (Excel .xlsx)
    config = dict des options contractuelles ADC :
        {
            'has_zebra': True,           # Zebra propre → alerte si étiquetage facturé
            'volumetrique_barre': True,  # Clause barrée → alerte si refacturé
            'predict_actif': True,       # Predict transmis → alerte si avisés > 5%
            'cout_avis': 1.0,            # Tarif avisé négocié (1€ ou 4€)
        }
    """
    if config is None:
        config = {
            'has_zebra': True,
            'volumetrique_barre': True,
            'predict_actif': True,
            'cout_avis': 1.0,
        }

    _, sgo_dpd = get_sgo_mois(annee, mois, None, sgo_dpd_manuel)

    try:
        content = file_obj.read()
        df = pd.read_excel(BytesIO(content), engine='openpyxl')
    except Exception as e:
        try:
            df = pd.read_excel(BytesIO(content), engine='xlrd')
        except Exception as e2:
            return None, f"Erreur lecture Excel : {e2}"

    nb_colis = len(df)
    if nb_colis == 0:
        return None, "Fichier vide"

    # ─── STATS GLOBALES ──────────────────────────────────────────────────────
    stats = {
        'nb_colis': nb_colis,
        'transporteur': 'DPD',
        'sgo_dpd': sgo_dpd,

        # Coûts réels facturés
        'total_transport_ht': df['Prix transport'].sum() if 'Prix transport' in df.columns else 0,
        'total_sgo_ht': df['Indexation gasoil'].sum() if 'Indexation gasoil' in df.columns else 0,
        'total_surete_ht': df['Participation Sureté'].sum() if 'Participation Sureté' in df.columns else 0,
        'total_log_ht': df['Contribution Logistique Responsable'].sum() if 'Contribution Logistique Responsable' in df.columns else 0,
        'total_frais_compte_ht': df['Frais de tenue de compte'].sum() if 'Frais de tenue de compte' in df.columns else 0,
        'total_facture_ht': df['Prix cumulé'].sum() if 'Prix cumulé' in df.columns else 0,
        'total_tva': df['T.V.A'].sum() if 'T.V.A' in df.columns else 0,

        # Surcharges géo
        'total_ile_montagne_ht': df['Supplément île et montagne'].sum() if 'Supplément île et montagne' in df.columns else 0,
        'nb_ile_montagne': int((df['Supplément île et montagne'] > 0).sum()) if 'Supplément île et montagne' in df.columns else 0,

        # Avisés
        'nb_avis': int(df['Nombre statuts Absents Avisés'].sum()) if 'Nombre statuts Absents Avisés' in df.columns else 0,
        'cout_avis_ht': df['Fact. statuts Absent Avisés'].sum() if 'Fact. statuts Absent Avisés' in df.columns else 0,
        'taux_avis_pct': 0,

        # Volumétrique
        'nb_volumetrique': int((df['Colis refacturé'] == 1).sum()) if 'Colis refacturé' in df.columns else 0,

        # EDI
        'nb_edi': int(df['Nombre Consignation EDI manquante ou incomplète'].sum()) if 'Nombre Consignation EDI manquante ou incomplète' in df.columns else 0,
        'cout_edi_ht': df['Fact. Consignation EDI manquante ou incomplète'].sum() if 'Fact. Consignation EDI manquante ou incomplète' in df.columns else 0,

        # Retours
        'nb_retours': int(df['Nombre Retour expédition'].sum()) if 'Nombre Retour expédition' in df.columns else 0,
        'cout_retours_ht': df['Fact. Retour expédition'].sum() if 'Fact. Retour expédition' in df.columns else 0,

        # SMS Predict
        'nb_sms': int(df['Nombre Avisage par SMS'].sum()) if 'Nombre Avisage par SMS' in df.columns else 0,
        'cout_sms_ht': df['Fact. Avisage par SMS'].sum() if 'Fact. Avisage par SMS' in df.columns else 0,

        # Hors norme
        'nb_hors_norme': int(df['Nombre statuts Hors norme'].sum()) if 'Nombre statuts Hors norme' in df.columns else 0,

        # Contrôle anomalies
        'anomalies': [],
        'alertes': [],
    }

    # Taux avisés
    if nb_colis > 0:
        stats['taux_avis_pct'] = stats['nb_avis'] / nb_colis * 100

    stats['total_facture_ttc'] = stats['total_facture_ht'] + stats['total_tva']
    stats['cout_moyen_colis_ht'] = stats['total_facture_ht'] / nb_colis if nb_colis > 0 else 0

    # ─── ANOMALIES ET ALERTES CONTRACTUELLES ─────────────────────────────────
    anomalies = []

    # 1. Poids volumétrique (clause barrée dans contrat ADC)
    if config.get('volumetrique_barre') and stats['nb_volumetrique'] > 0:
        df_volu = df[df['Colis refacturé'] == 1].copy()
        df_volu['poids_reel'] = df_volu['Poids initial']
        df_volu['poids_facture'] = df_volu['Poids']
        df_volu['surpoids'] = df_volu['poids_facture'] - df_volu['poids_reel']
        surpoids_total = df_volu['surpoids'].sum()

        # Estimer le surcoût
        surtaxe = 0
        for _, row in df_volu.iterrows():
            bar_reel = get_dpd_bareme(row['Poids initial'], 'FR')
            bar_fact = row['Prix transport']
            surtaxe += max(0, bar_fact - bar_reel)

        anomalies.append({
            'Type': '🔴 Poids volumétrique (clause barrée)',
            'Nb colis': stats['nb_volumetrique'],
            'Surpoids total': f"+{surpoids_total:.1f} kg",
            'Surcoût estimé HT': f"+{surtaxe:.2f}€",
            'Action': 'RÉCLAMER À DPD — clause barrée dans votre contrat',
            'Gravité': '🔴 Élevée',
        })
        stats['alertes'].append(f"🔴 {stats['nb_volumetrique']} colis facturés au poids volumétrique — clause BARRÉE dans votre contrat ADC ! Surcoût estimé : {surtaxe:.2f}€ HT")

    # 2. EDI manquant
    if stats['nb_edi'] > 0:
        anomalies.append({
            'Type': '🟡 Consignation EDI manquante',
            'Nb colis': stats['nb_edi'],
            'Surpoids total': '—',
            'Surcoût estimé HT': f"+{stats['cout_edi_ht']:.2f}€",
            'Action': 'Corriger intégration technique avec DPD',
            'Gravité': '🟡 Modérée',
        })
        stats['alertes'].append(f"🟡 {stats['nb_edi']} colis avec EDI manquante ({stats['cout_edi_ht']:.2f}€ HT) — problème d'intégration technique à corriger")

    # 3. Avisés élevés
    if stats['taux_avis_pct'] > 5:
        anomalies.append({
            'Type': '⚠️ Taux d\'avisés élevé',
            'Nb colis': stats['nb_avis'],
            'Surpoids total': f"{stats['taux_avis_pct']:.1f}%",
            'Surcoût estimé HT': f"{stats['cout_avis_ht']:.2f}€",
            'Action': 'Vérifier transmission tél + email (Predict)',
            'Gravité': '🟡 Modérée',
        })
        stats['alertes'].append(f"⚠️ Taux d'avisés : {stats['taux_avis_pct']:.1f}% (>{5}%) — vérifier que le Predict est bien transmis")

    # 4. Tarif avisé > tarif négocié
    if stats['nb_avis'] > 0 and stats['cout_avis_ht'] > 0:
        cout_unit_reel = stats['cout_avis_ht'] / stats['nb_avis']
        cout_unit_negocie = config.get('cout_avis', 1.0)
        if cout_unit_reel > cout_unit_negocie + 0.10:
            surcoût_avis = (cout_unit_reel - cout_unit_negocie) * stats['nb_avis']
            anomalies.append({
                'Type': '🔴 Tarif avisé incorrect',
                'Nb colis': stats['nb_avis'],
                'Surpoids total': f"{cout_unit_reel:.2f}€/avisé facturé vs {cout_unit_negocie:.2f}€ négocié",
                'Surcoût estimé HT': f"+{surcoût_avis:.2f}€",
                'Action': 'RÉCLAMER — tarif supérieur au contrat',
                'Gravité': '🔴 Élevée',
            })
            stats['alertes'].append(f"🔴 Avisés facturés à {cout_unit_reel:.2f}€ au lieu de {cout_unit_negocie:.2f}€ négocié — surcoût : {surcoût_avis:.2f}€ HT")

    # 5. Alerte Zebra (frais fixes 60€/mois)
    if config.get('has_zebra'):
        frais_compte = stats['total_frais_compte_ht']
        if frais_compte > 65:  # 60€ + frais tenue de compte normaux
            stats['alertes'].append(f"⚠️ Frais fixes élevés ({frais_compte:.2f}€ HT) — vérifier qu'on ne paie pas la location Zebra (60€/mois)")

    stats['anomalies_df'] = pd.DataFrame(anomalies) if anomalies else pd.DataFrame()

    # ─── SIMULATION GLS ÉQUIVALENT ───────────────────────────────────────────
    # Calcul coût théorique GLS sur les mêmes colis pour comparaison
    from utils.tarifs import GLS_FR, GLS_CSR, GLS_PER, SGO_HISTORIQUE, GLS_REMISE_SGO
    import datetime
    now = datetime.datetime.now()
    key = (annee or now.year, mois or now.month)
    hist = SGO_HISTORIQUE.get(key, list(SGO_HISTORIQUE.values())[-1])
    sgo_gls_net = hist[0] - GLS_REMISE_SGO

    gls_theo_total = 0.0
    for _, row in df.iterrows():
        poids = to_f(row.get('Poids', 0)) or to_f(row.get('Poids initial', 0))
        if poids <= 0:
            poids = 4.0
        bareme = next((GLS_FR[k] for k in sorted(GLS_FR.keys()) if poids <= k), GLS_FR[30])
        base = bareme + GLS_CSR
        gls_theo_total += base * (1 + GLS_PER + sgo_gls_net)

    stats['gls_theorique_ht'] = gls_theo_total
    stats['economie_vs_gls_ht'] = gls_theo_total - stats['total_facture_ht']
    stats['economie_vs_gls_ttc'] = stats['economie_vs_gls_ht'] * 1.2

    # ─── DATAFRAME DÉTAILLÉ ──────────────────────────────────────────────────
    df_detail = df.copy()
    df_detail['bareme_theorique'] = df_detail.apply(
        lambda r: get_dpd_bareme(to_f(r.get('Poids', 0)) or 4.0, 'FR'), axis=1
    )
    df_detail['sgo_theorique'] = df_detail['bareme_theorique'] * sgo_dpd
    df_detail['total_theorique'] = df_detail['bareme_theorique'] + df_detail['sgo_theorique'] + DPD_SURETE + DPD_LOG
    df_detail['ecart_bareme'] = df_detail['Prix transport'] - df_detail['bareme_theorique']

    cols_garder = ['Poids', 'Poids initial', 'Prix transport', 'Indexation gasoil',
                   'Participation Sureté', 'Contribution Logistique Responsable',
                   'Prix cumulé', 'Colis refacturé',
                   'Nombre statuts Absents Avisés', 'Fact. statuts Absent Avisés',
                   'Nombre Consignation EDI manquante ou incomplète',
                   'bareme_theorique', 'sgo_theorique', 'total_theorique', 'ecart_bareme']
    cols_dispo = [c for c in cols_garder if c in df_detail.columns]
    stats['df'] = df_detail[cols_dispo].copy()

    return stats, None
