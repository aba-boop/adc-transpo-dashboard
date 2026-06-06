"""
Module d'alertes email — ADC Transpo Dashboard
Utilise Resend API pour envoyer les rapports mensuels
"""
import streamlit as st
from datetime import datetime

def send_monthly_report(stats_list, email_to="aba@alleeducommerce.com"):
    """
    Envoie un rapport mensuel par email après import de BCF.
    stats_list : liste des stats GLS des mois importés
    """
    try:
        import resend
        api_key = st.secrets.get("RESEND_API_KEY", "")
        if not api_key:
            return False, "Clé RESEND_API_KEY non configurée dans les secrets Streamlit"

        resend.api_key = api_key

        # Calculs globaux
        nb_mois = len(stats_list)
        tot_colis = sum(m['nb_colis'] for m in stats_list)
        tot_gls_ttc = sum(m['total_gls_ttc'] for m in stats_list)
        tot_dpd_ttc = sum(m['total_dpd_ttc'] for m in stats_list)
        tot_eco_ttc = sum(m['economie_ttc'] for m in stats_list)
        tot_ncy_ttc = sum(m['total_ncy_ht'] * 1.2 for m in stats_list)
        eco_pct = tot_eco_ttc / tot_gls_ttc * 100 if tot_gls_ttc else 0
        proj_an = tot_eco_ttc / nb_mois * 12 if nb_mois else 0

        # Couleur économie
        eco_color = "#22c55e" if tot_eco_ttc > 0 else "#ef4444"
        signe = "+" if tot_eco_ttc > 0 else ""

        # Tableau des mois
        mois_rows = ""
        for m in stats_list:
            eco_m = m['economie_ttc']
            color = "#22c55e" if eco_m > 0 else "#ef4444"
            mois_rows += f"""
            <tr>
                <td style="padding:10px 16px;border-bottom:1px solid #1e2235;color:#F0F2F8;font-weight:600;">{m['label']}</td>
                <td style="padding:10px 16px;border-bottom:1px solid #1e2235;color:#93b4fd;font-family:monospace;">{m['nb_colis']:,}".replace(',', ' ')</td>
                <td style="padding:10px 16px;border-bottom:1px solid #1e2235;color:#F0F2F8;font-family:monospace;">{m['total_gls_ttc']:,.0f}€".replace(',', ' ')</td>
                <td style="padding:10px 16px;border-bottom:1px solid #1e2235;color:#fca5a5;font-family:monospace;">{m['total_dpd_ttc']:,.0f}€".replace(',', ' ')</td>
                <td style="padding:10px 16px;border-bottom:1px solid #1e2235;color:{color};font-family:monospace;font-weight:700;">{eco_m:+,.0f}€ TTC".replace(',', ' ')</td>
                <td style="padding:10px 16px;border-bottom:1px solid #1e2235;color:#ef4444;font-family:monospace;">{m['total_ncy_ht']*1.2:,.0f}€".replace(',', ' ')</td>
            </tr>"""

        html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#07090f;font-family:'Helvetica Neue',Arial,sans-serif;">
