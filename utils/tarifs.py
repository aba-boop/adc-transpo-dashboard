"""
Grilles tarifaires ADC — GLS et DPD
Formules validées sur BCF réels (Déc 2025 → Mai 2026)
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ─── GRILLE GLS FRANCE — BusinessParcel (tarif 66645) ────────────────────────
GLS_FR = {
    0.5:4.22, 1:4.56, 2:4.78, 3:5.37, 4:6.05, 5:6.22,
    6:6.45,   7:6.68, 8:6.91, 9:7.14, 10:7.36, 11:7.81,
    12:8.03, 13:8.25, 14:8.50, 15:8.71, 16:9.16, 17:9.38,
    18:9.62, 19:9.83, 20:10.07, 21:11.11, 22:11.22, 23:11.32,
    24:11.44, 25:11.57, 26:11.67, 27:11.78, 28:11.91, 29:12.03, 30:12.12,
}
GLS_FR_SUPP_KG = 3.38  # par kg au-delà de 30kg

# ─── GRILLE GLS RELAIS — ShopDelivery ────────────────────────────────────────
GLS_RELAIS = {
    0.25:2.58, 0.5:2.66, 0.75:2.83, 1:3.01, 1.5:3.23, 2:3.45,
    3:3.84, 4:4.27, 5:4.71, 6:5.14, 7:5.59, 8:6.02, 9:6.46,
    10:6.91, 11:7.45, 12:7.98, 13:8.52, 14:9.06, 15:9.60,
    16:10.14, 17:10.68, 18:11.23, 19:11.77, 20:12.31,
    21:13.35, 22:13.89, 23:14.43, 24:14.96, 25:15.50,
    26:16.04, 27:16.59, 28:17.14, 29:17.68, 30:18.22,
}

# ─── GRILLE GLS EUROPE — EuroBusinessParcel (zones D11-D14) ──────────────────
# Zone D11 = Allemagne / D12 = Italie / D13 = Belgique,NL / D14 = Espagne,Portugal
GLS_EU = {
    'D11': {1:7.21,2:7.95,3:8.63,4:9.46,5:9.89,6:10.38,7:10.38,8:10.38,9:10.38,10:10.38,
            11:10.87,12:10.87,13:10.87,14:10.87,15:10.87,16:12.09,17:12.09,18:12.09,19:12.09,20:12.09,
            21:13.81,22:13.81,23:13.81,24:13.81,25:13.81,26:15.51,27:15.51,28:15.51,29:15.51,30:15.51},
    'D12': {1:7.37,2:8.13,3:8.82,4:9.67,5:10.12,6:10.62,7:10.62,8:10.62,9:10.62,10:10.62,
            11:11.12,12:11.12,13:11.12,14:11.12,15:11.12,16:12.36,17:12.36,18:12.36,19:12.36,20:12.36,
            21:14.12,22:14.12,23:14.12,24:14.12,25:14.12,26:15.86,27:15.86,28:15.86,29:15.86,30:15.86},
    'D13': {1:7.37,2:8.13,3:8.82,4:9.67,5:10.12,6:10.62,7:10.62,8:10.62,9:10.62,10:10.62,
            11:11.12,12:11.12,13:11.12,14:11.12,15:11.12,16:12.36,17:12.36,18:12.36,19:12.36,20:12.36,
            21:14.12,22:14.12,23:14.12,24:14.12,25:14.12,26:15.86,27:15.86,28:15.86,29:15.86,30:15.86},
    'D14': {1:11.14,2:11.63,3:12.52,4:13.57,5:13.84,6:14.40,7:14.40,8:14.40,9:14.40,10:14.40,
            11:14.51,12:14.51,13:14.51,14:14.51,15:14.51,16:16.44,17:16.44,18:16.44,19:16.44,20:16.44,
            21:18.95,22:18.95,23:18.95,24:18.95,25:18.95,26:21.65,27:21.65,28:21.65,29:21.65,30:21.65},
}

# Mapping pays → zone GLS Europe
PAYS_ZONE_GLS = {
    'DE':'D11',
    'IT':'D12',
    'BE':'D13','NL':'D13','LU':'D13',
    'ES':'D14','PT':'D14',
    'AT':'D13','PL':'D13','DK':'D13','CZ':'D13','HU':'D13',
    'SK':'D13','SI':'D13','HR':'D13','SE':'D13','FI':'D13',
    'GR':'D14','RO':'D14','BG':'D14','EE':'D14','LV':'D14','LT':'D14',
}

# ─── GRILLE DPD FRANCE — Predict ─────────────────────────────────────────────
DPD_FR = {
    1:4.62, 2:4.95, 3:5.29, 4:5.69, 5:6.29,
    6:6.65, 7:7.01, 8:7.41, 9:7.99, 10:8.05,
    11:8.55, 12:9.05, 13:9.55, 14:9.95, 15:10.05,
    16:10.11, 17:10.71, 18:11.11, 19:12.01, 20:12.21,
}
DPD_FR_SUPP_KG = 0.30  # par kg au-delà de 20kg

# ─── GRILLE DPD EUROPE ───────────────────────────────────────────────────────
DPD_EU = {
    1: {1:7.48,2:8.91,3:9.23,4:9.58,5:9.93,6:10.63,7:10.98,8:11.33,9:11.68,10:12.03,
        11:12.36,12:12.54,13:12.92,14:13.30,15:13.68,16:14.02,17:14.44,18:14.82,19:15.20,20:15.58},
    2: {1:8.74,2:9.50,3:9.88,4:10.26,5:10.64,6:11.02,7:11.40,8:11.78,9:12.16,10:12.54,
        11:12.54,12:12.54,13:13.08,14:13.68,15:14.44,16:16.02,17:16.72,18:17.48,19:17.85,20:18.24},
    3: {1:12.44,2:13.04,3:13.54,4:14.09,5:14.64,6:15.19,7:15.74,8:16.30,9:16.90,10:17.39,
        11:17.94,12:18.49,13:19.04,14:19.59,15:20.04,16:20.69,17:21.24,18:21.79,19:21.79,20:22.34},
    4: {1:16.12,2:16.82,3:17.39,4:18.12,5:18.82,6:19.12,7:19.12,8:19.12,9:19.12,10:20.62,
        11:21.62,12:21.12,13:21.12,14:21.12,15:21.12,16:24.62,17:24.62,18:27.12,19:27.12,20:27.12},
    5: {1:25.69,2:26.19,3:26.69,4:27.19,5:27.69,6:28.19,7:28.69,8:29.19,9:29.69,10:30.19,
        11:30.69,12:31.19,13:31.69,14:32.19,15:32.69,16:33.19,17:33.69,18:34.19,19:34.69,20:35.19},
}

PAYS_ZONE_DPD = {
    'DE':1,'NL':1,'BE':1,'LU':1,
    'AT':2,'ES':2,'PT':2,'PL':2,'DK':2,'CZ':2,'HU':2,'SK':2,'SI':2,'HR':2,
    'IT':3,'SE':3,'FI':3,'GR':3,'RO':3,'BG':3,'EE':3,'LV':3,'LT':3,
    'IE':4,'GB':4,
}

# Pays où GLS est recommandé même avec DPD disponible
PAYS_GARDER_GLS = {'IT'}  # Italie : DPD Zone 3 >> GLS D12

# ─── SUPPLÉMENTS GÉOGRAPHIQUES ───────────────────────────────────────────────
# Ces suppléments s'appliquent chez les DEUX transporteurs
SURCHARGES_GEO = {
    'SUR_ISL_D01': {'label': 'Corse/Littoral',    'gls': 22.78, 'dpd': 19.94},
    'SUR_MNT_D01': {'label': 'Zone montagne',     'gls':  6.84, 'dpd':  4.00},
    'SUR_ISL_D04': {'label': 'Îles Europe',       'gls': 60.93, 'dpd':  7.00},
    'SUR_RET_BUP_D01': {'label': 'Retour colis',  'gls': None,  'dpd': None},  # 100% aller
    'SUR_ADM_01':  {'label': 'Frais gestion',     'gls': 20.00, 'dpd': 20.00},
}

# NCY = uniquement GLS (seuil 150cm vs 300cm DPD)
SURCHARGES_NCY = {'SUR_NCB_01', 'SUR_NCC_01'}

# ─── CONSTANTES ──────────────────────────────────────────────────────────────
GLS_CSR = 0.71    # Contribution Sûreté et Risques
GLS_PER = 0.015   # Participation Évolution Réseau
DPD_SURETE = 0.86 # Contribution Sûreté
DPD_LOG    = 0.27 # Contribution Logistique Responsable

# ─── HISTORIQUE SGO (fallback si scraping indisponible) ──────────────────────
SGO_HISTORIQUE = {
    # (année, mois): (GLS_taux_site, DPD_routier_taux)
    (2025, 2):  (0.1779, 0.1330),
    (2025, 3):  (0.1839, 0.1288),
    (2025, 4):  (0.1869, 0.1256),
    (2025, 5):  (0.2089, 0.1256),
    (2025, 6):  (0.2089, 0.1256),
    (2025, 7):  (0.2044, 0.1407),
    (2025, 8):  (0.2089, 0.1404),
    (2025, 9):  (0.2129, 0.1331),
    (2025, 10): (0.2109, 0.1364),
    (2025, 11): (0.2109, 0.1321),
    (2025, 12): (0.2109, 0.1495),
    (2026, 1):  (0.2209, 0.1193),
    (2026, 2):  (0.2259, 0.1368),
    (2026, 3):  (0.2590, 0.1385),
    (2026, 4):  (0.2880, 0.2118),
    (2026, 5):  (0.3090, 0.2334),
    (2026, 6):  (0.2910, 0.2133),
}
GLS_REMISE_SGO = 0.06  # Remise contractuelle ADC : -6 points

# ─── SCRAPING SGO ────────────────────────────────────────────────────────────
def scraper_sgo_gls():
    try:
        r = requests.get("https://gls-group.eu/FR/fr/actualites/taxe-gazole/", timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows[:3]:
                cells = row.find_all(['td','th'])
                if len(cells) >= 2:
                    texte = cells[1].get_text(strip=True).replace(',','.').replace('%','').strip()
                    try:
                        val = float(texte) / 100
                        if 0.10 <= val <= 0.50:
                            return val
                    except:
                        pass
    except:
        pass
    return None

def scraper_sgo_dpd():
    try:
        r = requests.get("https://www.dpd.com/fr/fr/surcharge-carburant/", timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows[:3]:
                cells = row.find_all(['td','th'])
                if len(cells) >= 3:
                    texte = cells[2].get_text(strip=True).replace(',','.').replace('%','').strip()
                    try:
                        val = float(texte) / 100
                        if 0.05 <= val <= 0.50:
                            return val
                    except:
                        pass
    except:
        pass
    return None

def get_sgo_mois(annee=None, mois=None, gls_manuel=None, dpd_manuel=None):
    """Retourne (sgo_gls_net, sgo_dpd) pour un mois donné."""
    if gls_manuel is not None and dpd_manuel is not None:
        return gls_manuel - GLS_REMISE_SGO, dpd_manuel

    now = datetime.now()
    a = annee or now.year
    m = mois  or now.month

    # Essai scraping si mois courant
    if a == now.year and m == now.month:
        gls_site = scraper_sgo_gls()
        dpd_site = scraper_sgo_dpd()
        if gls_site and dpd_site:
            return gls_site - GLS_REMISE_SGO, dpd_site

    # Fallback historique
    if (a, m) in SGO_HISTORIQUE:
        gls_site, dpd_taux = SGO_HISTORIQUE[(a, m)]
        return gls_site - GLS_REMISE_SGO, dpd_taux

    # Dernier connu
    last = sorted(SGO_HISTORIQUE.keys())[-1]
    gls_site, dpd_taux = SGO_HISTORIQUE[last]
    return gls_site - GLS_REMISE_SGO, dpd_taux

# ─── CALCUL COÛT GLS ─────────────────────────────────────────────────────────
def cout_gls(poids, pays='FR', sgo_net=None, service='BusinessParcel'):
    """Calcule le coût HT d'un colis GLS (transport pur, sans NCY ni surcharges geo)."""
    if sgo_net is None:
        sgo_net, _ = get_sgo_mois()

    if pays == 'FR':
        grille = GLS_RELAIS if service == 'ShopDelivery' else GLS_FR
        bareme = _lookup(grille, poids, supp_kg=GLS_FR_SUPP_KG, base_max=30)
    else:
        zone = PAYS_ZONE_GLS.get(pays, 'D13')
        bareme = _lookup(GLS_EU[zone], poids, supp_kg=7.94, base_max=30)

    base = bareme + GLS_CSR
    per  = base * GLS_PER
    sgo  = base * sgo_net
    return bareme, base + per + sgo

