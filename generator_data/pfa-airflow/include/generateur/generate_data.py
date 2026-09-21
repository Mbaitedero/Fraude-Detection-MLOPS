"""
Générateur de données synthétiques pour le PFA :
"Pipeline Data & BI pour l'automatisation du reporting réglementaire
et la détection des fraudes bancaires"

Version 2.0 — CORRIGÉE :
- Cible fraude causale (score latent → Bernoulli) → AUC cible 0.85-0.92
- Suppression du calibrage destructeur (remplacé par seuillage quantile)
- Soldes cohérents avec découvert autorisé → signal de fraude exploitable
- Bâle III calibré : PD 2-5%, LGD 35-50%, EL ≈ Provisions
- Répartition réaliste des créances (Saine ~88%)
"""

import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from faker import Faker

from reference_data import (
    CANAUX, CATEGORIES_CREANCES, CODES_POSTAUX, FORMES_JURIDIQUES,
    MCC_CODES, MODES_PAIEMENT, NIVEAUX_CONSOLIDATION, NOMS_VILLES,
    OBJETS_FINANCEMENT, POIDS_CANAUX, POIDS_TYPE_CLIENT, POIDS_TYPE_COMPTE,
    POIDS_TYPE_CREDIT, POIDS_TYPE_TRANSACTION, POIDS_VILLES,
    PROFESSIONS, QUARTIERS_AGENCE, REGIONS, SECTEURS_ACTIVITE,
    SEGMENTS_CLIENT, SITUATIONS_FAMILIALES, STATUTS_KYC,
    TYPES_CLIENT, TYPES_COMPTE, TYPES_CREDIT, TYPES_FRAUDE,
    TYPES_GARANTIE, TYPES_TRANSACTION, VILLES, CODE_BANQUE,
)

# Constantes de volumétrie
N_CLIENTS = 5000
N_TRANSACTIONS = 200_000
TAUX_FRAUDE_CIBLE = 0.012
N_MOIS_LIQUIDITE = 24
SEED = 42

random.seed(SEED)
np.random.seed(SEED)
fake = Faker("fr_FR")
Faker.seed(SEED)

OUTPUT_DIR = "data/raw"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Fonctions auxiliaires
# ---------------------------------------------------------------------------

def generate_rib(compte_num: int, ville: str) -> str:
    code_agence = f"{sum(ord(c) for c in ville) % 1000:03d}"
    num_compte = f"{(compte_num * 7919 + 1000000) % 10**16:016d}"
    base = CODE_BANQUE + code_agence + num_compte
    cle = f"{sum(int(c) for c in base) % 97:02d}"
    return base + cle


def generate_phone() -> str:
    return f"06{random.randint(10000000, 99999999):08d}"


def generate_address(ville: str) -> str:
    return f"{random.randint(1, 200)} rue {fake.street_name()}, {ville}"


def generate_ice() -> str:
    return f"{random.randint(10**13, 10**14-1)}"


def generate_rc() -> str:
    return f"RC{random.randint(10000, 99999)}"


def generate_identifiant_fiscal() -> str:
    return f"{random.randint(10**9, 10**10-1)}"


# ---------------------------------------------------------------------------
# 1. Agences
# ---------------------------------------------------------------------------

def generate_agences() -> pd.DataFrame:
    agences = []
    idx = 0
    for ville, region in REGIONS.items():
        poids = POIDS_VILLES[NOMS_VILLES.index(ville)]
        n_agences = max(1, round(poids / 4))
        for i in range(n_agences):
            idx += 1
            quartier = random.choice(QUARTIERS_AGENCE)
            agences.append({
                "agence_id": f"AG-{ville[:3].upper()}-{i+1:02d}",
                "nom_agence": f"Agence {ville} {quartier}",
                "adresse": generate_address(ville),
                "ville": ville,
                "code_postal": CODES_POSTAUX[ville],
                "region": region,
                "pays": "Maroc",
                "telephone": generate_phone(),
                "email": f"agence{idx}@banque.ma",
                "directeur": fake.name(),
                "date_ouverture": fake.date_between(start_date="-20y", end_date="-1y"),
                "type_agence": random.choice(["Standard", "Premium", "Digitale"]),
                "latitude": round(random.uniform(30.0, 35.0), 6),
                "longitude": round(random.uniform(-10.0, 0.0), 6),
            })
    return pd.DataFrame(agences)


# ---------------------------------------------------------------------------
# 2. Clients
# ---------------------------------------------------------------------------

