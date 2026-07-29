import streamlit as st
import datetime
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from supabase import create_client, Client

# ==========================================
# 1. CONFIGURATION DE LA PAGE & SUPABASE
# ==========================================
st.set_page_config(
    page_title="Performance & Load Engine", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="expanded"
)
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# Initialisation des variables de session
if "user" not in st.session_state:
    st.session_state.user = None
if "athlete_info" not in st.session_state:
    st.session_state.athlete_info = None

# ==========================================
# 2. INJECTION DE STYLE CSS PROPRE & SANS CONFLIT
# ==========================================
st.markdown("""
<style>
    /* Cartes Métriques / KPI */
    .kpi-card {
        background: linear-gradient(135deg, #1e2638 0%, #111827 100%);
        border: 1px solid #2d3748;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        margin-bottom: 15px;
    }
    .kpi-title {
        color: #94a3b8;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .kpi-value {
        color: #ffffff;
        font-size: 1.8rem;
        font-weight: 700;
        margin-top: 4px;
    }
    .kpi-sub {
        font-size: 0.8rem;
        margin-top: 4px;
    }

    /* Badges de Statut */
    .badge-success { background-color: #10b98122; color: #34d399; border: 1px solid #10b981; padding: 3px 8px; border-radius: 6px; font-weight: bold; }
    .badge-warning { background-color: #f59e0b22; color: #fbbf24; border: 1px solid #fbbf24; padding: 3px 8px; border-radius: 6px; font-weight: bold; }
    .badge-danger { background-color: #ef444422; color: #f87171; border: 1px solid #ef4444; padding: 3px 8px; border-radius: 6px; font-weight: bold; }
    .badge-info { background-color: #3b82f622; color: #60a5fa; border: 1px solid #3b82f6; padding: 3px 8px; border-radius: 6px; font-weight: bold; }

    /* Customisation légère des Onglets */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0px 0px;
        padding: 8px 16px;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 3. COMPOSANTS VISUELS AVANCÉS
# ==========================================
def render_kpi_card(title, value, subtext="", badge_type="info"):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">{title}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub"><span class="badge-{badge_type}">{subtext}</span></div>
    </div>
    """, unsafe_allow_html=True)

