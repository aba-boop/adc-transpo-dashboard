"""
ADC — Transpo Dashboard V2
Comparatif GLS vs DPD — Allée du Commerce
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import io
from datetime import datetime

from utils.parsers import parse_bcf_gls
from utils.controle import controler_bcf_gls
from utils.ncy_analyse import tendance_ncy, calcul_surcoût_multicolis_dpd
from utils.tarifs import (
    cout_gls, cout_dpd, get_sgo_mois, scraper_sgo_gls, scraper_sgo_dpd,
    GLS_FR, DPD_FR, GLS_EU, DPD_EU, PAYS_ZONE_GLS, PAYS_ZONE_DPD,
    GLS_REMISE_SGO, SGO_HISTORIQUE
)

# ─── CONFIG ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ADC — Transpo Dashboard",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Syne', sans-serif; }
.mono { font-family: 'DM Mono', monospace; }

/* Cards KPI */
.kpi { background:#141720; border:1px solid #1e2235; border-radius:12px; padding:20px 22px; margin:4px 0; }
.kpi-label { font-size:11px; font-weight:600; color:#5a6080; text-transform:uppercase; letter-spacing:.1em; margin-bottom:6px; }
.kpi-val { font-size:26px; font-weight:800; font-family:'DM Mono',monospace; color:#F0F2F8; }
.kpi-sub { font-size:12px; color:#4a5070; margin-top:4px; }
.kpi-green { border-left:3px solid #22c55e; }
.kpi-red   { border-left:3px solid #ef4444; }
.kpi-gold  { border-left:3px solid #E8B84B; }

/* Badges transporteurs */
.badge-gls { background:#1a2a5e; color:#93b4fd; padding:3px 12px; border-radius:20px; font-size:13px; font-weight:700; }
.badge-dpd { background:#5e1a1a; color:#fca5a5; padding:3px 12px; border-radius:20px; font-size:13px; font-weight:700; }

/* Alertes */
.alert-gold { background:#1e1800; border:1px solid #E8B84B; border-radius:8px; padding:12px 16px; color:#fde68a; font-size:13px; margin:6px 0; }
.alert-green { background:#001a10; border:1px solid #22c55e; border-radius:8px; padding:12px 16px; color:#86efac; font-size:13px; margin:6px 0; }
.alert-red { background:#1a0000; border:1px solid #ef4444; border-radius:8px; padding:12px 16px; color:#fca5a5; font-size:13px; margin:6px 0; }

/* Section titles */
.section-title { font-size:17px; font-weight:800; color:#F0F2F8; padding-bottom:8px; border-bottom:1px solid #1e2235; margin:20px 0 12px 0; }

/* Big number */
.big-eco { font-size:52px; font-weight:800; font-family:'DM Mono',monospace; text-align:center; }
.eco-positive { color:#22c55e; }
.eco-negative { color:#ef4444; }
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ────────────────────────────────────────────────────────────
if 'mois_data' not in st.session_state:
    st.session_state.mois_data = []  # liste de stats par mois importé
if 'sgo_cache' not in st.session_state:
    st.session_state.sgo_cache = {'gls': None, 'dpd': None, 'ts': None}

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚚 Transpo Dashboard")
    st.markdown('<span class="badge-gls">GLS</span> &nbsp; vs &nbsp; <span class="badge-dpd">DPD</span>', unsafe_allow_html=True)
    st.markdown("---")

    # SGO en temps réel
    st.markdown("### 📊 Taux Gazole (SGO)")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Auto", use_container_width=True):
            with st.spinner("Scraping..."):
                gls_site = scraper_sgo_gls()
                dpd_site = scraper_sgo_dpd()
                if gls_site:
                    st.session_state.sgo_cache['gls'] = gls_site
                if dpd_site:
                    st.session_state.sgo_cache['dpd'] = dpd_site
                st.session_state.sgo_cache['ts'] = datetime.now()

    now = datetime.now()
    key = (now.year, now.month)
    hist = SGO_HISTORIQUE.get(key, list(SGO_HISTORIQUE.values())[-1])
    default_gls = (st.session_state.sgo_cache['gls'] or hist[0]) * 100
    default_dpd = (st.session_state.sgo_cache['dpd'] or hist[1]) * 100

    sgo_gls_input = st.number_input("GLS site (%)", value=round(default_gls, 2), step=0.01, format="%.2f")
    sgo_dpd_input = st.number_input("DPD routier (%)", value=round(default_dpd, 2), step=0.01, format="%.2f")

    sgo_gls_net = sgo_gls_input/100 - 0.06
    sgo_dpd     = sgo_dpd_input/100

    st.markdown(f"<small>GLS net (−6pts) : <b>{sgo_gls_net*100:.2f}%</b></small>", unsafe_allow_html=True)
    st.markdown("---")

    # Import BCF
    st.markdown("### 📂 Importer un BCF GLS")
    mois_label = st.text_input("Label du mois (ex: Juin 2026)", value=f"{datetime.now().strftime('%B %Y')}")
    bcf_file = st.file_uploader("BCF GLS (CSV)", type=['csv'])

    if st.button("➕ Analyser ce BCF", type="primary", use_container_width=True):
        if bcf_file:
            with st.spinner(f"Analyse {mois_label}..."):
                stats, err = parse_bcf_gls(
                    bcf_file,
                    sgo_gls_manuel=sgo_gls_input/100,
                    sgo_dpd_manuel=sgo_dpd_input/100,
                )
                if err:
                    st.error(f"Erreur : {err}")
                else:
                    stats['label'] = mois_label
                    # Éviter doublon
                    st.session_state.mois_data = [m for m in st.session_state.mois_data if m['label'] != mois_label]
                    st.session_state.mois_data.append(stats)
                    st.success(f"✅ {mois_label} importé — {stats['nb_colis']} colis")
        else:
            st.warning("Sélectionne un fichier BCF")

    if st.session_state.mois_data:
        st.markdown("**Mois chargés :**")
        for i, m in enumerate(st.session_state.mois_data):
            col_l, col_r = st.columns([4,1])
            with col_l:
                eco = m['economie_ttc']
                col = "🟢" if eco > 0 else "🔴"
                st.markdown(f"<small>{col} {m['label']} ({m['nb_colis']} colis)</small>", unsafe_allow_html=True)
            with col_r:
                if st.button("✕", key=f"del_{i}"):
                    st.session_state.mois_data.pop(i)
                    st.rerun()

    st.markdown("---")
    st.markdown("### ⚙️ Score final")
    w_cout = st.slider("💰 Coût", 0, 100, 40)
    w_qual = st.slider("⏱ Qualité", 0, 100, 40)
    w_fact = st.slider("📄 Facturation", 0, 100, 20)

# ─── HEADER ──────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex;align-items:center;gap:16px;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #1e2235;">
    <div style="font-size:28px;font-weight:800;color:#F0F2F8;">🚚 Transpo Dashboard</div>
    <span class="badge-gls">GLS</span>
    <span style="color:#3a4060;font-size:18px;">vs</span>
    <span class="badge-dpd">DPD</span>
    <div style="flex:1;"></div>
    <div style="font-size:11px;color:#3a4060;">Allée du Commerce — Marseille</div>
</div>
""", unsafe_allow_html=True)

