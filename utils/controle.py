import pandas as pd
from collections import defaultdict
from utils.tarifs import GLS_FR,GLS_EU,GLS_RELAIS,PAYS_ZONE_GLS,GLS_CSR,GLS_PER,SGO_HISTORIQUE,GLS_REMISE_SGO,SURCHARGES_NCY

def to_f(s):
    try: return float(str(s).replace(',','.').strip())
    except: return 0.0

def get_sgo_net_for_date(d):
    try:
        p=str(d).strip().split('.')
        if len(p)==3:
            k=(int(p[2]),int(p[1]))
            if k in SGO_HISTORIQUE:
                return SGO_HISTORIQUE[k][0]-GLS_REMISE_SGO
    except: pass
    return None

def bareme_gls_theorique(poids,pays,art):
    if pays=='FR':
        g=GLS_RELAIS if('SHD'in art or'SRS'in art)else GLS_FR
    else:
        g=GLS_EU.get(PAYS_ZONE_GLS.get(pays,'D13'),GLS_EU['D13'])
    for k in sorted(g.keys()):
        if poids<=k: return g[k]
    return g[max(g.keys())]+(poids-max(g.keys()))*3.38

def controler_bcf_gls(file_obj):
    try:
        c=file_obj.read()
        try: t=c.decode('utf-8')
        except: t=c.decode('latin-1')
        from io import StringIO
        df=pd.read_csv(StringIO(t),sep=';',dtype=str,on_bad_lines='skip')
    except Exception as e: return None,str(e)
    anomalies=[]
    stats={'nb_lignes':len(df),'nb_colis':0,'nb_anomalies':0,'montant_surcharge_injustifiee':0.0,'montant_sous_facture':0.0,'par_type':defaultdict(int),'par_type_montant':defaultdict(float)}
    cp={};cpa={};cd={}
    for _,r in df.iterrows():
        col=str(r.get('Numéro de colis','')).strip()
        p=to_f(r.get('Poids pour le traitement commande vente',''))
        pa=str(r.get('Code Pays','FR')).strip()or'FR'
        da=str(r.get('Date jour','')).strip()
        if col and col!='nan':
            if p>cp.get(col,0): cp[col]=p
            if pa not in('FR','','nan'): cpa[col]=pa
            if da and da!='nan': cd[col]=da
    cu=set()
    for _,r in df.iterrows():
        col=str(r.get('Numéro de colis','')).strip()
        art=str(r.get('Article','')).strip()
        pays=cpa.get(col,str(r.get('Code Pays','FR')).strip()or'FR')
        poids=cp.get(col,to_f(r.get('Poids pour le traitement commande vente','')))
        date=cd.get(col,str(r.get('Date jour','')).strip())
        vb=to_f(r.get('Valeur de Base',''))
        cf=to_f(r.get('CSR',''))
        pf=to_f(r.get('PER',''))
        sf=to_f(r.get('SGO',''))
        dest=str(r.get('adresse de destination NOM','')).strip()
        vil=str(r.get('adresse de destination VILLE','')).strip()
        if not col or col=='nan': continue
        if art.startswith('PARCEL_') and poids>0 and vb>0:
            bt=bareme_gls_theorique(poids,pays,art)
            e=vb-bt
            if abs(e)>0.10:
                t='Barème surfacturé'if e>0 else'Barème sous-facturé'
                anomalies.append({'Type':t,'Colis':col,'Article':art,'Poids':f"{poids:.2f}kg",'Pays':pays,'Date':date,'Facturé':f"{vb:.4f}€",'Théorique':f"{bt:.4f}€",'Écart':f"{e:+.4f}€",'Destinataire':f"{dest}-{vil}",'Gravité':'🔴 Élevée'if abs(e)>0.50 else'🟡 Faible'})
                stats['par_type'][t]+=1;stats['par_type_montant'][t]+=e
                if e>0: stats['montant_surcharge_injustifiee']+=e
                else: stats['montant_sous_facture']+=abs(e)
        if art.startswith('PARCEL_') and cf>0:
            e=cf-GLS_CSR
            if abs(e)>0.01:
                anomalies.append({'Type':'CSR incorrect','Colis':col,'Article':art,'Poids':f"{poids:.2f}kg",'Pays':pays,'Date':date,'Facturé':f"{cf:.4f}€",'Théorique':f"{GLS_CSR:.4f}€",'Écart':f"{e:+.4f}€",'Destinataire':f"{dest}-{vil}",'Gravité':'🔴 Élevée'})
                stats['par_type']['CSR incorrect']+=1;stats['montant_surcharge_injustifiee']+=max(0,e)
        if art.startswith('PARCEL_') and pf>0 and vb>0:
            pt=(vb+GLS_CSR)*GLS_PER;e=pf-pt
            if abs(e)>0.02:
                anomalies.append({'Type':'PER incorrect','Colis':col,'Article':art,'Poids':f"{poids:.2f}kg",'Pays':pays,'Date':date,'Facturé':f"{pf:.4f}€",'Théorique':f"{pt:.4f}€",'Écart':f"{e:+.4f}€",'Destinataire':f"{dest}-{vil}",'Gravité':'🟡 Faible'})
                stats['par_type']['PER incorrect']+=1
        if art.startswith('PARCEL_') and sf>0 and vb>0:
            sn=get_sgo_net_for_date(date)
            if sn:
                st2=(vb+GLS_CSR)*sn;e=sf-st2
                if abs(e)>0.05:
                    anomalies.append({'Type':'SGO incorrect','Colis':col,'Article':art,'Poids':f"{poids:.2f}kg",'Pays':pays,'Date':date,'Facturé':f"{sf:.4f}€",'Théorique':f"{st2:.4f}€",'Écart':f"{e:+.4f}€",'Destinataire':f"{dest}-{vil}",'Gravité':'🔴 Élevée'if abs(e)>0.20 else'🟡 Faible'})
                    stats['par_type']['SGO incorrect']+=1
        if art in SURCHARGES_NCY and poids>0 and poids<4.5:
            mn=to_f(r.get('Valeur de Base',''))+to_f(r.get('SGO',''))+to_f(r.get('PER',''))
            anomalies.append({'Type':'NCY injustifiée (<4.5kg)','Colis':col,'Article':art,'Poids':f"{poids:.2f}kg",'Pays':pays,'Date':date,'Facturé':f"{mn:.4f}€",'Théorique':"0.00€",'Écart':f"+{mn:.4f}€",'Destinataire':f"{dest}-{vil}",'Gravité':'🔴 Élevée'})
            stats['par_type']['NCY injustifiée (<4.5kg)']+=1;stats['montant_surcharge_injustifiee']+=mn
        if art in SURCHARGES_NCY:
            k=f"NCY_{col}"
            if k in cu:
                mn=to_f(r.get('Valeur de Base',''))+to_f(r.get('SGO',''))
                anomalies.append({'Type':'Double NCY','Colis':col,'Article':art,'Poids':f"{poids:.2f}kg",'Pays':pays,'Date':date,'Facturé':f"{mn:.4f}€",'Théorique':"0€ déjà facturé",'Écart':f"+{mn:.4f}€",'Destinataire':f"{dest}-{vil}",'Gravité':'🔴 Élevée'})
                stats['par_type']['Double NCY']+=1;stats['montant_surcharge_injustifiee']+=mn
            cu.add(k)
        if art.startswith('PARCEL_') and col not in cu:
            cu.add(col);stats['nb_colis']+=1
    stats['nb_anomalies']=len(anomalies)
    stats['anomalies_df']=pd.DataFrame(anomalies)if anomalies else pd.DataFrame()
    return stats,None
