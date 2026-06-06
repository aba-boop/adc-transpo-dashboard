"""
ADC Transpo Dashboard V5
- Sélecteur mois/année → SGO auto
- Import multi-BCF en une fois (plusieurs mois d'un coup)
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import io
from datetime import datetime

from utils.parsers import parse_bcf_gls
from utils.controle import controler_bcf_gls
from utils.parser_dpd import parse_bcf_dpd
from utils.ncy_analyse import tendance_ncy, calcul_surcoût_multicolis_dpd
from utils.tarifs import (
    cout_gls, cout_dpd, get_sgo_mois, scraper_sgo_gls, scraper_sgo_dpd,
    GLS_FR, DPD_FR, SGO_HISTORIQUE, GLS_REMISE_SGO
)

st.set_page_config(page_title="ADC — Transpo Dashboard", page_icon="🚚", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'Syne',sans-serif;}
.kpi{background:#141720;border:1px solid #1e2235;border-radius:12px;padding:18px 20px;margin:4px 0;}
.kpi-label{font-size:11px;font-weight:600;color:#5a6080;text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px;}
.kpi-val{font-size:24px;font-weight:800;font-family:'DM Mono',monospace;color:#F0F2F8;}
.kpi-sub{font-size:11px;color:#4a5070;margin-top:4px;}
.kpi-green{border-left:3px solid #22c55e;}
.kpi-red{border-left:3px solid #ef4444;}
.kpi-gold{border-left:3px solid #E8B84B;}
.kpi-blue{border-left:3px solid #3b82f6;}
.badge-gls{background:#1a2a5e;color:#93b4fd;padding:3px 12px;border-radius:20px;font-size:13px;font-weight:700;}
.badge-dpd{background:#5e1a1a;color:#fca5a5;padding:3px 12px;border-radius:20px;font-size:13px;font-weight:700;}
.alert-gold{background:#1e1800;border:1px solid #E8B84B;border-radius:8px;padding:10px 14px;color:#fde68a;font-size:13px;margin:4px 0;}
.alert-green{background:#001a10;border:1px solid #22c55e;border-radius:8px;padding:10px 14px;color:#86efac;font-size:13px;margin:4px 0;}
.alert-red{background:#1a0000;border:1px solid #ef4444;border-radius:8px;padding:10px 14px;color:#fca5a5;font-size:13px;margin:4px 0;}
.section-title{font-size:16px;font-weight:800;color:#F0F2F8;padding-bottom:8px;border-bottom:1px solid #1e2235;margin:16px 0 10px 0;}
.import-box{background:#141720;border:1px solid #1e2235;border-radius:12px;padding:20px;}
.import-box-gls{border-top:3px solid #3b82f6;}
.import-box-dpd{border-top:3px solid #ef4444;}
.big-eco{font-size:48px;font-weight:800;font-family:'DM Mono',monospace;text-align:center;}
.eco-pos{color:#22c55e;}.eco-neg{color:#ef4444;}
.mois-tag{background:#1e2235;border-radius:6px;padding:3px 10px;font-size:12px;color:#93b4fd;display:inline-block;margin:2px;}
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ────────────────────────────────────────────────────────────
for key, val in [
    ('gls_data', []), ('dpd_data', []),
    ('sgo_cache', {'gls': None, 'dpd': None}),
    ('dpd_config', {'has_zebra':True,'volumetrique_barre':True,'predict_actif':True,'cout_avis':1.0}),
    ('ncy_profils', {
        'grande_valise':{'label':'Grande valise (4.5-5kg / 154cm)','actif':True,'taux':33},
        'multi_soute':  {'label':'2 grandes valises cerclées (9-10kg / 308cm)','actif':True,'taux':39},
        'tri_cabine':   {'label':'3 cabines cerclées (9-10kg / 339cm)','actif':True,'taux':39},
        'bi_cabine':    {'label':'2 cabines cerclées (6-8kg / 226cm)','actif':False,'taux':0},
    }),
]:
    if key not in st.session_state:
        st.session_state[key] = val

MOIS_NOMS = ['Janvier','Février','Mars','Avril','Mai','Juin',
             'Juillet','Août','Septembre','Octobre','Novembre','Décembre']

def fmt_eur(v, ttc=False):
    if v is None: return "—"
    return f"{v:,.0f}€ {'TTC' if ttc else 'HT'}".replace(',', ' ')

def kpi(label, val, sub='', style='gold'):
    return f'<div class="kpi kpi-{style}"><div class="kpi-label">{label}</div><div class="kpi-val">{val}</div><div class="kpi-sub">{sub}</div></div>'

def get_sgo_from_mois_annee(mois_idx, annee):
    """Retourne (sgo_gls_site, sgo_dpd) depuis l'historique."""
    key = (annee, mois_idx)
    if key in SGO_HISTORIQUE:
        return SGO_HISTORIQUE[key]
    # Dernier connu
    last = sorted(SGO_HISTORIQUE.keys())[-1]
    return SGO_HISTORIQUE[last]

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚚 Transpo Dashboard")
    st.markdown('<span class="badge-gls">GLS</span> &nbsp;vs&nbsp; <span class="badge-dpd">DPD</span>', unsafe_allow_html=True)
    st.markdown("---")

    # SGO manuel (override)
    st.markdown("### 📊 SGO — Taux actuel")
    if st.button("🔄 Scraper site", use_container_width=True):
        with st.spinner("Récupération..."):
            g = scraper_sgo_gls()
            d = scraper_sgo_dpd()
            if g: st.session_state.sgo_cache['gls'] = g
            if d: st.session_state.sgo_cache['dpd'] = d

    now = datetime.now()
    hist_now = SGO_HISTORIQUE.get((now.year, now.month), list(SGO_HISTORIQUE.values())[-1])
    def_gls = (st.session_state.sgo_cache['gls'] or hist_now[0]) * 100
    def_dpd = (st.session_state.sgo_cache['dpd'] or hist_now[1]) * 100

    sgo_gls_override = st.number_input("GLS site % (mois actuel)", value=round(def_gls,2), step=0.01, format="%.2f")
    sgo_dpd_override = st.number_input("DPD routier % (mois actuel)", value=round(def_dpd,2), step=0.01, format="%.2f")
    st.markdown(f"<small>GLS net ADC (-6pts) : <b>{sgo_gls_override/100-0.06:.4f}</b> = <b>{(sgo_gls_override-6):.2f}%</b></small>", unsafe_allow_html=True)
    st.markdown("---")

    # Config DPD
    st.markdown("### ⚙️ Mon contrat DPD")
    cfg = st.session_state.dpd_config
    cfg['has_zebra']          = st.checkbox("✅ J'ai ma Zebra (pas de location)", value=cfg['has_zebra'])
    cfg['volumetrique_barre'] = st.checkbox("✅ Volumétrique barré dans contrat", value=cfg['volumetrique_barre'])
    cfg['predict_actif']      = st.checkbox("✅ Predict actif (tél+email transmis)", value=cfg['predict_actif'])
    cfg['cout_avis']          = st.number_input("Tarif avisé négocié (€/colis)", value=cfg['cout_avis'], step=0.5, min_value=0.5, max_value=4.0)
    st.markdown("---")

    # Profils NCY
    st.markdown("### 🔶 Profils NCY")
    profils = st.session_state.ncy_profils
    for key, p in profils.items():
        p['actif'] = st.checkbox(p['label'], value=p['actif'], key=f"ncy_{key}")
        if p['actif']:
            p['taux'] = st.slider(f"Taux %", 0, 100, p['taux'], key=f"taux_{key}")
    st.markdown("---")

    st.markdown("### 🏆 Pondération Score")
    w_cout = st.slider("💰 Coût", 0, 100, 40)
    w_qual = st.slider("⏱ Qualité", 0, 100, 40)
    w_fact = st.slider("📄 Facturation", 0, 100, 20)

