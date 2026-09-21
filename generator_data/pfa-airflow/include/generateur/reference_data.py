"""Référentiels pour la génération de données bancaires synthétiques marocaines."""

# Villes et régions
VILLES = [
    ("Casablanca", "Casablanca-Settat", 20000),
    ("Rabat", "Rabat-Salé-Kénitra", 10000),
    ("Fès", "Fès-Meknès", 8000),
    ("Marrakech", "Marrakech-Safi", 10000),
    ("Tanger", "Tanger-Tétouan-Al Hoceïma", 8000),
    ("Agadir", "Souss-Massa", 6000),
    ("Meknès", "Fès-Meknès", 4000),
    ("Oujda", "Oriental", 3000),
    ("Kénitra", "Rabat-Salé-Kénitra", 4000),
    ("Tétouan", "Tanger-Tétouan-Al Hoceïma", 3000),
    ("Salé", "Rabat-Salé-Kénitra", 4000),
    ("Nador", "Oriental", 3000),
    ("Settat", "Casablanca-Settat", 2000),
    ("El Jadida", "Casablanca-Settat", 3000),
    ("Béni Mellal", "Béni Mellal-Khénifra", 2000),
    ("Khouribga", "Béni Mellal-Khénifra", 2000),
    ("Safi", "Marrakech-Safi", 2000),
    ("Mohammedia", "Casablanca-Settat", 2000),
    ("Laâyoune", "Laâyoune-Sakia El Hamra", 2000),
    ("Khemisset", "Rabat-Salé-Kénitra", 2000),
]
# On extrait les noms, régions, codes postaux (approximatifs)
NOMS_VILLES = [v[0] for v in VILLES]
REGIONS = {v[0]: v[1] for v in VILLES}
CODES_POSTAUX = {v[0]: v[2] for v in VILLES}
POIDS_VILLES = [22, 12, 8, 10, 8, 6, 4, 3, 4, 3, 4, 3, 2, 3, 2, 2, 2, 2, 2, 2]

# Quartiers pour les agences
QUARTIERS_AGENCE = [
    "Centre", "Maarif", "Gueliz", "Agdal", "Hay Riad", "Anfa",
    "Ain Sebaa", "Massira", "Founty", "Val Fleuri", "Bourgogne",
    "Médina", "Ville Nouvelle", "Palais", "Océan", "Roches Noires",
]

# Canaux de transaction
CANAUX = ["Carte bancaire", "Virement", "Mobile banking", "Agence", "Prélèvement"]
POIDS_CANAUX = [0.30, 0.25, 0.25, 0.15, 0.05]

# Types de clients
TYPES_CLIENT = ["Particulier", "Entreprise"]
POIDS_TYPE_CLIENT = [0.82, 0.18]

# Codes banque (fictif) pour RIB
CODE_BANQUE = "230"

# Catégories de créances (inspirées BAM)
CATEGORIES_CREANCES = [
    {"categorie": "Saine", "jours_min": 0, "jours_max": 89, "taux_provision_min": 0.0},
    {"categorie": "Pré-douteuse", "jours_min": 90, "jours_max": 180, "taux_provision_min": 0.20},
    {"categorie": "Douteuse", "jours_min": 181, "jours_max": 360, "taux_provision_min": 0.50},
    {"categorie": "Compromise", "jours_min": 361, "jours_max": 3650, "taux_provision_min": 1.00},
]

# Types de comptes
TYPES_COMPTE = [
    "Compte courant",
    "Compte épargne",
    "Compte professionnel",
    "Compte entreprise",
    "Compte jeune",
]
POIDS_TYPE_COMPTE = [0.50, 0.20, 0.15, 0.10, 0.05]

# Types de crédits
TYPES_CREDIT = [
    "Crédit immobilier",
    "Crédit automobile",
    "Crédit consommation",
    "Crédit professionnel",
    "Crédit équipement",
    "Crédit investissement",
]
POIDS_TYPE_CREDIT = [0.30, 0.20, 0.20, 0.15, 0.10, 0.05]

# Types de transactions
TYPES_TRANSACTION = [
    "Virement",
    "Paiement",
    "Retrait",
    "Dépôt",
    "Prélèvement",
]
POIDS_TYPE_TRANSACTION = [0.25, 0.40, 0.15, 0.10, 0.10]

# Catégories de transactions (pour Paiement)
CATEGORIES_PAIEMENT = [
    "Alimentation", "Habillement", "Santé", "Éducation", "Transport",
    "Loisirs", "Hôtellerie", "Services", "Autres",
]
MCC_CODES = {
    "Alimentation": 5411, "Habillement": 5651, "Santé": 8011,
    "Éducation": 8299, "Transport": 4112, "Loisirs": 7996,
    "Hôtellerie": 7011, "Services": 7299, "Autres": 9999,
}

# Modes de paiement
MODES_PAIEMENT = ["Carte", "Virement", "Chèque", "Espèces", "Prélèvement"]

# Professions (pour particuliers)
PROFESSIONS = [
    "Ingénieur", "Médecin", "Enseignant", "Avocat", "Commerçant",
    "Artisan", "Employé", "Ouvrier", "Retraité", "Sans profession",
    "Étudiant", "Fonctionnaire", "Cadre supérieur", "Chef d'entreprise",
]

# Secteurs d'activité (pour entreprises)
SECTEURS_ACTIVITE = [
    "Agriculture", "Industrie", "BTP", "Commerce", "Transport",
    "Hôtellerie", "Finance", "Immobilier", "Santé", "Éducation",
    "Technologie", "Services", "Énergie",
]

# Formes juridiques
FORMES_JURIDIQUES = [
    "SARL", "SA", "SNC", "SAS", "EURL", "Entreprise individuelle",
]

# Situations familiales
SITUATIONS_FAMILIALES = [
    "Célibataire", "Marié", "Divorcé", "Veuf",
]

# Statuts KYC
STATUTS_KYC = ["Validé", "En cours", "Échoué", "Non soumis"]

# Segments clients
SEGMENTS_CLIENT = [
    "Premium", "Grandes entreprises", "PME", "Particuliers aisés",
    "Particuliers standard", "Jeunes",
]

# Types de fraude
TYPES_FRAUDE = [
    "Montant inhabituel",
    "Transaction nocturne",
    "Changement géographique",
    "Transactions rapides",
    "Nouveau device",
    "Nouvelle IP",
    "Transaction internationale inhabituelle",
    "Carte suspecte",
    "Montant élevé",
    "Combinaison d'anomalies",
]

# Types de garanties
TYPES_GARANTIE = [
    "Hypothèque", "Nantissement", "Caution personnelle",
    "Garantie autonome", "Sans garantie",
]

# Objets de financement
OBJETS_FINANCEMENT = [
    "Achat immobilier", "Travaux", "Véhicule", "Études",
    "Équipement professionnel", "Fonds de roulement", "Investissement",
]

# Niveaux de consolidation pour ratios
NIVEAUX_CONSOLIDATION = ["BANQUE", "GROUPE", "AGENCE"]