def cout_dpd(poids, pays='FR', sgo_dpd=None):
    """Calcule le coût HT d'un colis DPD (transport pur, sans surcharges geo)."""
    if sgo_dpd is None:
        _, sgo_dpd = get_sgo_mois()

    if pays == 'FR':
        bareme = _lookup(DPD_FR, poids, supp_kg=DPD_FR_SUPP_KG, base_max=20)
    else:
        zone = PAYS_ZONE_DPD.get(pays, 3)
        bareme = _lookup(DPD_EU[zone], poids, supp_kg=0, base_max=20)

    sgo  = bareme * sgo_dpd
    return bareme, bareme + sgo + DPD_SURETE + DPD_LOG

def _lookup(grille, poids, supp_kg=0, base_max=30):
    """Lookup dans une grille tarifaire avec extrapolation au-delà du max."""
    for k in sorted(grille.keys()):
        if poids <= k:
            return grille[k]
    max_val = grille[max(grille.keys())]
    return max_val + (poids - base_max) * supp_kg

def recommandation_transporteur(poids, pays):
    """Retourne le transporteur recommandé pour un format/pays donné."""
    if pays in PAYS_GARDER_GLS:
        return 'GLS', '⚠️ Italie : garder GLS (DPD Zone 3 beaucoup plus cher)'
    if poids >= 4.5:
        return 'DPD', '✅ Soute : DPD moins cher (pas de NCY)'
    return 'EQUAL', '≈ Cabine : quasi identique'

