"""
Analyse de tendance NCY et calcul surcoût multi-colis DPD
"""

def calcul_surcoût_multicolis_dpd(nb_colis_9_10kg, sgo_dpd, profil='auto'):
    """
    Pour les colis 9-10kg refusés chez DPD (>300cm) :
    - 2 grandes valises cerclées (308cm) → 2 colis DPD 5kg
    - 3 cabines cerclées (339cm) → 2 colis DPD (6kg + 3kg)
    Retourne le surcoût annuel DPD vs GLS sur ce flux
    """
    from utils.tarifs import DPD_FR, DPD_SURETE, DPD_LOG, GLS_FR, GLS_CSR, GLS_PER

    def dpd_cout(poids, sgo):
        for k in sorted(DPD_FR.keys()):
            if poids <= k:
                b = DPD_FR[k]
                return b * (1 + sgo) + DPD_SURETE + DPD_LOG
        return (DPD_FR[20] + (poids-20)*0.30) * (1+sgo) + DPD_SURETE + DPD_LOG

    def gls_cout_moy(poids, sgo_gls_net=0.18):
        for k in sorted(GLS_FR.keys()):
            if poids <= k:
                b = GLS_FR[k]
                base = b + GLS_CSR
                return base * (1 + GLS_PER + sgo_gls_net)
        return 0

    # GLS : 1 colis 9-10kg (poids moyen 9.5kg) avec NCY à 39%
    NCY_GLS = 7.45
    TAUX_NCY = 0.39
    gls_9kg = gls_cout_moy(9.5, 0.18) + NCY_GLS * TAUX_NCY

    # DPD cas A : 2 grandes valises → 2 × 5kg
    dpd_2_soutes = dpd_cout(5, sgo_dpd) * 2

    # DPD cas B : 3 cabines → 1 × 6kg + 1 × 3kg
    dpd_3_cabines = dpd_cout(6, sgo_dpd) + dpd_cout(3, sgo_dpd)

    # Surcoût par colis (pire cas = 50/50)
    dpd_moy = 0.5 * dpd_2_soutes + 0.5 * dpd_3_cabines
    surcoût_par_colis = dpd_moy - gls_9kg

    return {
        'gls_9kg_ht': round(gls_9kg, 2),
        'dpd_2_soutes_ht': round(dpd_2_soutes, 2),
        'dpd_3_cabines_ht': round(dpd_3_cabines, 2),
        'dpd_moy_ht': round(dpd_moy, 2),
        'surcoût_par_colis_ht': round(surcoût_par_colis, 2),
        'surcoût_total_ht': round(surcoût_par_colis * nb_colis_9_10kg, 2),
        'surcoût_total_ttc': round(surcoût_par_colis * nb_colis_9_10kg * 1.2, 2),
        'dpd_gagne': surcoût_par_colis < 0,
    }

def tendance_ncy(mois_data):
    """
    Calcule la tendance NCY sur les mois chargés.
    Retourne liste de dict {label, taux_ncy, nb_ncy, ncy_ht, trend_pts}
    """
    resultats = []
    prev_taux = None

    for m in mois_data:
        nb = m.get('nb_colis', 0)
        nb_ncy = m.get('nb_ncy', 0)
        ncy_ht = m.get('total_ncy_ht', 0)
        taux = nb_ncy/nb*100 if nb > 0 else 0

        trend = None
        if prev_taux is not None:
            trend = taux - prev_taux

        resultats.append({
            'label': m['label'],
            'nb_colis': nb,
            'nb_ncy': nb_ncy,
            'taux_ncy': round(taux, 1),
            'ncy_ht': round(ncy_ht, 2),
            'ncy_ttc': round(ncy_ht * 1.2, 2),
            'ncy_par_colis': round(ncy_ht/nb, 2) if nb else 0,
            'trend_pts': round(trend, 1) if trend is not None else None,
        })
        prev_taux = taux

    return resultats