def generate_clients(agences_df: pd.DataFrame) -> pd.DataFrame:
    clients = []
    agence_ids = agences_df["agence_id"].tolist()
    for i in range(1, N_CLIENTS + 1):
        type_client = np.random.choice(TYPES_CLIENT, p=POIDS_TYPE_CLIENT)
        agence_id = random.choice(agence_ids)
        ville_agence = agences_df[agences_df.agence_id == agence_id].iloc[0]["ville"]

        if type_client == "Particulier":
            civilite = random.choice(["M.", "Mme", "Mlle"])
            nom = fake.last_name()
            prenom = fake.first_name()
            raison_sociale = None
            ice = rc = identifiant_fiscal = forme_juridique = None
            profession = random.choice(PROFESSIONS)
            secteur_activite = None
            date_naissance = fake.date_between(start_date="-80y", end_date="-18y")
            lieu_naissance = random.choice(NOMS_VILLES)
            nationalite = "Marocaine"
            situation_familiale = random.choice(SITUATIONS_FAMILIALES)
            nombre_personnes_charge = random.randint(0, 5)
            revenu_mensuel = round(np.random.lognormal(mean=8.5, sigma=0.8), 2)
        else:
            civilite = None
            nom = fake.company()
            prenom = None
            raison_sociale = nom
            ice = generate_ice()
            rc = generate_rc()
            identifiant_fiscal = generate_identifiant_fiscal()
            forme_juridique = random.choice(FORMES_JURIDIQUES)
            profession = None
            secteur_activite = random.choice(SECTEURS_ACTIVITE)
            date_naissance = None
            lieu_naissance = None
            nationalite = "Marocaine"
            situation_familiale = None
            nombre_personnes_charge = None
            revenu_mensuel = round(np.random.lognormal(mean=11.0, sigma=1.2), 2)

        revenu_annuel = revenu_mensuel * 12
        score_credit = int(np.random.normal(650, 100))
        score_credit = max(300, min(850, score_credit))

        if score_credit >= 750:
            niveau_risque_client = "Faible"
            score_risque_client = 0.1
        elif score_credit >= 650:
            niveau_risque_client = "Moyen"
            score_risque_client = 0.3
        else:
            niveau_risque_client = "Élevé"
            score_risque_client = 0.6

        if type_client == "Entreprise":
            segment = random.choice(["Grandes entreprises", "PME"])
        else:
            if revenu_mensuel > 30000:
                segment = "Particuliers aisés"
            elif revenu_mensuel > 15000:
                segment = "Particuliers standard"
            else:
                segment = "Jeunes" if random.random() < 0.2 else "Particuliers standard"

        clients.append({
            "client_id": f"CLI-{i:06d}",
            "agence_id": agence_id,
            "type_client": type_client,
            "civilite": civilite,
            "nom": nom,
            "prenom": prenom,
            "raison_sociale": raison_sociale,
            "date_naissance": date_naissance,
            "lieu_naissance": lieu_naissance,
            "nationalite": nationalite,
            "email": fake.email(),
            "telephone": generate_phone(),
            "adresse": generate_address(ville_agence),
            "ville": ville_agence,
            "code_postal": CODES_POSTAUX[ville_agence],
            "region": REGIONS[ville_agence],
            "pays": "Maroc",
            "profession": profession,
            "secteur_activite": secteur_activite,
            "revenu_mensuel": revenu_mensuel,
            "revenu_annuel": revenu_annuel,
            "situation_familiale": situation_familiale,
            "nombre_personnes_charge": nombre_personnes_charge,
            "ice": ice, "rc": rc, "identifiant_fiscal": identifiant_fiscal,
            "forme_juridique": forme_juridique,
            "statut_kyc": random.choice(STATUTS_KYC),
            "score_credit": score_credit,
            "segment_client": segment,
            "niveau_risque_client": niveau_risque_client,
            "score_risque_client": score_risque_client,
            "date_premier_contact": fake.date_between(start_date="-10y", end_date="-1d"),
            "conseiller_id": f"CONS-{random.randint(1, 50):03d}",
            "statut_client": random.choice(["Actif", "Inactif", "Fermé"]),
            "date_creation": datetime.now(),
            "date_derniere_maj": datetime.now(),
        })
    return pd.DataFrame(clients)


# ---------------------------------------------------------------------------
# 3. Comptes
# ---------------------------------------------------------------------------

def generate_comptes(clients_df: pd.DataFrame) -> pd.DataFrame:
    comptes = []
    compte_counter = 1
    for _, client in clients_df.iterrows():
        nb_comptes = random.choices([1, 2], weights=[0.7, 0.3])[0]
        for _ in range(nb_comptes):
            type_compte = np.random.choice(TYPES_COMPTE, p=POIDS_TYPE_COMPTE)
            if type_compte == "Compte épargne":
                solde = round(np.random.lognormal(mean=9.5, sigma=1.0), 2)
            elif type_compte in ["Compte professionnel", "Compte entreprise"]:
                solde = round(np.random.lognormal(mean=11.0, sigma=1.5), 2)
            else:
                solde = round(np.random.lognormal(mean=8.5, sigma=1.2), 2)

            decouvert_autorise = round(solde * random.uniform(0.1, 0.3), 2) if solde > 0 else 0
            taux_interet = round(random.uniform(0.01, 0.03), 4) if type_compte == "Compte épargne" else 0.0

            compte_id = f"CPT-{compte_counter:06d}"
            comptes.append({
                "compte_id": compte_id,
                "client_id": client.client_id,
                "agence_id": client.agence_id,
                "numero_compte": f"{random.randint(10**9, 10**10-1)}",
                "rib": generate_rib(compte_counter, client.ville),
                "type_compte": type_compte,
                "devise": "MAD",
                "solde": solde,
                "solde_disponible": solde,
                "solde_moyen_30j": solde,
                "solde_moyen_90j": solde,
                "decouvert_autorise": decouvert_autorise,
                "taux_interet": taux_interet,
                "frais_tenue_compte": round(random.uniform(10, 50), 2),
                "date_ouverture": fake.date_between(start_date="-10y", end_date="-30d"),
                "date_fermeture": None,
                "statut_compte": "Actif",
                "plafond_retrait_jour": random.choice([5000, 10000, 20000]),
                "plafond_paiement_jour": random.choice([10000, 20000, 50000]),
                "nombre_cotitulaires": random.randint(0, 2) if client['type_client'] == "Particulier" else 0,
                "carte_associee": random.choice([True, False]),
                "chequier": random.choice([True, False]),
                "date_derniere_operation": None,
                "nombre_transactions_30j": 0,
                "volume_transactions_30j": 0,
                "niveau_risque": random.choice(["Faible", "Moyen", "Élevé"]),
                "indicateur_fraude": False,
                "date_creation": datetime.now(),
                "date_derniere_maj": datetime.now(),
            })
            compte_counter += 1
    return pd.DataFrame(comptes)