def mef_jauge_acwr(valeur_acwr):
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = valeur_acwr,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "Ratio ACWR", 'font': {'size': 18, 'color': "white"}},
        number = {'font': {'size': 36, 'color': "white"}},
        gauge = {
            'axis': {'range': [0, 2.2], 'tickwidth': 1, 'tickcolor': "white"},
            'bar': {'color': "#ffffff", 'thickness': 0.15},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 0,
            'steps': [
                {'range': [0, 0.8], 'color': 'rgba(241, 196, 15, 0.6)'},
                {'range': [0.8, 1.3], 'color': 'rgba(46, 204, 113, 0.7)'},
                {'range': [1.3, 1.5], 'color': 'rgba(230, 126, 34, 0.7)'},
                {'range': [1.5, 2.2], 'color': 'rgba(231, 76, 60, 0.8)'}
            ],
        }
    ))
    fig.update_layout(
        height=220, 
        margin=dict(l=20, r=20, t=30, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig

# ==========================================
# 4. MOTEURS DE CALCUL
# ==========================================
def calculer_triple_charge(duree_min, rpe, sport, terrain, batterie):
    charge_globale = duree_min * rpe
    
    facteurs_sport = {
        "Course à pied": 1.0, "Trail": 1.2, "Cyclisme": 0.4, 
        "Natation": 4.0, "Renforcement": 0.5, "Autre": 0.8
    }
    coef_sport = facteurs_sport.get(sport, 1.0)
    km_eq = round((duree_min / 60.0) * (rpe * 2.5) * coef_sport, 1)

    facteurs_terrain = {
        "Piste / Bitume": 1.0, "Chemin / Sous-bois": 1.1,
        "Montagne / Dérivé Trail": 1.3, "Sable / Boue": 1.4, "Salle / Tapis": 0.9
    }
    coef_terrain = facteurs_terrain.get(terrain, 1.0)

    ratio_nerveux = 0.8 + (rpe / 10.0) * 0.5
    ratio_meca = coef_terrain * (1.2 if sport in ["Course à pied", "Trail"] else 0.6)
    facteur_batterie = 1.0 + ((5 - batterie) * 0.05)

    charge_meta = round(charge_globale * facteur_batterie, 1)
    charge_nerveuse = round(charge_globale * ratio_nerveux * facteur_batterie, 1)
    charge_meca = round(charge_globale * ratio_meca * facteur_batterie, 1)

    return charge_globale, km_eq, charge_meta, charge_nerveuse, charge_meca

def calculer_acwr(df_seances):
    if df_seances.empty:
        return df_seances

    df_seances['date_seance'] = pd.to_datetime(df_seances['date_seance'])
    
    for col in ['charge_meta', 'charge_nerveuse', 'charge_meca']:
        if col not in df_seances.columns:
            df_seances[col] = df_seances['duree_min'] * df_seances['rpe']

    if 'charge_seance' not in df_seances.columns:
        df_seances['charge_seance'] = df_seances['duree_min'] * df_seances['rpe']

    min_date = df_seances['date_seance'].min()
    max_date = max(df_seances['date_seance'].max(), pd.to_datetime(datetime.date.today()))
    idx_dates = pd.date_range(min_date, max_date)

    df_daily = df_seances.groupby('date_seance').agg({
        'charge_seance': 'sum',
        'charge_meta': 'sum',
        'charge_nerveuse': 'sum',
        'charge_meca': 'sum'
    }).reindex(idx_dates, fill_value=0).reset_index()
    
    df_daily.rename(columns={'index': 'date_seance', 'charge_seance': 'charge_du_jour'}, inplace=True)

    df_daily['charge_aigue_7d'] = df_daily['charge_du_jour'].rolling(window=7, min_periods=1).mean()
    df_daily['charge_chronique_28d'] = df_daily['charge_du_jour'].rolling(window=28, min_periods=1).mean()

    df_daily['acwr'] = np.where(
        df_daily['charge_chronique_28d'] > 0,
        df_daily['charge_aigue_7d'] / df_daily['charge_chronique_28d'],
        0
    )
    df_daily['acwr'] = df_daily['acwr'].round(2)

    df_daily['charge_hebdo'] = df_daily['charge_du_jour'].rolling(window=7, min_periods=1).sum()
    df_daily['charge_hebdo_prec'] = df_daily['charge_hebdo'].shift(7)
    df_daily['spike_pct'] = np.where(
        df_daily['charge_hebdo_prec'] > 0,
        ((df_daily['charge_hebdo'] - df_daily['charge_hebdo_prec']) / df_daily['charge_hebdo_prec']) * 100,
        0
    )

    for col in ['meta', 'nerveuse', 'meca']:
        c_name = f'charge_{col}'
        if c_name in df_daily.columns:
            df_daily[f'ATL_{col}'] = df_daily[c_name].rolling(window=7, min_periods=1).mean()
            df_daily[f'CTL_{col}'] = df_daily[c_name].rolling(window=28, min_periods=1).mean()

    df_daily['CTLm'] = df_daily.get('CTL_meta', 0)
    df_daily['CTLN'] = df_daily.get('CTL_nerveuse', 0)
    df_daily['CTLM'] = df_daily.get('CTL_meca', 0)

    roll_mean_7d = df_daily['charge_du_jour'].rolling(7, min_periods=1).mean()
    roll_std_7d = df_daily['charge_du_jour'].rolling(7, min_periods=1).std().fillna(1.0)
    roll_std_7d = np.where(roll_std_7d == 0, 1.0, roll_std_7d)

    df_daily['monotonie'] = (roll_mean_7d / roll_std_7d).round(2)
    df_daily['strain'] = (df_daily['charge_hebdo'] * df_daily['monotonie']).round(1)
    df_daily['strain_div_16'] = (df_daily['strain'] / 1.6).round(1)

    for col, code in [('meta', 'm'), ('nerveuse', 'N'), ('meca', 'M')]:
        c_name = f'charge_{col}'
        if c_name in df_daily.columns:
            m_axe = df_daily[c_name].rolling(7, min_periods=1).mean()
            s_axe = df_daily[c_name].rolling(7, min_periods=1).std().fillna(1.0)
            s_axe = np.where(s_axe == 0, 1.0, s_axe)
            mono_axe = m_axe / s_axe
            hebdo_axe = df_daily[c_name].rolling(7, min_periods=1).sum()
            df_daily[f'Strain_{code}'] = (hebdo_axe * mono_axe).round(1)

    df_daily['fraicheur'] = (df_daily['charge_chronique_28d'] - df_daily['charge_aigue_7d']).round(1)
    df_daily['RCm'] = np.where(df_daily['CTLm'] > 0, df_daily.get('ATL_meta', 0) / df_daily['CTLm'], 0).round(2)
    df_daily['RCN'] = np.where(df_daily['CTLN'] > 0, df_daily.get('ATL_nerveuse', 0) / df_daily['CTLN'], 0).round(2)
    df_daily['RCM'] = np.where(df_daily['CTLM'] > 0, df_daily.get('ATL_meca', 0) / df_daily['CTLM'], 0).round(2)

    return df_daily

# ==========================================
# 5. COMPOSANT CHANGEMENT DE MOT DE PASSE
# ==========================================
def render_password_change_form(key="form_change_password"):
    st.markdown("### 🔑 Modifier le mot de passe")
    
    user_email = st.session_state.user.email if st.session_state.user else "Non renseigné"
    st.info(f"👤 Compte concerné : **{user_email}**")

    with st.form(key):
        pwd1 = st.text_input("Nouveau mot de passe", type="password")
        pwd2 = st.text_input("Confirmer le nouveau mot de passe", type="password")
        btn_pwd = st.form_submit_button("🔒 Mettre à jour le mot de passe", use_container_width=True)
        
        if btn_pwd:
            if not pwd1 or len(pwd1) < 6:
                st.error("Le mot de passe doit contenir au moins 6 caractères.")
            elif pwd1 != pwd2:
                st.error("Les deux mots de passe ne correspondent pas.")
            else:
                try:
                    supabase.auth.update_user({"password": pwd1})
                    st.success("Votre mot de passe a été modifié avec succès !")
                except Exception as e:
                    st.error(f"Erreur lors de la modification : {e}")

# ==========================================
# 6. AUTHENTIFICATION & NAVIGATION
# ==========================================
def login(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        
        profile = supabase.table("athletes").select("*").eq("user_id", res.user.id).execute()
        if profile.data:
            st.session_state.athlete_info = profile.data[0]
        else:
            st.session_state.athlete_info = {"nom": email, "role": "athlete", "id": None, "vma": 15.0, "pma": 300, "ie_endurance": -7.0}
            
        st.success("Connexion réussie !")
        st.rerun()
    except Exception as e:
        st.error(f"Erreur de connexion : {e}")

def logout():
    supabase.auth.sign_out()
    st.session_state.user = None
    st.session_state.athlete_info = None
    st.rerun()

if st.session_state.user is None:
    st.markdown("<h1 style='text-align: center; color: #ffffff;'>⚡ Performance & Load Engine</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: #94a3b8;'>Plateforme de Suivi de Charge & Performance</h4>", unsafe_allow_html=True)
    st.write("")
    
    col_c1, col_c2, col_c3 = st.columns([1, 2, 1])
    with col_c2:
        with st.form("form_login"):
            st.subheader("Connexion")
            email = st.text_input("E-mail")
            password = st.text_input("Mot de passe", type="password")
            submit_login = st.form_submit_button("Se connecter", use_container_width=True)
            if submit_login:
                login(email, password)
    st.stop()

# ==========================================
# 7. APPLICATION PRINCIPALE
# ==========================================
profil = st.session_state.athlete_info
is_coach = profil.get("role") == "coach"

def get_athletes_dict():
    res = supabase.table("athletes").select("id, nom").execute()
    dict_ath = {}
    if res.data:
        for a in res.data:
            nom_brut = a.get("nom")
            if nom_brut and str(nom_brut).strip():
                dict_ath[str(nom_brut).strip()] = a["id"]
    return dict_ath

# Header Profil avec informations
st.markdown(f"""
<div style="display: flex; justify-content: space-between; align-items: center; background-color: #1f2937; padding: 15px 25px; border-radius: 12px; margin-bottom: 25px; border: 1px solid #374151;">
    <div>
        <h2 style="margin: 0; color: #ffffff;">👋 {profil.get('nom', 'Athlète')}</h2>
        <span style="color: #94a3b8;">{'🏋️‍♂️ Coach' if is_coach else '🏃 Athlète'} | VMA: <b style="color:#ffffff;">{profil.get('vma', 15)} km/h</b> | PMA: <b style="color:#ffffff;">{profil.get('pma', 300)} W</b> | IE: <b style="color:#ffffff;">{profil.get('ie_endurance', -7.0)}</b></span>
    </div>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------
# SIDEBAR UNIQUE ET FORCÉE AU CONTEXTE
# ------------------------------------------
dict_athletes = get_athletes_dict()

with st.sidebar:
    st.markdown("### ⚡ Option Saisie & Groupe")
    
    if is_coach:
        type_action = st.radio(
            "Type d'entrée :", 
            ["Séance Réalisée (Passée)", "Prescription / Prévu (Futur)"],
            key="sb_type_action_key"
        )
        
        est_prescription = (type_action == "Prescription / Prévu (Futur)")
        liste_base = sorted(list(dict_athletes.keys())) if dict_athletes else ["Aucun profil"]
        
        if est_prescription:
            options_target = ["👥 TOUS LES ATHLÈTES", "🌐 TOUS (Athlètes + Coachs)"] + liste_base
        else:
            options_target = liste_base

        nom_selectionne = st.selectbox(
            "Athlète / Groupe concerné :", 
            options=options_target,
            key="sb_nom_target_key"
        )
    else:
        type_action = "Séance Réalisée (Passée)"
        est_prescription = False
        nom_selectionne = profil.get("nom")

    st.write("---")
    if st.button("🚪 Déconnexion", use_container_width=True, key="sb_logout_btn"):
        logout()

# --- DÉCLARATION DES ONGLETS ---
if is_coach:
    tabs = st.tabs([
        "🚨 Dashboard & Alertes",
        "📝 Saisie / Prescription", 
        "🗓️ Prévu vs Réalisé", 
        "🎯 ACWR & Risques", 
        "🔥 Strain & Monotonie", 
        "⚡ Rendements (RC)", 
        "🏃‍♂️ Physiologie", 
        "⚙️ Admin Coach"
    ])
    tab_dash, tab_saisie, tab_plan, tab_acwr, tab_strain, tab_rc, tab_physio, tab_admin = tabs
else:
    tabs = st.tabs([
        "📝 Saisir ma séance", 
        "🗓️ Mon Planning (Prévu/Réalisé)", 
        "🎯 Mon ACWR & Forme", 
        "🔥 Strain & Monotonie", 
        "⚡ Rendements (RC)", 
        "🏃‍♂️ Mon Profil"
    ])
    tab_saisie, tab_plan, tab_acwr, tab_strain, tab_rc, tab_physio = tabs

# ==========================================
# ONGLET COACH : DASHBOARD & ALERTES AUTO
# ==========================================
if is_coach:
    with tab_dash:
        st.subheader("🚨 Centre d'Alertes & Santé du Groupe")
        dict_ath = get_athletes_dict()
        if not dict_ath:
            st.info("Aucun athlète enregistré.")
        else:
            alertes_trouvees = 0
            cols_dash = st.columns(3)
            
            for index, (nom_ath, id_ath) in enumerate(dict_ath.items()):
                seances_ath = supabase.table("seances").select("*").eq("athlete_id", id_ath).order("date_seance", desc=False).execute().data
                if seances_ath and len(seances_ath) >= 2:
                    df_ath = calculer_acwr(pd.DataFrame(seances_ath))
                    last_ath = df_ath.iloc[-1]
                    
                    acwr_v = last_ath['acwr']
                    mono_v = last_ath['monotonie']
                    spike_v = last_ath['spike_pct']

                    is_danger = acwr_v > 1.5 or mono_v > 2.0 or spike_v > 15
                    is_warning = (1.3 < acwr_v <= 1.5) or (1.5 < mono_v <= 2.0)

                    if is_danger or is_warning:
                        alertes_trouvees += 1
                        badge_style = "danger" if is_danger else "warning"
                        st_text = "CRITIQUE" if is_danger else "ATTENTION"
                        
                        col_target = cols_dash[index % 3]
                        with col_target:
                            st.markdown(f"""
                            <div class="kpi-card" style="border-left: 5px solid {'#ef4444' if is_danger else '#f59e0b'};">
                                <div style="display: flex; justify-content: space-between;">
                                    <b style="color:#ffffff;">{nom_ath}</b>
                                    <span class="badge-{badge_style}">{st_text}</span>
                                </div>
                                <hr style="margin: 8px 0; border-color: #374151;">
                                <div style="font-size: 0.85rem; color:#cbd5e1;">
                                    <b>ACWR :</b> {acwr_v}<br>
                                    <b>Monotonie :</b> {mono_v}<br>
                                    <b>Spike Hebdo :</b> +{spike_v}%
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

            if alertes_trouvees == 0:
                st.success("🟢 Aucun athlète en zone d'alerte critique actuellement.")

# ==========================================
# ONGLET : SAISIE & PRESCRIPTION
# ==========================================
with tab_saisie:
    st.subheader("📝 Enregistrer une Séance ou une Prescription")

    if is_coach:
        if est_prescription:
            st.info(f"📌 **Mode Prescription actif** ➔ Cible : **{nom_selectionne}**")
        else:
            st.success(f"✏️ **Mode Séance Réalisée actif** ➔ Athlète : **{nom_selectionne}**")

    with st.form("form_seance", clear_on_submit=True):
        date_saisie = st.date_input("Date de la séance", value=datetime.date.today())
        
        c1, c2, c3 = st.columns(3)
        with c1:
            sport = st.selectbox("Sport", ["Course à pied", "Trail", "Cyclisme", "Renforcement", "Natation", "Autre"])
        with c2:
            type_seance = st.text_input("Intitulé / Type", value="Endurance / VMA")
        with c3:
            terrain = st.selectbox("Terrain / Surface", ["Piste / Bitume", "Chemin / Sous-bois", "Montagne / Dérivé Trail", "Sable / Boue", "Salle / Tapis"])

        duree = st.number_input("Durée prévue/réalisée (min)", min_value=5, max_value=600, value=60, step=5)
        
        st.write("---")
        cr1, cr2 = st.columns(2)
        with cr1:
            rpe = st.slider("RPE - Intensité (1 à 10)", 1, 10, 5)
            batterie = st.slider("Batterie / Énergie (1=Vide, 5=Pleine)", 1, 5, 4)
        with cr2:
            fatigue = st.slider("Fatigue ressentie (1=Frais, 5=Épuisé)", 1, 5, 2)
            douleur = st.slider("Douleurs (1=Aucune, 5=Forte)", 1, 5, 1)

        c_globale, km_eq, c_meta, c_nerv, c_meca = calculer_triple_charge(duree, rpe, sport, terrain, batterie)

        st.markdown("**⚡ Aperçu du calcul de charge :**")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Km Équivalent", f"{km_eq} km_eq")
        m2.metric("Méta", f"{c_meta} AU")
        m3.metric("Nerveux", f"{c_nerv} AU")
        m4.metric("Mécanique", f"{c_meca} AU")

        commentaire = st.text_area("Remarques / Directives Coach", placeholder="Consignes de séance...")

        submit_form = st.form_submit_button("🚀 Valider et Envoyer", use_container_width=True)

        if submit_form:
            base_payload = {
                "date_seance": str(date_saisie),
                "sport": sport,
                "type_seance": type_seance,
                "terrain": terrain,
                "duree_min": int(duree),
                "rpe": int(rpe),
                "km_eq": float(km_eq),
                "charge_meta": float(c_meta),
                "charge_nerveuse": float(c_nerv),
                "charge_meca": float(c_meca),
                "batterie": int(batterie),
                "fatigue_sante": int(fatigue),
                "douleur": int(douleur),
                "commentaire": str(commentaire),
                "est_prevu": est_prescription
            }

            try:
                if nom_selectionne == "👥 TOUS LES ATHLÈTES":
                    res_target = supabase.table("athletes").select("id").eq("role", "athlete").execute()
                    if res_target.data:
                        batch = [{**base_payload, "athlete_id": r["id"]} for r in res_target.data]
                        supabase.table("seances").insert(batch).execute()
                        st.success(f"Prescription envoyée à {len(batch)} athlètes !")
                        st.rerun()

                elif nom_selectionne == "🌐 TOUS (Athlètes + Coachs)":
                    res_target = supabase.table("athletes").select("id").execute()
                    if res_target.data:
                        batch = [{**base_payload, "athlete_id": r["id"]} for r in res_target.data]
                        supabase.table("seances").insert(batch).execute()
                        st.success(f"Prescription envoyée à l'ensemble des membres ({len(batch)} profils) !")
                        st.rerun()

                else:
                    selected_id = dict_athletes.get(nom_selectionne) if is_coach else profil.get("id")
                    if selected_id:
                        base_payload["athlete_id"] = int(selected_id)
                        supabase.table("seances").insert(base_payload).execute()
                        st.success("Enregistrement réussi !")
                        st.rerun()
                    else:
                        st.error("Aucun athlète sélectionné.")

            except Exception as e:
                st.error(f"Erreur Supabase : {e}")

# ==========================================
# ONGLET : PLANNING & PRÉVU VS RÉALISÉ
# ==========================================
with tab_plan:
    st.subheader("🗓️ Planning & Prévu vs Réalisé")
    
    if is_coach:
        dict_p = get_athletes_dict()
        nom_p = st.selectbox("Athlète :", options=sorted(list(dict_p.keys())), key="p_plan")
        target_plan_id = dict_p.get(nom_p)
    else:
        target_plan_id = profil.get("id")

    if target_plan_id:
        col_d1, col_d2 = st.columns(2)
        today_val = datetime.date.today()
        lundi_defaut = today_val - datetime.timedelta(days=today_val.weekday())
        dimanche_defaut = lundi_defaut + datetime.timedelta(days=6)

        with col_d1:
            date_debut = st.date_input("Date de début :", value=lundi_defaut, key="d_start_plan")
        with col_d2:
            date_fin = st.date_input("Date de fin :", value=dimanche_defaut, key="d_end_plan")

        if date_debut > date_fin:
            st.error("La date de début doit être antérieure ou égale à la date de fin.")
        else:
            raw_seances = supabase.table("seances") \
                .select("*") \
                .eq("athlete_id", target_plan_id) \
                .gte("date_seance", str(date_debut)) \
                .lte("date_seance", str(date_fin)) \
                .execute().data

            if raw_seances:
                df_semaine = pd.DataFrame(raw_seances)
                df_semaine['date_seance'] = pd.to_datetime(df_semaine['date_seance'])

                if 'est_prevu' not in df_semaine.columns:
                    df_semaine['est_prevu'] = False
                else:
                    df_semaine['est_prevu'] = df_semaine['est_prevu'].fillna(False).astype(bool)

                df_prevu = df_semaine[df_semaine['est_prevu'] == True]
                df_realise = df_semaine[df_semaine['est_prevu'] == False]

                c_prevu_total = (df_prevu['duree_min'] * df_prevu['rpe']).sum() if not df_prevu.empty else 0
                c_real_total = (df_realise['duree_min'] * df_realise['rpe']).sum() if not df_realise.empty else 0

                col_k1, col_k2, col_k3 = st.columns(3)
                with col_k1:
                    render_kpi_card("Charge Prescrite (Prévu)", f"{c_prevu_total:.0f} AU", "Cible Coach", "info")
                with col_k2:
                    render_kpi_card("Charge Réalisée", f"{c_real_total:.0f} AU", "Exécuté", "success" if c_real_total <= (c_prevu_total * 1.1 if c_prevu_total > 0 else 9999) else "danger")
                with col_k3:
                    ratio_respect = (c_real_total / c_prevu_total * 100) if c_prevu_total > 0 else 100
                    render_kpi_card("Taux de Respect", f"{ratio_respect:.1f} %", "Conformité", "success" if 90 <= ratio_respect <= 110 else "warning")

                st.markdown("### 📋 Tableau Détaillé de la Période")
                cols_aff = [c for c in ["date_seance", "sport", "type_seance", "duree_min", "rpe", "charge_meta", "charge_meca", "est_prevu", "commentaire"] if c in df_semaine.columns]
                st.dataframe(df_semaine[cols_aff], use_container_width=True)

                st.write("---")
                csv_data = df_semaine.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Télécharger le bilan de la période (CSV)",
                    data=csv_data,
                    file_name=f"bilan_{date_debut.strftime('%Y%m%d')}_au_{date_fin.strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("Aucune séance enregistrée pour cette période.")

# ==========================================
# ONGLET : ACWR & JAUGE INTERACTIVE
# ==========================================
with tab_acwr:
    st.subheader("🎯 Modèle ACWR & Analyse de Forme")
    
    if is_coach:
        dict_a = get_athletes_dict()
        nom_a = st.selectbox("Athlète :", options=sorted(list(dict_a.keys())), key="acwr_sel")
        target_acwr_id = dict_a.get(nom_a)
    else:
        target_acwr_id = profil.get("id")

    if target_acwr_id:
        seances_acwr = supabase.table("seances").select("*").eq("athlete_id", target_acwr_id).order("date_seance", desc=False).execute().data
        if seances_acwr and len(seances_acwr) >= 2:
            df_acwr = calculer_acwr(pd.DataFrame(seances_acwr))
            last_r = df_acwr.iloc[-1]

            col_jauge, col_stats = st.columns([1, 2])
            with col_jauge:
                fig_j = mef_jauge_acwr(last_r['acwr'])
                st.plotly_chart(fig_j, use_container_width=True)
            with col_stats:
                st.write("")
                st.write("")
                c_a, c_b, c_c = st.columns(3)
                with c_a:
                    render_kpi_card("Aiguë (7j)", f"{last_r['charge_aigue_7d']:.0f} AU", "ATL", "info")
                with c_b:
                    render_kpi_card("Chronique (28j)", f"{last_r['charge_chronique_28d']:.0f} AU", "CTL", "success")
                with c_c:
                    spk = last_r['spike_pct']
                    render_kpi_card("Spike Hebdo", f"{spk:+.1f} %", "Δ 7 jours", "danger" if spk > 15 else "success")

            st.markdown("### 📈 Chronologie de la Charge Aiguë, Chronique & Ratio ACWR")
            
            fig_acwr_full = go.Figure()
            fig_acwr_full.add_trace(go.Bar(x=df_acwr['date_seance'], y=df_acwr['charge_du_jour'], name="Charge Jour", marker_color='rgba(148, 163, 184, 0.3)'))
            fig_acwr_full.add_trace(go.Scatter(x=df_acwr['date_seance'], y=df_acwr['charge_aigue_7d'], name="Aiguë (ATL 7j)", line=dict(color='#3b82f6', width=2)))
            fig_acwr_full.add_trace(go.Scatter(x=df_acwr['date_seance'], y=df_acwr['charge_chronique_28d'], name="Chronique (CTL 28j)", line=dict(color='#10b981', width=2)))
            fig_acwr_full.add_trace(go.Scatter(x=df_acwr['date_seance'], y=df_acwr['acwr'], name="Ratio ACWR", yaxis="y2", line=dict(color='#f59e0b', width=3)))

            fig_acwr_full.update_layout(
                xaxis_title="Date",
                yaxis=dict(title="Charge (AU)"),
                yaxis2=dict(title="ACWR Ratio", overlaying="y", side="right", range=[0, 2.5]),
                hovermode="x unified",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_acwr_full, use_container_width=True)

# ==========================================
# ONGLET : STRAIN & MONOTONIE
# ==========================================
with tab_strain:
    st.subheader("🔥 Monotonie & Strain de Foster")
    if target_acwr_id:
        seances_st = supabase.table("seances").select("*").eq("athlete_id", target_acwr_id).order("date_seance", desc=False).execute().data
        if seances_st and len(seances_st) >= 2:
            df_st = calculer_acwr(pd.DataFrame(seances_st))
            last_s = df_st.iloc[-1]

            cs1, cs2, cs3 = st.columns(3)
            with cs1:
                render_kpi_card("Monotonie", f"{last_s['monotonie']:.2f}", "Seuil: 1.5", "warning" if last_s['monotonie'] > 1.5 else "success")
            with cs2:
                render_kpi_card("Strain Total", f"{last_s['strain']:.0f}", "Charge x Mono", "info")
            with cs3:
                render_kpi_card("Strain / 1.6", f"{last_s['strain_div_16']:.0f}", "Indice Ajusté", "danger" if last_s['strain_div_16'] > 1000 else "success")

            fig_st = go.Figure()
            fig_st.add_trace(go.Scatter(x=df_st['date_seance'], y=df_st['strain'], name="Strain", fill='tozeroy', fillcolor='rgba(239, 68, 68, 0.2)', line=dict(color='#ef4444', width=2)))
            fig_st.add_trace(go.Scatter(x=df_st['date_seance'], y=df_st['monotonie'], name="Monotonie", yaxis="y2", line=dict(color='#f59e0b', width=2, dash='dot')))
            
            fig_st.update_layout(
                xaxis_title="Date",
                yaxis=dict(title="Strain (AU)"),
                yaxis2=dict(title="Monotonie", overlaying="y", side="right", range=[0, 3]),
                hovermode="x unified",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_st, use_container_width=True)

# ==========================================
# ONGLET : RATIOS DE RENDEMENT (RC)
# ==========================================
with tab_rc:
    st.subheader("⚡ Ratios de Rendement (RC - Triple Charge)")
    if target_acwr_id:
        seances_rc = supabase.table("seances").select("*").eq("athlete_id", target_acwr_id).order("date_seance", desc=False).execute().data
        if seances_rc and len(seances_rc) >= 2:
            df_rc = calculer_acwr(pd.DataFrame(seances_rc))
            last_rc = df_rc.iloc[-1]

            crc1, crc2, crc3 = st.columns(3)
            with crc1:
                render_kpi_card("RC Métabolique", f"{last_rc['RCm']:.2f}", "Axe Cardio/Méta", "info")
            with crc2:
                render_kpi_card("RC Nerveux", f"{last_rc['RCN']:.2f}", "Axe SNC / Intensité", "warning" if last_rc['RCN'] > 1.3 else "success")
            with crc3:
                render_kpi_card("RC Mécanique", f"{last_rc['RCM']:.2f}", "Axe Impact/Lésionnel", "danger" if last_rc['RCM'] > 1.4 else "success")

            fig_rc = go.Figure()
            fig_rc.add_trace(go.Scatter(x=df_rc['date_seance'], y=df_rc['RCm'], name="RC Métabolique", line=dict(color='#3b82f6', width=2)))
            fig_rc.add_trace(go.Scatter(x=df_rc['date_seance'], y=df_rc['RCN'], name="RC Nerveux", line=dict(color='#8b5cf6', width=2)))
            fig_rc.add_trace(go.Scatter(x=df_rc['date_seance'], y=df_rc['RCM'], name="RC Mécanique", line=dict(color='#ec4899', width=2)))
            
            fig_rc.update_layout(
                xaxis_title="Date",
                yaxis=dict(title="Ratio RC"),
                hovermode="x unified",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_rc, use_container_width=True)

# ==========================================
# ONGLET : PHYSIOLOGIE & PROFIL
# ==========================================
with tab_physio:
    st.subheader("🏃‍♂️ Profil Physiologique & Paramètres")
    
    col_physio, col_security = st.columns(2)

    with col_physio:
        st.markdown("### 📊 Mesures & Constantes")
        with st.form("form_update_physio"):
            raw_vma = profil.get("vma") if profil else None
            raw_pma = profil.get("pma") if profil else None
            raw_ie = profil.get("ie_endurance") if profil else None

            vma_current = float(raw_vma) if raw_vma is not None else 15.0
            pma_current = int(raw_pma) if raw_pma is not None else 300
            ie_current = float(raw_ie) if raw_ie is not None else -7.0

            vma_val = st.number_input("VMA (km/h)", min_value=8.0, max_value=26.0, value=vma_current, step=0.5)
            pma_val = st.number_input("PMA (Watts)", min_value=100, max_value=700, value=pma_current, step=5)
            ie_val = st.number_input("Indice d'Endurance (IE)", min_value=-15.0, max_value=0.0, value=ie_current, step=0.5)

            btn_physio = st.form_submit_button("💾 Mettre à jour mes constantes", use_container_width=True)

            if btn_physio:
                user_athlete_id = profil.get("id") if profil else None
                if user_athlete_id:
                    try:
                        supabase.table("athletes").update({
                            "vma": vma_val,
                            "pma": pma_val,
                            "ie_endurance": ie_val
                        }).eq("id", user_athlete_id).execute()
                        
                        st.session_state.athlete_info["vma"] = vma_val
                        st.session_state.athlete_info["pma"] = pma_val
                        st.session_state.athlete_info["ie_endurance"] = ie_val
                        
                        st.success("Constantes physiologiques mises à jour ! 🔥")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erreur de mise à jour : {e}")
                else:
                    st.warning("Aucun profil athlète rattaché à ce compte Supabase.")

    with col_security:
        render_password_change_form(key="pwd_form_profile")

# ==========================================
# ONGLET : ADMIN COACH (SI COACH)
# ==========================================
if is_coach:
    with tab_admin:
        st.subheader("⚙️ Administration Coach")
        
        col_create, col_list = st.columns([1, 1])

        with col_create:
            st.markdown("### ➕ Créer un nouvel Athlète ou Coach")
            with st.form("form_create_user", clear_on_submit=True):
                new_email = st.text_input("Adresse E-mail du membre *")
                new_nom = st.text_input("Nom Prénom / Identifiant *")
                new_password = st.text_input("Mot de passe provisoire (min. 6 car.) *", type="password")
                new_role = st.selectbox("Rôle", ["athlete", "coach"])
                
                c_vma, c_pma, c_ie = st.columns(3)
                with c_vma:
                    vma_init = st.number_input("VMA initiale", value=15.0, step=0.5)
                with c_pma:
                    pma_init = st.number_input("PMA initiale", value=300, step=5)
                with c_ie:
                    ie_init = st.number_input("IE initial", value=-7.0, step=0.5)

                btn_create = st.form_submit_button("🚀 Créer le compte", use_container_width=True)

                if btn_create:
                    if not new_email or not new_password or not new_nom:
                        st.error("Veuillez remplir tous les champs obligatoires (*).")
                    elif len(new_password) < 6:
                        st.error("Le mot de passe doit faire au moins 6 caractères.")
                    else:
                        try:
                            auth_res = supabase.auth.sign_up({
                                "email": new_email,
                                "password": new_password
                            })
                            
                            new_user_id = auth_res.user.id if auth_res.user else None

                            payload_athlete = {
                                "user_id": new_user_id,
                                "nom": new_nom.strip(),
                                "role": new_role,
                                "vma": float(vma_init),
                                "pma": int(pma_init),
                                "ie_endurance": float(ie_init)
                            }
                            
                            supabase.table("athletes").insert(payload_athlete).execute()
                            st.success(f"Compte {new_role} créé avec succès pour {new_nom} ({new_email}) !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur lors de la création du compte : {e}")

        with col_list:
            render_password_change_form(key="pwd_form_admin")
            
            st.markdown("---")
            st.markdown("### 👥 Membres Inscrits")
            try:
                res_members = supabase.table("athletes").select("id, nom, role, vma, pma, ie_endurance").execute()
                if res_members.data:
                    df_members = pd.DataFrame(res_members.data)
                    st.dataframe(df_members, use_container_width=True)
                else:
                    st.info("Aucun profil enregistré dans la table 'athletes'.")
            except Exception as e:
                st.error(f"Impossible de récupérer la liste des membres : {e}")