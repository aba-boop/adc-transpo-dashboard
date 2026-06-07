"""
ADC Transpo Dashboard V7 — UI Pro avec shadcn-ui + aggrid
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import io, re
from datetime import datetime

import streamlit_shadcn_ui as ui
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

from utils.parsers import parse_bcf_gls
from utils.controle import controler_bcf_gls
from utils.parser_dpd import parse_bcf_dpd
from utils.ncy_analyse import tendance_ncy, calcul_surcoût_multicolis_dpd
from utils.email_alerts import send_monthly_report, send_anomaly_alert
from utils.tarifs import (
    cout_gls, cout_dpd, get_sgo_mois, scraper_sgo_gls, scraper_sgo_dpd,
    SGO_HISTORIQUE, GLS_REMISE_SGO
)

st.set_page_config(page_title="ADC — Transpo Dashboard", page_icon="🚚", layout="wide")

def check_password():
    """Vérifie le mot de passe — multi-utilisateurs."""
    def password_entered():
        pwd = st.session_state["password"]
        # Mots de passe valides : ADC + clients
        valid_passwords = {
            st.secrets.get("PASSWORD", "adc2026"): {"user": "ADC", "remise_sgo": True},
            st.secrets.get("PASSWORD_CLIENT1", "client2026"): {"user": "CLIENT1", "remise_sgo": False},
        }
        if pwd in valid_passwords:
            st.session_state["password_correct"] = True
            st.session_state["user_config"] = valid_passwords[pwd]
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    st.markdown("""
    <div style="max-width:400px;margin:120px auto;text-align:center;">
        <div style="font-size:48px;margin-bottom:16px;">🚚</div>
        <div style="font-size:24px;font-weight:800;color:#F0F2F8;margin-bottom:8px;">Transpo Dashboard</div>
        <div style="font-size:13px;color:#5a6080;margin-bottom:32px;">Analyse transport e-commerce</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.text_input("Mot de passe", type="password",
                      on_change=password_entered, key="password",
                      placeholder="Entrez le mot de passe...")
        if "password_correct" in st.session_state and not st.session_state["password_correct"]:
            st.error("❌ Mot de passe incorrect")
    return False

if not check_password():
    st.stop()


# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&display=swap');
html,body,[class*="css"]{font-family:'Syne',sans-serif;}
.stApp{background:#07090f;}
section[data-testid="stSidebar"]{background:#0a0c14 !important;border-right:1px solid #1a1e2e;}
.stTabs [data-baseweb="tab-list"]{background:#0a0c14;border-radius:12px;padding:4px;gap:2px;}
.stTabs [data-baseweb="tab"]{border-radius:8px;color:#5a6080;font-weight:600;font-size:13px;}
.stTabs [aria-selected="true"]{background:#141720 !important;color:#F0F2F8 !important;}
button[kind="primary"]{background:linear-gradient(135deg,#E8B84B,#f0c96a) !important;color:#07090f !important;font-weight:800 !important;border:none !important;border-radius:10px !important;}
button[kind="primary"]:hover{transform:translateY(-1px);box-shadow:0 4px 20px rgba(232,184,75,.35) !important;}
.badge-gls{background:linear-gradient(135deg,#1a2a5e,#1e3270);color:#93b4fd;padding:5px 16px;border-radius:20px;font-size:13px;font-weight:700;border:1px solid #2a3a7e;display:inline-block;}
.badge-dpd{background:linear-gradient(135deg,#5e1a1a,#721e1e);color:#fca5a5;padding:5px 16px;border-radius:20px;font-size:13px;font-weight:700;border:1px solid #8a2a2a;display:inline-block;}
.kpi{background:linear-gradient(135deg,#0f1120,#141720);border:1px solid #1e2235;border-radius:16px;padding:20px 22px;margin:4px 0;transition:transform .15s,box-shadow .15s;position:relative;overflow:hidden;}
.kpi::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;border-radius:2px 2px 0 0;}
.kpi-green::before{background:linear-gradient(90deg,#22c55e,#16a34a);}
.kpi-red::before{background:linear-gradient(90deg,#ef4444,#dc2626);}
.kpi-gold::before{background:linear-gradient(90deg,#E8B84B,#f0c96a);}
.kpi-blue::before{background:linear-gradient(90deg,#3b82f6,#2563eb);}
.kpi:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(0,0,0,.4);border-color:#2a2e45;}
.kpi-label{font-size:10px;font-weight:700;color:#4a5070;text-transform:uppercase;letter-spacing:.12em;margin-bottom:8px;}
.kpi-val{font-size:22px;font-weight:800;font-family:'DM Mono',monospace;color:#F0F2F8;line-height:1.2;}
.kpi-sub{font-size:11px;color:#3a4060;margin-top:6px;}
.big-eco-wrap{background:linear-gradient(135deg,#08090f,#0f1120);border:1px solid #1e2235;border-radius:20px;padding:32px;text-align:center;margin:16px 0;box-shadow:inset 0 1px 0 rgba(255,255,255,.03);}
.big-eco{font-size:54px;font-weight:800;font-family:'DM Mono',monospace;line-height:1;letter-spacing:-2px;}
.eco-pos{color:#22c55e;}
.eco-neg{color:#ef4444;}
.eco-label{font-size:10px;color:#4a5070;text-transform:uppercase;letter-spacing:.12em;margin-bottom:12px;}
.eco-proj{font-size:13px;color:#5a6080;margin-top:10px;}
.eco-proj b{color:#E8B84B;}
.alert-gold{background:#1a1400;border:1px solid #E8B84B30;border-left:3px solid #E8B84B;border-radius:10px;padding:12px 16px;color:#fde68a;font-size:13px;margin:6px 0;}
.alert-green{background:#001208;border:1px solid #22c55e30;border-left:3px solid #22c55e;border-radius:10px;padding:12px 16px;color:#86efac;font-size:13px;margin:6px 0;}
.alert-red{background:#120000;border:1px solid #ef444430;border-left:3px solid #ef4444;border-radius:10px;padding:12px 16px;color:#fca5a5;font-size:13px;margin:6px 0;}
.section-title{font-size:15px;font-weight:800;color:#F0F2F8;padding-bottom:10px;border-bottom:1px solid #1a1e2e;margin:20px 0 12px 0;}
.import-box{background:linear-gradient(135deg,#08090f,#0f1120);border:1px solid #1a1e2e;border-radius:16px;padding:22px;}
.import-box-gls{border-top:3px solid #3b82f6;}
.import-box-dpd{border-top:3px solid #ef4444;}
[data-testid="stFileUploader"]{background:#0a0c14 !important;border:1px dashed #1e2235 !important;border-radius:10px !important;}
.stSelectbox > div > div > div{background:#0a0c14 !important;}
</style>
""", unsafe_allow_html=True)

MOIS_NOMS = ['Janvier','Février','Mars','Avril','Mai','Juin',
             'Juillet','Août','Septembre','Octobre','Novembre','Décembre']

# ─── SESSION STATE ────────────────────────────────────────────────────────────
# Config utilisateur (défaut = ADC)
if 'user_config' not in st.session_state:
    st.session_state['user_config'] = {"user": "ADC", "remise_sgo": True}

for key, val in [
    ('gls_data',[]),('dpd_data',[]),
    ('sgo_cache',{'gls':None,'dpd':None}),
    ('dpd_config',{'has_zebra':True,'volumetrique_barre':True,'predict_actif':True,'cout_avis':1.0}),
    ('ncy_profils',{
        'grande_valise':{'label':'Grande valise (4.5-5kg / 154cm)','actif':True,'taux':33},
        'multi_soute':{'label':'2 grandes valises cerclées (9-10kg / 308cm)','actif':True,'taux':39},
        'tri_cabine':{'label':'3 cabines cerclées (9-10kg / 339cm)','actif':True,'taux':39},
        'bi_cabine':{'label':'2 cabines cerclées (6-8kg / 226cm)','actif':False,'taux':0},
    }),
]:
    if key not in st.session_state:
        st.session_state[key] = val

def get_sgo_from_mois_annee(mois_idx, annee):
    key = (annee, mois_idx)
    if key in SGO_HISTORIQUE:
        return SGO_HISTORIQUE[key]
    return list(SGO_HISTORIQUE.values())[-1]

def fmt_eur(v, ttc=False):
    if v is None: return "—"
    return f"{v:,.0f}€ {'TTC' if ttc else 'HT'}".replace(',', ' ')

def aggrid_table(df, height=300, color_col=None, red_if_positive=False):
    """Affiche un DataFrame avec AgGrid dark theme + coloration conditionnelle."""
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(resizable=True, sortable=True, filter=True,
                                 wrapText=True, autoHeight=True)
    gb.configure_grid_options(domLayout='normal')

    if color_col and color_col in df.columns:
        red_cond = "params.value > 0" if red_if_positive else "params.value < 0"
        cell_style = JsCode(f"""
        function(params) {{
            if ({red_cond}) return {{'color': '#fca5a5', 'fontWeight': '600'}};
            if (params.value == 0) return {{'color': '#5a6080'}};
            return {{'color': '#86efac', 'fontWeight': '600'}};
        }}
        """)
        gb.configure_column(color_col, cellStyle=cell_style)

    go_opts = gb.build()
    return AgGrid(df, gridOptions=go_opts, height=height,
                  theme='alpine-dark', update_mode=GridUpdateMode.NO_UPDATE,
                  allow_unsafe_jscode=True, fit_columns_on_grid_load=True)

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚚 Transpo Dashboard")
    st.markdown('<span class="badge-gls">GLS</span> &nbsp;vs&nbsp; <span class="badge-dpd">DPD</span>', unsafe_allow_html=True)
    st.markdown("---")

    st.markdown("### 📊 SGO — Taux gazole")
    if st.button("🔄 Scraper auto", use_container_width=True):
        with st.spinner("Scraping..."):
            g = scraper_sgo_gls()
            d = scraper_sgo_dpd()
            if g: st.session_state.sgo_cache['gls'] = g
            if d: st.session_state.sgo_cache['dpd'] = d

    now = datetime.now()
    hist_now = SGO_HISTORIQUE.get((now.year, now.month), list(SGO_HISTORIQUE.values())[-1])
    def_gls = (st.session_state.sgo_cache['gls'] or hist_now[0]) * 100
    def_dpd = (st.session_state.sgo_cache['dpd'] or hist_now[1]) * 100
    sgo_gls_input = st.number_input("GLS site (%)", value=round(def_gls,2), step=0.01, format="%.2f")
    sgo_dpd_input = st.number_input("DPD routier (%)", value=round(def_dpd,2), step=0.01, format="%.2f")
    st.markdown(f"<small>GLS net ADC (-6pts) : <b>{sgo_gls_input/100-0.06:.4f}</b></small>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### ⚙️ Contrat DPD")
    cfg = st.session_state.dpd_config
    cfg['has_zebra'] = st.checkbox("✅ Ma propre Zebra", value=cfg['has_zebra'])
    cfg['volumetrique_barre'] = st.checkbox("✅ Volumétrique barré", value=cfg['volumetrique_barre'])
    cfg['predict_actif'] = st.checkbox("✅ Predict actif", value=cfg['predict_actif'])
    cfg['cout_avis'] = st.number_input("Tarif avisé (€)", value=cfg['cout_avis'], step=0.5, min_value=0.5, max_value=4.0)
    cfg['taux_avis'] = st.slider("Taux avisés estimé (%)", 0.0, 15.0,
        value=cfg.get('taux_avis', 3.0), step=0.5,
        help="3% optimiste (Predict actif) / 5% réaliste / 9% pessimiste")
    st.markdown(f"<small>Surcoût avisés : ~<b>{cfg['taux_avis']/100*cfg['cout_avis']:.3f}€</b>/colis DPD</small>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🔶 Profils NCY")
    for key, p in st.session_state.ncy_profils.items():
        p['actif'] = st.checkbox(p['label'], value=p['actif'], key=f"ncy_{key}")
        if p['actif']:
            p['taux'] = st.slider("Taux %", 0, 100, p['taux'], key=f"taux_{key}")

    st.markdown("---")
    st.markdown("### 🏆 Score")
    w_cout = st.slider("💰 Coût", 0, 100, 40)
    w_qual = st.slider("⏱ Qualité", 0, 100, 40)
    w_fact = st.slider("📄 Facturation", 0, 100, 20)

# ─── HEADER ──────────────────────────────────────────────────────────────────
c1, c2 = st.columns([6,1])
with c1:
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

# ─── IMPORT GLS + DPD COTE A COTE ────────────────────────────────────────────
col_gls, col_dpd = st.columns(2)

with col_gls:
    st.markdown('<div class="import-box import-box-gls">', unsafe_allow_html=True)
    st.markdown('<span class="badge-gls">GLS</span> &nbsp; Import BCF', unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    with c1: mois_gls = st.selectbox("Mois", MOIS_NOMS, index=now.month-1, key='mg')
    with c2: annee_gls = st.selectbox("Année", list(range(2023,now.year+2)), index=list(range(2023,now.year+2)).index(now.year), key='ag')
    mois_idx_gls = MOIS_NOMS.index(mois_gls)+1
    sg_h, sd_h = get_sgo_from_mois_annee(mois_idx_gls, annee_gls)
    if (annee_gls, mois_idx_gls) in SGO_HISTORIQUE:
        st.markdown(f'<div class="alert-green">✅ SGO auto : GLS {sg_h*100:.2f}% → net {(sg_h-0.06)*100:.2f}% / DPD {sd_h*100:.2f}%</div>', unsafe_allow_html=True)
    else:
        sg_h = sgo_gls_input/100; sd_h = sgo_dpd_input/100
        st.markdown(f'<div class="alert-gold">⚠️ SGO non connu → valeurs sidebar utilisées</div>', unsafe_allow_html=True)
    gls_files = st.file_uploader("BCF GLS (CSV) — multi-sélection OK", type=['csv'], key='gf', accept_multiple_files=True)
    if st.button("➕ Analyser BCF GLS", type="primary", use_container_width=True):
        if gls_files:
            nb_ok = 0
            for f in gls_files:
                m_d = re.search(r'_(\d{4})(\d{2})\d{2}_', f.name)
                if m_d:
                    a_f,m_f = int(m_d.group(1)),int(m_d.group(2))
                    sg_f,sd_f = get_sgo_from_mois_annee(m_f,a_f)
                    lbl = f"{MOIS_NOMS[m_f-1]} {a_f}"
                else:
                    sg_f,sd_f = sg_h,sd_h
                    lbl = f"{mois_gls} {annee_gls}" if len(gls_files)==1 else f.name
                with st.spinner(f"Analyse {lbl}..."):
                    s,e = parse_bcf_gls(f, sgo_gls_manuel=sg_f, sgo_dpd_manuel=sd_f,
                    taux_avis_dpd=st.session_state.dpd_config.get('taux_avis',3.0)/100,
                    cout_avis_dpd=st.session_state.dpd_config.get('cout_avis',1.0))
                if e: st.error(f"{lbl}: {e}")
                else:
                    s['label'] = lbl
                    st.session_state.gls_data = [m for m in st.session_state.gls_data if m['label']!=lbl]
                    st.session_state.gls_data.append(s)
                    nb_ok += 1
            def sk(m):
                for i,mn in enumerate(MOIS_NOMS):
                    if mn in m['label']:
                        yr = re.search(r'\d{4}',m['label'])
                        return (int(yr.group()) if yr else 2025)*100+i
                return 0
            st.session_state.gls_data.sort(key=sk)
            st.success(f"✅ {nb_ok} BCF GLS analysés")
            # Envoi email automatique du rapport
            if st.session_state.gls_data:
                ok, msg = send_monthly_report(st.session_state.gls_data)
                if ok:
                    st.toast("📧 Rapport envoyé à aba@alleeducommerce.com", icon="✅")
                else:
                    st.toast(f"Email non envoyé : {msg}", icon="⚠️")
        else: st.warning("Sélectionne au moins un fichier")
    if st.session_state.gls_data:
        cols = st.columns(min(len(st.session_state.gls_data),4))
        for i,m in enumerate(st.session_state.gls_data):
            with cols[i%4]:
                eco = m['economie_ttc']
                if st.button(f"{'🟢' if eco>0 else '🔴'} {m['label']}\n{m['nb_colis']}c", key=f"dg{i}"):
                    st.session_state.gls_data.pop(i); st.rerun()
        st.caption("Cliquer sur un mois pour le supprimer")
    st.markdown('</div>', unsafe_allow_html=True)

with col_dpd:
    st.markdown('<div class="import-box import-box-dpd">', unsafe_allow_html=True)
    st.markdown('<span class="badge-dpd">DPD</span> &nbsp; Import BCF', unsafe_allow_html=True)
    c1,c2 = st.columns(2)
    with c1: mois_dpd = st.selectbox("Mois", MOIS_NOMS, index=now.month-1, key='md')
    with c2: annee_dpd = st.selectbox("Année", list(range(2023,now.year+2)), index=list(range(2023,now.year+2)).index(now.year), key='ad')
    mois_idx_dpd = MOIS_NOMS.index(mois_dpd)+1
    _,sd_dpd = get_sgo_from_mois_annee(mois_idx_dpd, annee_dpd)
    if (annee_dpd, mois_idx_dpd) in SGO_HISTORIQUE:
        st.markdown(f'<div class="alert-green">✅ SGO DPD auto : {sd_dpd*100:.2f}%</div>', unsafe_allow_html=True)
    else:
        sd_dpd = sgo_dpd_input/100
        st.markdown(f'<div class="alert-gold">⚠️ SGO non connu → valeur sidebar</div>', unsafe_allow_html=True)
    dpd_files = st.file_uploader("BCF DPD (Excel) — multi-sélection OK", type=['xlsx','xls'], key='df', accept_multiple_files=True)
    if st.button("➕ Analyser BCF DPD", type="primary", use_container_width=True):
        if dpd_files:
            nb_ok = 0
            for f in dpd_files:
                m_d = re.search(r'_(\d{4})(\d{2})\d{2}_', f.name)
                if m_d:
                    a_f,m_f = int(m_d.group(1)),int(m_d.group(2))
                    _,sd_f = get_sgo_from_mois_annee(m_f,a_f)
                    lbl = f"{MOIS_NOMS[m_f-1]} {a_f}"
                else:
                    sd_f = sd_dpd
                    lbl = f"{mois_dpd} {annee_dpd}" if len(dpd_files)==1 else f.name
                with st.spinner(f"Analyse DPD {lbl}..."):
                    s,e = parse_bcf_dpd(f, config=st.session_state.dpd_config, sgo_dpd_manuel=sd_f)
                if e: st.error(f"{lbl}: {e}")
                else:
                    s['label'] = lbl
                    st.session_state.dpd_data = [m for m in st.session_state.dpd_data if m['label']!=lbl]
                    st.session_state.dpd_data.append(s)
                    nb_ok += 1
                    for a in s.get('alertes',[]):
                        if '🔴' in a: st.error(a)
                        else: st.warning(a)
            st.success(f"✅ {nb_ok} BCF DPD analysés")
        else: st.warning("Sélectionne au moins un fichier")
    if st.session_state.dpd_data:
        cols = st.columns(min(len(st.session_state.dpd_data),4))
        for i,m in enumerate(st.session_state.dpd_data):
            with cols[i%4]:
                if st.button(f"🔴 {m['label']}\n{m['nb_colis']}c", key=f"dd{i}"):
                    st.session_state.dpd_data.pop(i); st.rerun()
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
            st.markdown('<div style="text-align:center;padding:60px 0;color:#3a4060;"><div style="font-size:40px;">📂</div><div style="font-size:16px;font-weight:700;color:#5a6080;margin-top:12px;">Importe un ou plusieurs BCF ci-dessus</div></div>', unsafe_allow_html=True)
    else:
        if has_gls:
            st.markdown('<div class="section-title">🔵 GLS — Données réelles</div>', unsafe_allow_html=True)
            tg_ttc = sum(m['total_gls_ttc'] for m in st.session_state.gls_data)
            td_ttc = sum(m['total_dpd_ttc'] for m in st.session_state.gls_data)
            te_ttc = sum(m['economie_ttc'] for m in st.session_state.gls_data)
            tn_ttc = sum(m['total_ncy_ht']*1.2 for m in st.session_state.gls_data)
            tc = sum(m['nb_colis'] for m in st.session_state.gls_data)
            nb_m = len(st.session_state.gls_data)
            ep = te_ttc/tg_ttc*100 if tg_ttc else 0
            proj = te_ttc/nb_m*12 if nb_m else 0

            # KPIs shadcn
            c1,c2,c3,c4,c5 = st.columns(5)
            with c1: ui.metric_card(title="Colis analysés", content=f"{tc:,}".replace(',', ' '), description=f"{nb_m} mois")
            with c2: ui.metric_card(title="GLS facturé TTC", content=f"{tg_ttc:,.0f}€".replace(',', ' '), description="réel")
            with c3: ui.metric_card(title="DPD simulé TTC", content=f"{td_ttc:,.0f}€".replace(',', ' '), description="théorique")
            with c4: ui.metric_card(title="Économie DPD", content=f"{te_ttc:,.0f}€ TTC".replace(',', ' '), description=f"{ep:.1f}%")
            with c5: ui.metric_card(title="NCY TTC", content=f"{tn_ttc:,.0f}€ TTC".replace(',', ' '), description="GLS only")

            signe = "+" if te_ttc>0 else ""
            st.markdown(f"""
            <div class="big-eco-wrap">
                <div class="eco-label">Économie cumulée GLS → DPD ({nb_m} mois · {tc:,} colis)</div>
                <div class="big-eco {'eco-pos' if te_ttc>0 else 'eco-neg'}">{signe}{te_ttc:,.0f}€ TTC</div>
                <div class="eco-proj">Projection 12 mois : <b>{proj:,.0f}€ TTC/an</b> &nbsp;·&nbsp; soit <b>{proj/12:,.0f}€/mois</b></div>
            </div>""".replace(',', ' '), unsafe_allow_html=True)

            # Alerte surcoût avisés DPD
            tot_surc_avis = sum(m.get('surcoût_avis_dpd_ht',0) for m in st.session_state.gls_data)
            cfg_avis = st.session_state.dpd_config
            if tot_surc_avis > 0:
                msg = f'<div class="alert-gold">⚠️ Surcoût avisés DPD intégré : <b>{tot_surc_avis*1.2:,.0f}€ TTC</b> ({cfg_avis.get("taux_avis",3):.1f}% × {cfg_avis.get("cout_avis",1):.2f}€/avisé) — inclus dans simulation</div>'.replace(',', ' ')
                st.markdown(msg, unsafe_allow_html=True)
            for m in st.session_state.gls_data:
                for a in m.get('alertes',[]):
                    if '⚠️' in a: st.markdown(f'<div class="alert-gold">{a}</div>', unsafe_allow_html=True)
                    elif '✅' in a: st.markdown(f'<div class="alert-green">{a}</div>', unsafe_allow_html=True)

        if has_dpd:
            st.markdown('<div class="section-title">🔴 DPD — Données réelles</div>', unsafe_allow_html=True)
            for m in st.session_state.dpd_data:
                c1,c2,c3,c4,c5 = st.columns(5)
                eco = m.get('economie_vs_gls_ttc',0)
                taux = m.get('taux_avis_pct',0)
                with c1: ui.metric_card(title="Colis", content=str(m['nb_colis']), description=m['label'])
                with c2: ui.metric_card(title="Facture DPD TTC", content=f"{m['total_facture_ttc']:,.0f}€".replace(',', ' '), description="réel")
                with c3: ui.metric_card(title="GLS théorique TTC", content=f"{m.get('gls_theorique_ht',0)*1.2:,.0f}€".replace(',', ' '), description="sim")
                with c4: ui.metric_card(title="Éco vs GLS", content=f"{eco:+,.0f}€ TTC".replace(',', ' '), description="")
                with c5: ui.metric_card(title="Taux avisés", content=f"{taux:.1f}%", description="cible <5%")
                for a in m.get('alertes',[]):
                    if '🔴' in a: st.markdown(f'<div class="alert-red">{a}</div>', unsafe_allow_html=True)
                    else: st.markdown(f'<div class="alert-gold">{a}</div>', unsafe_allow_html=True)

        if len(st.session_state.gls_data)>1:
            st.markdown('<div class="section-title">📈 Évolution mensuelle</div>', unsafe_allow_html=True)
            df_m = pd.DataFrame([{'Mois':m['label'],'GLS TTC':round(m['total_gls_ttc']),
                'DPD TTC':round(m['total_dpd_ttc']),'Économie':round(m['economie_ttc'])} for m in st.session_state.gls_data])
            fig = go.Figure()
            fig.add_trace(go.Bar(name='GLS TTC',x=df_m['Mois'],y=df_m['GLS TTC'],marker_color='#3b82f6'))
            fig.add_trace(go.Bar(name='DPD TTC',x=df_m['Mois'],y=df_m['DPD TTC'],marker_color='#ef4444'))
            fig.add_trace(go.Scatter(name='Économie',x=df_m['Mois'],y=df_m['Économie'],
                mode='lines+markers+text',line=dict(color='#E8B84B',width=3),
                text=df_m['Économie'].apply(lambda x:f'+{x:,.0f}€'.replace(',', ' ')),
                textposition='top center',yaxis='y2'))
            fig.update_layout(barmode='group',plot_bgcolor='#141720',paper_bgcolor='#141720',
                font_color='#F0F2F8',height=380,legend=dict(orientation='h',y=1.1),
                yaxis2=dict(overlaying='y',side='right',showgrid=False))
            st.plotly_chart(fig,use_container_width=True)

# ════════════ TAB 2 — COÛTS ════════════
with tab2:
    st.markdown('<div class="section-title">💰 Décomposition par format</div>', unsafe_allow_html=True)
    if not st.session_state.gls_data:
        st.info("Importe des BCF GLS.")
    else:
        par_format = {}
        for m in st.session_state.gls_data:
            for fmt,d in m['par_format'].items():
                if fmt not in par_format:
                    par_format[fmt] = {'nb':0,'gls':0.0,'dpd':0.0,'ncy':0.0}
                for k in ['nb','gls','dpd','ncy']:
                    par_format[fmt][k] += d[k]
        rows = []
        for fmt,d in sorted(par_format.items(),key=lambda x:-x[1]['gls']):
            eco = d['gls']-d['dpd']
            rows.append({'Format':fmt,'Nb':d['nb'],
                'GLS HT moy':f"{d['gls']/d['nb']:.2f}€" if d['nb'] else '—',
                'DPD HT moy':f"{d['dpd']/d['nb']:.2f}€" if d['nb'] else '—',
                'Éco/colis':f"{eco/d['nb']:+.2f}€" if d['nb'] else '—',
                'NCY HT':f"{d['ncy']:,.0f}€".replace(',', ' '),
                'Gagnant':'🔵 GLS' if eco<0 else('🔴 DPD' if eco>100 else'≈')})
        aggrid_table(pd.DataFrame(rows), height=250)

        # NCY
        st.markdown('<div class="section-title">⚠️ Surcharges NCY — Tendance</div>', unsafe_allow_html=True)
        tot_ncy = sum(m['total_ncy_ht'] for m in st.session_state.gls_data)
        nb_ncy  = sum(m['nb_ncy'] for m in st.session_state.gls_data)
        nb_col  = sum(m['nb_colis'] for m in st.session_state.gls_data)
        nb_m    = len(st.session_state.gls_data)

        c1,c2,c3,c4 = st.columns(4)
        with c1: ui.metric_card(title="NCY HT", content=f"{tot_ncy:,.0f}€".replace(',', ' '), description="période")
        with c2: ui.metric_card(title="NCY TTC", content=f"{tot_ncy*1.2:,.0f}€".replace(',', ' '), description="+TVA")
        with c3: ui.metric_card(title="Colis NCY", content=str(nb_ncy), description=f"{nb_ncy/nb_col*100:.1f}%")
        with c4: ui.metric_card(title="Projection 12M", content=f"{tot_ncy/nb_m*12*1.2:,.0f}€".replace(',', ' '), description="TTC/an")

        for k,p in st.session_state.ncy_profils.items():
            if p['actif']:
                st.markdown(f'<div class="alert-gold">🔶 {p["label"]} — NCY GLS : ~{p["taux"]}% → 0€ chez DPD</div>', unsafe_allow_html=True)

        if len(st.session_state.gls_data)>=2:
            tendance = tendance_ncy(st.session_state.gls_data)
            df_ncy = pd.DataFrame(tendance)
            dernier = tendance[-1]; avant = tendance[-2]
            diff = dernier['taux_ncy']-avant['taux_ncy']
            moy = sum(t['taux_ncy'] for t in tendance)/len(tendance)
            if diff>3: st.markdown(f'<div class="alert-red">📈 NCY en hausse : +{diff:.1f}pts vs mois précédent ({dernier["taux_ncy"]:.1f}%)</div>', unsafe_allow_html=True)
            elif diff<-3: st.markdown(f'<div class="alert-green">📉 NCY en baisse : {diff:.1f}pts</div>', unsafe_allow_html=True)
            else: st.markdown(f'<div class="alert-gold">📊 NCY stable — taux moyen : {moy:.1f}%</div>', unsafe_allow_html=True)

            colors = ['#ef4444' if (t['trend_pts'] and t['trend_pts']>2) else
                      '#22c55e' if (t['trend_pts'] and t['trend_pts']<-2) else '#E8B84B' for t in tendance]
            fig_ncy = go.Figure()
            fig_ncy.add_trace(go.Bar(name='NCY HT (€)',x=df_ncy['label'],y=df_ncy['ncy_ht'],
                marker_color=colors,yaxis='y1',
                text=df_ncy['ncy_ht'].apply(lambda x:f"{x:,.0f}€".replace(',', ' ')),textposition='outside'))
            fig_ncy.add_trace(go.Scatter(name='Taux NCY (%)',x=df_ncy['label'],y=df_ncy['taux_ncy'],
                mode='lines+markers+text',line=dict(color='#ffffff',width=2),marker=dict(size=8),
                text=df_ncy['taux_ncy'].apply(lambda x:f"{x:.1f}%"),textposition='top center',yaxis='y2'))
            for t in tendance:
                if t['trend_pts'] is not None:
                    s = f"▲+{t['trend_pts']:.1f}pts" if t['trend_pts']>0.5 else (f"▼{t['trend_pts']:.1f}pts" if t['trend_pts']<-0.5 else "→")
                    c = '#ef4444' if t['trend_pts']>2 else ('#22c55e' if t['trend_pts']<-2 else '#E8B84B')
                    fig_ncy.add_annotation(x=t['label'],y=t['taux_ncy']+1.5,text=s,showarrow=False,font=dict(size=10,color=c),yref='y2')
            fig_ncy.update_layout(plot_bgcolor='#141720',paper_bgcolor='#141720',font_color='#F0F2F8',height=350,
                legend=dict(orientation='h',y=1.1),
                yaxis=dict(title='NCY HT (€)'),
                yaxis2=dict(title='Taux NCY (%)',overlaying='y',side='right',showgrid=False),
                title='Évolution mensuelle NCY GLS')
            st.plotly_chart(fig_ncy,use_container_width=True)

            rows_ncy = []
            for t in tendance:
                ts = f"▲+{t['trend_pts']:.1f}pts" if t['trend_pts'] and t['trend_pts']>0.5 else (f"▼{t['trend_pts']:.1f}pts" if t['trend_pts'] and t['trend_pts']<-0.5 else "→")
                rows_ncy.append({'Mois':t['label'],'Colis':t['nb_colis'],'NCY':t['nb_ncy'],
                    'Taux':f"{t['taux_ncy']:.1f}%",'NCY HT':f"{t['ncy_ht']:,.0f}€".replace(',', ' '),
                    'NCY TTC':f"{t['ncy_ttc']:,.0f}€".replace(',', ' '),'NCY/colis':f"{t['ncy_par_colis']:.2f}€",'Trend':ts})
            aggrid_table(pd.DataFrame(rows_ncy), height=200)

        # Multicolis
        st.markdown('<div class="section-title">📦 Colis 9-10kg cerclés → 2 colis DPD (>300cm)</div>', unsafe_allow_html=True)
        col_mc1,col_mc2 = st.columns([1,2])
        with col_mc1:
            nb_mc = st.number_input("Nb colis 9-10kg/mois", min_value=0, max_value=500, value=56, step=5)
        with col_mc2:
            _,sd_mc = get_sgo_mois(now.year, now.month)
            res = calcul_surcoût_multicolis_dpd(nb_mc, sd_mc)
            c1,c2,c3 = st.columns(3)
            with c1: ui.metric_card(title="GLS 9-10kg", content=f"{res['gls_9kg_ht']:.2f}€ HT", description="1 colis + NCY 39%")
            with c2: ui.metric_card(title="DPD 2 colis", content=f"{res['dpd_moy_ht']:.2f}€ HT", description="50% 2×5kg / 50% 6+3kg")
            with c3: ui.metric_card(title="Surcoût/colis", content=f"{res['surcoût_par_colis_ht']:+.2f}€ HT", description="DPD plus cher" if res['surcoût_par_colis_ht']>0 else "DPD moins cher")
            impact = res['surcoût_total_ttc']*12
            st.markdown(f'<div class="alert-{"red" if impact>0 else "green"}">Impact annuel ({nb_mc} colis/mois) : <b>{impact:+,.0f}€ TTC/an</b> — {"⚠️ Garder GLS" if impact>0 else "✅ DPD OK"}</div>'.replace(',', ' '), unsafe_allow_html=True)

# ════════════ TAB 3 — GÉOGRAPHIE ════════════
with tab3:
    st.markdown('<div class="section-title">🌍 Analyse par pays</div>', unsafe_allow_html=True)
    if not st.session_state.gls_data:
        st.info("Importe des BCF GLS.")
    else:
        par_pays = {}
        for m in st.session_state.gls_data:
            for pays,d in m['par_pays'].items():
                if pays not in par_pays: par_pays[pays] = {'nb':0,'gls':0.0,'dpd':0.0,'ncy':0.0}
                for k in ['nb','gls','dpd','ncy']: par_pays[pays][k] += d[k]
        rows = []
        for pays,d in sorted(par_pays.items(),key=lambda x:-x[1]['gls']):
            eco = d['gls']-d['dpd']
            rows.append({'Pays':pays,'Nb':d['nb'],
                'GLS HT':f"{d['gls']:,.0f}€".replace(',', ' '),
                'DPD HT':f"{d['dpd']:,.0f}€".replace(',', ' '),
                'Éco HT':f"{eco:+,.0f}€".replace(',', ' '),
                'Éco%':f"{eco/d['gls']*100:+.1f}%" if d['gls'] else '—',
                'NCY HT':f"{d['ncy']:,.0f}€".replace(',', ' '),
                'Reco':"⚠️ Garder GLS" if pays=='IT' else ("✅ DPD" if eco>50 else "≈")})
        aggrid_table(pd.DataFrame(rows), height=350)
        st.markdown('<div class="alert-red">⚠️ Italie : conserver GLS — DPD Zone 3 nettement plus cher</div>', unsafe_allow_html=True)

# ════════════ TAB 4 — SIMULATEUR ════════════
with tab4:
    st.markdown('<div class="section-title">🔢 Simulateur tarifaire</div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    with c1: poids_sim = st.number_input("Poids (kg)", 0.1, 30.0, 5.0, 0.1)
    with c2: pays_sim = st.selectbox("Pays", ['FR','DE','BE','NL','ES','PT','IT','PL','AT','SE','DK'])
    with c3: mois_sim = st.selectbox("Mois", list(reversed(list(SGO_HISTORIQUE.keys()))),
            format_func=lambda x:f"{MOIS_NOMS[x[1]-1]} {x[0]}")
    sg,sd = get_sgo_mois(mois_sim[0],mois_sim[1])
    _,gt = cout_gls(poids_sim,pays_sim,sg)
    _,dt = cout_dpd(poids_sim,pays_sim,sd)
    eco = gt-dt
    c1,c2,c3 = st.columns(3)
    with c1: ui.metric_card(title="GLS HT", content=f"{gt:.2f}€", description=f"SGO net {sg*100:.2f}%")
    with c2: ui.metric_card(title="DPD HT", content=f"{dt:.2f}€", description=f"SGO {sd*100:.2f}%")
    with c3: ui.metric_card(title="Écart", content=f"{eco:+.2f}€", description="DPD" if eco>0.05 else ("GLS" if eco<-0.05 else "Égal"))
    if pays_sim=='IT': st.markdown('<div class="alert-red">⚠️ Italie : garder GLS — DPD Zone 3 beaucoup plus cher</div>', unsafe_allow_html=True)
    elif poids_sim>=4.5 and eco>0: st.markdown(f'<div class="alert-green">✅ Soute {poids_sim}kg : DPD moins cher de {eco:.2f}€/colis (hors NCY)</div>', unsafe_allow_html=True)

    rows = [{'Poids':f"{k}kg",'GLS HT':f"{cout_gls(k,'FR',sg)[1]:.2f}€",
        'DPD HT':f"{cout_dpd(k,'FR',sd)[1]:.2f}€",
        'Écart':f"{cout_gls(k,'FR',sg)[1]-cout_dpd(k,'FR',sd)[1]:+.2f}€",
        'NCY':">4.5kg" if k>=4.5 else "—"} for k in [1,2,3,4,5,6,7,8,9,10,12,15,20]]
    aggrid_table(pd.DataFrame(rows), height=380)

# ════════════ TAB 5 — HISTORIQUE ════════════
with tab5:
    st.markdown('<div class="section-title">📈 Historique SGO GLS vs DPD</div>', unsafe_allow_html=True)
    rows = [{'Mois':f"{MOIS_NOMS[m-1]} {a}",'GLS site':f"{gs*100:.2f}%",
        'GLS net ADC':f"{(gs-0.06)*100:.2f}%",'DPD routier':f"{ds*100:.2f}%",
        'Écart':f"{(gs-0.06-ds)*100:+.2f}pts"}
        for (a,m),(gs,ds) in sorted(SGO_HISTORIQUE.items())]
    aggrid_table(pd.DataFrame(rows), height=400)

    df_h = pd.DataFrame(rows)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_h['Mois'],y=[float(r.replace('%','')) for r in df_h['GLS net ADC']],
        name='GLS net ADC',line=dict(color='#3b82f6',width=2),mode='lines+markers'))
    fig.add_trace(go.Scatter(x=df_h['Mois'],y=[float(r.replace('%','')) for r in df_h['DPD routier']],
        name='DPD routier',line=dict(color='#ef4444',width=2),mode='lines+markers'))
    fig.update_layout(plot_bgcolor='#141720',paper_bgcolor='#141720',font_color='#F0F2F8',height=300)
    st.plotly_chart(fig,use_container_width=True)

    if len(st.session_state.gls_data)>1:
        st.markdown('<div class="section-title">Économies cumulées</div>', unsafe_allow_html=True)
        cum = 0
        rows2 = []
        for m in st.session_state.gls_data:
            cum += m['economie_ttc']
            rows2.append({'Mois':m['label'],'Éco TTC':f"{m['economie_ttc']:+,.0f}€".replace(',', ' '),
                'Cumulé TTC':f"{cum:+,.0f}€".replace(',', ' '),'NCY TTC':f"{m['total_ncy_ht']*1.2:,.0f}€".replace(',', ' ')})
        aggrid_table(pd.DataFrame(rows2), height=300)

# ════════════ TAB 6 — SCORE ════════════
with tab6:
    st.markdown('<div class="section-title">🏆 Score final</div>', unsafe_allow_html=True)
    if not st.session_state.gls_data:
        st.info("Importe des BCF.")
    else:
        tg = sum(m['total_gls_ht'] for m in st.session_state.gls_data)
        td = sum(m['total_dpd_ht'] for m in st.session_state.gls_data)
        ep = (tg-td)/tg*100 if tg else 0
        np_ = sum(m['total_ncy_ht'] for m in st.session_state.gls_data)/tg*100 if tg else 0
        scg=max(0,100-ep*2); scd=min(100,100+(ep-10)*2) if ep>0 else 50
        sfg=max(0,100-np_*5); sfd=95
        sqd=st.slider("Score qualité DPD (terrain)",0,100,75)
        sqg=80
        tw=w_cout+w_qual+w_fact
        if tw>0:
            sg_s=(scg*w_cout+sqg*w_qual+sfg*w_fact)/tw
            sd_s=(scd*w_cout+sqd*w_qual+sfd*w_fact)/tw
        else: sg_s=sd_s=50

        c1,c2 = st.columns(2)
        def sc(s): return '#22c55e' if s>=70 else('#E8B84B' if s>=50 else'#ef4444')
        with c1: st.markdown(f'<div style="background:#141720;border-radius:16px;padding:32px;text-align:center;border:1px solid #1e2235;"><span class="badge-gls">GLS</span><div style="font-size:64px;font-weight:800;font-family:DM Mono,monospace;color:{sc(sg_s)};margin:12px 0;">{sg_s:.0f}</div><div style="color:#5a6080;">/ 100</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div style="background:#141720;border-radius:16px;padding:32px;text-align:center;border:1px solid #1e2235;"><span class="badge-dpd">DPD</span><div style="font-size:64px;font-weight:800;font-family:DM Mono,monospace;color:{sc(sd_s)};margin:12px 0;">{sd_s:.0f}</div><div style="color:#5a6080;">/ 100</div></div>', unsafe_allow_html=True)

        diff=sd_s-sg_s
        ea=sum(m['economie_ttc'] for m in st.session_state.gls_data)/len(st.session_state.gls_data)*12
        if diff>5: st.markdown(f'<div class="alert-green">✅ <b>DPD recommandé</b> (+{diff:.0f}pts) — Économie projetée : <b>{ea:,.0f}€ TTC/an</b></div>'.replace(',', ' '), unsafe_allow_html=True)
        elif diff<-5: st.markdown('<div class="alert-red">⚠️ GLS reste compétitif — réévalue dans 1 mois</div>', unsafe_allow_html=True)
        else: st.markdown('<div class="alert-gold">🔄 Scores proches — continuer la phase de test</div>', unsafe_allow_html=True)

        col_e1, col_e2 = st.columns(2)
        with col_e1:
            if st.button("📧 Envoyer rapport par email", use_container_width=True):
                with st.spinner("Envoi en cours..."):
                    ok, msg = send_monthly_report(st.session_state.gls_data)
                if ok:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")
        with col_e2:
            if st.button("📥 Export Excel", use_container_width=True):
                out = io.BytesIO()
            with pd.ExcelWriter(out,engine='xlsxwriter') as w:
                pd.DataFrame([{'Mois':m['label'],'Colis':m['nb_colis'],
                    'GLS HT':round(m['total_gls_ht'],2),'DPD HT':round(m['total_dpd_ht'],2),
                    'Éco HT':round(m['economie_ht'],2),'Éco TTC':round(m['economie_ttc'],2),
                    'NCY HT':round(m['total_ncy_ht'],2)} for m in st.session_state.gls_data]
                ).to_excel(w,sheet_name='Synthèse',index=False)
            st.download_button("⬇️ Télécharger",data=out.getvalue(),
                file_name=f"ADC_transpo_{now.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ════════════ TAB 7 — CONTRÔLE ════════════
with tab7:
    st.markdown('<div class="section-title">🔍 Contrôle Facturation</div>', unsafe_allow_html=True)
    c1,c2 = st.columns(2)

    with c1:
        st.markdown('<span class="badge-gls">GLS</span> &nbsp; Contrôle barème / CSR / PER / SGO / NCY', unsafe_allow_html=True)
        cf_gls = st.file_uploader("BCF GLS à contrôler (CSV)", type=['csv'], key='cg')
        if cf_gls:
            with st.spinner("Contrôle GLS..."):
                cs,ce = controler_bcf_gls(cf_gls)
            if ce: st.error(ce)
            else:
                na=cs['nb_anomalies']; sf=cs['montant_surcharge_injustifiee']
                c_1,c_2 = st.columns(2)
                with c_1: ui.metric_card(title="Anomalies", content=str(na), description="")
                with c_2: ui.metric_card(title="Surfacturation HT", content=f"{sf:.2f}€", description="à réclamer")
                if na==0:
                    st.markdown('<div class="alert-green">✅ Aucune anomalie détectée</div>', unsafe_allow_html=True)
                else:
                    for t,n in cs['par_type'].items():
                        mt=cs['par_type_montant'][t]
                        st.markdown(f'<div class="alert-{"red" if mt>0 else "gold"}">{t} : {n} cas — {mt:+.2f}€ HT</div>', unsafe_allow_html=True)
                    if len(cs['anomalies_df'])>0:
                        aggrid_table(cs['anomalies_df'], height=300, color_col='Écart', red_if_positive=True)
                        out=io.BytesIO()
                        with pd.ExcelWriter(out,engine='xlsxwriter') as w:
                            cs['anomalies_df'].to_excel(w,sheet_name='Anomalies GLS',index=False)
                        # Alerte email si anomalies élevées
                    if na >= 5:
                        if st.button("📧 Envoyer alerte anomalies GLS", key="email_anomalies"):
                            ok, msg = send_anomaly_alert(cs['anomalies_df'], "Contrôle GLS")
                            st.success(msg) if ok else st.error(msg)
                    st.download_button("📥 Export GLS",data=out.getvalue(),
                            file_name=f"GLS_anomalies_{now.strftime('%Y%m%d')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.markdown('<div style="background:#141720;border-radius:8px;padding:14px;font-size:13px;color:#5a6080;line-height:2;">🔴 Barème poids · 🔴 CSR (0,71€) · 🔴 SGO mensuel<br>🔴 NCY injustifiée · 🔴 Double NCY · 🟡 PER (1,5%)</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<span class="badge-dpd">DPD</span> &nbsp; Contrôle contractuel ADC', unsafe_allow_html=True)
        cf_dpd = st.file_uploader("BCF DPD à contrôler (Excel)", type=['xlsx','xls'], key='cd')
        if cf_dpd:
            with st.spinner("Contrôle DPD..."):
                ds,de = parse_bcf_dpd(cf_dpd,config=st.session_state.dpd_config,sgo_dpd_manuel=sgo_dpd_input/100)
            if de: st.error(de)
            else:
                adf=ds.get('anomalies_df',pd.DataFrame())
                c_1,c_2 = st.columns(2)
                with c_1: ui.metric_card(title="Anomalies DPD", content=str(len(adf)), description="")
                with c_2: ui.metric_card(title="Taux avisés", content=f"{ds['taux_avis_pct']:.1f}%", description="cible <5%")
                for a in ds.get('alertes',[]):
                    if '🔴' in a: st.markdown(f'<div class="alert-red">{a}</div>', unsafe_allow_html=True)
                    else: st.markdown(f'<div class="alert-gold">{a}</div>', unsafe_allow_html=True)
                if len(adf)>0:
                    aggrid_table(adf, height=300)
        else:
            st.markdown('<div style="background:#141720;border-radius:8px;padding:14px;font-size:13px;color:#5a6080;line-height:2;">🔴 Volumétrique barré · 🟡 EDI manquante<br>⚠️ Avisés >5% · 🔴 Tarif avisé > négocié · ⚠️ Zebra 60€</div>', unsafe_allow_html=True)