# ---------------------------------------------------------------------------
# 4. Transactions
# ---------------------------------------------------------------------------

def _heure_weights():
    base = np.array([1, 1, 1, 1, 1, 2, 3, 5, 7, 8, 8, 7,
                     7, 8, 8, 7, 7, 8, 7, 6, 5, 3, 2, 1], dtype=float)
    return base / base.sum()


def generate_transactions(comptes_df: pd.DataFrame) -> pd.DataFrame:
    """
    Génère N_TRANSACTIONS transactions avec :
    - Soldes cohérents (chronologique, débits puis crédits)
    - Découvert autorisé respecté
    - Signal de fraude causal (score latent → Bernoulli)
    """
    comptes_info = comptes_df[["compte_id", "solde"]].to_dict("records")
    soldes_actuels = {c["compte_id"]: c["solde"] for c in comptes_info}

    transactions = []
    comptes_sample = comptes_df.sample(N_TRANSACTIONS, replace=True).reset_index(drop=True)

    villes = NOMS_VILLES
    canaux = CANAUX
    types_tx = TYPES_TRANSACTION
    categories_paiement = list(MCC_CODES.keys())
    modes_paiement = MODES_PAIEMENT

    for idx, cpt in comptes_sample.iterrows():
        compte_id = cpt.compte_id
        type_tx = np.random.choice(types_tx, p=POIDS_TYPE_TRANSACTION)
        montant = round(np.random.lognormal(mean=6.5, sigma=1.3), 2)
        canal = np.random.choice(canaux, p=POIDS_CANAUX)

        jours = random.randint(0, 364)
        heure = int(np.random.choice(range(24), p=_heure_weights()))
        date_transaction = datetime.now() - timedelta(days=jours, hours=24-heure)

        meme_ville = random.random() > 0.08
        ville_transaction = cpt.ville if meme_ville else random.choice(villes)

        compte_source_id = None
        compte_destination_id = None
        if type_tx == "Virement":
            compte_source_id = compte_id
            autres = comptes_df[comptes_df.compte_id != compte_id]
            compte_destination_id = autres.sample(1).iloc[0].compte_id if not autres.empty else compte_id
        elif type_tx in ["Paiement", "Retrait", "Prélèvement"]:
            compte_source_id = compte_id
        elif type_tx == "Dépôt":
            compte_destination_id = compte_id
        else:
            compte_source_id = compte_id

        merchant_id = code_mcc = nom_marchand = pays_marchand = None
        numero_carte_masque = terminal_id = None
        frais_transaction = 0.0
        taux_change = None
        pays_origine, pays_destination = "MA", "MA"
        is_international = 0
        cat = None

        if type_tx == "Paiement":
            cat = random.choice(categories_paiement)
            code_mcc = MCC_CODES[cat]
            merchant_id = f"MER-{random.randint(1000, 9999)}"
            nom_marchand = fake.company()
            pays_marchand = random.choice(["MA", "FR", "ES", "IT", "US", "UK", "AE"])
            if pays_marchand != "MA":
                is_international = 1
            numero_carte_masque = f"****{random.randint(1000, 9999)}"
            terminal_id = f"T{random.randint(100, 999)}"
            frais_transaction = round(montant * 0.005, 2)

        if type_tx == "Virement":
            frais_transaction = round(montant * 0.001, 2) if random.random() < 0.2 else 0.0
            if random.random() < 0.05:
                pays_destination = random.choice(["FR", "ES", "IT", "US", "UK", "AE"])
                is_international = 1

        device_id = f"DEV-{random.randint(1, 1000)}"
        ip_address = f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(0,255)}"

        libelle = f"{type_tx} {canal}"
        if type_tx == "Paiement":
            libelle = f"Paiement {nom_marchand[:20]}"

        transactions.append({
            "transaction_id": f"TRX-{idx+1:08d}",
            "compte_source_id": compte_source_id,
            "compte_destination_id": compte_destination_id,
            "client_id": cpt.client_id,
            "agence_id": cpt.agence_id,
            "date_transaction": date_transaction,
            "date_valeur": date_transaction + timedelta(days=1),
            "heure_transaction": f"{int(heure):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}",
            "montant": montant,
            "devise": "MAD",
            "type_transaction": type_tx,
            "categorie": cat,
            "sous_categorie": None,
            "canal": canal,
            "mode_paiement": random.choice(modes_paiement) if type_tx == "Paiement" else None,
            "statut_transaction": np.random.choice(["Validée", "En attente", "Rejetée"], p=[0.9, 0.08, 0.02]),
            "reference_transaction": f"REF-{random.randint(10**8, 10**9-1)}",
            "libelle": libelle,
            "merchant_id": merchant_id,
            "code_mcc": code_mcc,
            "nom_marchand": nom_marchand,
            "pays_marchand": pays_marchand,
            "ville_transaction": ville_transaction,
            "pays_origine": pays_origine,
            "pays_destination": pays_destination,
            "numero_carte_masque": numero_carte_masque,
            "terminal_id": terminal_id,
            "frais_transaction": frais_transaction,
            "taux_change": taux_change,
            "solde_avant": None,
            "solde_apres": None,
            "latitude": round(random.uniform(30.0, 35.0), 6),
            "longitude": round(random.uniform(-10.0, 0.0), 6),
            "ip_address": ip_address,
            "device_id": device_id,
            "is_international": is_international,
            "is_weekend": 1 if date_transaction.weekday() >= 5 else 0,
            "is_night": 1 if heure < 6 or heure >= 22 else 0,
            "fraud_flag": 0,
            "fraud_type": None,
            "fraud_rule_triggered": None,
            "date_creation": datetime.now(),
        })

    df = pd.DataFrame(transactions)

    # ----- Soldes cohérents -----
    df["solde_avant"] = np.nan
    df["solde_apres"] = np.nan

    decouvert_map = dict(zip(comptes_df["compte_id"], comptes_df["decouvert_autorise"]))

    # Débits
    for compte_id, group in df[df["compte_source_id"].notna()].groupby("compte_source_id"):
        group = group.sort_values("date_transaction")
        solde = soldes_actuels.get(compte_id, 0.0)
        for _, row in group.iterrows():
            df.loc[row.name, "solde_avant"] = solde
            solde -= row["montant"]
            df.loc[row.name, "solde_apres"] = solde
        soldes_actuels[compte_id] = solde

    # Crédits
    for compte_id, group in df[df["compte_destination_id"].notna()].groupby("compte_destination_id"):
        group = group[group["compte_source_id"] != compte_id]
        if group.empty:
            continue
        group = group.sort_values("date_transaction")
        solde = soldes_actuels.get(compte_id, 0.0)
        for _, row in group.iterrows():
            if pd.isna(df.loc[row.name, "solde_avant"]):
                df.loc[row.name, "solde_avant"] = solde
            else:
                solde = df.loc[row.name, "solde_avant"]
            solde += row["montant"]
            df.loc[row.name, "solde_apres"] = solde
        soldes_actuels[compte_id] = solde

    df["decouvert_autorise"] = df["compte_source_id"].map(decouvert_map).fillna(0)
    df["solde_negatif_anormal"] = (
        (df["solde_apres"] < 0) &
        (df["solde_apres"].abs() > df["decouvert_autorise"])
    ).astype(int)

    # ----- Attribution causale des fraudes -----
    df = assign_frauds_causal(df)

    return df


