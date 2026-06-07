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

# Cacher le menu Streamlit (hamburger, footer, header)
st.markdown("""
<style>
#MainMenu {visibility: hidden !important;}
footer {visibility: hidden !important;}
header {visibility: hidden !important;}
[data-testid="stToolbar"] {visibility: hidden !important;}
.stDeployButton {display: none !important;}
</style>
""", unsafe_allow_html=True)

def check_password():
    """Vérifie le mot de passe — multi-utilisateurs."""
    def password_entered():
        pwd = st.session_state.get("password", "")
        if not pwd:
            return
        # Mots de passe valides : ADC + clients
        valid_passwords = {
            st.secrets.get("PASSWORD", "adc2026"): {"user": "ADC", "remise_sgo": True},
            st.secrets.get("PASSWORD_CLIENT1", "client2026"): {"user": "CLIENT1", "remise_sgo": False},
        }
        if pwd in valid_passwords:
            st.session_state["password_correct"] = True
            st.session_state["user_config"] = valid_passwords[pwd]
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
.kpi::before{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:2px 2px 0 0;}
.kpi-green{background:linear-gradient(135deg,#001508,#001e0a);border-color:#22c55e;box-shadow:0 0 20px rgba(34,197,94,.12);}
.kpi-green::before{background:linear-gradient(90deg,#22c55e,#16a34a);}
.kpi-green .kpi-val{color:#22c55e !important;text-shadow:0 0 20px rgba(34,197,94,.4);}
.kpi-red{background:linear-gradient(135deg,#150000,#1e0000);border-color:#ef4444;box-shadow:0 0 20px rgba(239,68,68,.12);}
.kpi-red::before{background:linear-gradient(90deg,#ef4444,#dc2626);}
.kpi-red .kpi-val{color:#ef4444 !important;text-shadow:0 0 20px rgba(239,68,68,.4);}
.kpi-gold{background:linear-gradient(135deg,#0f1120,#141720);border-color:#E8B84B;}
.kpi-gold::before{background:linear-gradient(90deg,#E8B84B,#f0c96a);}
.kpi-gold .kpi-val{color:#E8B84B !important;}
.kpi-blue::before{background:linear-gradient(90deg,#3b82f6,#2563eb);}
.kpi:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(0,0,0,.4);border-color:#2a2e45;}
.kpi-label{font-size:10px;font-weight:700;color:#4a5070;text-transform:uppercase;letter-spacing:.12em;margin-bottom:8px;}
.kpi-val{font-size:22px;font-weight:800;font-family:'DM Mono',monospace;color:#F0F2F8;line-height:1.2;}
.kpi-sub{font-size:11px;color:#3a4060;margin-top:6px;}
.big-eco-wrap{border-radius:20px;padding:36px;text-align:center;margin:16px 0;position:relative;overflow:hidden;}
.big-eco-wrap.pos{background:linear-gradient(135deg,#001a08,#002810);border:2px solid #22c55e;box-shadow:0 0 40px rgba(34,197,94,.15),inset 0 1px 0 rgba(34,197,94,.1);}
.big-eco-wrap.neg{background:linear-gradient(135deg,#1a0000,#280000);border:2px solid #ef4444;box-shadow:0 0 40px rgba(239,68,68,.15),inset 0 1px 0 rgba(239,68,68,.1);}
.big-eco{font-size:64px;font-weight:800;font-family:'DM Mono',monospace;line-height:1;letter-spacing:-3px;text-shadow:0 0 30px currentColor;}
.eco-pos{color:#22c55e;}
.eco-neg{color:#ef4444;}
.eco-label-pos{font-size:11px;text-transform:uppercase;letter-spacing:.15em;color:#22c55e;opacity:.8;margin-bottom:12px;}
.eco-label-neg{font-size:11px;text-transform:uppercase;letter-spacing:.15em;color:#ef4444;opacity:.8;margin-bottom:12px;}
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

def kpi(label, val, sub='', style='gold'):
    """KPI card HTML avec ligne colorée en haut."""
    return f'<div class="kpi kpi-{style}"><div class="kpi-label">{label}</div><div class="kpi-val">{val}</div><div class="kpi-sub">{sub}</div></div>'

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
c1, c2 = st.columns([8,1])
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
with c2:
    st.markdown("<div style='padding-top:4px;'></div>", unsafe_allow_html=True)
    if st.button("🔓 Quitter", use_container_width=True, key="btn_logout"):
        st.session_state["password_correct"] = False
        st.session_state.pop("user_config", None)
        st.rerun()

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
    "🔢 Simulateur","📈 Historique","🎯 Recommandations","🔍 Contrôle"
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
            with c1: st.markdown(kpi("Colis analysés", f"{tc:,}".replace(',', ' '), f"{nb_m} mois"), unsafe_allow_html=True)
            with c2: st.markdown(kpi("GLS facturé TTC", f"{tg_ttc:,.0f}€".replace(',', ' '), "réel"), unsafe_allow_html=True)
            with c3: st.markdown(kpi("DPD simulé TTC", f"{td_ttc:,.0f}€".replace(',', ' '), "théorique"), unsafe_allow_html=True)
            with c4: st.markdown(kpi("Économie DPD", f"{te_ttc:,.0f}€ TTC".replace(',', ' '), f"{ep:.1f}%", 'green' if te_ttc>0 else 'red'), unsafe_allow_html=True)
            with c5: st.markdown(kpi("NCY TTC", f"{tn_ttc:,.0f}€ TTC".replace(',', ' '), "GLS only", 'red'), unsafe_allow_html=True)

            signe = "+" if te_ttc>0 else ""
            wrap_class = "pos" if te_ttc>0 else "neg"
            label_class = "eco-label-pos" if te_ttc>0 else "eco-label-neg"
            ico = "✅" if te_ttc>0 else "⚠️"
            msg_eco = "Vous économisez avec DPD" if te_ttc>0 else "DPD moins avantageux ce mois"
            st.markdown(f"""
            <div class="big-eco-wrap {wrap_class}">
                <div class="{label_class}">{ico} {msg_eco} — {nb_m} mois · {tc:,} colis</div>
                <div class="big-eco {'eco-pos' if te_ttc>0 else 'eco-neg'}">{signe}{te_ttc:,.0f}€ TTC</div>
                <div style="font-size:14px;color:{'#22c55e' if te_ttc>0 else '#ef4444'};margin-top:10px;opacity:.8;">
                    Projection 12 mois : <b>{proj:,.0f}€ TTC/an</b> &nbsp;·&nbsp; soit <b>{proj/12:,.0f}€/mois</b>
                </div>
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
                with c1: st.markdown(kpi("Colis", str(m['nb_colis']), m['label'], 'blue'), unsafe_allow_html=True)
                with c2: st.markdown(kpi("Facture DPD TTC", f"{m['total_facture_ttc']:,.0f}€".replace(',', ' '), "réel"), unsafe_allow_html=True)
                with c3: st.markdown(kpi("GLS théorique TTC", f"{m.get('gls_theorique_ht',0)*1.2:,.0f}€".replace(',', ' '), "sim"), unsafe_allow_html=True)
                with c4: st.markdown(kpi("Éco vs GLS", f"{eco:+,.0f}€ TTC".replace(',', ' '), "", 'green' if eco>0 else 'red'), unsafe_allow_html=True)
                with c5: st.markdown(kpi("Taux avisés", f"{taux:.1f}%", "cible <5%"), unsafe_allow_html=True)
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
    has_gls2 = bool(st.session_state.gls_data)
    has_dpd2 = bool(st.session_state.dpd_data)
    if not has_gls2 and not has_dpd2:
        st.info("Importe des BCF GLS et/ou DPD pour voir l'analyse des coûts.")
    # ── GLS section ──
    if has_gls2:
        st.markdown('<div class="section-title">🔵 GLS — Décomposition par format (simulation DPD incluse)</div>', unsafe_allow_html=True)
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
                'DPD sim. HT moy':f"{d['dpd']/d['nb']:.2f}€" if d['nb'] else '—',
                'Éco/colis':f"{eco/d['nb']:+.2f}€" if d['nb'] else '—',
                'NCY HT':f"{d['ncy']:,.0f}€".replace(',', ' '),
                'Gagnant':'🔵 GLS' if eco<0 else('🔴 DPD' if eco>100 else'≈')})
        aggrid_table(pd.DataFrame(rows), height=250)
    # ── DPD section ──
    if has_dpd2:
        st.markdown('<div class="section-title">🔴 DPD — Analyse des BCF réels</div>', unsafe_allow_html=True)
        for m in st.session_state.dpd_data:
            st.markdown(f"**{m['label']}** — {m['nb_colis']} colis")
            c1,c2,c3,c4,c5 = st.columns(5)
            with c1: st.markdown(kpi("Facture HT", f"{m['total_facture_ht']:,.0f}€".replace(',', ' '), "réel"), unsafe_allow_html=True)
            with c2: st.markdown(kpi("Transport HT", f"{m['total_transport_ht']:,.0f}€".replace(',', ' '), "barème pur"), unsafe_allow_html=True)
            with c3: st.markdown(kpi("SGO HT", f"{m['total_sgo_ht']:,.0f}€".replace(',', ' '), f"taux {m['sgo_dpd']*100:.2f}%"), unsafe_allow_html=True)
            with c4: st.markdown(kpi("Sûreté+Log.", f"{(m['total_surete_ht']+m['total_log_ht']):.2f}€", "fixe/colis"), unsafe_allow_html=True)
            with c5:
                taux = m.get('taux_avis_pct',0)
                st.markdown(kpi("Taux avisés", f"{taux:.1f}%", "cible <5%", 'green' if taux<5 else ('gold' if taux<9 else 'red')), unsafe_allow_html=True)
            rows_dpd = []
            if m.get('nb_ile_montagne',0)>0: rows_dpd.append({'Surcharge':'🏝️ Île/montagne','Nb':m['nb_ile_montagne'],'HT':f"{m['total_ile_montagne_ht']:.2f}€",'Moy':f"{m['total_ile_montagne_ht']/m['nb_ile_montagne']:.2f}€"})
            if m.get('nb_avis',0)>0: rows_dpd.append({'Surcharge':'⚠️ Avisés','Nb':m['nb_avis'],'HT':f"{m['cout_avis_ht']:.2f}€",'Moy':f"{m['cout_avis_ht']/m['nb_avis']:.2f}€"})
            if m.get('nb_edi',0)>0: rows_dpd.append({'Surcharge':'🟡 EDI manquante','Nb':m['nb_edi'],'HT':f"{m['cout_edi_ht']:.2f}€",'Moy':f"{m['cout_edi_ht']/m['nb_edi']:.2f}€"})
            if m.get('nb_retours',0)>0: rows_dpd.append({'Surcharge':'↩️ Retours','Nb':m['nb_retours'],'HT':f"{m['cout_retours_ht']:.2f}€",'Moy':f"{m['cout_retours_ht']/m['nb_retours']:.2f}€"})
            if rows_dpd:
                st.dataframe(pd.DataFrame(rows_dpd), use_container_width=True, hide_index=True)
            else:
                st.markdown('<div class="alert-green">✅ Aucune surcharge anormale détectée</div>', unsafe_allow_html=True)
            for a in m.get('alertes',[]):
                if '🔴' in a: st.markdown(f'<div class="alert-red">{a}</div>', unsafe_allow_html=True)
                else: st.markdown(f'<div class="alert-gold">{a}</div>', unsafe_allow_html=True)
            st.markdown("---")

        # NCY
        st.markdown('<div class="section-title">⚠️ Surcharges NCY — Tendance</div>', unsafe_allow_html=True)
        tot_ncy = sum(m['total_ncy_ht'] for m in st.session_state.gls_data)
        nb_ncy  = sum(m['nb_ncy'] for m in st.session_state.gls_data)
        nb_col  = sum(m['nb_colis'] for m in st.session_state.gls_data)
        nb_m    = len(st.session_state.gls_data)

        c1,c2,c3,c4 = st.columns(4)
        with c1: st.markdown(kpi("NCY HT", f"{tot_ncy:,.0f}€".replace(',', ' '), "période", 'red'), unsafe_allow_html=True)
        with c2: st.markdown(kpi("NCY TTC", f"{tot_ncy*1.2:,.0f}€".replace(',', ' '), "+TVA", 'red'), unsafe_allow_html=True)
        with c3: st.markdown(kpi("Colis NCY", str(nb_ncy), f"{nb_ncy/nb_col*100 if nb_col else 0:.1f}%", 'red'), unsafe_allow_html=True)
        with c4: st.markdown(kpi("Projection 12M", f"{tot_ncy/nb_m*12*1.2 if nb_m else 0:,.0f}€".replace(',', ' '), "TTC/an", 'red'), unsafe_allow_html=True)

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
            with c1: st.markdown(kpi("GLS 9-10kg", f"{res['gls_9kg_ht']:.2f}€ HT", "1 colis + NCY 39%"), unsafe_allow_html=True)
            with c2: st.markdown(kpi("DPD 2 colis", f"{res['dpd_moy_ht']:.2f}€ HT", "50% 2×5kg / 50% 6+3kg"), unsafe_allow_html=True)
            with c3: st.markdown(kpi("Surcoût/colis", f"{res['surcoût_par_colis_ht']:+.2f}€ HT", "DPD plus cher"), unsafe_allow_html=True)
            impact = res['surcoût_total_ttc']*12
            st.markdown(f'<div class="alert-{"red" if impact>0 else "green"}">Impact annuel ({nb_mc} colis/mois) : <b>{impact:+,.0f}€ TTC/an</b> — {"⚠️ Garder GLS" if impact>0 else "✅ DPD OK"}</div>'.replace(',', ' '), unsafe_allow_html=True)

# ════════════ TAB 3 — GÉOGRAPHIE ════════════
with tab3:
    has_gls3 = bool(st.session_state.gls_data)
    has_dpd3 = bool(st.session_state.dpd_data)
    if not has_gls3 and not has_dpd3:
        st.info("Importe des BCF pour voir l'analyse géographique.")
    if has_gls3:
        st.markdown('<div class="section-title">🔵 GLS — Analyse par pays (simulation DPD)</div>', unsafe_allow_html=True)
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
                'DPD sim. HT':f"{d['dpd']:,.0f}€".replace(',', ' '),
                'Éco HT':f"{eco:+,.0f}€".replace(',', ' '),
                'Éco%':f"{eco/d['gls']*100:+.1f}%" if d['gls'] else '—',
                'NCY HT':f"{d['ncy']:,.0f}€".replace(',', ' '),
                'Reco':"⚠️ Garder GLS" if pays=='IT' else ("✅ DPD" if eco>50 else "≈")})
        aggrid_table(pd.DataFrame(rows), height=300)
        st.markdown('<div class="alert-red">⚠️ Italie : conserver GLS — DPD Zone 3 nettement plus cher</div>', unsafe_allow_html=True)
    if has_dpd3:
        st.markdown('<div class="section-title">🔴 DPD — Analyse par pays (données réelles)</div>', unsafe_allow_html=True)
        for idx_m, m in enumerate(st.session_state.dpd_data):
            st.markdown(f"**{m['label']}** — {m['nb_colis']} colis")
            c1,c2,c3 = st.columns(3)
            with c1: st.markdown(kpi("Colis", str(m['nb_colis']), m['label'], 'blue'), unsafe_allow_html=True)
            with c2:
                tav = m.get('taux_avis_pct',0)
                style_av = 'green' if tav<5 else ('gold' if tav<9 else 'red')
                st.markdown(kpi("Taux avisés", f"{tav:.1f}%", "cible <5%", style_av), unsafe_allow_html=True)
            with c3: st.markdown(kpi("Île/montagne", str(m.get('nb_ile_montagne',0)), f"{m.get('total_ile_montagne_ht',0):.2f}€ HT", 'gold'), unsafe_allow_html=True)
            # Tableau surcharges géo depuis le df DPD
            # Détail surcharges géographiques
            rows_geo = []
            if m.get('nb_ile_montagne', 0) > 0:
                rows_geo.append({
                    'Type': '🏝️ Île / Corse / Montagne',
                    'Nb colis': m['nb_ile_montagne'],
                    'Total HT': f"{m['total_ile_montagne_ht']:.2f}€",
                    'Coût moy/colis': f"{m['total_ile_montagne_ht']/m['nb_ile_montagne']:.2f}€",
                    'Remarque': 'Supplément géographique standard'
                })
            if m.get('nb_avis', 0) > 0:
                cout_u = m['cout_avis_ht']/m['nb_avis'] if m['nb_avis'] > 0 else 0
                rows_geo.append({
                    'Type': '⚠️ Avisés (absent)',
                    'Nb colis': m['nb_avis'],
                    'Total HT': f"{m['cout_avis_ht']:.2f}€",
                    'Coût moy/colis': f"{cout_u:.2f}€",
                    'Remarque': '⚠️ Tarif > 1€ ?' if cout_u > 1.1 else '✅ Tarif conforme'
                })
            if m.get('nb_retours', 0) > 0:
                rows_geo.append({
                    'Type': '↩️ Retours',
                    'Nb colis': m['nb_retours'],
                    'Total HT': f"{m['cout_retours_ht']:.2f}€",
                    'Coût moy/colis': f"{m['cout_retours_ht']/m['nb_retours']:.2f}€" if m['nb_retours'] else '—',
                    'Remarque': "Retour à l'expéditeur"
                })
            if m.get('nb_edi', 0) > 0:
                rows_geo.append({
                    'Type': '🟡 EDI manquante',
                    'Nb colis': m['nb_edi'],
                    'Total HT': f"{m['cout_edi_ht']:.2f}€",
                    'Coût moy/colis': f"{m['cout_edi_ht']/m['nb_edi']:.2f}€" if m['nb_edi'] else '—',
                    'Remarque': '🔧 Corriger intégration technique'
                })
            if rows_geo:
                st.markdown("**Surcharges détectées :**")
                st.dataframe(pd.DataFrame(rows_geo), use_container_width=True, hide_index=True)
            else:
                st.markdown('<div class="alert-green">✅ Aucune surcharge géographique détectée</div>', unsafe_allow_html=True)
            st.markdown("---")

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
    with c1: st.markdown(kpi("GLS HT", f"{gt:.2f}€", f"SGO net {sg*100:.2f}%"), unsafe_allow_html=True)
    with c2: st.markdown(kpi("DPD HT", f"{dt:.2f}€", f"SGO {sd*100:.2f}%"), unsafe_allow_html=True)
    with c3: st.markdown(kpi("Écart", f"{eco:+.2f}€", "DPD"), unsafe_allow_html=True)
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

# ════════════ TAB 6 — RECOMMANDATIONS ════════════
with tab6:
    st.markdown('<div class="section-title">🎯 Recommandations & Alertes prioritaires</div>', unsafe_allow_html=True)
    has_gls6 = bool(st.session_state.gls_data)
    has_dpd6 = bool(st.session_state.dpd_data)

    if not has_gls6 and not has_dpd6:
        st.markdown('<div style="text-align:center;padding:40px;color:#3a4060;"><div style="font-size:36px;">🎯</div><div style="font-size:14px;margin-top:12px;">Importe des BCF pour voir les recommandations</div></div>', unsafe_allow_html=True)
    else:
        # ── ALERTES PRIORITAIRES ─────────────────────────────────────────────
        alertes_rouges = []
        alertes_orange = []
        alertes_vertes = []

        if has_gls6:
            tot_eco = sum(m['economie_ttc'] for m in st.session_state.gls_data)
            tot_ncy = sum(m['total_ncy_ht']*1.2 for m in st.session_state.gls_data)
            nb_m6   = len(st.session_state.gls_data)
            proj_an = tot_eco/nb_m6*12 if nb_m6 else 0
            ncy_an  = tot_ncy/nb_m6*12 if nb_m6 else 0

            if tot_eco > 0:
                alertes_vertes.append(f"✅ Économie DPD confirmée : <b>+{tot_eco:,.0f}€ TTC</b> sur {nb_m6} mois → projection <b>+{proj_an:,.0f}€ TTC/an</b>".replace(',', ' '))
            else:
                alertes_rouges.append(f"🔴 DPD moins avantageux sur la période : <b>{tot_eco:,.0f}€ TTC</b> — réévaluer la stratégie transport".replace(',', ' '))

            if ncy_an > 15000:
                alertes_rouges.append(f"🔴 NCY GLS critique : <b>{ncy_an:,.0f}€ TTC/an</b> — exiger clause d'exclusion contractuelle immédiatement".replace(',', ' '))
            elif ncy_an > 8000:
                alertes_orange.append(f"⚠️ NCY GLS élevée : <b>{ncy_an:,.0f}€ TTC/an</b> — mettre la pression à GLS lors de la prochaine négo".replace(',', ' '))
            else:
                alertes_vertes.append(f"✅ NCY GLS maîtrisée : <b>{ncy_an:,.0f}€ TTC/an</b>".replace(',', ' '))

            # Tendance NCY
            if len(st.session_state.gls_data) >= 2:
                from utils.ncy_analyse import tendance_ncy
                tendance = tendance_ncy(st.session_state.gls_data)
                if len(tendance) >= 2:
                    diff_ncy = tendance[-1]['taux_ncy'] - tendance[-2]['taux_ncy']
                    if diff_ncy > 3:
                        alertes_rouges.append(f"🔴 Taux NCY en forte hausse : <b>+{diff_ncy:.1f}pts</b> ce mois ({tendance[-1]['taux_ncy']:.1f}%) — vérifier le mix produits expédiés")
                    elif diff_ncy > 1:
                        alertes_orange.append(f"⚠️ Taux NCY en légère hausse : +{diff_ncy:.1f}pts ce mois")
                    elif diff_ncy < -3:
                        alertes_vertes.append(f"✅ Taux NCY en baisse : {diff_ncy:.1f}pts ce mois — bonne évolution")

        if has_dpd6:
            for m in st.session_state.dpd_data:
                tav = m.get('taux_avis_pct', 0)
                lbl = m['label']
                if tav >= 9:
                    alertes_rouges.append(f"🔴 {lbl} — Taux avisés DPD critique : <b>{tav:.1f}%</b> — vérifier que le Predict (tél+email) est bien transmis. Objectif : &lt;5%")
                elif tav >= 5:
                    alertes_orange.append(f"⚠️ {lbl} — Taux avisés DPD élevé : <b>{tav:.1f}%</b> — surveiller, risque de surcoût avisés")
                else:
                    alertes_vertes.append(f"✅ {lbl} — Taux avisés DPD : <b>{tav:.1f}%</b> — excellent, objectif &lt;5% atteint")
                for a in m.get('alertes', []):
                    if '🔴' in a: alertes_rouges.append(a)
                    elif '⚠️' in a or '🟡' in a: alertes_orange.append(a)

        # Afficher les alertes par priorité
        if alertes_rouges:
            st.markdown("**🔴 Actions urgentes**")
            for a in alertes_rouges:
                st.markdown(f'<div class="alert-red" style="font-size:14px;padding:14px 18px;margin:6px 0;">{a}</div>', unsafe_allow_html=True)

        if alertes_orange:
            st.markdown("**⚠️ Points de vigilance**")
            for a in alertes_orange:
                st.markdown(f'<div class="alert-gold" style="font-size:14px;padding:14px 18px;margin:6px 0;">{a}</div>', unsafe_allow_html=True)

        if alertes_vertes:
            st.markdown("**✅ Points positifs**")
            for a in alertes_vertes:
                st.markdown(f'<div class="alert-green" style="font-size:14px;padding:14px 18px;margin:6px 0;">{a}</div>', unsafe_allow_html=True)

        # ── ACTIONS À FAIRE ─────────────────────────────────────────────────
        st.markdown('<div class="section-title" style="margin-top:24px;">📋 Actions recommandées</div>', unsafe_allow_html=True)
        actions = []

        if has_gls6:
            tot_eco6 = sum(m['economie_ttc'] for m in st.session_state.gls_data)
            tot_ncy6 = sum(m['total_ncy_ht']*1.2 for m in st.session_state.gls_data)
            nb_m6b   = len(st.session_state.gls_data)
            ncy_an6  = tot_ncy6/nb_m6b*12 if nb_m6b else 0

            if ncy_an6 > 5000:
                actions.append(("🔴 Haute priorité", f"Appeler GLS — argument : {ncy_an6:,.0f}€ TTC/an de NCY sur vos formats. Exiger clause d'exclusion ou avoir.".replace(',', ' ')))
            actions.append(("🔵 Mensuel", "Importer le nouveau BCF GLS dès réception pour suivre l'évolution de la NCY"))
            actions.append(("🔵 Mensuel", "Comparer avec le BCF DPD du même mois pour valider l'économie réelle"))

        if has_dpd6:
            for m in st.session_state.dpd_data:
                tav6 = m.get('taux_avis_pct', 0)
                if tav6 >= 5:
                    actions.append(("⚠️ Urgent", f"Vérifier avec DPD que le Predict est bien activé — taux avisés {m['label']} : {tav6:.1f}%"))
                if m.get('nb_edi', 0) > 0:
                    actions.append(("🟡 Technique", f"Corriger l'intégration EDI DPD — {m['nb_edi']} colis pénalisés à 0.50€/colis"))

        actions.append(("📅 Trimestriel", "Renégocier les contrats GLS et DPD avec les données du dashboard comme argument"))
        actions.append(("📅 Annuel", "Vérifier l'évolution des seuils NCY GLS — mécanisation des entrepôts → taux va augmenter"))

        for prio, desc in actions:
            color = '#ef4444' if 'Haute' in prio or 'Urgent' in prio else ('#E8B84B' if 'Urgent' in prio or 'Technique' in prio else '#5a6080')
            st.markdown(f'<div style="background:#0f1120;border:1px solid #1e2235;border-left:3px solid {color};border-radius:10px;padding:14px 18px;margin:6px 0;"><span style="font-size:11px;font-weight:700;color:{color};text-transform:uppercase;letter-spacing:.1em;">{prio}</span><div style="font-size:13px;color:#d0d8f0;margin-top:6px;">{desc}</div></div>', unsafe_allow_html=True)

        # ── RÉSUMÉ CHIFFRÉ ──────────────────────────────────────────────────
        if has_gls6:
            st.markdown('<div class="section-title" style="margin-top:24px;">💶 Résumé financier</div>', unsafe_allow_html=True)
            tot_e = sum(m['economie_ttc'] for m in st.session_state.gls_data)
            tot_g = sum(m['total_gls_ttc'] for m in st.session_state.gls_data)
            tot_n = sum(m['total_ncy_ht']*1.2 for m in st.session_state.gls_data)
            nb_c6 = sum(m['nb_colis'] for m in st.session_state.gls_data)
            nb_m6c = len(st.session_state.gls_data)
            proj6 = tot_e/nb_m6c*12 if nb_m6c else 0
            c1,c2,c3,c4 = st.columns(4)
            with c1: st.markdown(kpi("Économie cumulée TTC", f"{tot_e:+,.0f}€".replace(',', ' '), f"{nb_m6c} mois", 'green' if tot_e>0 else 'red'), unsafe_allow_html=True)
            with c2: st.markdown(kpi("Projection annuelle", f"{proj6:,.0f}€ TTC".replace(',', ' '), "sur 12 mois", 'green' if proj6>0 else 'red'), unsafe_allow_html=True)
            with c3: st.markdown(kpi("NCY cumulée TTC", f"{tot_n:,.0f}€".replace(',', ' '), "coût GLS uniquement", 'red'), unsafe_allow_html=True)
            with c4: st.markdown(kpi("Éco/colis TTC", f"{tot_e/nb_c6:.2f}€" if nb_c6 else "—", f"{nb_c6:,} colis".replace(',', ' '), 'green' if tot_e>0 else 'red'), unsafe_allow_html=True)

            # Export rapport
            if st.button("📧 Envoyer rapport par email", use_container_width=True):
                with st.spinner("Envoi en cours..."):
                    ok, msg = send_monthly_report(st.session_state.gls_data)
                if ok: st.success(f"✅ {msg}")
                else:  st.error(f"❌ {msg}")

            if st.button("📥 Export Excel complet", use_container_width=True):
                out6 = io.BytesIO()
                with pd.ExcelWriter(out6, engine='xlsxwriter') as w:
                    pd.DataFrame([{'Mois':m['label'],'Colis':m['nb_colis'],
                        'GLS HT':round(m['total_gls_ht'],2),'DPD HT':round(m['total_dpd_ht'],2),
                        'Éco HT':round(m['economie_ht'],2),'Éco TTC':round(m['economie_ttc'],2),
                        'NCY HT':round(m['total_ncy_ht'],2)} for m in st.session_state.gls_data]
                    ).to_excel(w, sheet_name='Synthèse', index=False)
                st.download_button("⬇️ Télécharger Excel",data=out6.getvalue(),
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
            if st.button("🔍 Valider le BCF GLS", type="primary", use_container_width=True, key="btn_val_gls"):
                with st.spinner("Contrôle GLS en cours..."):
                    cs,ce = controler_bcf_gls(cf_gls)
                if ce: st.error(ce)
                else: st.session_state['gls_ctrl_result'] = cs

        if 'gls_ctrl_result' in st.session_state:
            cs = st.session_state['gls_ctrl_result']
            na=cs['nb_anomalies']; sf=cs['montant_surcharge_injustifiee']
            c_1,c_2 = st.columns(2)
            with c_1: st.markdown(kpi("Anomalies GLS", str(na), "", 'red' if na>0 else 'green'), unsafe_allow_html=True)
            with c_2: st.markdown(kpi("Surfacturation HT", f"{sf:.2f}€", "à réclamer", 'red' if sf>0 else 'green'), unsafe_allow_html=True)
            if na==0:
                st.markdown('<div class="alert-green">✅ Aucune anomalie — facturation GLS conforme</div>', unsafe_allow_html=True)
            else:
                for t,n in cs['par_type'].items():
                    mt=cs['par_type_montant'][t]
                    st.markdown(f'<div class="alert-{"red" if mt>0 else "gold"}">{t} : {n} cas — {mt:+.2f}€ HT</div>', unsafe_allow_html=True)
                if len(cs['anomalies_df'])>0:
                    st.dataframe(cs['anomalies_df'], use_container_width=True, hide_index=True)
                    out=io.BytesIO()
                    with pd.ExcelWriter(out,engine='xlsxwriter') as w:
                        # Feuille 1 : Anomalies avec numéros de colis
                        cs['anomalies_df'].to_excel(w, sheet_name='Anomalies GLS', index=False)
                        # Feuille 2 : Résumé réclamation
                        pd.DataFrame([
                            {'Information':'Date contrôle','Valeur':now.strftime('%d/%m/%Y')},
                            {'Information':'Nb anomalies','Valeur':na},
                            {'Information':'Surfacturation HT','Valeur':f"{sf:.2f}€"},
                            {'Information':'Sous-facturation HT','Valeur':f"{cs.get('montant_sous_facture',0):.2f}€"},
                            {'Information':'Action','Valeur':'Envoyer ce fichier à votre commercial GLS pour réclamation'},
                        ]).to_excel(w, sheet_name='Résumé réclamation', index=False)
                    st.download_button(
                        "📥 Exporter dossier de réclamation GLS (Excel)",
                        data=out.getvalue(),
                        file_name=f"GLS_reclamation_{now.strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                    st.markdown('<div class="alert-gold">💡 Le fichier contient les numéros de colis concernés et un résumé de réclamation prêt à envoyer à GLS.</div>', unsafe_allow_html=True)
                    if na >= 5:
                        if st.button("📧 Envoyer alerte email anomalies GLS", key="email_anomalies"):
                            ok, msg = send_anomaly_alert(cs['anomalies_df'], "Contrôle GLS")
                            st.success(msg) if ok else st.error(msg)
        else:
            st.markdown('<div style="background:#141720;border-radius:8px;padding:14px;font-size:13px;color:#5a6080;line-height:2;">Upload un BCF GLS et clique Valider pour contrôler la facturation.<br>🔴 Barème · 🔴 CSR (0,71€) · 🔴 SGO · 🔴 NCY injustifiée · 🟡 PER</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<span class="badge-dpd">DPD</span> &nbsp; Contrôle contractuel — vérification facturation', unsafe_allow_html=True)
        cf_dpd = st.file_uploader("BCF DPD à contrôler (Excel)", type=['xlsx','xls'], key='cd')
        if cf_dpd:
            if st.button("🔍 Valider le BCF DPD", type="primary", use_container_width=True, key="btn_val_dpd"):
                with st.spinner("Contrôle facturation DPD..."):
                    ds,de = parse_bcf_dpd(cf_dpd,config=st.session_state.dpd_config,sgo_dpd_manuel=sgo_dpd_input/100)
                if de:
                    st.error(de)
                else:
                    st.session_state['dpd_ctrl_result'] = ds

        if 'dpd_ctrl_result' in st.session_state:
            ds = st.session_state['dpd_ctrl_result']
            adf = ds.get('anomalies_df', pd.DataFrame())
            na = len(adf)
            tav = ds.get('taux_avis_pct', 0)
            style_av = 'green' if tav<5 else ('gold' if tav<9 else 'red')
            c_1,c_2,c_3 = st.columns(3)
            with c_1: st.markdown(kpi("Anomalies DPD", str(na), "à vérifier", 'red' if na>0 else 'green'), unsafe_allow_html=True)
            with c_2: st.markdown(kpi("Taux avisés", f"{tav:.1f}%", "cible <5%", style_av), unsafe_allow_html=True)
            with c_3: st.markdown(kpi("Colis analysés", str(ds.get('nb_colis',0)), ""), unsafe_allow_html=True)
            for a in ds.get('alertes',[]):
                if '🔴' in a: st.markdown(f'<div class="alert-red">{a}</div>', unsafe_allow_html=True)
                else: st.markdown(f'<div class="alert-gold">{a}</div>', unsafe_allow_html=True)
            if na == 0:
                st.markdown('<div class="alert-green">✅ Aucune anomalie — facturation DPD conforme au contrat</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="alert-red">⚠️ {na} anomalie(s) détectée(s) — export disponible pour réclamation</div>', unsafe_allow_html=True)
                st.dataframe(adf, use_container_width=True, hide_index=True)
                out_dpd = io.BytesIO()
                with pd.ExcelWriter(out_dpd, engine='xlsxwriter') as w:
                    # Feuille 1 : Anomalies détaillées avec numéros de colis
                    adf_export = adf.copy()
                    # Renommer les colonnes pour clarté
                    col_renames = {
                        'Type': 'Type anomalie',
                        'Nb colis': 'Nb colis concernés',
                        'Surpoids total': 'Détail',
                        'Surcoût estimé HT': 'Surcoût estimé HT',
                        'Action': 'Action recommandée',
                        'Gravité': 'Priorité',
                    }
                    adf_export = adf_export.rename(columns={k:v for k,v in col_renames.items() if k in adf_export.columns})
                    adf_export.to_excel(w, sheet_name='Anomalies détaillées', index=False)

                    # Feuille 2 : Résumé pour la réclamation
                    resume_data = {
                        'Information': [
                            'Date du contrôle',
                            'BCF analysé',
                            'Nombre de colis',
                            'Facture HT totale',
                            "Nombre d'anomalies",
                            'Taux avisés',
                            'Action recommandée',
                        ],
                        'Valeur': [
                            now.strftime('%d/%m/%Y'),
                            ds.get('label', ''),
                            ds.get('nb_colis', 0),
                            f"{ds.get('total_facture_ht', 0):.2f}€",
                            na,
                            f"{tav:.1f}%",
                            'Envoyer ce fichier à votre commercial DPD pour réclamation',
                        ]
                    }
                    pd.DataFrame(resume_data).to_excel(w, sheet_name='Résumé réclamation', index=False)

                    # Feuille 3 : Données brutes du BCF
                    if ds.get('df') is not None and len(ds['df']) > 0:
                        ds['df'].to_excel(w, sheet_name='BCF complet', index=False)

                    # Mise en forme
                    wb_xl = w.book
                    fmt_header = wb_xl.add_format({'bold':True,'bg_color':'#1a1a2e','font_color':'white','border':1})
                    fmt_red    = wb_xl.add_format({'font_color':'#ef4444','bold':True})
                    fmt_green  = wb_xl.add_format({'font_color':'#22c55e'})

                st.download_button(
                    "📥 Exporter le dossier de réclamation DPD (Excel)",
                    data=out_dpd.getvalue(),
                    file_name=f"DPD_reclamation_{now.strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key="dl_dpd_anomalies",
                )
                st.markdown('<div class="alert-gold">💡 Ce fichier contient 3 onglets : anomalies détaillées, résumé de réclamation, et le BCF complet. Envoyez-le directement à votre commercial DPD.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="background:#141720;border-radius:8px;padding:14px;font-size:13px;color:#5a6080;line-height:2;">Upload un BCF DPD et clique Valider pour vérifier la conformité au contrat.<br>🟡 EDI manquante · ⚠️ Avisés &gt;5% · 🔴 Tarif avisé &gt; négocié · ⚠️ Zebra 60€</div>', unsafe_allow_html=True)
