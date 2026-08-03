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

url = st.secrets.get("SUPABASE_URL", "")
key = st.secrets.get("SUPABASE_KEY", "")
supabase: Client = create_client(url, key)

# ----------------------------------------------------
# 💡 INJECTION JS : CONVERTIT LE HASH (#) EN QUERY PARAMS (?)
# Exemple : /#access_token=xxx&type=recovery -> /?access_token=xxx&type=recovery
# ----------------------------------------------------
st.components.v1.html(
    """
    <script>
    if (window.location.hash && window.location.hash.includes('access_token')) {
        let hash = window.location.hash.substring(1);
        let newUrl = window.location.pathname + '?' + hash;
        window.history.replaceState(null, null, newUrl);
        window.location.reload();
    }
    </script>
    """,
    height=0,
    width=0
)

# ----------------------------------------------------
# 🔑 INTERCEPTION DU LIEN DE RÉINITIALISATION DE MOT DE PASSE
# ----------------------------------------------------
params = st.query_params

if params.get("type") == "recovery" or "access_token" in params:
    st.title("🔑 Redéfinition de votre mot de passe")
    st.info("Vous avez cliqué sur le lien de réinitialisation. Veuillez saisir votre nouveau mot de passe ci-dessous.")

    # 1. Extraction des tokens de l'URL
    access_token = params.get("access_token")
    refresh_token = params.get("refresh_token", access_token)

    # 2. Initialisation explicite de la session Supabase si le token est présent
    if access_token:
        try:
            supabase.auth.set_session(access_token, refresh_token)
        except Exception:
            pass

    with st.form("form_recovery_password"):
        new_pwd = st.text_input("Nouveau mot de passe", type="password", key="rec_pwd1")
        confirm_pwd = st.text_input("Confirmer le nouveau mot de passe", type="password", key="rec_pwd2")
        submit_btn = st.form_submit_button("💾 Enregistrer le nouveau mot de passe", use_container_width=True)

        if submit_btn:
            if not new_pwd or len(new_pwd) < 6:
                st.error("Le mot de passe doit contenir au moins 6 caractères.")
            elif new_pwd != confirm_pwd:
                st.error("Les deux mots de passe ne correspondent pas.")
            else:
                try:
                    # 3. Réactivation de la session juste avant l'update
                    if access_token:
                        supabase.auth.set_session(access_token, refresh_token)

                    # 4. Mise à jour du mot de passe utilisateur
                    supabase.auth.update_user({"password": new_pwd})
                    st.success("✅ Votre mot de passe a été réinitialisé avec succès !")
                    
                    st.query_params.clear()
                    if st.button("Se connecter à l'application", type="primary"):
                        st.rerun()
                except Exception as e:
                    st.error(f"Erreur lors de la mise à jour : {e}")

    # Bloque le chargement du reste de l'application tant qu'on est en mode recovery
    st.stop()

# Initialisation des variables de session
if "user" not in st.session_state:
    st.session_state.user = None
if "athlete_info" not in st.session_state:
    st.session_state.athlete_info = None