<div style="max-width:680px;margin:0 auto;padding:32px 16px;">

    <!-- Header -->
    <div style="text-align:center;padding:40px 0 32px;">
        <div style="font-size:40px;margin-bottom:12px;">🚚</div>
        <div style="font-size:22px;font-weight:800;color:#F0F2F8;margin-bottom:4px;">Transpo Dashboard</div>
        <div style="font-size:13px;color:#5a6080;">Allée du Commerce — Rapport du {datetime.now().strftime('%d/%m/%Y à %Hh%M')}</div>
    </div>

    <!-- Big number -->
    <div style="background:linear-gradient(135deg,#0a0c14,#0f1120);border:1px solid #1e2235;border-radius:16px;padding:32px;text-align:center;margin-bottom:24px;">
        <div style="font-size:11px;color:#4a5070;text-transform:uppercase;letter-spacing:.12em;margin-bottom:12px;">Économie cumulée GLS → DPD ({nb_mois} mois · {tot_colis:,} colis)".replace(',', ' ')</div>
        <div style="font-size:52px;font-weight:800;color:{eco_color};font-family:monospace;line-height:1;">{signe}{tot_eco_ttc:,.0f}€ TTC".replace(',', ' ')</div>
        <div style="font-size:13px;color:#5a6080;margin-top:12px;">Projection 12 mois : <span style="color:#E8B84B;font-weight:700;">{proj_an:,.0f}€ TTC/an</span>".replace(',', ' ')</div>
    </div>

    <!-- KPIs -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:24px;">
        <div style="background:#0f1120;border:1px solid #1e2235;border-radius:12px;padding:20px;border-top:2px solid #3b82f6;">
            <div style="font-size:10px;color:#4a5070;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;">GLS facturé TTC</div>
            <div style="font-size:24px;font-weight:800;color:#F0F2F8;font-family:monospace;">{tot_gls_ttc:,.0f}€".replace(',', ' ')</div>
        </div>
        <div style="background:#0f1120;border:1px solid #1e2235;border-radius:12px;padding:20px;border-top:2px solid #ef4444;">
            <div style="font-size:10px;color:#4a5070;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;">DPD simulé TTC</div>
            <div style="font-size:24px;font-weight:800;color:#F0F2F8;font-family:monospace;">{tot_dpd_ttc:,.0f}€".replace(',', ' ')</div>
        </div>
        <div style="background:#0f1120;border:1px solid #1e2235;border-radius:12px;padding:20px;border-top:2px solid #ef4444;">
            <div style="font-size:10px;color:#4a5070;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;">NCY GLS TTC</div>
            <div style="font-size:24px;font-weight:800;color:#fca5a5;font-family:monospace;">{tot_ncy_ttc:,.0f}€".replace(',', ' ')</div>
            <div style="font-size:11px;color:#5a6070;margin-top:4px;">{tot_ncy_ttc/tot_gls_ttc*100:.1f}% de la facture GLS</div>
        </div>
        <div style="background:#0f1120;border:1px solid #1e2235;border-radius:12px;padding:20px;border-top:2px solid #22c55e;">
            <div style="font-size:10px;color:#4a5070;text-transform:uppercase;letter-spacing:.1em;margin-bottom:8px;">Économie / colis</div>
            <div style="font-size:24px;font-weight:800;color:#86efac;font-family:monospace;">{tot_eco_ttc/tot_colis:.2f}€ TTC</div>
            <div style="font-size:11px;color:#5a6070;margin-top:4px;">{eco_pct:.1f}% d'économie</div>
        </div>
    </div>

    <!-- Tableau détaillé -->
    <div style="background:#0f1120;border:1px solid #1e2235;border-radius:12px;overflow:hidden;margin-bottom:24px;">
        <div style="padding:16px 20px;border-bottom:1px solid #1e2235;font-size:13px;font-weight:700;color:#F0F2F8;">
            📊 Détail par mois
        </div>
        <table style="width:100%;border-collapse:collapse;">
            <thead>
                <tr style="background:#07090f;">
                    <th style="padding:10px 16px;text-align:left;font-size:10px;color:#4a5070;text-transform:uppercase;letter-spacing:.08em;">Mois</th>
                    <th style="padding:10px 16px;text-align:left;font-size:10px;color:#4a5070;text-transform:uppercase;">Colis</th>
                    <th style="padding:10px 16px;text-align:left;font-size:10px;color:#4a5070;text-transform:uppercase;">GLS TTC</th>
                    <th style="padding:10px 16px;text-align:left;font-size:10px;color:#4a5070;text-transform:uppercase;">DPD TTC</th>
                    <th style="padding:10px 16px;text-align:left;font-size:10px;color:#4a5070;text-transform:uppercase;">Économie</th>
                    <th style="padding:10px 16px;text-align:left;font-size:10px;color:#4a5070;text-transform:uppercase;">NCY TTC</th>
                </tr>
            </thead>
            <tbody>{mois_rows}</tbody>
        </table>
    </div>

    <!-- Footer -->
    <div style="text-align:center;padding:24px 0;color:#3a4060;font-size:12px;">
        ADC Transpo Dashboard · Allée du Commerce Marseille 13015<br>
        <a href="https://adctransport.streamlit.app" style="color:#E8B84B;text-decoration:none;">Ouvrir le dashboard</a>
    </div>

