"""
Schémas Pydantic — validation + doc Swagger.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class TransactionInput(BaseModel):
    montant: float = Field(..., ge=0, description="Montant en MAD")
    type_transaction: str = Field(
        ..., description="Paiement, Virement, Retrait, Dépôt, Prélèvement"
    )
    mode_paiement: str = Field(
        "Carte", description="Carte, Espèces, Chèque, Virement, Non_applicable"
    )
    heure: int = Field(14, ge=0, le=23, description="Heure de la transaction")
    is_weekend: int = Field(0, ge=0, le=1)
    est_international: int = Field(0, ge=0, le=1)


class PredictionOutput(BaseModel):
    score: float
    pourcentage: float
    decision: str
    niveau_risque: str
    est_fraude: bool


class ModelInfo(BaseModel):
    name: str
    alias: str
    version: str
    features: List[str]
    pr_auc: Optional[float] = None
    roc_auc: Optional[float] = None
    lift: Optional[float] = None
    run_id: str


class HealthOutput(BaseModel):
    status: str
    model_loaded: bool
    checks: Optional[Dict[str, bool]] = None
    details: Optional[Dict[str, Any]] = None