# ─── TABS ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📊 Synthèse", "💰 Coûts détaillés", "🌍 Géographie", "🔢 Simulateur", "📈 Historique", "🏆 Score", "🔍 Contrôle"
])

def fmt_eur(v, ttc=False):
    if v is None: return "—"
    suffix = " TTC" if ttc else " HT"
    return f"{v:,.0f}€{suffix}".replace(',', ' ')

def kpi(label, val, sub='', style='gold'):
    return f'<div class="kpi kpi-{style}"><div class="kpi-label">{label}</div><div class="kpi-val">{val}</div><div class="kpi-sub">{sub}</div></div>'

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — SYNTHÈSE
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    if not st.session_state.mois_data:
        st.markdown("""
        <div style="text-align:center;padding:80px 0;color:#3a4060;">
            <div style="font-size:48px;margin-bottom:16px;">📂</div>
            <div style="font-size:18px;font-weight:700;color:#5a6080;">Importe un BCF GLS dans la barre latérale</div>
            <div style="font-size:13px;margin-top:8px;">Format CSV avec séparateur ; — export depuis your-gls</div>
        </div>""", unsafe_allow_html=True)
    else:
        # Cumuler tous les mois
        tot_gls  = sum(m['total_gls_ttc']  for m in st.session_state.mois_data)
        tot_dpd  = sum(m['total_dpd_ttc']  for m in st.session_state.mois_data)
        tot_eco  = sum(m['economie_ttc']   for m in st.session_state.mois_data)
        tot_ncy  = sum(m['total_ncy_ht']*1.2 for m in st.session_state.mois_data)
        tot_colis= sum(m['nb_colis']        for m in st.session_state.mois_data)
        nb_mois  = len(st.session_state.mois_data)

        # Grande économie centrale
        eco_color = "eco-positive" if tot_eco > 0 else "eco-negative"
        signe = "+" if tot_eco > 0 else ""
        st.markdown(f"""
        <div style="text-align:center;padding:32px 0 16px 0;">
            <div style="font-size:13px;color:#5a6080;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;">
                Économie cumulée ({nb_mois} mois • {tot_colis:,} colis)
            </div>
            <div class="big-eco {eco_color}">{signe}{tot_eco:,.0f}€ TTC</div>
            <div style="font-size:13px;color:#5a6080;margin-top:8px;">
                Projection 12 mois : <b style="color:#E8B84B;">{tot_eco/nb_mois*12:,.0f}€ TTC/an</b>
            </div>
        </div>""".replace(',', ' '), unsafe_allow_html=True)

        # KPIs
        c1, c2, c3, c4, c5 = st.columns(5)
        eco_pct = tot_eco/tot_gls*100 if tot_gls else 0
        with c1: st.markdown(kpi("Colis analysés", f"{tot_colis:,}".replace(',', ' '), f"{nb_mois} mois"), unsafe_allow_html=True)
        with c2: st.markdown(kpi("GLS TTC total", fmt_eur(tot_gls, True), "facturé réel"), unsafe_allow_html=True)
        with c3: st.markdown(kpi("DPD TTC simulé", fmt_eur(tot_dpd, True), "estimation"), unsafe_allow_html=True)
        with c4: st.markdown(kpi("Économie TTC", fmt_eur(tot_eco, True), f"{eco_pct:.1f}% d'écart", 'green' if tot_eco>0 else 'red'), unsafe_allow_html=True)
        with c5: st.markdown(kpi("NCY TTC", fmt_eur(tot_ncy, True), "surcharge GLS only", 'red'), unsafe_allow_html=True)

        # Alertes
        st.markdown('<div class="section-title">🔔 Alertes</div>', unsafe_allow_html=True)
        for m in st.session_state.mois_data:
            for alerte in m.get('alertes', []):
                if '⚠️' in alerte:
                    st.markdown(f'<div class="alert-gold">{alerte}</div>', unsafe_allow_html=True)
                elif '✅' in alerte:
                    st.markdown(f'<div class="alert-green">{alerte}</div>', unsafe_allow_html=True)
                elif '🇮🇹' in alerte:
                    st.markdown(f'<div class="alert-red">{alerte}</div>', unsafe_allow_html=True)

        # Graphique évolution mensuelle
        if nb_mois > 1:
            st.markdown('<div class="section-title">📈 Évolution mensuelle</div>', unsafe_allow_html=True)
            df_mois = pd.DataFrame([{
                'Mois': m['label'],
                'GLS TTC': round(m['total_gls_ttc'], 0),
                'DPD TTC': round(m['total_dpd_ttc'], 0),
                'Économie TTC': round(m['economie_ttc'], 0),
                'NCY TTC': round(m['total_ncy_ht']*1.2, 0),
            } for m in st.session_state.mois_data])

            fig = go.Figure()
            fig.add_trace(go.Bar(name='GLS TTC', x=df_mois['Mois'], y=df_mois['GLS TTC'],
                                  marker_color='#3b82f6', text=df_mois['GLS TTC'].apply(lambda x: f'{x:,.0f}€'.replace(',', ' ')), textposition='outside'))
            fig.add_trace(go.Bar(name='DPD TTC', x=df_mois['Mois'], y=df_mois['DPD TTC'],
                                  marker_color='#ef4444', text=df_mois['DPD TTC'].apply(lambda x: f'{x:,.0f}€'.replace(',', ' ')), textposition='outside'))
            fig.add_trace(go.Scatter(name='Économie TTC', x=df_mois['Mois'], y=df_mois['Économie TTC'],
                                      mode='lines+markers+text', line=dict(color='#E8B84B', width=3),
                                      marker=dict(size=8), text=df_mois['Économie TTC'].apply(lambda x: f'+{x:,.0f}€'.replace(',', ' ')),
                                      textposition='top center', yaxis='y2'))
            fig.update_layout(
                barmode='group', plot_bgcolor='#141720', paper_bgcolor='#141720',
                font_color='#F0F2F8', legend=dict(orientation='h', y=1.1),
                yaxis=dict(title='Montant TTC (€)'),
                yaxis2=dict(title='Économie TTC (€)', overlaying='y', side='right', showgrid=False),
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — COÛTS DÉTAILLÉS
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="section-title">💰 Décomposition des coûts par format</div>', unsafe_allow_html=True)

    if not st.session_state.mois_data:
        st.info("Importe un BCF pour voir la décomposition.")
    else:
        # Consolidation par format
        par_format = {}
        for m in st.session_state.mois_data:
            for fmt, d in m['par_format'].items():
                if fmt not in par_format:
                    par_format[fmt] = {'nb':0,'gls':0.0,'dpd':0.0,'ncy':0.0}
                par_format[fmt]['nb']  += d['nb']
                par_format[fmt]['gls'] += d['gls']
                par_format[fmt]['dpd'] += d['dpd']
                par_format[fmt]['ncy'] += d['ncy']

        rows = []
        for fmt, d in sorted(par_format.items(), key=lambda x: -x[1]['gls']):
            eco = d['gls'] - d['dpd']
            rows.append({
                'Format': fmt,
                'Nb colis': d['nb'],
                'GLS HT moy.': f"{d['gls']/d['nb']:.2f}€" if d['nb'] else '—',
                'DPD HT moy.': f"{d['dpd']/d['nb']:.2f}€" if d['nb'] else '—',
                'Éco HT/colis': f"{eco/d['nb']:+.2f}€" if d['nb'] else '—',
                'NCY HT total': f"{d['ncy']:,.0f}€".replace(',', ' '),
                'Gagnant': '🔵 GLS' if eco < 0 else ('🔴 DPD' if eco > 100 else '≈ Égal'),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # NCY breakdown
        st.markdown('<div class="section-title">⚠️ Surcharges NCY (GLS only → 0€ chez DPD)</div>', unsafe_allow_html=True)
        tot_ncy_ht = sum(m['total_ncy_ht'] for m in st.session_state.mois_data)
        nb_ncy_tot = sum(m['nb_ncy'] for m in st.session_state.mois_data)
        nb_colis_tot = sum(m['nb_colis'] for m in st.session_state.mois_data)

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(kpi("Total NCY HT", f"{tot_ncy_ht:,.0f}€".replace(',', ' '), "sur la période", 'red'), unsafe_allow_html=True)
        with c2: st.markdown(kpi("Total NCY TTC", f"{tot_ncy_ht*1.2:,.0f}€".replace(',', ' '), "+20% TVA", 'red'), unsafe_allow_html=True)
        with c3: st.markdown(kpi("Colis frappés NCY", str(nb_ncy_tot), f"{nb_ncy_tot/nb_colis_tot*100:.1f}% du total", 'red'), unsafe_allow_html=True)
        with c4:
            nb_mois = len(st.session_state.mois_data)
            proj = tot_ncy_ht/nb_mois*12*1.2 if nb_mois else 0
            st.markdown(kpi("Projection NCY 12M", f"{proj:,.0f}€ TTC".replace(',', ' '), "annualisé", 'red'), unsafe_allow_html=True)

        # ─── GRAPHE TENDANCE NCY ──────────────────────────────────────────────
        if len(st.session_state.mois_data) >= 2:
            tendance = tendance_ncy(st.session_state.mois_data)
            df_ncy = pd.DataFrame(tendance)

            dernier = tendance[-1]
            avant_dernier = tendance[-2]
            diff_taux = dernier['taux_ncy'] - avant_dernier['taux_ncy']
            taux_moy = sum(t['taux_ncy'] for t in tendance) / len(tendance)

            if diff_taux > 3:
                st.markdown(f'<div class="alert-red">📈 NCY en hausse : +{diff_taux:.1f}pts vs mois précédent ({dernier["taux_ncy"]:.1f}% vs {avant_dernier["taux_ncy"]:.1f}%). Vérifier le mix produits.</div>', unsafe_allow_html=True)
            elif diff_taux < -3:
                st.markdown(f'<div class="alert-green">📉 NCY en baisse : {diff_taux:.1f}pts vs mois précédent. Bonne évolution.</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="alert-gold">📊 NCY stable — taux moyen : {taux_moy:.1f}%</div>', unsafe_allow_html=True)

            colors = ['#ef4444' if (t['trend_pts'] and t['trend_pts'] > 2) else
                      '#22c55e' if (t['trend_pts'] and t['trend_pts'] < -2) else
                      '#E8B84B' for t in tendance]

            fig_ncy = go.Figure()
            fig_ncy.add_trace(go.Bar(
                name='NCY HT (€)', x=df_ncy['label'], y=df_ncy['ncy_ht'],
                marker_color=colors, yaxis='y1',
                text=df_ncy['ncy_ht'].apply(lambda x: f"{x:,.0f}€".replace(',', ' ')),
                textposition='outside',
            ))
            fig_ncy.add_trace(go.Scatter(
                name='Taux NCY (%)', x=df_ncy['label'], y=df_ncy['taux_ncy'],
                mode='lines+markers+text', line=dict(color='#ffffff', width=2),
                marker=dict(size=8, color='#ffffff'),
                text=df_ncy['taux_ncy'].apply(lambda x: f"{x:.1f}%"),
                textposition='top center', yaxis='y2',
            ))
            for i, t in enumerate(tendance):
                if t['trend_pts'] is not None:
                    s = f"▲+{t['trend_pts']:.1f}pts" if t['trend_pts'] > 0.5 else (f"▼{t['trend_pts']:.1f}pts" if t['trend_pts'] < -0.5 else "→")
                    c = '#ef4444' if t['trend_pts'] > 2 else ('#22c55e' if t['trend_pts'] < -2 else '#E8B84B')
                    fig_ncy.add_annotation(x=t['label'], y=t['taux_ncy']+1.5,
                        text=s, showarrow=False, font=dict(size=10, color=c), yref='y2')

            fig_ncy.update_layout(
                plot_bgcolor='#141720', paper_bgcolor='#141720', font_color='#F0F2F8',
                height=350, legend=dict(orientation='h', y=1.1),
                yaxis=dict(title='NCY HT (€)'),
                yaxis2=dict(title='Taux NCY (%)', overlaying='y', side='right', showgrid=False),
                title='Évolution mensuelle NCY GLS',
            )
            st.plotly_chart(fig_ncy, use_container_width=True)

            rows_ncy = []
            for t in tendance:
                ts = (f"▲+{t['trend_pts']:.1f}pts" if t['trend_pts'] and t['trend_pts']>0.5
                      else (f"▼{t['trend_pts']:.1f}pts" if t['trend_pts'] and t['trend_pts']<-0.5 else "→ stable"))
                rows_ncy.append({'Mois':t['label'],'Colis':t['nb_colis'],
                    'NCY':t['nb_ncy'],'Taux':f"{t['taux_ncy']:.1f}%",
                    'NCY HT':f"{t['ncy_ht']:,.0f}€".replace(',', ' '),
                    'NCY TTC':f"{t['ncy_ttc']:,.0f}€".replace(',', ' '),
                    'NCY/colis':f"{t['ncy_par_colis']:.2f}€",'Trend':ts})
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
            st.markdown(f'<div class="alert-{"red" if impact_an>0 else "green"}">Impact annuel sur {nb_mc} colis/mois : <b style="color:{couleur}">{impact_an:+,.0f}€ TTC/an</b> — {"⚠️ Garder GLS pour ce format" if impact_an>0 else "✅ DPD reste intéressant"}</div>'.replace(',', ' '), unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — GÉOGRAPHIE
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown('<div class="section-title">🌍 Analyse par pays et zone</div>', unsafe_allow_html=True)

    if not st.session_state.mois_data:
        st.info("Importe un BCF pour voir l'analyse géographique.")
    else:
        par_pays = {}
        for m in st.session_state.mois_data:
            for pays, d in m['par_pays'].items():
                if pays not in par_pays:
                    par_pays[pays] = {'nb':0,'gls':0.0,'dpd':0.0,'ncy':0.0}
                par_pays[pays]['nb']  += d['nb']
                par_pays[pays]['gls'] += d['gls']
                par_pays[pays]['dpd'] += d['dpd']
                par_pays[pays]['ncy'] += d['ncy']

        rows = []
        for pays, d in sorted(par_pays.items(), key=lambda x: -x[1]['gls']):
            eco = d['gls'] - d['dpd']
            eco_pct = eco/d['gls']*100 if d['gls'] else 0
            reco = "🔴 DPD" if pays == 'IT' else ("✅ DPD" if eco > 50 else "≈ Égal")
            if pays == 'IT':
                reco = "⚠️ Garder GLS"
            rows.append({
                'Pays': pays,
                'Nb colis': d['nb'],
                'GLS HT': f"{d['gls']:,.0f}€".replace(',', ' '),
                'DPD HT': f"{d['dpd']:,.0f}€".replace(',', ' '),
                'Éco HT': f"{eco:+,.0f}€".replace(',', ' '),
                'Éco %': f"{eco_pct:+.1f}%",
                'NCY HT': f"{d['ncy']:,.0f}€".replace(',', ' '),
                'Recommandation': reco,
            })

        df_pays = pd.DataFrame(rows)
        st.dataframe(df_pays, use_container_width=True, hide_index=True)

        # Graphique par pays
        df_plot = pd.DataFrame([{
            'Pays': r['Pays'],
            'GLS': par_pays[r['Pays']]['gls'],
            'DPD': par_pays[r['Pays']]['dpd'],
        } for r in rows]).sort_values('GLS', ascending=False).head(10)

        fig = go.Figure()
        fig.add_trace(go.Bar(name='GLS HT', x=df_plot['Pays'], y=df_plot['GLS'], marker_color='#3b82f6'))
        fig.add_trace(go.Bar(name='DPD HT', x=df_plot['Pays'], y=df_plot['DPD'], marker_color='#ef4444'))
        fig.update_layout(barmode='group', plot_bgcolor='#141720', paper_bgcolor='#141720',
                          font_color='#F0F2F8', height=350, title='GLS vs DPD par pays (HT)')
        st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="alert-red">⚠️ Italie : conserver GLS — DPD Zone 3 est significativement plus cher (~5€/colis)</div>', unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — SIMULATEUR TARIFAIRE
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<div class="section-title">🔢 Simulateur — Prix colis à la demande</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        poids_sim = st.number_input("Poids (kg)", min_value=0.1, max_value=30.0, value=5.0, step=0.1)
    with col2:
        pays_sim = st.selectbox("Destination", ['FR','DE','BE','NL','ES','PT','IT','PL','AT','SE','DK','CZ','HU','RO','BG','GB'])
    with col3:
        mois_sim = st.selectbox("Mois SGO", list(reversed(list(SGO_HISTORIQUE.keys()))), format_func=lambda x: f"{x[1]:02d}/{x[0]}")

    sgo_gls_sim, sgo_dpd_sim = get_sgo_mois(mois_sim[0], mois_sim[1])
    _, gls_total = cout_gls(poids_sim, pays_sim, sgo_gls_sim)
    _, dpd_total = cout_dpd(poids_sim, pays_sim, sgo_dpd_sim)
    eco = gls_total - dpd_total

    c1, c2, c3 = st.columns(3)
    with c1:
        style = 'red' if eco < 0 else 'green'
        st.markdown(kpi("GLS HT", f"{gls_total:.2f}€",
                        f"SGO net {sgo_gls_sim*100:.2f}%"), unsafe_allow_html=True)
    with c2:
        st.markdown(kpi("DPD HT", f"{dpd_total:.2f}€",
                        f"SGO {sgo_dpd_sim*100:.2f}% (barème seul)"), unsafe_allow_html=True)
    with c3:
        gagnant = "GLS" if eco > 0.05 else ("DPD" if eco < -0.05 else "Égal")
        st.markdown(kpi("Écart", f"{eco:+.2f}€ HT",
                        f"Gagnant : {gagnant}", 'green' if eco > 0 else 'red'), unsafe_allow_html=True)

    if pays_sim == 'IT':
        st.markdown('<div class="alert-red">⚠️ Italie : DPD Zone 3 — conserver GLS systématiquement</div>', unsafe_allow_html=True)
    elif poids_sim >= 4.5 and eco > 0:
        st.markdown(f'<div class="alert-green">✅ Soute ({poids_sim}kg) : DPD recommandé — économie de {eco:.2f}€/colis (hors NCY)</div>', unsafe_allow_html=True)

    # Tableau comparatif multi-poids
    st.markdown('<div class="section-title">Grille comparative complète — France</div>', unsafe_allow_html=True)
    rows_sim = []
    for kg in [1,2,3,4,5,6,7,8,9,10,12,15,20]:
        _, g = cout_gls(kg, 'FR', sgo_gls_sim)
        _, d = cout_dpd(kg, 'FR', sgo_dpd_sim)
        e = g - d
        ncy_info = "Oui (×33%)" if kg >= 4.5 else "Non"
        rows_sim.append({
            'Poids': f"{kg} kg",
            'GLS HT': f"{g:.2f}€",
            'DPD HT': f"{d:.2f}€",
            'Écart HT': f"{e:+.2f}€",
            'NCY applicable': ncy_info,
            'Gagnant pur': "GLS" if e > 0.05 else ("DPD" if e < -0.05 else "≈ Égal"),
        })
    st.dataframe(pd.DataFrame(rows_sim), use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — HISTORIQUE
# ════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown('<div class="section-title">📈 Historique SGO & Économies</div>', unsafe_allow_html=True)

    # Historique SGO
    hist_rows = []
    for (a, m), (gls_site, dpd_taux) in sorted(SGO_HISTORIQUE.items()):
        hist_rows.append({
            'Mois': f"{m:02d}/{a}",
            'GLS site (%)': f"{gls_site*100:.2f}%",
            'GLS net ADC (%)': f"{(gls_site-0.06)*100:.2f}%",
            'DPD routier (%)': f"{dpd_taux*100:.2f}%",
            'Écart net': f"{(gls_site-0.06-dpd_taux)*100:+.2f}pts",
        })
    st.dataframe(pd.DataFrame(hist_rows), use_container_width=True, hide_index=True)

    # Graph évolution SGO
    df_hist = pd.DataFrame(hist_rows)
    fig_sgo = go.Figure()
    fig_sgo.add_trace(go.Scatter(
        x=df_hist['Mois'],
        y=[float(r.replace('%','')) for r in df_hist['GLS net ADC (%)']],
        name='GLS net ADC', line=dict(color='#3b82f6', width=2), mode='lines+markers'
    ))
    fig_sgo.add_trace(go.Scatter(
        x=df_hist['Mois'],
        y=[float(r.replace('%','')) for r in df_hist['DPD routier (%)']],
        name='DPD routier', line=dict(color='#ef4444', width=2), mode='lines+markers'
    ))
    fig_sgo.update_layout(
        title='Évolution taux SGO GLS vs DPD',
        plot_bgcolor='#141720', paper_bgcolor='#141720',
        font_color='#F0F2F8', height=300,
        yaxis_title='Taux (%)',
    )
    st.plotly_chart(fig_sgo, use_container_width=True)

    # Économies cumulées si BCF chargés
    if len(st.session_state.mois_data) > 1:
        st.markdown('<div class="section-title">Économies cumulées par mois</div>', unsafe_allow_html=True)
        eco_cum = 0
        cum_rows = []
        for m in st.session_state.mois_data:
            eco_cum += m['economie_ttc']
            cum_rows.append({
                'Mois': m['label'],
                'Économie TTC': f"{m['economie_ttc']:+,.0f}€".replace(',', ' '),
                'Cumulé TTC': f"{eco_cum:+,.0f}€".replace(',', ' '),
                'NCY TTC': f"{m['total_ncy_ht']*1.2:,.0f}€".replace(',', ' '),
            })
        st.dataframe(pd.DataFrame(cum_rows), use_container_width=True, hide_index=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 6 — SCORE FINAL
# ════════════════════════════════════════════════════════════════════════════
with tab6:
    st.markdown('<div class="section-title">🏆 Score final & Recommandation</div>', unsafe_allow_html=True)

    if not st.session_state.mois_data:
        st.info("Importe des BCF pour générer le score.")
    else:
        tot_gls  = sum(m['total_gls_ht']  for m in st.session_state.mois_data)
        tot_dpd  = sum(m['total_dpd_ht']  for m in st.session_state.mois_data)
        eco_pct  = (tot_gls - tot_dpd) / tot_gls * 100 if tot_gls else 0
        ncy_pct  = sum(m['total_ncy_ht'] for m in st.session_state.mois_data) / tot_gls * 100 if tot_gls else 0

        # Scores (0-100, 100 = meilleur)
        score_cout_gls = max(0, 100 - eco_pct * 2)
        score_cout_dpd = min(100, 100 + (eco_pct - 10) * 2) if eco_pct > 0 else 50

        # Score facturation GLS (pénalisé par NCY)
        score_fact_gls = max(0, 100 - ncy_pct * 5)
        score_fact_dpd = 95  # pas de NCY

        # Score qualité : à renseigner manuellement (pas de données tracking)
        score_qual = st.slider("Score qualité DPD (données terrain)", 0, 100, 75,
                                help="Ajuste selon ton expérience réelle DPD")
        score_qual_gls = 80  # historique connu

        # Score global
        total_w = w_cout + w_qual + w_fact
        if total_w > 0:
            score_gls = (score_cout_gls*w_cout + score_qual_gls*w_qual + score_fact_gls*w_fact) / total_w
            score_dpd = (score_cout_dpd*w_cout + score_qual*w_qual + score_fact_dpd*w_fact) / total_w
        else:
            score_gls = score_dpd = 50

        col1, col2 = st.columns(2)
        def score_color(s):
            return '#22c55e' if s >= 70 else ('#E8B84B' if s >= 50 else '#ef4444')

        with col1:
            st.markdown(f"""
            <div style="background:#141720;border-radius:16px;padding:32px;text-align:center;border:1px solid #1e2235;">
                <span class="badge-gls">GLS</span>
                <div style="font-size:72px;font-weight:800;font-family:'DM Mono',monospace;color:{score_color(score_gls)};margin:16px 0;">
                    {score_gls:.0f}
                </div>
                <div style="font-size:13px;color:#5a6080;">Score / 100</div>
            </div>""", unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="background:#141720;border-radius:16px;padding:32px;text-align:center;border:1px solid #1e2235;">
                <span class="badge-dpd">DPD</span>
                <div style="font-size:72px;font-weight:800;font-family:'DM Mono',monospace;color:{score_color(score_dpd)};margin:16px 0;">
                    {score_dpd:.0f}
                </div>
                <div style="font-size:13px;color:#5a6080;">Score / 100</div>
            </div>""", unsafe_allow_html=True)

        # Radar
        categories = ['Coût', 'Qualité', 'Facturation']
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=[score_cout_gls, score_qual_gls, score_fact_gls, score_cout_gls],
            theta=categories + [categories[0]],
            fill='toself', name='GLS',
            line_color='#3b82f6', fillcolor='rgba(59,130,246,0.15)'
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=[score_cout_dpd, score_qual, score_fact_dpd, score_cout_dpd],
            theta=categories + [categories[0]],
            fill='toself', name='DPD',
            line_color='#ef4444', fillcolor='rgba(239,68,68,0.15)'
        ))
        fig_radar.update_layout(
            polar=dict(bgcolor='#141720', radialaxis=dict(range=[0,100], color='#3a4060')),
            plot_bgcolor='#141720', paper_bgcolor='#141720', font_color='#F0F2F8',
            showlegend=True, height=350
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        # Recommandation
        diff = score_dpd - score_gls
        eco_ttc_ann = sum(m['economie_ttc'] for m in st.session_state.mois_data) / len(st.session_state.mois_data) * 12

        if diff > 5:
            st.markdown(f"""<div class="alert-green">
                ✅ <strong>Recommandation : DPD</strong><br>
                Score supérieur de {diff:.0f} points. Économie projetée : <strong>{eco_ttc_ann:,.0f}€ TTC/an</strong>.
                Garder l'Italie chez GLS.
            </div>""".replace(',', ' '), unsafe_allow_html=True)
        elif diff < -5:
            st.markdown(f'<div class="alert-red">⚠️ <strong>GLS reste compétitif</strong> sur ce mois. Réévalue dans 1 mois.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="alert-gold">🔄 Scores proches. Continuer la phase de test.</div>', unsafe_allow_html=True)

        # Export Excel
        st.markdown("---")
        if st.button("📥 Exporter en Excel"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Synthèse
                df_synth = pd.DataFrame([{
                    'Mois': m['label'], 'Colis': m['nb_colis'],
                    'GLS HT': round(m['total_gls_ht'],2), 'DPD HT': round(m['total_dpd_ht'],2),
                    'Économie HT': round(m['economie_ht'],2), 'Économie TTC': round(m['economie_ttc'],2),
                    'NCY HT': round(m['total_ncy_ht'],2), 'NCY TTC': round(m['total_ncy_ht']*1.2,2),
                } for m in st.session_state.mois_data])
                df_synth.to_excel(writer, sheet_name='Synthèse', index=False)
                # Données colis
                for m in st.session_state.mois_data:
                    if 'df' in m and len(m['df']) > 0:
                        m['df'].to_excel(writer, sheet_name=m['label'][:31], index=False)
            st.download_button(
                "⬇️ Télécharger",
                data=output.getvalue(),
                file_name=f"ADC_transpo_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

# ════════════════════════════════════════════════════════════════════════════
# TAB 7 — CONTRÔLE FACTURATION
# ════════════════════════════════════════════════════════════════════════════
with tab7:
    st.markdown('<div class="section-title">🔍 Contrôle Facturation GLS</div>', unsafe_allow_html=True)
    st.markdown("Vérifie chaque ligne du BCF contre tes grilles contractuelles — détecte les erreurs de facturation.")

    ctrl_file = st.file_uploader("BCF GLS à contrôler (CSV)", type=['csv'], key='ctrl_bcf')

    if ctrl_file:
        with st.spinner("Analyse en cours..."):
            ctrl_stats, ctrl_err = controler_bcf_gls(ctrl_file)

        if ctrl_err:
            st.error(f"Erreur : {ctrl_err}")
        else:
            nb_a = ctrl_stats['nb_anomalies']
            surf = ctrl_stats['montant_surcharge_injustifiee']
            sous = ctrl_stats['montant_sous_facture']

            # KPIs
            c1, c2, c3, c4 = st.columns(4)
            style_a = 'red' if nb_a > 0 else 'green'
            with c1: st.markdown(kpi("Colis analysés", f"{ctrl_stats['nb_colis']:,}".replace(',', ' '), f"{ctrl_stats['nb_lignes']} lignes"), unsafe_allow_html=True)
            with c2: st.markdown(kpi("Anomalies détectées", str(nb_a), "lignes en écart", style_a), unsafe_allow_html=True)
            with c3: st.markdown(kpi("Surfacturation HT", f"{surf:,.2f}€".replace(',', ' '), "à réclamer à GLS", 'red' if surf > 0 else 'green'), unsafe_allow_html=True)
            with c4: st.markdown(kpi("Sous-facturation HT", f"{sous:,.2f}€".replace(',', ' '), "en ta faveur", 'gold'), unsafe_allow_html=True)

            if nb_a == 0:
                st.markdown('<div class="alert-green">✅ Aucune anomalie détectée — la facturation GLS semble correcte sur ce BCF.</div>', unsafe_allow_html=True)
            else:
                # Résumé par type
                st.markdown('<div class="section-title">Anomalies par type</div>', unsafe_allow_html=True)
                type_rows = []
                for t, nb in sorted(ctrl_stats['par_type'].items(), key=lambda x: -abs(ctrl_stats['par_type_montant'][x[0]])):
                    montant = ctrl_stats['par_type_montant'][t]
                    type_rows.append({
                        'Type anomalie': t,
                        'Nb cas': nb,
                        'Impact HT total': f"{montant:+,.2f}€".replace(',', ' '),
                        'Impact TTC': f"{montant*1.2:+,.2f}€".replace(',', ' '),
                        'Action': '⚡ Réclamer' if montant > 0 else '✅ En ta faveur',
                    })
                st.dataframe(pd.DataFrame(type_rows), use_container_width=True, hide_index=True)

                # Tableau détaillé
                st.markdown('<div class="section-title">Détail des anomalies</div>', unsafe_allow_html=True)

                # Filtres
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    types_dispo = ['Tous'] + list(ctrl_stats['par_type'].keys())
                    filtre_type = st.selectbox("Filtrer par type", types_dispo)
                with col_f2:
                    filtre_gravite = st.selectbox("Filtrer par gravité", ['Toutes', '🔴 Élevée', '🟡 Faible'])

                df_a = ctrl_stats['anomalies_df'].copy()
                if filtre_type != 'Tous':
                    df_a = df_a[df_a['Type'] == filtre_type]
                if filtre_gravite != 'Toutes':
                    df_a = df_a[df_a['Gravité'] == filtre_gravite]

                st.dataframe(df_a, use_container_width=True, hide_index=True)

                # Export anomalies
                if len(df_a) > 0:
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df_a.to_excel(writer, sheet_name='Anomalies', index=False)
                        pd.DataFrame(type_rows).to_excel(writer, sheet_name='Résumé', index=False)
                    st.download_button(
                        "📥 Exporter les anomalies Excel",
                        data=output.getvalue(),
                        file_name=f"GLS_anomalies_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                    if surf > 10:
                        st.markdown(f'<div class="alert-red">⚠️ <strong>{surf:,.2f}€ HT ({surf*1.2:,.2f}€ TTC) de surfacturation détectée</strong> — prépare un dossier de réclamation GLS.</div>'.replace(',', ' '), unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:#141720;border-radius:12px;padding:24px;border:1px solid #1e2235;margin-top:16px;">
            <div style="font-size:14px;font-weight:700;color:#F0F2F8;margin-bottom:12px;">Ce module vérifie :</div>
            <div style="font-size:13px;color:#5a6080;line-height:2;">
                🔴 <b>Barème poids incorrect</b> — tarif facturé ≠ grille contractuelle<br>
                🔴 <b>CSR incorrect</b> — doit être exactement 0,71€/colis<br>
                🔴 <b>SGO incorrect</b> — vérifié contre l'historique mensuel<br>
                🔴 <b>NCY injustifiée</b> — appliquée sur un colis < 4,5 kg<br>
                🔴 <b>Double NCY</b> — deux surcharges NCY sur le même colis<br>
                🟡 <b>PER incorrect</b> — doit être 1,5% sur (barème + CSR)
            </div>
        </div>
        """, unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR — CONFIG CONTRACTUELLE DPD + IMPORT BCF DPD
# ════════════════════════════════════════════════════════════════════════════
# (Ajout dans la sidebar existante via st.sidebar context)

from utils.parser_dpd import parse_bcf_dpd

if 'dpd_data' not in st.session_state:
    st.session_state.dpd_data = []

if 'dpd_config' not in st.session_state:
    st.session_state.dpd_config = {
        'has_zebra': True,
        'volumetrique_barre': True,
        'predict_actif': True,
        'cout_avis': 1.0,
    }

# ════════════════════════════════════════════════════════════════════════════
# TAB 8 — BCF DPD + CONTRÔLE CONTRACTUEL
# ════════════════════════════════════════════════════════════════════════════
with st.expander("📋 Configuration contrat DPD", expanded=False):
    st.markdown("**Mon équipement & options :**")
    cfg = st.session_state.dpd_config
    cfg['has_zebra']          = st.checkbox("✅ J'ai ma propre imprimante Zebra (→ alerte si 60€/mois facturé)", value=cfg['has_zebra'])
    cfg['volumetrique_barre'] = st.checkbox("✅ Poids volumétrique barré dans mon contrat", value=cfg['volumetrique_barre'])
    cfg['predict_actif']      = st.checkbox("✅ Je transmets tél + email systématiquement (Predict)", value=cfg['predict_actif'])
    cfg['cout_avis']          = st.number_input("Tarif avisé négocié (€/colis)", value=cfg['cout_avis'], step=0.5, min_value=0.5, max_value=4.0)
    st.markdown(f"<small>Tarif catalogue DPD = 4€ / Tarif observé client valises = 1€</small>", unsafe_allow_html=True)

st.markdown("### 📦 Importer un BCF DPD")
dpd_label  = st.text_input("Label mois DPD", value="Juillet 2026", key='dpd_label')
dpd_file   = st.file_uploader("BCF DPD (Excel .xlsx)", type=['xlsx','xls'], key='dpd_file')

if st.button("➕ Analyser BCF DPD", type="secondary", use_container_width=True):
    if dpd_file:
        with st.spinner(f"Analyse DPD {dpd_label}..."):
            dpd_stats, dpd_err = parse_bcf_dpd(
                dpd_file,
                config=st.session_state.dpd_config,
                sgo_dpd_manuel=sgo_dpd_input/100,
            )
            if dpd_err:
                st.error(f"Erreur : {dpd_err}")
            else:
                dpd_stats['label'] = dpd_label
                st.session_state.dpd_data = [d for d in st.session_state.dpd_data if d['label'] != dpd_label]
                st.session_state.dpd_data.append(dpd_stats)
                st.success(f"✅ {dpd_label} — {dpd_stats['nb_colis']} colis DPD analysés")
                # Afficher alertes immédiatement
                for alerte in dpd_stats.get('alertes', []):
                    if '🔴' in alerte:
                        st.error(alerte)
                    elif '⚠️' in alerte or '🟡' in alerte:
                        st.warning(alerte)
                    else:
                        st.info(alerte)
    else:
        st.warning("Sélectionne un fichier BCF DPD")

if st.session_state.dpd_data:
    st.markdown("**BCF DPD chargés :**")
    for d in st.session_state.dpd_data:
        eco = d.get('economie_vs_gls_ttc', 0)
        st.markdown(f"<small>🔴 {d['label']} ({d['nb_colis']} colis) — vs GLS : {eco:+,.0f}€ TTC</small>".replace(',', ' '), unsafe_allow_html=True)

# Section DPD dans la synthèse (si données DPD dispo)
if st.session_state.dpd_data and tab1:
    with tab1:
        st.markdown('<div class="section-title">📦 Analyse BCF DPD réels</div>', unsafe_allow_html=True)

        for dpd_s in st.session_state.dpd_data:
            st.markdown(f"**{dpd_s['label']}** — {dpd_s['nb_colis']} colis")

            c1,c2,c3,c4,c5 = st.columns(5)
            with c1: st.markdown(kpi("Facture DPD HT", fmt_eur(dpd_s['total_facture_ht']), "réel"), unsafe_allow_html=True)
            with c2: st.markdown(kpi("Facture DPD TTC", fmt_eur(dpd_s['total_facture_ttc'],True), ""), unsafe_allow_html=True)
            with c3: st.markdown(kpi("GLS théorique HT", fmt_eur(dpd_s['gls_theorique_ht']), "simulation"), unsafe_allow_html=True)
            with c4:
                eco = dpd_s['economie_vs_gls_ttc']
                style = 'green' if eco > 0 else 'red'
                st.markdown(kpi("Économie vs GLS TTC", fmt_eur(eco,True), "", style), unsafe_allow_html=True)
            with c5:
                st.markdown(kpi("Taux avisés", f"{dpd_s['taux_avis_pct']:.1f}%",
                               "cible < 5%", 'green' if dpd_s['taux_avis_pct'] < 5 else 'red'), unsafe_allow_html=True)

            # Alertes
            for alerte in dpd_s.get('alertes', []):
                if '🔴' in alerte:
                    st.markdown(f'<div class="alert-red">{alerte}</div>', unsafe_allow_html=True)
                elif '⚠️' in alerte or '🟡' in alerte:
                    st.markdown(f'<div class="alert-gold">{alerte}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="alert-green">{alerte}</div>', unsafe_allow_html=True)

            # Anomalies
            if len(dpd_s.get('anomalies_df', pd.DataFrame())) > 0:
                st.dataframe(dpd_s['anomalies_df'], use_container_width=True, hide_index=True)