# ═══════════════════════════════════════════════════════════════════════════════
# TARIFS CLIENT 1 — Grilles spécifiques (valises, même activité qu'ADC)
# GLS : grille PMV hors SGO PER (sans remise -6pts sur SGO)
# DPD : prix finaux HT déjà calculés (SGO 21.33% inclus)
# ═══════════════════════════════════════════════════════════════════════════════

# ─── GLS CLIENT 1 — France PMV hors SGO PER ──────────────────────────────────
GLS_FR_C1 = {
    0:5.65, 1:5.65, 2:5.74, 3:5.83, 4:5.91, 5:6.00,
    6:6.62, 7:7.01, 8:7.50, 9:7.63, 10:7.73,
    11:8.64, 12:9.16, 13:9.57, 14:9.64, 15:9.73,
    16:9.95, 17:10.51, 18:11.06, 19:11.62, 20:12.18,
    21:12.73, 22:13.06, 23:13.41, 24:13.74, 25:14.07,
    26:14.43, 27:14.45, 28:14.45, 29:14.47, 30:14.48,
}

# ─── GLS CLIENT 1 — Europe PMV hors SGO PER ──────────────────────────────────
GLS_EU_C1 = {
    'Z1': {  # DE, BE, NL, LU
        0:0.81, 1:7.65, 2:7.87, 3:8.04, 4:8.29, 5:8.42,
        6:9.35, 7:9.35, 8:9.35, 9:9.35, 10:9.35,
        11:10.59, 12:10.59, 13:10.59, 14:10.59, 15:11.59,
        16:13.11, 17:13.11, 18:13.11, 19:13.11, 20:13.11,
        21:14.08, 22:14.08, 23:14.08, 24:14.08, 25:14.08,
        26:15.15, 27:15.15, 28:15.15, 29:15.15, 30:15.15,
    },
    'Z2': {  # AT, ES, PT, PL, IT, CZ, etc.
        0:0.0,  1:8.61, 2:8.85, 3:9.13, 4:9.41, 5:9.65,
        6:10.97, 7:10.97, 8:10.97, 9:10.97, 10:10.97,
        11:12.45, 12:12.45, 13:12.45, 14:12.45, 15:12.45,
        16:13.73, 17:13.73, 18:13.73, 19:13.73, 20:13.73,
        21:15.21, 22:15.21, 23:15.21, 24:15.21, 25:15.21,
        26:16.53, 27:16.53, 28:16.53, 29:16.53, 30:16.53,
    },
    'Z3': {  # DK, SE, FI, IE, GR, RO, BG, etc.
        0:0.0,  1:9.40, 2:9.78, 3:10.16, 4:10.59, 5:10.97,
        6:13.18, 7:13.18, 8:13.18, 9:13.18, 10:13.18,
        11:15.64, 12:15.64, 13:15.64, 14:15.64, 15:15.64,
        16:17.85, 17:17.85, 18:17.85, 19:17.85, 20:17.85,
        21:20.70, 22:20.70, 23:20.70, 24:20.70, 25:20.70,
        26:23.42, 27:23.42, 28:23.42, 29:23.42, 30:23.42,
    },
}