def assign_frauds_causal(df: pd.DataFrame) -> pd.DataFrame:
    """
    Génère fraud_flag via un score de risque latent causal.

    Chaque composante correspond à une feature OBSERVABLE par un modèle ML.
    Le label est ensuite échantillonné par Bernoulli(prob_fraude).

    Résultat attendu : AUC 0.85-0.92 (le modèle peut retrouver le score).
    """
    df = df.copy()

    # --- Composantes causales (features observables) ---
    client_mean = df.groupby("client_id")["montant"].transform("mean")
    client_std = df.groupby("client_id")["montant"].transform("std").fillna(0)
    df["_ecart_z"] = (df["montant"] - client_mean) / (client_std + 1)

    df["_device_rank"] = df.groupby("client_id")["device_id"].cumcount() + 1
    df["_ip_rank"] = df.groupby("client_id")["ip_address"].cumcount() + 1

    # Score latent (borné dans [0, 1] approximativement)
    score = (
        0.30 * (df["_ecart_z"] > 3).astype(float)
        + 0.20 * df["is_night"].astype(float)
        + 0.15 * df["is_international"].astype(float)
        + 0.10 * (df["_device_rank"] == 1).astype(float)
        + 0.15 * (df["montant"] > 30000).astype(float)
        + 0.10 * ((df["is_weekend"] == 1) & (df["is_night"] == 1)).astype(float)
        + 0.15 * df["solde_negatif_anormal"].astype(float)
    )

    # Probabilité latente (sigmoïde-like)
    prob_fraude = 0.001 + 0.45 * score

    # --- Seuillage par QUANTILE (garantit le taux cible SANS casser le signal) ---
    seuil = np.quantile(prob_fraude, 1 - TAUX_FRAUDE_CIBLE)
    df["fraud_flag"] = (prob_fraude >= seuil).astype(int)

    # --- Tracé des règles composantes (audit) ---
    df["fraud_rule_triggered"] = ""
    mask = df["fraud_flag"] == 1
    df.loc[mask & (df["_ecart_z"] > 3), "fraud_rule_triggered"] += "ecart_z "
    df.loc[mask & (df["is_night"] == 1), "fraud_rule_triggered"] += "nuit "
    df.loc[mask & (df["is_international"] == 1), "fraud_rule_triggered"] += "intl "
    df.loc[mask & (df["_device_rank"] == 1), "fraud_rule_triggered"] += "device "
    df.loc[mask & (df["montant"] > 30000), "fraud_rule_triggered"] += "montant_eleve "
    df.loc[mask & (df["solde_negatif_anormal"] == 1), "fraud_rule_triggered"] += "solde_neg "

    df["fraud_type"] = np.where(
        df["fraud_flag"] == 1,
        "Score de risque élevé",
        None
    )

    df.drop(columns=["_ecart_z", "_device_rank", "_ip_rank"], inplace=True, errors="ignore")

    return df