# ─── HEADER ──────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex;align-items:center;gap:16px;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid #1e2235;">
    <div style="font-size:26px;font-weight:800;color:#F0F2F8;">🚚 Transpo Dashboard</div>
    <span class="badge-gls">GLS</span>
    <span style="color:#3a4060;font-size:16px;">vs</span>
    <span class="badge-dpd">DPD</span>
    <div style="flex:1;"></div>
    <div style="font-size:11px;color:#3a4060;">Allée du Commerce — Marseille 13015</div>
</div>
""", unsafe_allow_html=True)

# ─── ZONE IMPORT COTE A COTE ─────────────────────────────────────────────────
col_gls, col_dpd = st.columns(2)

with col_gls:
    st.markdown('<div class="import-box import-box-gls">', unsafe_allow_html=True)
    st.markdown('<span class="badge-gls">GLS</span> &nbsp; Import BCF (1 ou plusieurs mois)', unsafe_allow_html=True)

    # Sélecteur mois/année
    c1, c2 = st.columns(2)
    with c1:
        mois_gls = st.selectbox("Mois", MOIS_NOMS, index=now.month-1, key='mois_gls')
    with c2:
        annee_gls = st.selectbox("Année", list(range(2023, now.year+2)), index=list(range(2023, now.year+2)).index(now.year), key='annee_gls')

    mois_idx_gls = MOIS_NOMS.index(mois_gls) + 1
    sgo_gls_hist, sgo_dpd_hist = get_sgo_from_mois_annee(mois_idx_gls, annee_gls)

    # Afficher SGO auto-détecté
    if (annee_gls, mois_idx_gls) in SGO_HISTORIQUE:
        st.markdown(f'<div class="alert-green">✅ SGO auto : GLS {sgo_gls_hist*100:.2f}% → net {(sgo_gls_hist-0.06)*100:.2f}% / DPD {sgo_dpd_hist*100:.2f}%</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="alert-gold">⚠️ SGO non connu pour ce mois → utilise les valeurs sidebar</div>', unsafe_allow_html=True)
        sgo_gls_hist = sgo_gls_override / 100
        sgo_dpd_hist = sgo_dpd_override / 100

    # Multi-upload
    gls_files = st.file_uploader(
        "BCF GLS (CSV) — sélectionne 1 ou plusieurs fichiers",
        type=['csv'], key='gls_files', accept_multiple_files=True
    )

    if st.button("➕ Analyser BCF GLS", type="primary", use_container_width=True):
        if gls_files:
            nb_ok = 0
            for gls_file in gls_files:
                # Détecter mois depuis le nom de fichier si possible
                fname = gls_file.name
                # Essayer de lire mois depuis nom ex: _20260505_
                import re
                m_date = re.search(r'_(\d{4})(\d{2})\d{2}_', fname)
                if m_date:
                    a_f, m_f = int(m_date.group(1)), int(m_date.group(2))
                    sg_f, sd_f = get_sgo_from_mois_annee(m_f, a_f)
                    label_f = f"{MOIS_NOMS[m_f-1]} {a_f}"
                else:
                    sg_f, sd_f = sgo_gls_hist, sgo_dpd_hist
                    label_f = f"{mois_gls} {annee_gls}" if len(gls_files)==1 else fname

                with st.spinner(f"Analyse {label_f}..."):
                    stats, err = parse_bcf_gls(gls_file,
                        sgo_gls_manuel=sg_f,
                        sgo_dpd_manuel=sd_f)
                if err:
                    st.error(f"{label_f} : {err}")
                else:
                    stats['label'] = label_f
                    stats['sgo_gls_site'] = sg_f
                    stats['sgo_dpd_taux'] = sd_f
                    st.session_state.gls_data = [m for m in st.session_state.gls_data if m['label'] != label_f]
                    st.session_state.gls_data.append(stats)
                    nb_ok += 1

            # Trier par ordre chronologique
            def sort_key(m):
                lbl = m['label']
                for i, mn in enumerate(MOIS_NOMS):
                    if mn in lbl:
                        yr = re.search(r'\d{4}', lbl)
                        return (int(yr.group()) if yr else 2025) * 100 + i
                return 0
            st.session_state.gls_data.sort(key=sort_key)
            st.success(f"✅ {nb_ok} BCF GLS analysés")
        else:
            st.warning("Sélectionne au moins un fichier BCF GLS")

    # Liste des BCF chargés
    if st.session_state.gls_data:
        st.markdown("**BCF chargés :**")
        cols_tags = st.columns(min(len(st.session_state.gls_data), 4))
        for i, m in enumerate(st.session_state.gls_data):
            with cols_tags[i % 4]:
                eco = m['economie_ttc']
                col = "🟢" if eco > 0 else "🔴"
                if st.button(f"{col} {m['label']}\n{m['nb_colis']}c / {eco:+,.0f}€".replace(',', ' '), key=f"del_gls_{i}"):
                    st.session_state.gls_data.pop(i); st.rerun()
        st.markdown("<small style='color:#3a4060;'>Cliquer sur un mois pour le supprimer</small>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col_dpd:
    st.markdown('<div class="import-box import-box-dpd">', unsafe_allow_html=True)
    st.markdown('<span class="badge-dpd">DPD</span> &nbsp; Import BCF (1 ou plusieurs mois)', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        mois_dpd = st.selectbox("Mois", MOIS_NOMS, index=now.month-1, key='mois_dpd')
    with c2:
        annee_dpd = st.selectbox("Année", list(range(2023, now.year+2)), index=list(range(2023, now.year+2)).index(now.year), key='annee_dpd')

    mois_idx_dpd = MOIS_NOMS.index(mois_dpd) + 1
    _, sgo_dpd_auto = get_sgo_from_mois_annee(mois_idx_dpd, annee_dpd)

    if (annee_dpd, mois_idx_dpd) in SGO_HISTORIQUE:
        st.markdown(f'<div class="alert-green">✅ SGO DPD auto : {sgo_dpd_auto*100:.2f}%</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="alert-gold">⚠️ SGO non connu → utilise valeur sidebar</div>', unsafe_allow_html=True)
        sgo_dpd_auto = sgo_dpd_override / 100

    dpd_files = st.file_uploader(
        "BCF DPD (Excel) — sélectionne 1 ou plusieurs fichiers",
        type=['xlsx','xls'], key='dpd_files', accept_multiple_files=True
    )

    if st.button("➕ Analyser BCF DPD", type="primary", use_container_width=True):
        if dpd_files:
            nb_ok = 0
            for dpd_file in dpd_files:
                fname = dpd_file.name
                import re
                m_date = re.search(r'_(\d{4})(\d{2})\d{2}_', fname)
                if m_date:
                    a_f, m_f = int(m_date.group(1)), int(m_date.group(2))
                    _, sd_f = get_sgo_from_mois_annee(m_f, a_f)
                    label_f = f"{MOIS_NOMS[m_f-1]} {a_f}"
                else:
                    sd_f = sgo_dpd_auto
                    label_f = f"{mois_dpd} {annee_dpd}" if len(dpd_files)==1 else fname

                with st.spinner(f"Analyse DPD {label_f}..."):
                    stats, err = parse_bcf_dpd(dpd_file,
                        config=st.session_state.dpd_config,
                        sgo_dpd_manuel=sd_f)
                if err:
                    st.error(f"{label_f} : {err}")
                else:
                    stats['label'] = label_f
                    st.session_state.dpd_data = [m for m in st.session_state.dpd_data if m['label'] != label_f]
                    st.session_state.dpd_data.append(stats)
                    nb_ok += 1
                    for a in stats.get('alertes', []):
                        if '🔴' in a: st.error(a)
                        else: st.warning(a)

            st.success(f"✅ {nb_ok} BCF DPD analysés")
        else:
            st.warning("Sélectionne au moins un fichier BCF DPD")

    if st.session_state.dpd_data:
        st.markdown("**BCF chargés :**")
        cols_tags = st.columns(min(len(st.session_state.dpd_data), 4))
        for i, m in enumerate(st.session_state.dpd_data):
            with cols_tags[i % 4]:
                eco = m.get('economie_vs_gls_ttc', 0)
                col = "🟢" if eco > 0 else "🔴"
                if st.button(f"{col} {m['label']}\n{m['nb_colis']}c", key=f"del_dpd_{i}"):
                    st.session_state.dpd_data.pop(i); st.rerun()
        st.markdown("<small style='color:#3a4060;'>Cliquer sur un mois pour le supprimer</small>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<div style='margin:12px 0;'></div>", unsafe_allow_html=True)

# ─── TABS ─────────────────────────────────────────────────────────────────────
tab1,tab2,tab3,tab4,tab5,tab6,tab7 = st.tabs([
    "📊 Synthèse","💰 Coûts","🌍 Géographie",
    "🔢 Simulateur","📈 Historique","🏆 Score","🔍 Contrôle"
])

# ════════════ TAB 1 — SYNTHÈSE ════════════
with tab1:
    has_gls = bool(st.session_state.gls_data)
    has_dpd = bool(st.session_state.dpd_data)

    if not has_gls and not has_dpd:
        st.markdown('<div style="text-align:center;padding:60px 0;color:#3a4060;"><div style="font-size:40px;">📂</div><div style="font-size:16px;font-weight:700;color:#5a6080;margin-top:12px;">Importe un ou plusieurs BCF ci-dessus</div><div style="font-size:13px;margin-top:8px;">Tu peux sélectionner plusieurs fichiers en même temps</div></div>', unsafe_allow_html=True)
    else:
        if has_gls:
            st.markdown('<div class="section-title">🔵 GLS — Données réelles</div>', unsafe_allow_html=True)
            tot_gls_ttc = sum(m['total_gls_ttc'] for m in st.session_state.gls_data)
            tot_dpd_sim = sum(m['total_dpd_ttc'] for m in st.session_state.gls_data)
            tot_eco     = sum(m['economie_ttc'] for m in st.session_state.gls_data)
            tot_ncy     = sum(m['total_ncy_ht']*1.2 for m in st.session_state.gls_data)
            tot_col     = sum(m['nb_colis'] for m in st.session_state.gls_data)
            nb_m        = len(st.session_state.gls_data)
            eco_pct     = tot_eco/tot_gls_ttc*100 if tot_gls_ttc else 0
            proj_an     = tot_eco/nb_m*12 if nb_m else 0

            c1,c2,c3,c4,c5 = st.columns(5)
            with c1: st.markdown(kpi("Colis analysés", f"{tot_col:,}".replace(',', ' '), f"{nb_m} mois"), unsafe_allow_html=True)
            with c2: st.markdown(kpi("GLS facturé TTC", fmt_eur(tot_gls_ttc,True), "réel"), unsafe_allow_html=True)
            with c3: st.markdown(kpi("DPD simulé TTC", fmt_eur(tot_dpd_sim,True), "théorique"), unsafe_allow_html=True)
            with c4: st.markdown(kpi("Économie DPD", fmt_eur(tot_eco,True), f"{eco_pct:.1f}%",'green' if tot_eco>0 else 'red'), unsafe_allow_html=True)
            with c5: st.markdown(kpi("NCY TTC", fmt_eur(tot_ncy,True), "GLS only",'red'), unsafe_allow_html=True)

            signe = "+" if tot_eco>0 else ""
            st.markdown(f"""
            <div style="text-align:center;padding:20px 0 8px;">
                <div style="font-size:11px;color:#5a6080;text-transform:uppercase;letter-spacing:.1em;">Économie cumulée GLS → DPD ({nb_m} mois)</div>
                <div class="big-eco {'eco-pos' if tot_eco>0 else 'eco-neg'}">{signe}{tot_eco:,.0f}€ TTC</div>
                <div style="font-size:13px;color:#5a6080;margin-top:6px;">Projection 12 mois : <b style="color:#E8B84B;">{proj_an:,.0f}€ TTC/an</b></div>
            </div>""".replace(',', ' '), unsafe_allow_html=True)

            for m in st.session_state.gls_data:
                for a in m.get('alertes',[]):
                    if '⚠️' in a: st.markdown(f'<div class="alert-gold">{a}</div>', unsafe_allow_html=True)
                    elif '✅' in a: st.markdown(f'<div class="alert-green">{a}</div>', unsafe_allow_html=True)

        if has_dpd:
            st.markdown('<div class="section-title">🔴 DPD — Données réelles</div>', unsafe_allow_html=True)
            for m in st.session_state.dpd_data:
                c1,c2,c3,c4,c5 = st.columns(5)
                with c1: st.markdown(kpi("Colis", str(m['nb_colis']), m['label'],'blue'), unsafe_allow_html=True)
                with c2: st.markdown(kpi("Facture DPD TTC", fmt_eur(m['total_facture_ttc'],True), "réel"), unsafe_allow_html=True)
                with c3: st.markdown(kpi("GLS théorique TTC", fmt_eur(m.get('gls_theorique_ht',0)*1.2,True), "sim"), unsafe_allow_html=True)
                with c4:
                    eco = m.get('economie_vs_gls_ttc',0)
                    st.markdown(kpi("Éco vs GLS", fmt_eur(eco,True), "",'green' if eco>0 else 'red'), unsafe_allow_html=True)
                with c5:
                    t = m.get('taux_avis_pct',0)
                    st.markdown(kpi("Taux avisés", f"{t:.1f}%", "cible <5%",'green' if t<5 else 'red'), unsafe_allow_html=True)
                for a in m.get('alertes',[]):
                    if '🔴' in a: st.markdown(f'<div class="alert-red">{a}</div>', unsafe_allow_html=True)
                    else: st.markdown(f'<div class="alert-gold">{a}</div>', unsafe_allow_html=True)

        # Graphe
        if len(st.session_state.gls_data) > 1:
            st.markdown('<div class="section-title">📈 Évolution mensuelle</div>', unsafe_allow_html=True)
            df_m = pd.DataFrame([{'Mois':m['label'],'GLS TTC':round(m['total_gls_ttc']),
                'DPD TTC':round(m['total_dpd_ttc']),'Économie':round(m['economie_ttc']),
                'NCY TTC':round(m['total_ncy_ht']*1.2)} for m in st.session_state.gls_data])
            fig = go.Figure()
            fig.add_trace(go.Bar(name='GLS TTC', x=df_m['Mois'], y=df_m['GLS TTC'], marker_color='#3b82f6'))
            fig.add_trace(go.Bar(name='DPD TTC', x=df_m['Mois'], y=df_m['DPD TTC'], marker_color='#ef4444'))
            fig.add_trace(go.Scatter(name='Économie', x=df_m['Mois'], y=df_m['Économie'],
                mode='lines+markers+text', line=dict(color='#E8B84B',width=3),
                text=df_m['Économie'].apply(lambda x:f'+{x:,.0f}€'.replace(',', ' ')),
                textposition='top center', yaxis='y2'))
            fig.update_layout(barmode='group',plot_bgcolor='#141720',paper_bgcolor='#141720',
                font_color='#F0F2F8',height=380,legend=dict(orientation='h',y=1.1),
                yaxis2=dict(overlaying='y',side='right',showgrid=False))
            st.plotly_chart(fig, use_container_width=True)

# ════════════ TAB 2 — COÛTS ════════════
with tab2:
    st.markdown('<div class="section-title">💰 Décomposition par format de colis</div>', unsafe_allow_html=True)
    if not st.session_state.gls_data:
        st.info("Importe des BCF GLS pour voir la décomposition.")
    else:
        par_format = {}
        for m in st.session_state.gls_data:
            for fmt, d in m['par_format'].items():
                if fmt not in par_format:
                    par_format[fmt] = {'nb':0,'gls':0.0,'dpd':0.0,'ncy':0.0}
                for k in ['nb','gls','dpd','ncy']:
                    par_format[fmt][k] += d[k]
        rows = []
        for fmt, d in sorted(par_format.items(), key=lambda x:-x[1]['gls']):
            eco = d['gls']-d['dpd']
            rows.append({'Format':fmt,'Nb':d['nb'],
                'GLS HT moy':f"{d['gls']/d['nb']:.2f}€" if d['nb'] else '—',
                'DPD HT moy':f"{d['dpd']/d['nb']:.2f}€" if d['nb'] else '—',
                'Éco/colis':f"{eco/d['nb']:+.2f}€" if d['nb'] else '—',
                'NCY HT':f"{d['ncy']:,.0f}€".replace(',', ' '),
                'Gagnant':'🔵 GLS' if eco<0 else('🔴 DPD' if eco>100 else'≈')})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        st.markdown('<div class="section-title">⚠️ Surcharges NCY — Profils ADC</div>', unsafe_allow_html=True)
        tot_ncy = sum(m['total_ncy_ht'] for m in st.session_state.gls_data)
        nb_ncy  = sum(m['nb_ncy'] for m in st.session_state.gls_data)
        nb_col  = sum(m['nb_colis'] for m in st.session_state.gls_data)
        nb_m    = len(st.session_state.gls_data)
        c1,c2,c3,c4 = st.columns(4)
        with c1: st.markdown(kpi("NCY HT", f"{tot_ncy:,.0f}€".replace(',', ' '), "période",'red'), unsafe_allow_html=True)
        with c2: st.markdown(kpi("NCY TTC", f"{tot_ncy*1.2:,.0f}€".replace(',', ' '), "+TVA",'red'), unsafe_allow_html=True)
        with c3: st.markdown(kpi("Colis NCY", str(nb_ncy), f"{nb_ncy/nb_col*100:.1f}%",'red'), unsafe_allow_html=True)
        with c4: st.markdown(kpi("Projection 12M", f"{tot_ncy/nb_m*12*1.2:,.0f}€".replace(',', ' '), "TTC/an",'red'), unsafe_allow_html=True)

        for k, p in st.session_state.ncy_profils.items():
            if p['actif']:
                st.markdown(f'<div class="alert-gold">🔶 {p["label"]} — NCY GLS : ~{p["taux"]}% des colis → 0€ chez DPD (seuil 300cm)</div>', unsafe_allow_html=True)

        # ─── GRAPHE TENDANCE NCY ──────────────────────────────────────────────
        if len(st.session_state.gls_data) >= 2:
            tendance = tendance_ncy(st.session_state.gls_data)
            df_ncy = pd.DataFrame(tendance)
            dernier = tendance[-1]
            avant_dernier = tendance[-2]
            diff_taux = dernier['taux_ncy'] - avant_dernier['taux_ncy']
            taux_moy = sum(t['taux_ncy'] for t in tendance) / len(tendance)
            if diff_taux > 3:
                st.markdown(f'<div class="alert-red">📈 NCY en hausse : +{diff_taux:.1f}pts vs mois précédent ({dernier["taux_ncy"]:.1f}% vs {avant_dernier["taux_ncy"]:.1f}%). Vérifier le mix produits.</div>', unsafe_allow_html=True)
            elif diff_taux < -3:
                st.markdown(f'<div class="alert-green">📉 NCY en baisse : {diff_taux:.1f}pts vs mois précédent.</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="alert-gold">📊 NCY stable — taux moyen : {taux_moy:.1f}%</div>', unsafe_allow_html=True)

            colors = ['#ef4444' if (t['trend_pts'] and t['trend_pts']>2) else
                      '#22c55e' if (t['trend_pts'] and t['trend_pts']<-2) else '#E8B84B' for t in tendance]
            fig_ncy = go.Figure()
            fig_ncy.add_trace(go.Bar(name='NCY HT (€)', x=df_ncy['label'], y=df_ncy['ncy_ht'],
                marker_color=colors, yaxis='y1',
                text=df_ncy['ncy_ht'].apply(lambda x: f"{x:,.0f}€".replace(',', ' ')), textposition='outside'))
            fig_ncy.add_trace(go.Scatter(name='Taux NCY (%)', x=df_ncy['label'], y=df_ncy['taux_ncy'],
                mode='lines+markers+text', line=dict(color='#ffffff', width=2), marker=dict(size=8),
                text=df_ncy['taux_ncy'].apply(lambda x: f"{x:.1f}%"), textposition='top center', yaxis='y2'))
            for t in tendance:
                if t['trend_pts'] is not None:
                    s = f"▲+{t['trend_pts']:.1f}pts" if t['trend_pts']>0.5 else (f"▼{t['trend_pts']:.1f}pts" if t['trend_pts']<-0.5 else "→")
                    c = '#ef4444' if t['trend_pts']>2 else ('#22c55e' if t['trend_pts']<-2 else '#E8B84B')
                    fig_ncy.add_annotation(x=t['label'], y=t['taux_ncy']+1.5, text=s,
                        showarrow=False, font=dict(size=10, color=c), yref='y2')
            fig_ncy.update_layout(plot_bgcolor='#141720', paper_bgcolor='#141720', font_color='#F0F2F8',
                height=350, legend=dict(orientation='h', y=1.1),
                yaxis=dict(title='NCY HT (€)'),
                yaxis2=dict(title='Taux NCY (%)', overlaying='y', side='right', showgrid=False),
                title='Évolution mensuelle NCY GLS')
            st.plotly_chart(fig_ncy, use_container_width=True)

            rows_ncy = []
            for t in tendance:
                ts = (f"▲+{t['trend_pts']:.1f}pts" if t['trend_pts'] and t['trend_pts']>0.5
                      else (f"▼{t['trend_pts']:.1f}pts" if t['trend_pts'] and t['trend_pts']<-0.5 else "→"))
                rows_ncy.append({'Mois':t['label'],'Colis':t['nb_colis'],'NCY':t['nb_ncy'],
                    'Taux':f"{t['taux_ncy']:.1f}%",'NCY HT':f"{t['ncy_ht']:,.0f}€".replace(',', ' '),
                    'NCY TTC':f"{t['ncy_ttc']:,.0f}€".replace(',', ' '),'NCY/colis':f"{t['ncy_par_colis']:.2f}€",'Trend':ts})
            st.dataframe(pd.DataFrame(rows_ncy), use_container_width=True, hide_index=True)

        # ─── SURCOÛT MULTICOLIS 9-10KG ───────────────────────────────────────
        st.markdown('<div class="section-title">📦 Colis 9-10kg cerclés → 2 colis DPD (>300cm refusé)</div>', unsafe_allow_html=True)
        col_mc1, col_mc2 = st.columns([1, 2])
        with col_mc1:
            nb_mc = st.number_input("Nb colis 9-10kg/mois", min_value=0, max_value=500, value=56, step=5,
                help="Moyenne observée sur tes BCF 2025 : 56/mois")
        with col_mc2:
            _, sd_mc = get_sgo_mois(datetime.now().year, datetime.now().month)
            res = calcul_surcoût_multicolis_dpd(nb_mc, sd_mc)
            c1,c2,c3 = st.columns(3)
            with c1: st.markdown(kpi("GLS 9-10kg", f"{res['gls_9kg_ht']:.2f}€ HT", "1 colis + NCY 39%", 'blue'), unsafe_allow_html=True)
            with c2: st.markdown(kpi("DPD 2 colis moy.", f"{res['dpd_moy_ht']:.2f}€ HT", "50% 2×5kg / 50% 6+3kg", 'blue'), unsafe_allow_html=True)
            with c3:
                surc = res['surcoût_par_colis_ht']
                st.markdown(kpi("Surcoût/colis DPD", f"{surc:+.2f}€ HT", "DPD plus cher" if surc>0 else "DPD moins cher", 'red' if surc>0 else 'green'), unsafe_allow_html=True)
            impact_an = res['surcoût_total_ttc'] * 12
            couleur = '#ef4444' if impact_an > 0 else '#22c55e'
            st.markdown(f'<div class="alert-{"red" if impact_an>0 else "green"}">Impact annuel ({nb_mc} colis/mois) : <b style="color:{couleur}">{impact_an:+,.0f}€ TTC/an</b> — {"⚠️ Garder GLS pour ce format" if impact_an>0 else "✅ DPD intéressant"}</div>'.replace(',', ' '), unsafe_allow_html=True)

# ════════════ TAB 3 — GÉOGRAPHIE ════════════
with tab3:
    st.markdown('<div class="section-title">🌍 Analyse par pays</div>', unsafe_allow_html=True)
    if not st.session_state.gls_data:
        st.info("Importe des BCF GLS.")
    else:
        par_pays = {}
        for m in st.session_state.gls_data:
            for pays, d in m['par_pays'].items():
                if pays not in par_pays:
                    par_pays[pays] = {'nb':0,'gls':0.0,'dpd':0.0,'ncy':0.0}
                for k in ['nb','gls','dpd','ncy']:
                    par_pays[pays][k] += d[k]
        rows = []
        for pays, d in sorted(par_pays.items(), key=lambda x:-x[1]['gls']):
            eco = d['gls']-d['dpd']
            reco = "⚠️ Garder GLS" if pays=='IT' else ("✅ DPD" if eco>50 else "≈")
            rows.append({'Pays':pays,'Nb':d['nb'],
                'GLS HT':f"{d['gls']:,.0f}€".replace(',', ' '),
                'DPD HT':f"{d['dpd']:,.0f}€".replace(',', ' '),
                'Éco HT':f"{eco:+,.0f}€".replace(',', ' '),
                'Éco%':f"{eco/d['gls']*100:+.1f}%" if d['gls'] else '—',
                'NCY HT':f"{d['ncy']:,.0f}€".replace(',', ' '),
                'Reco':reco})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.markdown('<div class="alert-red">⚠️ Italie : conserver GLS — DPD Zone 3 nettement plus cher</div>', unsafe_allow_html=True)

        df_p = pd.DataFrame([{'Pays':r['Pays'],'GLS':par_pays[r['Pays']]['gls'],'DPD':par_pays[r['Pays']]['dpd']} for r in rows]).sort_values('GLS',ascending=False).head(10)
        fig = go.Figure()
        fig.add_trace(go.Bar(name='GLS HT', x=df_p['Pays'], y=df_p['GLS'], marker_color='#3b82f6'))
        fig.add_trace(go.Bar(name='DPD HT', x=df_p['Pays'], y=df_p['DPD'], marker_color='#ef4444'))
        fig.update_layout(barmode='group',plot_bgcolor='#141720',paper_bgcolor='#141720',font_color='#F0F2F8',height=320)
        st.plotly_chart(fig, use_container_width=True)

# ════════════ TAB 4 — SIMULATEUR ════════════
with tab4:
    st.markdown('<div class="section-title">🔢 Simulateur tarifaire</div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    with c1: poids_sim = st.number_input("Poids (kg)", 0.1, 30.0, 5.0, 0.1)
    with c2: pays_sim  = st.selectbox("Pays", ['FR','DE','BE','NL','ES','PT','IT','PL','AT','SE','DK'])
    with c3:
        mois_sim = st.selectbox("Mois", list(reversed(list(SGO_HISTORIQUE.keys()))),
            format_func=lambda x:f"{MOIS_NOMS[x[1]-1]} {x[0]}")

    sg, sd = get_sgo_mois(mois_sim[0], mois_sim[1])
    _, gt = cout_gls(poids_sim, pays_sim, sg)
    _, dt = cout_dpd(poids_sim, pays_sim, sd)
    eco = gt-dt
    c1,c2,c3 = st.columns(3)
    with c1: st.markdown(kpi("GLS HT", f"{gt:.2f}€", f"SGO net {sg*100:.2f}%"), unsafe_allow_html=True)
    with c2: st.markdown(kpi("DPD HT", f"{dt:.2f}€", f"SGO {sd*100:.2f}%"), unsafe_allow_html=True)
    with c3: st.markdown(kpi("Écart", f"{eco:+.2f}€", "DPD" if eco>0.05 else("GLS" if eco<-0.05 else"Égal"),'green' if eco>0 else 'red'), unsafe_allow_html=True)

    if pays_sim=='IT':
        st.markdown('<div class="alert-red">⚠️ Italie : garder GLS — DPD Zone 3 beaucoup plus cher</div>', unsafe_allow_html=True)
    elif poids_sim>=4.5 and eco>0:
        st.markdown(f'<div class="alert-green">✅ Soute {poids_sim}kg : DPD moins cher de {eco:.2f}€/colis (hors NCY)</div>', unsafe_allow_html=True)

    rows = []
    for kg in [1,2,3,4,5,6,7,8,9,10,12,15,20]:
        _,g=cout_gls(kg,'FR',sg); _,d=cout_dpd(kg,'FR',sd)
        rows.append({'Poids':f"{kg}kg",'GLS HT':f"{g:.2f}€",'DPD HT':f"{d:.2f}€",
            'Écart':f"{g-d:+.2f}€",'NCY':">4.5kg" if kg>=4.5 else "—",
            'Gagnant':'GLS' if g-d>0.05 else('DPD' if g-d<-0.05 else'≈')})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ════════════ TAB 5 — HISTORIQUE ════════════
with tab5:
    st.markdown('<div class="section-title">📈 Historique SGO</div>', unsafe_allow_html=True)
    rows = [{'Mois':f"{MOIS_NOMS[m-1]} {a}",'GLS site':f"{gs*100:.2f}%",
        'GLS net ADC':f"{(gs-0.06)*100:.2f}%",'DPD routier':f"{ds*100:.2f}%",
        'Écart':f"{(gs-0.06-ds)*100:+.2f}pts"}
        for (a,m),(gs,ds) in sorted(SGO_HISTORIQUE.items())]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    df_h = pd.DataFrame(rows)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_h['Mois'],y=[float(r.replace('%','')) for r in df_h['GLS net ADC']],
        name='GLS net ADC',line=dict(color='#3b82f6',width=2),mode='lines+markers'))
    fig.add_trace(go.Scatter(x=df_h['Mois'],y=[float(r.replace('%','')) for r in df_h['DPD routier']],
        name='DPD routier',line=dict(color='#ef4444',width=2),mode='lines+markers'))
    fig.update_layout(plot_bgcolor='#141720',paper_bgcolor='#141720',font_color='#F0F2F8',height=300)
    st.plotly_chart(fig, use_container_width=True)

    if len(st.session_state.gls_data) > 1:
        st.markdown('<div class="section-title">Économies cumulées</div>', unsafe_allow_html=True)
        cum = 0
        rows2 = []
        for m in st.session_state.gls_data:
            cum += m['economie_ttc']
            rows2.append({'Mois':m['label'],'Éco TTC':f"{m['economie_ttc']:+,.0f}€".replace(',', ' '),
                'Cumulé TTC':f"{cum:+,.0f}€".replace(',', ' '),'NCY TTC':f"{m['total_ncy_ht']*1.2:,.0f}€".replace(',', ' ')})
        st.dataframe(pd.DataFrame(rows2), use_container_width=True, hide_index=True)

# ════════════ TAB 6 — SCORE ════════════
with tab6:
    st.markdown('<div class="section-title">🏆 Score final</div>', unsafe_allow_html=True)
    if not st.session_state.gls_data:
        st.info("Importe des BCF pour générer le score.")
    else:
        tg = sum(m['total_gls_ht'] for m in st.session_state.gls_data)
        td = sum(m['total_dpd_ht'] for m in st.session_state.gls_data)
        ep = (tg-td)/tg*100 if tg else 0
        np_ = sum(m['total_ncy_ht'] for m in st.session_state.gls_data)/tg*100 if tg else 0
        scg = max(0,100-ep*2); scd = min(100,100+(ep-10)*2) if ep>0 else 50
        sfg = max(0,100-np_*5); sfd = 95
        sqd = st.slider("Score qualité DPD (terrain)", 0, 100, 75)
        sqg = 80
        tw = w_cout+w_qual+w_fact
        if tw>0:
            sg_s = (scg*w_cout+sqg*w_qual+sfg*w_fact)/tw
            sd_s = (scd*w_cout+sqd*w_qual+sfd*w_fact)/tw
        else:
            sg_s=sd_s=50
        def sc(s): return '#22c55e' if s>=70 else('#E8B84B' if s>=50 else'#ef4444')
        c1,c2=st.columns(2)
        with c1: st.markdown(f'<div style="background:#141720;border-radius:16px;padding:32px;text-align:center;border:1px solid #1e2235;"><span class="badge-gls">GLS</span><div style="font-size:64px;font-weight:800;font-family:DM Mono,monospace;color:{sc(sg_s)};margin:12px 0;">{sg_s:.0f}</div><div style="color:#5a6080;">/ 100</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div style="background:#141720;border-radius:16px;padding:32px;text-align:center;border:1px solid #1e2235;"><span class="badge-dpd">DPD</span><div style="font-size:64px;font-weight:800;font-family:DM Mono,monospace;color:{sc(sd_s)};margin:12px 0;">{sd_s:.0f}</div><div style="color:#5a6080;">/ 100</div></div>', unsafe_allow_html=True)
        diff = sd_s-sg_s
        ea = sum(m['economie_ttc'] for m in st.session_state.gls_data)/len(st.session_state.gls_data)*12
        if diff>5: st.markdown(f'<div class="alert-green">✅ <b>DPD recommandé</b> (+{diff:.0f}pts) — Économie projetée : <b>{ea:,.0f}€ TTC/an</b></div>'.replace(',', ' '), unsafe_allow_html=True)
        elif diff<-5: st.markdown('<div class="alert-red">⚠️ GLS reste compétitif — réévalue dans 1 mois</div>', unsafe_allow_html=True)
        else: st.markdown('<div class="alert-gold">🔄 Scores proches — continuer la phase de test</div>', unsafe_allow_html=True)

        if st.button("📥 Export Excel"):
            out = io.BytesIO()
            with pd.ExcelWriter(out,engine='xlsxwriter') as w:
                pd.DataFrame([{'Mois':m['label'],'Colis':m['nb_colis'],
                    'GLS HT':round(m['total_gls_ht'],2),'DPD HT':round(m['total_dpd_ht'],2),
                    'Éco HT':round(m['economie_ht'],2),'Éco TTC':round(m['economie_ttc'],2),
                    'NCY HT':round(m['total_ncy_ht'],2)} for m in st.session_state.gls_data]
                ).to_excel(w,sheet_name='Synthèse',index=False)
            st.download_button("⬇️ Télécharger",data=out.getvalue(),
                file_name=f"ADC_transpo_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ════════════ TAB 7 — CONTRÔLE ════════════
with tab7:
    st.markdown('<div class="section-title">🔍 Contrôle Facturation</div>', unsafe_allow_html=True)
    c1,c2 = st.columns(2)

    with c1:
        st.markdown('<span class="badge-gls">GLS</span> &nbsp; Contrôle barème / CSR / PER / SGO / NCY', unsafe_allow_html=True)
        cf_gls = st.file_uploader("BCF GLS à contrôler (CSV)", type=['csv'], key='ctrl_gls')
        if cf_gls:
            with st.spinner("Contrôle GLS..."):
                cs, ce = controler_bcf_gls(cf_gls)
            if ce: st.error(ce)
            else:
                na = cs['nb_anomalies']; sf = cs['montant_surcharge_injustifiee']
                c_1,c_2=st.columns(2)
                with c_1: st.markdown(kpi("Anomalies", str(na), "",'red' if na>0 else 'green'), unsafe_allow_html=True)
                with c_2: st.markdown(kpi("Surfacturation HT", f"{sf:.2f}€", "à réclamer",'red' if sf>0 else 'green'), unsafe_allow_html=True)
                if na==0:
                    st.markdown('<div class="alert-green">✅ Aucune anomalie détectée</div>', unsafe_allow_html=True)
                else:
                    for t,n in cs['par_type'].items():
                        mt = cs['par_type_montant'][t]
                        st.markdown(f'<div class="alert-{"red" if mt>0 else "gold"}">{t} : {n} cas — {mt:+.2f}€ HT</div>', unsafe_allow_html=True)
                    if len(cs['anomalies_df'])>0:
                        st.dataframe(cs['anomalies_df'], use_container_width=True, hide_index=True)
                        out=io.BytesIO()
                        with pd.ExcelWriter(out,engine='xlsxwriter') as w:
                            cs['anomalies_df'].to_excel(w,sheet_name='Anomalies GLS',index=False)
                        st.download_button("📥 Export GLS",data=out.getvalue(),
                            file_name=f"GLS_anomalies_{datetime.now().strftime('%Y%m%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.markdown('<div style="background:#141720;border-radius:8px;padding:14px;font-size:13px;color:#5a6080;line-height:2;">🔴 Barème poids · 🔴 CSR (0,71€) · 🔴 SGO mensuel<br>🔴 NCY injustifiée (&lt;4,5kg) · 🔴 Double NCY · 🟡 PER (1,5%)</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<span class="badge-dpd">DPD</span> &nbsp; Contrôle contractuel ADC', unsafe_allow_html=True)
        cf_dpd = st.file_uploader("BCF DPD à contrôler (Excel)", type=['xlsx','xls'], key='ctrl_dpd')
        if cf_dpd:
            with st.spinner("Contrôle DPD..."):
                ds, de = parse_bcf_dpd(cf_dpd, config=st.session_state.dpd_config, sgo_dpd_manuel=sgo_dpd_override/100)
            if de: st.error(de)
            else:
                adf = ds.get('anomalies_df', pd.DataFrame())
                c_1,c_2=st.columns(2)
                with c_1: st.markdown(kpi("Anomalies DPD", str(len(adf)), "",'red' if len(adf)>0 else 'green'), unsafe_allow_html=True)
                with c_2: st.markdown(kpi("Taux avisés", f"{ds['taux_avis_pct']:.1f}%", "cible <5%",'green' if ds['taux_avis_pct']<5 else 'red'), unsafe_allow_html=True)
                for a in ds.get('alertes',[]):
                    if '🔴' in a: st.markdown(f'<div class="alert-red">{a}</div>', unsafe_allow_html=True)
                    else: st.markdown(f'<div class="alert-gold">{a}</div>', unsafe_allow_html=True)
                if len(adf)>0:
                    st.dataframe(adf, use_container_width=True, hide_index=True)
        else:
            st.markdown('<div style="background:#141720;border-radius:8px;padding:14px;font-size:13px;color:#5a6080;line-height:2;">🔴 Volumétrique barré · 🟡 EDI manquante<br>⚠️ Avisés &gt;5% · 🔴 Tarif avisé &gt; négocié · ⚠️ Zebra 60€</div>', unsafe_allow_html=True)