# Mapping pays → zone GLS Europe pour client 1
PAYS_ZONE_GLS_C1 = {
    'DE':'Z1','BE':'Z1','NL':'Z1','LU':'Z1',
    'AT':'Z2','ES':'Z2','PT':'Z2','PL':'Z2','IT':'Z2',
    'CZ':'Z2','HU':'Z2','SK':'Z2','SI':'Z2','HR':'Z2',
    'LI':'Z2','CH':'Z2','GB':'Z2',
    'DK':'Z3','SE':'Z3','FI':'Z3','IE':'Z3',
    'GR':'Z3','RO':'Z3','BG':'Z3','EE':'Z3','LV':'Z3','LT':'Z3',
    'NO':'Z3','HR':'Z3','AD':'Z3',
}

# ─── DPD CLIENT 1 — Prix finaux HT déjà calculés (SGO 21.33% inclus) ─────────
# Source : fichier Excel client, colonne "Prix finaux HT" (jaune)
# SGO 21.33% + Sûreté 0.86€ + Contribution Logistique 0.20817€ déjà intégrés
DPD_FR_C1 = {
    1:6.649,  2:7.013,  3:7.353,  4:7.717,  5:8.069,
    6:8.420,  7:8.700,  8:8.967,  9:9.331,  10:9.816,
    11:10.301, 12:10.787, 13:11.272, 14:11.757, 15:12.243,
    16:13.213, 17:13.699, 18:14.184, 19:14.669, 20:15.155,
}