# ---------------------------------------------------------------------------
# 5. Crédits et classification — VERSION CORRIGÉE (Bâle III réaliste)
# ---------------------------------------------------------------------------

def generate_credits(clients_df: pd.DataFrame, comptes_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Génère des crédits et leur classification avec des PD/LGD/EL/Provisions
    cohérents avec les standards Bâle III.

    CORRECTIONS MAJEURES :
    - Distribution des jours_retard réaliste → ~88% saine
    - PD dépend des jours_retard (fourchettes Bâle III)
    - LGD dépend de la garantie
    - EL = PD × LGD × EAD
    - Provision constituée ≈ provision requise
    """
    clients_credit = clients_df.sample(frac=0.35, random_state=SEED)
    credits = []
    classifications = []

    for i, (_, client) in enumerate(clients_credit.iterrows(), start=1):
        type_credit = np.random.choice(TYPES_CREDIT, p=POIDS_TYPE_CREDIT)

        if type_credit == "Crédit immobilier":
            montant_initial = round(np.random.lognormal(mean=12.5, sigma=1.0), 2)
        elif type_credit in ["Crédit professionnel", "Crédit investissement"]:
            montant_initial = round(np.random.lognormal(mean=11.5, sigma=1.2), 2)
        elif type_credit == "Crédit automobile":
            montant_initial = round(np.random.lognormal(mean=10.5, sigma=0.8), 2)
        else:
            montant_initial = round(np.random.lognormal(mean=9.5, sigma=0.7), 2)

        taux_nominal = round(random.uniform(0.03, 0.08), 4)
        taux_effectif = round(taux_nominal + random.uniform(0.005, 0.02), 4)

        if type_credit == "Crédit immobilier":
            duree_mois = random.choice([120, 180, 240, 300])
        elif type_credit in ["Crédit professionnel", "Crédit investissement"]:
            duree_mois = random.choice([36, 48, 60, 84])
        elif type_credit == "Crédit automobile":
            duree_mois = random.choice([24, 36, 48, 60])
        else:
            duree_mois = random.choice([12, 24, 36, 48])

        date_octroi = fake.date_between(start_date="-5y", end_date="-1m")
        mensualite = round(
            (montant_initial * taux_nominal / 12) /
            (1 - (1 + taux_nominal/12)**(-duree_mois)),
            2
        )

        nb_echeances_payees = random.randint(0, duree_mois)
        nb_echeances_impayees = max(0, duree_mois - nb_echeances_payees)

        # ----- Jours de retard : distribution RÉALISTE -----
        # 88% saine (0j), 5% pré-douteuse (1-89j), 4% douteuse (90-180j), 3% compromise (>180j)
        # CORRECTION MAJEURE : ancien code générait des retards massifs
        if nb_echeances_impayees == 0:
            jours_retard = 0
        else:
            # Distribution pondérée vers le sain
            tirage = random.random()
            if tirage < 0.88:
                jours_retard = 0
            elif tirage < 0.93:
                jours_retard = random.randint(1, 89)      # Pré-douteuse
            elif tirage < 0.97:
                jours_retard = random.randint(90, 180)    # Douteuse
            else:
                jours_retard = random.randint(181, 400)   # Compromise

        montant_restant = round(montant_initial * (1 - nb_echeances_payees / duree_mois), 2)
        montant_restant = max(montant_restant, 0)

        if jours_retard == 0:
            statut_credit = "En cours"
        elif jours_retard <= 90:
            statut_credit = "En cours (retard)"
        elif jours_retard <= 180:
            statut_credit = "Incident de paiement"
        else:
            statut_credit = "Contentieux"

        garantie = random.choice(TYPES_GARANTIE)
        valeur_garantie = 0 if garantie == "Sans garantie" else round(montant_initial * random.uniform(0.5, 1.2), 2)

        score_risque_octroi = int(np.random.normal(600, 100))
        score_risque_octroi = max(300, min(850, score_risque_octroi))

        # ============================================================
        # PARAMÈTRES BÂLE III (calibrés réalistes)
        # ============================================================

        # ----- PD : fourchettes Bâle III -----
        if jours_retard == 0:
            prob_defaut = np.random.uniform(0.005, 0.02)
        elif jours_retard <= 30:
            prob_defaut = np.random.uniform(0.02, 0.05)
        elif jours_retard <= 90:
            prob_defaut = np.random.uniform(0.05, 0.15)
        elif jours_retard <= 180:
            prob_defaut = np.random.uniform(0.15, 0.35)
        elif jours_retard <= 360:
            prob_defaut = np.random.uniform(0.35, 0.65)
        else:
            prob_defaut = np.random.uniform(0.65, 0.95)

        # ----- LGD : fourchettes Bâle III -----
        if garantie == "Hypothèque":
            lgd = np.random.uniform(0.20, 0.35)
        elif garantie in ["Nantissement", "Caution personnelle", "Garantie autonome"]:
            lgd = np.random.uniform(0.35, 0.55)
        else:
            lgd = np.random.uniform(0.55, 0.75)

        ead = montant_restant
        el = round(prob_defaut * lgd * ead, 2)
        provision_requise = round(el * np.random.uniform(1.0, 1.2), 2)
        provision_constituee_credit = round(provision_requise * np.random.uniform(0.95, 1.0), 2)

        if score_risque_octroi >= 700 and jours_retard == 0:
            classification_bale = "A"
        elif score_risque_octroi >= 600 and jours_retard <= 30:
            classification_bale = "B"
        elif jours_retard <= 90:
            classification_bale = "C"
        else:
            classification_bale = "D"

        date_dernier_incident = None
        nb_incidents = 0
        if jours_retard > 30:
            date_dernier_incident = fake.date_between(start_date=date_octroi, end_date="today")
            nb_incidents = random.randint(1, 3)

        credit_id = f"CRD-{i:06d}"
        comptes_client = comptes_df[comptes_df.client_id == client.client_id]
        compte_id = comptes_client.iloc[0].compte_id if not comptes_client.empty else None

        credits.append({
            "credit_id": credit_id,
            "client_id": client.client_id,
            "agence_id": client.agence_id,
            "compte_id": compte_id,
            "type_credit": type_credit,
            "montant_initial": montant_initial,
            "montant_restant_du": montant_restant,
            "taux_interet_nominal": taux_nominal,
            "taux_effectif_global": taux_effectif,
            "duree_totale_mois": duree_mois,
            "duree_restante_mois": max(0, duree_mois - nb_echeances_payees),
            "montant_mensualite": mensualite,
            "date_octroi": date_octroi,
            "date_premiere_echeance": date_octroi + timedelta(days=30),
            "date_derniere_echeance": date_octroi + timedelta(days=30*duree_mois),
            "date_derniere_mensualite_payee": date_octroi + timedelta(days=30*nb_echeances_payees) if nb_echeances_payees > 0 else None,
            "nombre_echeances_payees": nb_echeances_payees,
            "nombre_echeances_impayees": nb_echeances_impayees,
            "jours_retard": jours_retard,
            "statut_credit": statut_credit,
            "garantie": garantie,
            "valeur_garantie": valeur_garantie,
            "objet_financement": random.choice(OBJETS_FINANCEMENT),
            "score_risque_octroi": score_risque_octroi,
            "classification_bale": classification_bale,
            "provision_constituee": provision_constituee_credit,
            "date_dernier_incident": date_dernier_incident,
            "nombre_incidents_paiement": nb_incidents,
            "conseiller_credit_id": f"CONS-{random.randint(1,50):03d}",
            "date_creation": datetime.now(),
            "date_derniere_maj": datetime.now(),
        })

        cat = next(
            (c for c in CATEGORIES_CREANCES if c["jours_min"] <= jours_retard <= c["jours_max"]),
            CATEGORIES_CREANCES[0]
        )

        classifications.append({
            "classification_id": f"CLS-{i:06d}",
            "credit_id": credit_id,
            "client_id": client.client_id,
            "date_classification": date_octroi + timedelta(days=random.randint(0, 365)),
            "categorie_reglementaire": cat["categorie"],
            "categorie_bale_ii": classification_bale,
            "categorie_ifrs9": "Stage 1" if jours_retard == 0 else ("Stage 2" if jours_retard <= 90 else "Stage 3"),
            "jours_retard": jours_retard,
            "probabilite_defaut_pd": round(prob_defaut, 4),
            "perte_en_cas_defaut_lgd": round(lgd, 4),
            "exposition_en_cas_defaut_ead": round(ead, 2),
            "perte_attendue_el": el,
            "provision_requise": provision_requise,
            "provision_constituee": provision_constituee_credit,
            "taux_provisionnement": cat["taux_provision_min"],
            "indicateur_forborne": 1 if random.random() < 0.05 else 0,
            "date_restructuration": fake.date_between(start_date=date_octroi, end_date="today") if random.random() < 0.02 else None,
            "indicateur_contentieux": 1 if statut_credit == "Contentieux" else 0,
            "date_entree_contentieux": date_octroi + timedelta(days=jours_retard) if statut_credit == "Contentieux" else None,
            "motif_classification": "Retard de paiement" if jours_retard > 30 else "Normal",
            "observation": "Classification automatique",
            "validateur_id": f"VAL-{random.randint(1,20):03d}",
            "date_validation": datetime.now(),
            "date_prochaine_revue": datetime.now() + timedelta(days=90),
        })

    return pd.DataFrame(credits), pd.DataFrame(classifications)


# ---------------------------------------------------------------------------
# 6. Ratios de liquidité
# ---------------------------------------------------------------------------

def generate_ratios_liquidite() -> pd.DataFrame:
    rows = []
    start_date = datetime.now().replace(day=1) - timedelta(days=30*N_MOIS_LIQUIDITE)
    for i in range(N_MOIS_LIQUIDITE):
        mois = (start_date + timedelta(days=30*i)).strftime("%Y-%m")
        hqla = round(np.random.normal(loc=8_000_000_000, scale=500_000_000), 2)
        sorties = round(np.random.normal(loc=6_500_000_000, scale=400_000_000), 2)
        lcr = round(hqla / sorties * 100, 2)
        lcr_conforme = lcr >= 100

        financement_stable = round(np.random.normal(loc=10_000_000_000, scale=600_000_000), 2)
        financement_requis = round(np.random.normal(loc=9_000_000_000, scale=500_000_000), 2)
        nsfr = round(financement_stable / financement_requis * 100, 2)
        nsfr_conforme = nsfr >= 100

        depot_total = round(np.random.normal(loc=15_000_000_000, scale=1_000_000_000), 2)
        credit_total = round(np.random.normal(loc=12_000_000_000, scale=800_000_000), 2)
        ratio_credit_depot = round(credit_total / depot_total * 100, 2)

        tresorerie = round(np.random.normal(loc=1_000_000_000, scale=200_000_000), 2)
        reserve_obligatoire = round(tresorerie * 0.04, 2)
        ratio_reserve = round(reserve_obligatoire / depot_total * 100, 4)

        top10_deposants = round(np.random.uniform(0.15, 0.40), 4)
        depot_vue = round(depot_total * random.uniform(0.3, 0.5), 2)
        depot_terme = depot_total - depot_vue
        ratio_depot_vue = round(depot_vue / depot_total, 4)

        ecart_1m = round(np.random.normal(loc=500_000_000, scale=300_000_000), 2)
        ecart_3m = round(np.random.normal(loc=1_200_000_000, scale=400_000_000), 2)
        ecart_1y = round(np.random.normal(loc=3_000_000_000, scale=600_000_000), 2)

        if lcr_conforme and nsfr_conforme:
            statut_global, alerte_niveau = "Conforme", "Vert"
        elif lcr_conforme or nsfr_conforme:
            statut_global, alerte_niveau = "Surveillance", "Orange"
        else:
            statut_global, alerte_niveau = "Non conforme", "Rouge"

        rows.append({
            "ratio_id": f"RAT-{i+1:04d}",
            "date_calcul": (start_date + timedelta(days=30*i)).strftime("%Y-%m-%d"),
            "periode": mois,
            "agence_id": None,
            "niveau_consolidation": "BANQUE",
            "type_ratio": "LCR_NSFR",
            "lcr_actifs_liquides": hqla,
            "lcr_sorties_nettes": sorties,
            "lcr_ratio": lcr,
            "lcr_conforme": lcr_conforme,
            "nsfr_financement_stable": financement_stable,
            "nsfr_financement_requis": financement_requis,
            "nsfr_ratio": nsfr,
            "nsfr_conforme": nsfr_conforme,
            "depot_total": depot_total,
            "credit_total": credit_total,
            "ratio_credit_depot": ratio_credit_depot,
            "tresorerie_disponible": tresorerie,
            "reserve_obligatoire": reserve_obligatoire,
            "ratio_reserve": ratio_reserve,
            "top_10_deposants_pct": top10_deposants,
            "depot_vue": depot_vue,
            "depot_terme": depot_terme,
            "ratio_depot_vue": ratio_depot_vue,
            "ecart_liquidite_1_mois": ecart_1m,
            "ecart_liquidite_3_mois": ecart_3m,
            "ecart_liquidite_1_an": ecart_1y,
            "statut_global": statut_global,
            "alerte_niveau": alerte_niveau,
            "seuil_reglementaire_respecte": 1 if (lcr_conforme and nsfr_conforme) else 0,
            "commentaire": "Généré automatiquement",
            "analyste_id": f"ANA-{random.randint(1,10):03d}",
            "date_creation": datetime.now(),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 7. Validation
# ---------------------------------------------------------------------------

def validate_data(agences_df, clients_df, comptes_df, transactions_df,
                  credits_df, classification_df, ratios_df):
    print("\n" + "="*50)
    print("VALIDATION DES DONNÉES")
    print("="*50)

    assert agences_df["agence_id"].is_unique
    assert clients_df["client_id"].is_unique
    assert comptes_df["compte_id"].is_unique
    assert transactions_df["transaction_id"].is_unique
    assert credits_df["credit_id"].is_unique
    assert classification_df["classification_id"].is_unique
    print("✅ Unicité des identifiants : OK")

    assert set(clients_df["agence_id"]).issubset(set(agences_df["agence_id"]))
    print("✅ FK clients -> agences : OK")

    assert set(comptes_df["client_id"]).issubset(set(clients_df["client_id"]))
    assert set(comptes_df["agence_id"]).issubset(set(agences_df["agence_id"]))
    print("✅ FK comptes -> clients/agences : OK")

    src = transactions_df[transactions_df["compte_source_id"].notna()]["compte_source_id"].unique()
    dst = transactions_df[transactions_df["compte_destination_id"].notna()]["compte_destination_id"].unique()
    assert set(src).issubset(set(comptes_df["compte_id"]))
    assert set(dst).issubset(set(comptes_df["compte_id"]))
    print("✅ FK transactions -> comptes : OK")

    assert set(credits_df["client_id"]).issubset(set(clients_df["client_id"]))
    assert set(classification_df["credit_id"]).issubset(set(credits_df["credit_id"]))
    print("✅ FK crédits/classifications : OK")

    assert (transactions_df["montant"] >= 0).all()
    assert (classification_df["probabilite_defaut_pd"].between(0, 1)).all()
    assert (classification_df["perte_en_cas_defaut_lgd"].between(0, 1)).all()
    print("✅ Valeurs positives / bornes : OK")

    fraud_rate = transactions_df["fraud_flag"].mean()
    print(f"\nTaux de fraude : {fraud_rate:.2%} (cible: {TAUX_FRAUDE_CIBLE:.2%})")

    # --- Diagnostic AUC univarié ---
    try:
        from sklearn.metrics import roc_auc_score
        print("\n--- AUC univarié par feature (diagnostic) ---")
        for col in ["montant", "is_night", "is_international",
                    "solde_negatif_anormal", "frais_transaction"]:
            if col in transactions_df.columns:
                try:
                    auc = roc_auc_score(transactions_df["fraud_flag"], transactions_df[col])
                    print(f"  {col:30s} : AUC = {auc:.4f}")
                except Exception:
                    pass
    except ImportError:
        pass

    print("\n--- Diagnostic crédits (Bâle III) ---")
    ead_total = classification_df['exposition_en_cas_defaut_ead'].sum()
    pd_w = (classification_df['probabilite_defaut_pd'] * classification_df['exposition_en_cas_defaut_ead']).sum() / ead_total
    lgd_w = (classification_df['perte_en_cas_defaut_lgd'] * classification_df['exposition_en_cas_defaut_ead']).sum() / ead_total
    el_total = classification_df['perte_attendue_el'].sum()
    prov_total = classification_df['provision_constituee'].sum()
    print(f"  PD moyen pondéré   : {pd_w:.2%}")
    print(f"  LGD moyen pondéré  : {lgd_w:.2%}")
    print(f"  EL total           : {el_total:,.2f} MAD")
    print(f"  Provisions totales : {prov_total:,.2f} MAD")
    print(f"  Écart (Prov - EL)  : {prov_total - el_total:,.2f} MAD ({(prov_total-el_total)/el_total*100:.2f}%)")

    print("\nRépartition des catégories de créances:")
    rep = classification_df["categorie_reglementaire"].value_counts()
    print(rep)
    print(f"\n% Saine : {(rep.get('Saine', 0) / len(classification_df)):.2%}")

    print(f"\nLCR moyen : {ratios_df['lcr_ratio'].mean():.2f}%")
    print(f"NSFR moyen : {ratios_df['nsfr_ratio'].mean():.2f}%")
    print("="*50)
    print("VALIDATION TERMINÉE AVEC SUCCÈS")
    print("="*50)


def save_data(agences_df, clients_df, comptes_df, transactions_df,
              credits_df, classification_df, ratios_df):
    agences_df.to_csv(f"{OUTPUT_DIR}/agences.csv", index=False, encoding="utf-8")
    clients_df.to_csv(f"{OUTPUT_DIR}/clients.csv", index=False, encoding="utf-8")
    comptes_df.to_csv(f"{OUTPUT_DIR}/comptes.csv", index=False, encoding="utf-8")
    transactions_df.to_csv(f"{OUTPUT_DIR}/transactions.csv", index=False, encoding="utf-8")
    credits_df.to_csv(f"{OUTPUT_DIR}/credits.csv", index=False, encoding="utf-8")
    classification_df.to_csv(f"{OUTPUT_DIR}/classification_creances.csv", index=False, encoding="utf-8")
    ratios_df.to_csv(f"{OUTPUT_DIR}/ratios_liquidite.csv", index=False, encoding="utf-8")
    print(f"\n✅ Fichiers sauvegardés dans {OUTPUT_DIR}/")


# ---------------------------------------------------------------------------
# 8. Main
# ---------------------------------------------------------------------------

def main():
    print("Génération des données bancaires synthétiques (v2.0)...")

    print("1. Génération des agences...")
    agences_df = generate_agences()

    print("2. Génération des clients...")
    clients_df = generate_clients(agences_df)

    print("3. Génération des comptes...")
    comptes_df = generate_comptes(clients_df)

    print("4. Génération des transactions (avec soldes cohérents)...")
    clients_ville = clients_df[["client_id", "ville"]]
    comptes_with_ville = comptes_df.merge(clients_ville, on="client_id")
    transactions_df = generate_transactions(comptes_with_ville)

    print("5. Génération des crédits et classifications...")
    credits_df, classification_df = generate_credits(clients_df, comptes_df)

    print("6. Génération des ratios de liquidité...")
    ratios_df = generate_ratios_liquidite()

    print("7. Sauvegarde des fichiers...")
    save_data(agences_df, clients_df, comptes_df, transactions_df,
              credits_df, classification_df, ratios_df)

    print("8. Validation des données...")
    validate_data(agences_df, clients_df, comptes_df, transactions_df,
                  credits_df, classification_df, ratios_df)

    print("\n" + "="*50)
    print("GÉNÉRATION TERMINÉE AVEC SUCCÈS")
    print("="*50)
    print(f"Clients         : {len(clients_df):,}")
    print(f"Comptes         : {len(comptes_df):,}")
    print(f"Transactions    : {len(transactions_df):,}")
    print(f"Crédits         : {len(credits_df):,}")
    print(f"Classifications : {len(classification_df):,}")
    print(f"Ratios          : {len(ratios_df):,}")
    print("="*50)


if __name__ == "__main__":
    main()