# ==========================================
# 2. INJECTION DE STYLE CSS PROPRE
# ==========================================
st.markdown("""
<style>
    .kpi-card {
        background: linear-gradient(135deg, #1e2638 0%, #111827 100%);
        border: 1px solid #2d3748;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        margin-bottom: 15px;
    }
    .kpi-title { color: #94a3b8; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; }
    .kpi-value { color: #ffffff; font-size: 1.8rem; font-weight: 700; margin-top: 4px; }
    .kpi-sub { font-size: 0.8rem; margin-top: 4px; }
    .badge-success { background-color: #10b98122; color: #34d399; border: 1px solid #10b981; padding: 3px 8px; border-radius: 6px; font-weight: bold; }
    .badge-warning { background-color: #f59e0b22; color: #fbbf24; border: 1px solid #fbbf24; padding: 3px 8px; border-radius: 6px; font-weight: bold; }
    .badge-danger { background-color: #ef444422; color: #f87171; border: 1px solid #ef4444; padding: 3px 8px; border-radius: 6px; font-weight: bold; }
    .badge-info { background-color: #3b82f622; color: #60a5fa; border: 1px solid #3b82f6; padding: 3px 8px; border-radius: 6px; font-weight: bold; }
    
    /* Styles spécifiques planning */
    .text-prevu { color: #94a3b8; font-weight: 500; }
    .text-realise { color: #60a5fa; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# GESTION DU POP-UP FORCE DE CHANGEMENT DE MOT DE PASSE
# ==========================================
@st.dialog("🔒 Modification de votre mot de passe requise", width="small")
def modal_changement_mot_de_passe():
    st.warning("Votre entraîneur exige la définition/mise à jour de votre mot de passe pour accéder à votre espace.")
    
    with st.form("form_modal_reset_pwd"):
        pwd1 = st.text_input("Nouveau mot de passe", type="password", key="modal_pwd1")
        pwd2 = st.text_input("Confirmer le mot de passe", type="password", key="modal_pwd2")
        
        if st.form_submit_button("💾 Enregistrer et accéder à l'application", use_container_width=True):
            if not pwd1 or len(pwd1) < 6:
                st.error("Le mot de passe doit contenir au moins 6 caractères.")
            elif pwd1 != pwd2:
                st.error("Les deux mots de passe ne correspondent pas.")
            else:
                try:
                    # S'assurer que la session active est bien transmise si disponible
                    if st.session_state.get("user") and hasattr(st.session_state.user, "access_token"):
                        supabase.auth.set_session(st.session_state.user.access_token, st.session_state.user.refresh_token)

                    # 1. Mise à jour du mot de passe dans Supabase Auth
                    supabase.auth.update_user({"password": pwd1})
                    
                    # 2. Désactivation du drapeau force_reset_pwd dans la BDD
                    if st.session_state.athlete_info and st.session_state.athlete_info.get("id"):
                        supabase.table("athletes").update({"force_reset_pwd": False}).eq("id", st.session_state.athlete_info["id"]).execute()
                        st.session_state.athlete_info["force_reset_pwd"] = False
                        
                    st.success("Mot de passe mis à jour avec succès !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur lors de la mise à jour : {e}")
# Trigger de contrôle au démarrage de la session
if st.session_state.get("athlete_info") and st.session_state.athlete_info.get("force_reset_pwd", False):
    modal_changement_mot_de_passe()

# ==========================================
# 3. UTILS & FONCTIONS CONVERSION
# ==========================================
def convert_vma_to_100m(vma_kmh):
    """Convertit la VMA (km/h) en temps aux 100m (MM'SS")."""
    if not vma_kmh or vma_kmh <= 0:
        return "N/A"
    sec_per_100m = 3600.0 / (vma_kmh * 10.0)
    minutes = int(sec_per_100m // 60)
    seconds = int(sec_per_100m % 60)
    return f"{minutes}'{seconds:02d}\"/100m"

def deduire_filiere(pct_vma):
    """Déduit automatiquement la filière énergétique selon le % de VMA."""
    if pct_vma < 60:
        return "Base (Récup / Endurance douce)"
    elif 60 <= pct_vma <= 110:
        return "Aérobie (Seuil / VMA)"
    else:
        return "Anaérobie (Sprint / Lactique)"

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
        mode="gauge+number",
        value=valeur_acwr,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Ratio ACWR", 'font': {'size': 18, 'color': "white"}},
        number={'font': {'size': 36, 'color': "white"}},
        gauge={
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
    fig.update_layout(height=220, margin=dict(l=20, r=20, t=30, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

# ==========================================
# 4. RADAR ÉTAT DE FORME (RÉORDONNÉ CDC)
# ==========================================
def afficher_radar_etat_de_forme(df_journalier):
    """
    Radar réordonné selon les spécifications :
    - Opposés : Mécanique vs Casse Mécanique (Douleur/Raideur)
    - Adjacents 1 : Métabolique & Jambes
    - Adjacents 2 : SNC & Motivation/NRJ
    """
    if df_journalier.empty:
        return
        
    df_7j = df_journalier.tail(7)
    
    # Nouvel ordre des axes conforme au CdC
    axes = ['Mécanique', 'Casse Mécanique', 'Métabolique', 'Jambes', 'SNC', 'Motivation / NRJ']
    
    potentiel_vals = [
        float(df_7j['CTLM'].mean() if 'CTLM' in df_7j else 0),
        float(10 - df_7j['casse_mecanique'].mean() if 'casse_mecanique' in df_7j else 10),
        float(df_7j['CTLm'].mean() if 'CTLm' in df_7j else 0),
        float(df_7j['jambes'].mean() if 'jambes' in df_7j else 5),
        float(df_7j['CTLN'].mean() if 'CTLN' in df_7j else 0),
        float(df_7j['batterie'].mean() if 'batterie' in df_7j else 5)
    ]
    
    contrainte_vals = [
        float(df_7j['Strain_M'].mean() if 'Strain_M' in df_7j else 0),
        float(df_7j['casse_mecanique'].mean() if 'casse_mecanique' in df_7j else 0),
        float(df_7j['Strain_m'].mean() if 'Strain_m' in df_7j else 0),
        float(10 - df_7j['jambes'].mean() if 'jambes' in df_7j else 5),
        float(df_7j['Strain_N'].mean() if 'Strain_N' in df_7j else 0),
        float(10 - df_7j['batterie'].mean() if 'batterie' in df_7j else 5)
    ]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=potentiel_vals, theta=axes, fill='toself', name='Potentiel (Forme 7j)', line=dict(color='#3b82f6', width=2), fillcolor='rgba(59, 130, 246, 0.25)'))
    fig.add_trace(go.Scatterpolar(r=contrainte_vals, theta=axes, fill='toself', name='Contrainte (Fatigue 7j)', line=dict(color='#ef4444', width=2), fillcolor='rgba(239, 68, 68, 0.25)'))

    max_val = max(max(potentiel_vals or [10]), max(contrainte_vals or [10])) * 1.15

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, max_val if max_val > 0 else 10], gridcolor='#334155'), angularaxis=dict(gridcolor='#334155', color='#f1f5f9'), bgcolor='rgba(0,0,0,0)'),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(font=dict(color='#f1f5f9'), orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
        margin=dict(l=40, r=40, t=30, b=40)
    )
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 5. MOTEURS DE CALCUL ROBUSTE
# ==========================================
def calculer_triple_charge(duree_min, rpe, sport, batterie, jambes=5, casse_mecanique=1, rpe_coach=None):
    # Pondération du RPE si l'entraîneur intervient (2/3 Athlète, 1/3 Coach)
    rpe_effective = rpe if rpe_coach is None else round((2/3)*rpe + (1/3)*rpe_coach, 2)
    
    charge_globale = duree_min * rpe_effective
    
    facteurs_sport = {"Course à pied": 1.0, "Trail": 1.2, "Cyclisme": 0.4, "Natation": 4.0, "Renforcement": 0.5, "Autre": 0.8}
    coef_sport = facteurs_sport.get(sport, 1.0)
    km_eq = round((duree_min / 60.0) * (rpe_effective * 2.5) * coef_sport, 1)

    facteur_jambes = 1.0 + ((10 - jambes) * 0.02)
    facteur_casse = 1.0 + ((casse_mecanique - 1) * 0.03)

    ratio_nerveux = 0.8 + (rpe_effective / 10.0) * 0.5
    ratio_meca = (1.2 if sport in ["Course à pied", "Trail"] else 0.6) * facteur_jambes
    facteur_batterie = 1.0 + ((10 - batterie) * 0.03)

    charge_meta = round(charge_globale * facteur_batterie, 1)
    charge_nerveuse = round(charge_globale * ratio_nerveux * facteur_batterie, 1)
    charge_meca = round(charge_globale * ratio_meca * facteur_casse, 1)

    return charge_globale, km_eq, charge_meta, charge_nerveuse, charge_meca, rpe_effective

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

    agg_dict = {'charge_seance': 'sum', 'charge_meta': 'sum', 'charge_nerveuse': 'sum', 'charge_meca': 'sum'}
    for extra_col in ['batterie', 'jambes', 'casse_mecanique']:
        if extra_col in df_seances.columns:
            agg_dict[extra_col] = 'mean'

    df_daily = df_seances.groupby('date_seance').agg(agg_dict).reindex(idx_dates, fill_value=0).reset_index()
    df_daily.rename(columns={'index': 'date_seance', 'charge_seance': 'charge_du_jour'}, inplace=True)

    df_daily['charge_aigue_7d'] = df_daily['charge_du_jour'].ewm(span=7, adjust=False).mean()
    df_daily['charge_chronique_28d'] = df_daily['charge_du_jour'].ewm(span=28, adjust=False).mean()

    df_daily['acwr'] = np.where(df_daily['charge_chronique_28d'] > 0, df_daily['charge_aigue_7d'] / df_daily['charge_chronique_28d'], 0).round(2)
    df_daily['charge_hebdo'] = df_daily['charge_du_jour'].rolling(window=7, min_periods=1).sum()

    for col in ['meta', 'nerveuse', 'meca']:
        c_name = f'charge_{col}'
        if c_name in df_daily.columns:
            df_daily[f'ATL_{col}'] = df_daily[c_name].ewm(span=7, adjust=False).mean()
            df_daily[f'CTL_{col}'] = df_daily[c_name].ewm(span=28, adjust=False).mean()

    df_daily['CTLm'] = df_daily.get('CTL_meta', 0)
    df_daily['CTLN'] = df_daily.get('CTL_nerveuse', 0)
    df_daily['CTLM'] = df_daily.get('CTL_meca', 0)

    roll_mean_7d = df_daily['charge_du_jour'].rolling(7, min_periods=1).mean()
    roll_std_7d = df_daily['charge_du_jour'].rolling(7, min_periods=1).std().fillna(1.0)
    roll_std_7d = np.where(roll_std_7d == 0, 1.0, roll_std_7d)

    df_daily['monotonie'] = (roll_mean_7d / roll_std_7d).round(2)
    df_daily['strain'] = (df_daily['charge_hebdo'] * df_daily['monotonie']).round(1)
    df_daily['resistance_strain'] = (1.6 * df_daily['charge_chronique_28d']).round(1) # Courbe limiteCdC

    for col, code in [('meta', 'm'), ('nerveuse', 'N'), ('meca', 'M')]:
        c_name = f'charge_{col}'
        if c_name in df_daily.columns:
            m_axe = df_daily[c_name].rolling(7, min_periods=1).mean()
            s_axe = df_daily[c_name].rolling(7, min_periods=1).std().fillna(1.0)
            s_axe = np.where(s_axe == 0, 1.0, s_axe)
            mono_axe = m_axe / s_axe
            hebdo_axe = df_daily[c_name].rolling(7, min_periods=1).sum()
            df_daily[f'Strain_{code}'] = (hebdo_axe * mono_axe).round(1)

    df_daily['TSB_meta'] = (df_daily['CTLm'] - df_daily.get('ATL_meta', 0)).round(1)
    df_daily['TSB_SNC'] = (df_daily['CTLN'] - df_daily.get('ATL_nerveuse', 0)).round(1)

    return df_daily

# ==========================================
# 6. AUTHENTIFICATION & RÔLES
# ==========================================
def login(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        st.session_state.user = res.user
        
        profile = supabase.table("athletes").select("*").eq("user_id", res.user.id).execute()
        if profile.data:
            st.session_state.athlete_info = profile.data[0]
        else:
            # Profil par défaut si non trouvé
            st.session_state.athlete_info = {
                "nom": email, "role": "competiteur", "id": None, 
                "vma": 15.0, "ie_endurance": -7.0, "ip1": 1.0, "ip2": 1.0
            }
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
    col_c1, col_c2, col_c3 = st.columns([1, 2, 1])
    with col_c2:
        with st.form("form_login"):
            st.subheader("Connexion")
            email = st.text_input("E-mail")
            password = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("Se connecter", use_container_width=True):
                login(email, password)
    st.stop()

# ==========================================
# 7. HEADER FIXE ATHLÈTE (CONFORME CDC)
# ==========================================
profil = st.session_state.athlete_info
role = profil.get("role", "competiteur") # "lecteur", "competiteur", "coach"

vma_val = profil.get('vma', 15.0)
vma_100m = convert_vma_to_100m(vma_val)
ie_val = profil.get('ie_endurance', -7.0)
ip1_val = profil.get('ip1', 1.0)
ip2_val = profil.get('ip2', 1.0)

st.markdown(f"""
<div style="display: flex; justify-content: space-between; align-items: center; background-color: #1f2937; padding: 15px 25px; border-radius: 12px; margin-bottom: 20px; border: 1px solid #374151;">
    <div>
        <h2 style="margin: 0; color: #ffffff;">👋 {profil.get('nom', 'Utilisateur')}</h2>
        <span style="color: #94a3b8;">Rôle : <b style="color:#ffffff;">{role.upper()}</b></span>
    </div>
    <div style="text-align: right; font-size: 0.95rem; color: #cbd5e1;">
        VMA : <b style="color:#34d399;">{vma_100m}</b> ({vma_val} km/h) | 
        IE : <b style="color:#60a5fa;">{ie_val}</b> | 
        IP1 : <b style="color:#f59e0b;">{ip1_val}</b> | 
        IP2 : <b style="color:#f59e0b;">{ip2_val}</b>
    </div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 8. GESTION DES ACCÈS ET SIDEBAR
# ==========================================
def get_athletes_dict():
    """Récupère la liste des athlètes avec gestion des erreurs réseau/Supabase."""
    # Vérification préalable des identifiants
    if not url or not key:
        st.warning("⚠️ Les identifiants SUPABASE_URL ou SUPABASE_KEY ne sont pas configurés dans st.secrets.")
        return {}
        
    try:
        res = supabase.table("athletes").select("id, nom").execute()
        if res.data:
            return {str(a["nom"]).strip(): a["id"] for a in res.data if a.get("nom")}
        return {}
    except Exception as e:
        st.error(f"❌ Impossible de se connecter à Supabase : {e}")
        return {}


dict_athletes = get_athletes_dict()

with st.sidebar:
    st.markdown("### ⚡ Options & Navigation")
    if role == "coach":
        nom_selectionne = st.selectbox("Athlète / Groupe sélectionné :", options=["👥 TOUS LES ATHLÈTES"] + sorted(list(dict_athletes.keys())), key="sb_target")
        is_groupe_selected = (nom_selectionne == "👥 TOUS LES ATHLÈTES")
    else:
        nom_selectionne = profil.get("nom")
        is_groupe_selected = False

    st.write("---")
    if st.button("🚪 Déconnexion", use_container_width=True):
        logout()

# ==========================================
# 9. STRUCTURE DES ONGLETS SELON CDC
# ==========================================
if role == "coach":
    tabs = st.tabs([
        "🗓️ Planning Prévu VS Réalisé",
        "📊 Tableaux de bord athlètes",
        "🎯 Calendrier & Objectifs",
        "🚨 Alerte Groupe",
        "📝 Saisie & Prescriptions",
        "⚙️ Admin Coach"
    ])
    tab_plan, tab_dash_ath, tab_cal, tab_alertes, tab_saisie, tab_admin = tabs
else:
    # Mode Compétiteur ou Lecteur
    tabs = st.tabs([
        "🗓️ Page Prévu VS Réalisé",
        "📊 Tableaux de bord athlètes",
        "🎯 Calendrier & Objectifs",
        "📝 Saisie de mon suivi" if role != "lecteur" else "👀 Consultation"
    ])
    tab_plan, tab_dash_ath, tab_cal, tab_saisie = tabs

# ==========================================
# ONGLET 1 : PLANNING PRÉVU VS RÉALISÉ (CDC)
# ==========================================
with tab_plan:
    st.subheader("🗓️ Planning & Suivi Hebdomadaire")
    
    # Sélecteur de semaine (CdC)
    semaine_selected = st.date_input("Sélectionner la semaine (Choisissez un lundi) :", value=datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday()))
    debut_semaine = semaine_selected - datetime.timedelta(days=semaine_selected.weekday())
    fin_semaine = debut_semaine + datetime.timedelta(days=6)

    target_id = dict_athletes.get(nom_selectionne) if role == "coach" and not is_groupe_selected else profil.get("id")

    if target_id:
        raw_seances = supabase.table("seances").select("*").eq("athlete_id", target_id).gte("date_seance", str(debut_semaine)).lte("date_seance", str(fin_semaine)).execute().data
        
        # Structure 8 lignes / 4 colonnes (CdC)
        jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        tableau_planning = []

        for i, j_nom in enumerate(jours):
            d_jour = debut_semaine + datetime.timedelta(days=i)
            seance_jour = [s for s in (raw_seances or []) if s.get('date_seance') == str(d_jour)]
            
            desc_text = ""
            vol_km = 0.0
            rpe_val = ""

            for s in seance_jour:
                # Masquage si séance programmée future cachée par le coach
                if s.get('masquer_jusqu_j', False) and role != "coach" and d_jour > datetime.date.today():
                    continue

                is_prevu = s.get('est_prevu', False)
                color_class = "text-prevu" if is_prevu else "text-realise"
                prefix = "[PRÉVU]" if is_prevu else "[RÉALISÉ]"
                
                types_str = ", ".join(s.get('types_seance', [])) if isinstance(s.get('types_seance'), list) else s.get('type_seance', '')
                desc_text += f"<div class='{color_class}'>{prefix} {s.get('sport','')} - {types_str} : {s.get('commentaire','')}</div>"
                vol_km += float(s.get('km_eq', 0))
                rpe_val += f"{s.get('rpe', '-')}/10 "

            tableau_planning.append({
                "Jour de la semaine": f"{j_nom} ({d_jour.strftime('%d/%m')})",
                "Descriptif": desc_text if desc_text else "<span style='color:#4b5563;'>Repos / Aucune séance</span>",
                "Volume (km_eq)": f"{vol_km:.1f} km",
                "RPE / 10": rpe_val if rpe_val else "-"
            })

        df_plan_visu = pd.DataFrame(tableau_planning)
        st.write(df_plan_visu.to_html(escape=False, index=False), unsafe_allow_html=True)

# ==========================================
# ONGLET 2 : TABLEAUX DE BORD ATHLÈTES (CDC)
# ==========================================
with tab_dash_ath:
    st.subheader("📊 Tableaux de Bord & Analyse de Forme")

    target_id = dict_athletes.get(nom_selectionne) if role == "coach" and not is_groupe_selected else profil.get("id")

    if target_id:
        seances = supabase.table("seances").select("*").eq("athlete_id", target_id).order("date_seance", desc=False).execute().data
        if seances and len(seances) >= 2:
            df_daily = calculer_acwr(pd.DataFrame(seances))
            
            st.markdown("### 1) Suivi Instantané (Profil de Forme 7 jours)")
            afficher_radar_etat_de_forme(df_daily)

            st.write("---")
            st.markdown("### 📈 Courbe de Strain & Résistance Limite (1.6 * CTL)")
            fig_st = go.Figure()
            fig_st.add_trace(go.Scatter(x=df_daily['date_seance'], y=df_daily['strain'], name="Strain Réalisé", line=dict(color='#ef4444', width=2)))
            fig_st.add_trace(go.Scatter(x=df_daily['date_seance'], y=df_daily['resistance_strain'], name="Résistance Maximale (1.6*CTL)", line=dict(color='#f59e0b', width=2, dash='dash')))
            fig_st.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis_title="Strain (AU)")
            st.plotly_chart(fig_st, use_container_width=True)

            st.write("---")
            st.markdown("### 2) Macro-suivi de la Charge (Empilé par Filière & Volume km)")
            
            # Histogramme empilé par filière
            fig_macro = go.Figure()
            fig_macro.add_trace(go.Bar(x=df_daily['date_seance'], y=df_daily['charge_meta'], name="Charge Base / Aérobie", marker_color='#3b82f6'))
            fig_macro.add_trace(go.Bar(x=df_daily['date_seance'], y=df_daily['charge_nerveuse'], name="Charge Anaérobie (SNC)", marker_color='#ef4444'))
            fig_macro.update_layout(barmode='stack', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis_title="Charge AU")
            st.plotly_chart(fig_macro, use_container_width=True)

# ==========================================
# ONGLET 3 : CALENDRIER & OBJECTIFS (CDC)
# ==========================================
with tab_cal:
    st.subheader("🎯 Calendrier & Saisie des Objectifs")

    target_id = dict_athletes.get(nom_selectionne) if role == "coach" and not is_groupe_selected else profil.get("id")

    col_add, col_visu = st.columns([1, 1])

    with col_add:
        if role in ["coach", "competiteur"]:
            st.markdown("### Fixer un Objectif")
            with st.form("form_obj"):
                nom_obj = st.text_input("Intitulé de l'objectif")
                d_obj = st.date_input("Date")
                prio = st.selectbox("Priorité", ["A", "B", "C"])
                justif = st.text_area("Justificatif / Stratégie")
                if st.form_submit_button("Enregistrer l'objectif", use_container_width=True):
                    supabase.table("objectifs").insert({
                        "athlete_id": target_id, "nom_evenement": nom_obj, 
                        "date_objectif": str(d_obj), "priorite": prio, "commentaire": justif
                    }).execute()
                    st.success("Objectif enregistré !")
                    st.rerun()

    with col_visu:
        st.markdown("### Liste & Validation des Objectifs")
        if target_id:
            objs = supabase.table("objectifs").select("*").eq("athlete_id", target_id).execute().data
            if objs:
                for o in objs:
                    realise = st.checkbox(f"{o['date_objectif']} - {o['nom_evenement']} (Prio {o['priorite']})", value=o.get('realise', False), key=f"obj_{o['id']}")
                    if realise != o.get('realise', False):
                        supabase.table("objectifs").update({"realise": realise}).eq("id", o['id']).execute()
                        st.rerun()

# ==========================================
# ONGLET 4 (COACH) : ALERTE GROUPE (CDC)
# ==========================================
if role == "coach":
    with tab_alertes:
        st.subheader("🚨 Centre d'Alertes Groupe")
        dict_ath = get_athletes_dict()
        
        if not dict_ath:
            st.info("ℹ️ Aucun athlète enregistré dans la base de données.")
        else:
            alertes_trouvees = 0
            athletes_charges_insuffisantes = []

            for nom_a, id_a in dict_ath.items():
                seances_a = supabase.table("seances").select("*").eq("athlete_id", id_a).execute().data
                
                if seances_a and len(seances_a) >= 2:
                    df_a = calculer_acwr(pd.DataFrame(seances_a))
                    last_a = df_a.iloc[-1]
                    
                    # Détection des anomalies
                    is_acwr_critique = last_a['acwr'] > 1.5
                    is_mono_critique = last_a['monotonie'] > 2.0
                    
                    if is_acwr_critique or is_mono_critique:
                        alertes_trouvees += 1
                        st.error(
                            f"⚠️ **{nom_a}** en Zone Critique !\n\n"
                            f"* **ACWR :** `{last_a['acwr']}` (Seuil max : 1.5)\n"
                            f"* **Monotonie :** `{last_a['monotonie']}` (Seuil max : 2.0)"
                        )
                else:
                    athletes_charges_insuffisantes.append(nom_a)

            # Si aucune alerte n'a été déclenchée
            if alertes_trouvees == 0:
                st.success("✅ **Toutes les voyants sont au vert !** Aucun athlète ne présente de surcharge ou de monotonie critique actuellement.")

            # Petit rappel indicatif sur les données manquantes
            if athletes_charges_insuffisantes:
                with st.expander("ℹ️ Athlètes avec données insuffisantes (< 2 séances)"):
                    st.write(", ".join(athletes_charges_insuffisantes))


# ==========================================
# ONGLET : SAISIE & PRESCRIPTIONS (CDC)
# ==========================================
if role != "lecteur":
    with tab_saisie:
        st.subheader("📝 Saisie des Séances & Prescriptions")

        with st.form("form_seance_cdc", clear_on_submit=True):
            d_seance = st.date_input("Date de la séance", value=datetime.date.today())

            c1, c2, c3 = st.columns(3)
            with c1:
                sport = st.selectbox("Sport", ["Course à pied", "Trail", "Cyclisme", "Natation", "Renforcement", "Autre"])
                nb_repetition = st.number_input("Nombre de répétitions (1 à 50)", min_value=1, max_value=50, value=1)
            
            with c2:
                # Choix multiple type de séance (CdC)
                types_seance = st.multiselect(
                    "Type de séance (Choix multiples) :",
                    ["🏃 Endurance", "⚡ VMA", "⛰️ Dénivelé", "🏋️ Renforcement", "🧘 Récupération", "🚴 Vélo d'assaut"]
                )
                allure_input = st.text_input("Allure moyenne (Ex: 4:30/km ou 0'25\"/100m)")

            with c3:
                duree = st.number_input("Durée (min)", min_value=5, max_value=600, value=60, step=5)
                pct_vma_estime = st.number_input("% VMA moyen estimé", min_value=30, max_value=200, value=75)

            # Déduction auto de la filière
            filiere_auto = deduire_filiere(pct_vma_estime)
            st.info(f"💡 Filière énergétique déduite : **{filiere_auto}**")

            st.write("---")
            st.markdown("##### 🎚️ Évaluations & RPE (Échelle CdC)")

            cr1, cr2 = st.columns(2)
            with cr1:
                # Échelle RPE : 1 à 7 puis 0.5 jusqu'à 10 (CdC)
                rpe_options = [1, 2, 3, 4, 5, 6, 7, 7.5, 8, 8.5, 9, 9.5, 10]
                rpe_athlete = st.select_slider("RPE Athlète (1 à 10)", options=rpe_options, value=5)
                jambes = st.slider("État des jambes (1 = Lourdes, 10 = Frais)", 1, 10, 5)

            with cr2:
                # Fusion Raideur matinale & Douleurs articulaires = Casse Mécanique (CdC)
                casse_mecanique = st.slider("Casse Mécanique (Raideur / Douleurs articulaires)", 1, 10, 1)
                batterie = st.slider("Motivation / SNC", 1, 10, 5)

            rpe_coach_val = None
            masquer_j = False
            if role == "coach":
                st.write("---")
                st.markdown("##### 🏋️ Options Entraîneur / Coach")
                cp1, cp2 = st.columns(2)
                with cp1:
                    rpe_coach_val = st.select_slider("RPE Pondéré par le Coach (Poids 1/3)", options=rpe_options, value=rpe_athlete)
                with cp2:
                    masquer_j = st.checkbox("Cacher la séance programmée aux athlètes jusqu'au Jour J")

            commentaires = st.text_area("Commentaires / Descriptif séance")

            if st.form_submit_button("🚀 Valider la séance", use_container_width=True):
                target_user_id = dict_athletes.get(nom_selectionne) if role == "coach" and not is_groupe_selected else profil.get("id")
                
                c_globale, km_eq, c_meta, c_nerv, c_meca, rpe_eff = calculer_triple_charge(
                    duree, rpe_athlete, sport, batterie, jambes, casse_mecanique, rpe_coach_val
                )

                payload = {
                    "athlete_id": target_user_id,
                    "date_seance": str(d_seance),
                    "sport": sport,
                    "nb_repetitions": int(nb_repetition),
                    "types_seance": types_seance,
                    "duree_min": int(duree),
                    "rpe": float(rpe_eff),
                    "rpe_athlete": float(rpe_athlete),
                    "rpe_coach": float(rpe_coach_val) if rpe_coach_val else None,
                    "jambes": int(jambes),
                    "casse_mecanique": int(casse_mecanique),
                    "batterie": int(batterie),
                    "km_eq": float(km_eq),
                    "charge_meta": float(c_meta),
                    "charge_nerveuse": float(c_nerv),
                    "charge_meca": float(c_meca),
                    "commentaire": commentaires,
                    "est_prevu": (role == "coach" and d_seance > datetime.date.today()),
                    "masquer_jusqu_j": masquer_j
                }

                try:
                    supabase.table("seances").insert(payload).execute()
                    st.success("Séance enregistrée avec succès !")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erreur Supabase : {e}")
# Helper pour convertir en float de manière sécurisée (gère les None / NULL de Supabase)
def safe_float(val, default=0.0):
    if val is None:
        return float(default)
    try:
        return float(val)
    except (ValueError, TypeError):
        return float(default)

# ==========================================
# ONGLET ADMIN (COACH UNIQUEMENT)
# ==========================================
if role == "coach":
    with tab_admin:
        st.subheader("⚙️ Administration & Configuration")
        
        tab_adm1, tab_adm2, tab_adm3 = st.tabs([
            "👥 Gestion des Athlètes", 
            "➕ Ajouter un Athlète", 
            "🧮 Paramètres du Moteur (ATL/CTL)"
        ])

        # --- SOUS-ONGLET 1 : ÉDITION DES PROFILS EXISTANTS & SÉCURITÉ ---
        with tab_adm1:
            st.markdown("### 📝 Editer les profils et paramètres de sécurité")
            
            # Récupération de tous les athlètes dans Supabase
            req_ath = supabase.table("athletes").select("*").execute()
            list_athletes = req_ath.data if req_ath.data else []

            if not list_athletes:
                st.warning("Aucun profil d'athlète trouvé dans la table 'athletes'.")
            else:
                # Choix de l'athlète à modifier
                dict_names = {f"{a.get('nom', 'Sans nom')} ({a.get('role', 'N/A')})": a for a in list_athletes}
                selected_name = st.selectbox(
                    "Sélectionner un athlète à éditer :", 
                    list(dict_names.keys()), 
                    key="sb_select_athlete_to_edit"
                )
                athlete_data = dict_names[selected_name]

                # 💡 CLÉ UNIQUE SÉCURISÉE POUR LE FORMULAIRE
                form_key = f"form_edit_ath_{athlete_data.get('id', 'no_id')}_{hash(selected_name)}"

                # --- FORMULAIRE D'ÉDITION ---
                with st.form(key=form_key):
                    col_e1, col_e2 = st.columns(2)
                    
                    with col_e1:
                        nom_edit = st.text_input("Nom complet", value=athlete_data.get('nom') or '')
                        email_edit = st.text_input("Adresse E-mail", value=athlete_data.get('email') or '')
                        
                        current_role = athlete_data.get('role') or 'competiteur'
                        roles_list = ["competiteur", "lecteur", "coach"]
                        role_index = roles_list.index(current_role) if current_role in roles_list else 0
                        role_edit = st.selectbox(
                            "Rôle attribué", 
                            roles_list, 
                            index=role_index,
                            key=f"sb_role_edit_{form_key}"
                        )
                        
                        vma_edit = st.number_input(
                            "VMA (km/h)", 
                            min_value=8.0, 
                            max_value=28.0, 
                            value=safe_float(athlete_data.get('vma'), 15.0), 
                            step=0.5,
                            key=f"num_vma_{form_key}"
                        )

                    with col_e2:
                        ie_edit = st.number_input(
                            "Indice d'Endurance (IE)", 
                            min_value=-15.0, 
                            max_value=0.0, 
                            value=safe_float(athlete_data.get('ie_endurance'), -7.0), 
                            step=0.1,
                            key=f"num_ie_{form_key}"
                        )
                        ip1_edit = st.number_input(
                            "Indice de Puissance 1 (IP1)", 
                            min_value=0.1, 
                            max_value=5.0, 
                            value=safe_float(athlete_data.get('ip1'), 1.0), 
                            step=0.1,
                            key=f"num_ip1_{form_key}"
                        )
                        ip2_edit = st.number_input(
                            "Indice de Puissance 2 (IP2)", 
                            min_value=0.1, 
                            max_value=5.0, 
                            value=safe_float(athlete_data.get('ip2'), 1.0), 
                            step=0.1,
                            key=f"num_ip2_{form_key}"
                        )
                        
                        force_pwd_edit = st.checkbox(
                            "🔒 Forcer la saisie d'un nouveau mot de passe à la prochaine connexion", 
                            value=bool(athlete_data.get('force_reset_pwd', False)),
                            key=f"chk_pwd_{form_key}"
                        )

                    # Bouton d'envoi OBLIGATOIRE du formulaire
                    submit_edit = st.form_submit_button("💾 Enregistrer les modifications", use_container_width=True)
                    
                    if submit_edit:
                        update_payload = {
                            "nom": nom_edit,
                            "email": email_edit,
                            "role": role_edit,
                            "vma": float(vma_edit),
                            "ie_endurance": float(ie_edit),
                            "ip1": float(ip1_edit),
                            "ip2": float(ip2_edit),
                            "force_reset_pwd": force_pwd_edit
                        }
                        try:
                            supabase.table("athletes").update(update_payload).eq("id", athlete_data['id']).execute()
                            st.success(f"Profil de {nom_edit} mis à jour avec succès !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur lors de la mise à jour : {e}")

                # --- SECTION INDÉPENDANTE HORS DU FORMULAIRE ---
                st.write("---")
                st.markdown("##### 🔐 Réinitialisation directe par E-mail")
                col_reset1, col_reset2 = st.columns([3, 1])
                with col_reset1:
                    st.caption(f"Envoie un e-mail officiel de réinitialisation de mot de passe à : **{athlete_data.get('email') or 'Non renseigné'}**")
                with col_reset2:
                    if st.button("📧 Envoyer Mail Reset", key=f"btn_reset_mail_{athlete_data['id']}", use_container_width=True):
                        target_email = athlete_data.get('email')
                        if target_email:
                            try:
                                # Force la redirection vers l'URL exacte de ton appli Streamlit
                                supabase.auth.reset_password_for_email(
                                    target_email,
                                    options={
                                        "redirect_to": "https://performance-engine-mk9cj73dgjoezq6wmwwdo9.streamlit.app/"  # 👈 REMPLACE PAR TON URL DEPLOIEMENT STREAMLIT
                                    }
                                )
                                st.success(f"E-mail de réinitialisation envoyé à {target_email} !")
                            except Exception as e:
                                st.error(f"Erreur d'envoi : {e}")

        # --- SOUS-ONGLET 2 : AJOUT D'UN NOUVEL ATHLÈTE ---
        with tab_adm2:
            st.markdown("### ➕ Créer une nouvelle fiche athlète")
            
            form_add_key = "form_create_new_athlete_v3"
            
            with st.form(key=form_add_key, clear_on_submit=True):
                ca1, ca2 = st.columns(2)
                with ca1:
                    new_nom = st.text_input("Nom & Prénom *", key=f"add_nom_{form_add_key}")
                    new_email = st.text_input("Adresse E-mail", key=f"add_email_{form_add_key}")
                    new_role = st.selectbox("Rôle", ["competiteur", "lecteur", "coach"], key=f"add_role_{form_add_key}")
                    new_vma = st.number_input("VMA initiale (km/h)", value=15.0, step=0.5, key=f"add_vma_{form_add_key}")
                with ca2:
                    new_ie = st.number_input("IE initial", value=-7.0, step=0.5, key=f"add_ie_{form_add_key}")
                    new_ip1 = st.number_input("IP1 initial", value=1.0, step=0.1, key=f"add_ip1_{form_add_key}")
                    new_ip2 = st.number_input("IP2 initial", value=1.0, step=0.1, key=f"add_ip2_{form_add_key}")
                    new_force_pwd = st.checkbox("🔒 Obliger à définir un mot de passe à la 1ère connexion", value=True, key=f"add_force_pwd_{form_add_key}")
                
                submit_add = st.form_submit_button("✨ Créer le profil", use_container_width=True)
                
                if submit_add:
                    if not new_nom.strip():
                        st.error("Le nom de l'athlète est obligatoire.")
                    else:
                        new_payload = {
                            "nom": new_nom.strip(),
                            "email": new_email.strip(),
                            "role": new_role,
                            "vma": float(new_vma),
                            "ie_endurance": float(new_ie),
                            "ip1": float(new_ip1),
                            "ip2": float(new_ip2),
                            "force_reset_pwd": new_force_pwd
                        }
                        try:
                            supabase.table("athletes").insert(new_payload).execute()
                            st.success(f"L'athlète **{new_nom}** a été ajouté avec succès !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur Supabase lors de la création : {e}")

        # --- SOUS-ONGLET 3 : HYPOTHÈSES DE CALCUL & CONSTANTES ---
        with tab_adm3:
            st.markdown("### 📐 Constantes globales du moteur de charge")
            st.info(
                "Ces constantes définissent les fenêtres de lissage exponentiel (EWMA) "
                "utilisées pour calculer la Fatigue Aiguë (ATL) et la Forme Chronique (CTL)."
            )
            
            c_p1, c_p2 = st.columns(2)
            with c_p1:
                st.number_input(
                    "Fenêtre Fatigue Aiguë ATL (jours)", 
                    min_value=3, 
                    max_value=14, 
                    value=7, 
                    disabled=True,
                    key="cfg_atl_window_days_l1027"
                )
                st.caption("Standard Banister : 7 jours")
            with c_p2:
                st.number_input(
                    "Fenêtre Charge Chronique CTL (jours)", 
                    min_value=14, 
                    max_value=60, 
                    value=28, 
                    disabled=True,
                    key="cfg_ctl_window_days_l1027"
                )
                st.caption("Standard Banister : 28 jours")
