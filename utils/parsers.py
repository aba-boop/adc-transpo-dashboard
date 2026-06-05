"""
Parsers BCF GLS et simulation DPD
"""
import csv
import pandas as pd
from io import StringIO
from collections import defaultdict
from utils.tarifs import (
    cout_gls, cout_dpd, get_sgo_mois,
    SURCHARGES_NCY, SURCHARGES_GEO, PAYS_GARDER_GLS,
    GLS_CSR, GLS_PER, DPD_SURETE, DPD_LOG
)

SURCHARGE_RETOUR = 'SUR_RET_BUP_D01'

def to_f(s):
    try:
        return float(str(s).replace(',', '.').strip())
    except:
        return 0.0

def parse_bcf_gls(file_obj, annee=None, mois=None, sgo_gls_manuel=None, sgo_dpd_manuel=None):
    """
    Parse un BCF GLS (CSV ;) et simule les coûts DPD équivalents.
    Retourne un dict avec stats complètes.
    """
    sgo_gls_net, sgo_dpd = get_sgo_mois(annee, mois, sgo_gls_manuel, sgo_dpd_manuel)

    try:
        content = file_obj.read()
        try:
            text = content.decode('utf-8')
        except:
            text = content.decode('latin-1')
        df_raw = pd.read_csv(StringIO(text), sep=';', dtype=str, on_bad_lines='skip')
    except Exception as e:
        return None, str(e)

    # Lecture ligne par ligne
    colis_data = {}

    for _, row in df_raw.iterrows():
        colis = str(row.get('Numéro de colis', '')).strip()
        art   = str(row.get('Article', '')).strip()
        pays  = str(row.get('Code Pays', 'FR')).strip() or 'FR'
        poids = to_f(row.get('Poids pour le traitement commande vente', ''))
        ligne = (to_f(row.get('Valeur de Base', '')) + to_f(row.get('CSR', '')) +
                 to_f(row.get('PER', '')) + to_f(row.get('SGO', '')) +
                 to_f(row.get('prix kilos additionnel', '')) +
                 to_f(row.get('Saisie manuelle', '')))

        if not colis or colis == 'nan':
            continue

        if colis not in colis_data:
            colis_data[colis] = {
                'pays': pays, 'poids': 0.0,
                'gls_transport': 0.0,
                'gls_surcharges_geo_gls': 0.0,
                'gls_surcharges_geo_dpd': 0.0,
                'gls_ncy': 0.0,
                'gls_retour': 0.0,
                'is_colis': False,
                'articles': [],
            }

        # Poids max sur toutes les lignes
        if poids > colis_data[colis]['poids']:
            colis_data[colis]['poids'] = poids
        if pays not in ('FR', '', 'nan'):
            colis_data[colis]['pays'] = pays

        colis_data[colis]['articles'].append(art)

        # Catégorisation
        if art in SURCHARGES_NCY:
            colis_data[colis]['gls_ncy'] += ligne

        elif art == SURCHARGE_RETOUR:
            colis_data[colis]['gls_retour'] += ligne

        elif art in SURCHARGES_GEO:
            colis_data[colis]['gls_surcharges_geo_gls'] += SURCHARGES_GEO[art]['gls'] or 0
            colis_data[colis]['gls_surcharges_geo_dpd'] += SURCHARGES_GEO[art]['dpd'] or 0

        elif art.startswith(('PARCEL_', 'FDS_', 'SDS_', 'EXPRESS_', 'SRS_')):
            colis_data[colis]['gls_transport'] += ligne
            if art.startswith(('PARCEL_', 'FDS_', 'SDS_')):
                colis_data[colis]['is_colis'] = True

    # Poids moyens par pays (imputation)
    poids_par_pays = defaultdict(list)
    for c, d in colis_data.items():
        if d['is_colis'] and d['poids'] > 0:
            poids_par_pays[d['pays']].append(d['poids'])
    poids_global = (sum(sum(v) for v in poids_par_pays.values()) /
                    max(sum(len(v) for v in poids_par_pays.values()), 1))

    # Simulation et statistiques
    rows = []
    stats = {
        'nb_colis': 0,
        'total_gls_ht': 0.0, 'total_dpd_ht': 0.0,
        'total_ncy_ht': 0.0, 'nb_ncy': 0,
        'total_retour_ht': 0.0, 'nb_retour': 0,
        'par_pays': defaultdict(lambda: {'nb': 0, 'gls': 0.0, 'dpd': 0.0, 'ncy': 0.0}),
        'par_zone': defaultdict(lambda: {'nb': 0, 'gls': 0.0, 'dpd': 0.0, 'ncy': 0.0}),
        'par_format': defaultdict(lambda: {'nb': 0, 'gls': 0.0, 'dpd': 0.0, 'ncy': 0.0}),
        'sgo_gls_net': sgo_gls_net,
        'sgo_dpd': sgo_dpd,
        'alertes': [],
    }

    for colis, d in colis_data.items():
        if not d['is_colis']:
            continue

        pays  = d['pays']
        poids = d['poids']
        if poids <= 0:
            pm = poids_par_pays.get(pays)
            poids = sum(pm) / len(pm) if pm else poids_global

        # Calcul DPD transport
        _, dpd_t = cout_dpd(poids, pays, sgo_dpd)

        # Retour DPD = même coût que aller DPD
        dpd_retour = dpd_t if d['gls_retour'] > 0 else 0.0

        # Totaux
        gls_total = (d['gls_transport'] + d['gls_surcharges_geo_gls'] +
                     d['gls_retour'] + d['gls_ncy'])
        dpd_total = dpd_t + d['gls_surcharges_geo_dpd'] + dpd_retour

        # Format colis
        if poids <= 0:
            fmt = 'Non renseigné'
        elif poids < 2.5:
            fmt = 'Petit (<2.5kg)'
        elif poids < 4.5:
            fmt = 'Cabine (2.5-4.5kg)'
        elif poids <= 5.0:
            fmt = 'Soute (4.5-5kg)'
        elif poids <= 10.0:
            fmt = 'Grande soute (5-10kg)'
        else:
            fmt = 'Multi-colis (>10kg)'

        # Zone
        if pays == 'FR':
            zone = 'France'
        elif pays in ('DE',):
            zone = 'Europe Zone 1'
        elif pays in ('BE', 'NL', 'LU'):
            zone = 'Europe Zone 1'
        elif pays in ('ES', 'PT', 'AT', 'PL'):
            zone = 'Europe Zone 2'
        elif pays in ('IT', 'SE', 'GR', 'RO', 'BG'):
            zone = 'Europe Zone 3'
        else:
            zone = f'Europe ({pays})'

        # Recommandation
        if pays in PAYS_GARDER_GLS:
            reco = 'GLS'
        elif poids >= 4.5:
            reco = 'DPD'
        else:
            reco = 'EQUAL'

        rows.append({
            'numero_colis': colis,
            'pays': pays,
            'zone': zone,
            'poids': poids,
            'format': fmt,
            'gls_ht': round(gls_total, 4),
            'dpd_ht': round(dpd_total, 4),
            'economie_ht': round(gls_total - dpd_total, 4),
            'ncy_ht': round(d['gls_ncy'], 4),
            'retour_ht': round(d['gls_retour'], 4),
            'has_ncy': d['gls_ncy'] > 0,
            'transporteur_reco': reco,
        })

        # Stats globales
        stats['nb_colis'] += 1
        stats['total_gls_ht'] += gls_total
        stats['total_dpd_ht'] += dpd_total
        stats['total_ncy_ht'] += d['gls_ncy']
        if d['gls_ncy'] > 0:
            stats['nb_ncy'] += 1
        if d['gls_retour'] > 0:
            stats['nb_retour'] += 1
            stats['total_retour_ht'] += d['gls_retour']

        stats['par_pays'][pays]['nb'] += 1
        stats['par_pays'][pays]['gls'] += gls_total
        stats['par_pays'][pays]['dpd'] += dpd_total
        stats['par_pays'][pays]['ncy'] += d['gls_ncy']

        stats['par_zone'][zone]['nb'] += 1
        stats['par_zone'][zone]['gls'] += gls_total
        stats['par_zone'][zone]['dpd'] += dpd_total
        stats['par_zone'][zone]['ncy'] += d['gls_ncy']

        stats['par_format'][fmt]['nb'] += 1
        stats['par_format'][fmt]['gls'] += gls_total
        stats['par_format'][fmt]['dpd'] += dpd_total
        stats['par_format'][fmt]['ncy'] += d['gls_ncy']

    # Alertes
    eco_pct = (stats['total_gls_ht'] - stats['total_dpd_ht']) / stats['total_gls_ht'] * 100 if stats['total_gls_ht'] else 0
    if stats['total_ncy_ht'] > 500:
        stats['alertes'].append(f"⚠️ NCY élevée : {stats['total_ncy_ht']:.0f}€ HT ({stats['nb_ncy']} colis)")
    if eco_pct > 10:
        stats['alertes'].append(f"✅ DPD permettrait d'économiser {eco_pct:.1f}% sur ce mois")

    it_gls = stats['par_pays'].get('IT', {}).get('gls', 0)
    it_dpd = stats['par_pays'].get('IT', {}).get('dpd', 0)
    if it_gls > 0 and it_dpd > it_gls:
        stats['alertes'].append(f"🇮🇹 Italie : garder GLS (DPD +{it_dpd-it_gls:.0f}€ plus cher ce mois)")

    stats['df'] = pd.DataFrame(rows)
    stats['economie_ht'] = stats['total_gls_ht'] - stats['total_dpd_ht']
    stats['economie_ttc'] = stats['economie_ht'] * 1.20
    stats['total_gls_ttc'] = stats['total_gls_ht'] * 1.20
    stats['total_dpd_ttc'] = stats['total_dpd_ht'] * 1.20

    return stats, None