DPD_EU_C1 = {
    1: {  # Zone 1 : DE, BE, NL, LU
        1:10.144, 2:10.568, 3:10.993, 4:11.418, 5:11.842,
        6:12.267, 7:12.692, 8:13.116, 9:13.541, 10:13.966,
        11:14.390, 12:14.815, 13:15.240, 14:15.664, 15:16.089,
    },
    2: {  # Zone 2 : AT, ES, PT, PL, IT, CZ, etc.
        1:11.672, 2:12.133, 3:12.595, 4:13.056, 5:13.517,
        6:13.978, 7:14.439, 8:14.900, 9:15.361, 10:15.822,
        11:16.283, 12:16.744, 13:17.205, 14:17.666, 15:18.127,
    },
    3: {  # Zone 3 : DK, SE, FI, IE, GR, RO, BG, etc.
        1:16.162, 2:16.829, 3:17.496, 4:18.164, 5:18.831,
        6:19.498, 7:20.166, 8:20.833, 9:21.500, 10:22.167,
        11:22.835, 12:23.502, 13:24.169, 14:24.837, 15:25.504,
    },
    4: {  # Zone 4 : BG, FI, GR, NO, RO
        1:20.627, 2:21.233, 3:21.840, 4:22.447, 5:23.053,
        6:23.660, 7:24.266, 8:24.873, 9:25.480, 10:26.086,
        11:26.693, 12:27.300, 13:27.906, 14:28.513, 15:29.120,
    },
}

# Mapping pays → zone DPD pour client 1 (identique à ADC)
PAYS_ZONE_DPD_C1 = {
    'DE':1,'NL':1,'BE':1,'LU':1,
    'AT':2,'ES':2,'PT':2,'PL':2,'CZ':2,'HU':2,'SK':2,'SI':2,'HR':2,'IT':2,'CH':2,'LI':2,'GB':2,
    'DK':3,'SE':3,'FI':3,'IE':3,'GR':3,'RO':3,'BG':3,'EE':3,'LV':3,'LT':3,'NO':3,'AD':3,
}

# ─── FONCTIONS TARIFS CLIENT 1 ────────────────────────────────────────────────
def cout_gls_c1(poids, pays, sgo_gls_taux):
    """
    Calcul coût GLS pour client 1 (sans remise SGO).
    sgo_gls_taux = taux site GLS brut (PAS de remise -6pts pour ce client)
    """
    pays = pays.strip().upper() if pays else 'FR'
    if pays == 'FR':
        bareme = next((GLS_FR_C1[k] for k in sorted(GLS_FR_C1.keys()) if poids <= k), GLS_FR_C1[30])
    else:
        zone = PAYS_ZONE_GLS_C1.get(pays, 'Z2')
        grille = GLS_EU_C1.get(zone, GLS_EU_C1['Z2'])
        bareme = next((grille[k] for k in sorted(grille.keys()) if poids <= k), grille[max(grille.keys())])

    base = bareme + GLS_CSR
    total = base * (1 + GLS_PER + sgo_gls_taux)  # PAS de remise -6pts
    return bareme, round(total, 4)


def cout_dpd_c1(poids, pays):
    """
    Coût DPD pour client 1 — prix finaux HT déjà calculés (SGO inclus).
    Pas de recalcul SGO — on utilise directement les prix contractuels.
    """
    pays = pays.strip().upper() if pays else 'FR'
    if pays == 'FR':
        grille = DPD_FR_C1
        p_int = max(1, round(poids))
        prix = next((grille[k] for k in sorted(grille.keys()) if p_int <= k), grille[20])
        if poids > 20:
            prix += (poids - 20) * 0.30
        return None, round(prix, 4)
    else:
        zone = PAYS_ZONE_DPD_C1.get(pays, 3)
        grille = DPD_EU_C1.get(zone, DPD_EU_C1[3])
        p_int = max(1, round(poids))
        prix = next((grille[k] for k in sorted(grille.keys()) if p_int <= k), grille[max(grille.keys())])
        return None, round(prix, 4)
