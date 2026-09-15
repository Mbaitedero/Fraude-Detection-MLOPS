"""
Logique de scoring — isolée pour être testable.
"""

import pandas as pd

from api.services import databricks_client as dbx


def predict_transaction(payload: dict) -> dict:
    """
    Prend un dict de features, retourne un dict avec score + décision.
    """
    model, feature_names = dbx.load_champion_model()
    encoder = dbx.load_encoder()

    # --- Feature engineering ---
    montant = payload["montant"]
    type_transaction = payload["type_transaction"]
    heure = payload.get("heure", 14)
    is_weekend = int(payload.get("is_weekend", 0))
    est_international = int(payload.get("est_international", 0))

    is_night = 1 if (heure < 6 or heure >= 22) else 0
    tranche_horaire = (
        "Nuit" if heure < 6 else "Matin" if heure < 12
        else "Après-midi" if heure < 18 else "Soir"
    )
    sens_operation = (
        "Débit" if type_transaction in ["Paiement", "Retrait", "Prélèvement"] else "Crédit"
    )

    input_row = pd.DataFrame([{
        "montant": montant,
        "frais_transaction": round(montant * 0.005, 2) if type_transaction == "Paiement" else 0.0,
        "ecart_relatif_montant": 0.0,
        "ratio_montant_revenu": 0.0,
        "taux_utilisation_30j": 1.0,
        "montant_moyen_client_30j": montant,
        "ecart_type_client_30j": 0.0,
        "nb_transactions_client_30j": 5,
        "montant_cumule_client": montant,
        "type_transaction": type_transaction,
        "mode_paiement": payload.get("mode_paiement", "Carte"),
        "sens_operation": sens_operation,
        "tranche_horaire": tranche_horaire,
        "is_night": is_night,
        "is_weekend": is_weekend,
        "est_international": est_international,
    }])

    cat_cols = list(encoder.feature_names_in_)
    input_row[cat_cols] = encoder.transform(input_row[cat_cols])
    input_row = input_row[feature_names]

    proba = float(model.predict_proba(input_row)[0, 1])

    if proba >= 0.8:
        niveau, decision = "Très élevé", "FRAUDE"
    elif proba >= 0.5:
        niveau, decision = "Élevé", "FRAUDE"
    elif proba >= 0.2:
        niveau, decision = "Moyen", "NORMAL"
    else:
        niveau, decision = "Faible", "NORMAL"

    return {
        "score": proba,
        "pourcentage": round(proba * 100, 2),
        "decision": decision,
        "niveau_risque": niveau,
        "est_fraude": proba >= 0.5,
    }