</div>
</body>
</html>"""

        params = {
            "from": "ADC Transpo <onboarding@resend.dev>",
            "to": [email_to],
            "subject": f"🚚 ADC Transport — Rapport {nb_mois} mois ({signe}{tot_eco_ttc:,.0f}€ TTC)".replace(',', ' '),
            "html": html,
        }

        email = resend.Emails.send(params)
        return True, f"Email envoyé à {email_to}"

    except Exception as e:
        return False, str(e)


def send_anomaly_alert(anomalies_df, mois_label, email_to="aba@alleeducommerce.com"):
    """
    Envoie une alerte si des anomalies GLS sont détectées lors du contrôle.
    """
    try:
        import resend
        api_key = st.secrets.get("RESEND_API_KEY", "")
        if not api_key:
            return False, "RESEND_API_KEY manquante"

        resend.api_key = api_key
        nb = len(anomalies_df)

        rows = ""
        for _, row in anomalies_df.head(20).iterrows():
            rows += f"""<tr>
                <td style="padding:8px 12px;border-bottom:1px solid #1e2235;color:#fca5a5;">{row.get('Type','')}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #1e2235;color:#F0F2F8;font-family:monospace;">{row.get('Colis','')}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #1e2235;color:#F0F2F8;">{row.get('Poids','')}</td>
                <td style="padding:8px 12px;border-bottom:1px solid #1e2235;color:#fca5a5;font-weight:700;">{row.get('Écart','')}</td>
            </tr>"""

        html = f"""
<!DOCTYPE html><html><body style="background:#07090f;font-family:Arial,sans-serif;">
<div style="max-width:640px;margin:0 auto;padding:32px 16px;">
    <div style="text-align:center;padding:32px 0;">
        <div style="font-size:36px;">⚠️</div>
        <div style="font-size:20px;font-weight:800;color:#F0F2F8;margin-top:8px;">Anomalies GLS détectées</div>
        <div style="font-size:13px;color:#5a6080;margin-top:4px;">{mois_label} — {nb} anomalie(s)</div>
    </div>
    <div style="background:#1a0000;border:1px solid #ef444440;border-left:3px solid #ef4444;border-radius:10px;padding:16px;margin-bottom:24px;">
        <div style="color:#fca5a5;font-weight:700;">{nb} anomalie(s) détectée(s) sur le BCF GLS {mois_label}</div>
        <div style="color:#5a6080;font-size:12px;margin-top:4px;">Vérifiez votre facturation GLS et réclamez si nécessaire.</div>
    </div>
    <table style="width:100%;border-collapse:collapse;background:#0f1120;border-radius:12px;overflow:hidden;">
        <thead><tr style="background:#07090f;">
            <th style="padding:10px 12px;text-align:left;font-size:10px;color:#4a5070;text-transform:uppercase;">Type</th>
            <th style="padding:10px 12px;text-align:left;font-size:10px;color:#4a5070;text-transform:uppercase;">Colis</th>
            <th style="padding:10px 12px;text-align:left;font-size:10px;color:#4a5070;text-transform:uppercase;">Poids</th>
            <th style="padding:10px 12px;text-align:left;font-size:10px;color:#4a5070;text-transform:uppercase;">Écart</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table>
    <div style="text-align:center;padding:24px 0;font-size:12px;color:#3a4060;">
        <a href="https://adctransport.streamlit.app" style="color:#E8B84B;">Ouvrir le dashboard</a>
    </div>
</div></body></html>"""

        params = {
            "from": "ADC Transpo <onboarding@resend.dev>",
            "to": [email_to],
            "subject": f"⚠️ {nb} anomalie(s) GLS détectée(s) — {mois_label}",
            "html": html,
        }
        resend.Emails.send(params)
        return True, f"Alerte envoyée à {email_to}"
    except Exception as e:
        return False, str(e)
