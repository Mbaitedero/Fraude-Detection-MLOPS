"""
Base de données SQLite — Utilisateurs + Alertes de fraude.
Fichier : ui/auth/users.db (créé automatiquement)
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = Path(__file__).parent / "users.db"


# ═════════════════════════════════════════════════════════════
# INITIALISATION
# ═════════════════════════════════════════════════════════════

def init_db():
    """Crée les tables users + alerts + logs si elles n'existent pas."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ─── Table users ───
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            prenom TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            telephone TEXT,
            adresse TEXT,
            fonction TEXT,
            profile_image TEXT,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'analyst',
            langue TEXT DEFAULT 'fr',
            theme TEXT DEFAULT 'light',
            actif INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    existing_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()
    }
    for column, definition in {
        "fonction": "TEXT",
        "profile_image": "TEXT",
    }.items():
        if column not in existing_columns:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")

    # ─── Table alerts (fraudes détectées) ───
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            transaction_data TEXT,
            score REAL,
            decision TEXT,
            niveau_risque TEXT,
            lu INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # ─── Table logs (audit) ───
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS batch_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            results TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contact_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            prenom TEXT NOT NULL,
            email TEXT NOT NULL,
            telephone TEXT,
            message TEXT NOT NULL,
            statut TEXT DEFAULT 'nouveau',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print(f"Base de données initialisée : {DB_PATH}")


def save_contact_message(nom, prenom, email, telephone, message):
    """Enregistre une demande de contact et retourne son identifiant."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO contact_messages
           (nom, prenom, email, telephone, message)
           VALUES (?, ?, ?, ?, ?)""",
        (nom.strip(), prenom.strip(), email.strip().lower(), telephone.strip(), message.strip()),
    )
    conn.commit()
    message_id = cursor.lastrowid
    conn.close()
    return message_id


def get_contact_messages(statut=None, limit=100):
    """Retourne les demandes de contact pour l'administration."""
    conn = sqlite3.connect(DB_PATH)
    query = """SELECT id, nom, prenom, email, telephone, message, statut, created_at
               FROM contact_messages"""
    params = []
    if statut:
        query += " WHERE statut = ?"
        params.append(statut)
    query += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [
        {
            "id": row[0], "nom": row[1], "prenom": row[2], "email": row[3],
            "telephone": row[4], "message": row[5], "statut": row[6],
            "created_at": row[7],
        }
        for row in rows
    ]


def update_contact_message_status(message_id, statut):
    """Met à jour le statut d'une demande de contact."""
    if statut not in {"nouveau", "lu", "traite"}:
        raise ValueError("Statut de contact invalide.")
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE contact_messages SET statut = ? WHERE id = ?",
        (statut, message_id),
    )
    conn.commit()
    conn.close()


# ═════════════════════════════════════════════════════════════
# GESTION DES UTILISATEURS
# ═════════════════════════════════════════════════════════════

def create_user(nom, prenom, email, telephone, adresse, password, role="analyst"):
    """Crée un utilisateur. Retourne (success, user_id_or_message)."""
    if not all([nom, prenom, email, password]):
        return False, "Tous les champs obligatoires doivent être remplis."

    if len(password) < 6:
        return False, "Le mot de passe doit contenir au moins 6 caractères."

    password_hash = generate_password_hash(password)

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (nom, prenom, email, telephone, adresse, password_hash, role)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (nom, prenom, email.lower().strip(), telephone, adresse, password_hash, role))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return True, user_id
    except sqlite3.IntegrityError: # noqa: BLE001
        return False, "Cet email est déjà utilisé."
    except Exception as e: # noqa: BLE001
        return False, f"Erreur : {e}"


def authenticate(email, password):
    """Authentifie un utilisateur. Retourne (success, user_dict_or_message)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, nom, prenom, email, telephone, adresse, fonction,
                      profile_image,
                      password_hash, role, langue, theme, actif
               FROM users WHERE email = ?""",
            (email.lower().strip(),)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return False, "Email ou mot de passe incorrect."

        (user_id, nom, prenom, user_email, telephone, adresse, fonction,
         profile_image, password_hash, role, langue, theme, actif) = row

        if not actif:
            return False, "Ce compte est désactivé."

        if not check_password_hash(password_hash, password):
            return False, "Email ou mot de passe incorrect."

        return True, {
            "id": user_id,
            "nom": nom,
            "prenom": prenom,
            "email": user_email,
            "telephone": telephone,
            "adresse": adresse,
            "fonction": fonction or "",
            "profile_image": profile_image,
            "role": role,
            "langue": langue,
            "theme": theme,
        }
    except Exception as e: # noqa: BLE001
        return False, f"Erreur : {e}"


def get_user(user_id):
    """Récupère un utilisateur par ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """SELECT id, nom, prenom, email, telephone, adresse, fonction,
              profile_image,
                  role, langue, theme, actif, created_at
           FROM users WHERE id = ?""",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "nom": row[1], "prenom": row[2], "email": row[3],
        "telephone": row[4], "adresse": row[5], "fonction": row[6] or "",
        "profile_image": row[7], "role": row[8], "langue": row[9],
        "theme": row[10], "actif": bool(row[11]), "created_at": row[12],
    }


def update_user_profile(user_id, nom, prenom, email, telephone, adresse,
                        password=None, fonction="", profile_image=None):
    """Met à jour les informations personnelles d'un utilisateur."""
    if not all([nom, prenom, email]):
        return False, "Le nom, le prénom et l'email sont obligatoires."

    fields = [
        nom.strip(), prenom.strip(), email.lower().strip(), telephone, adresse,
        (fonction or "").strip(),
    ]
    query = """
        UPDATE users
        SET nom = ?, prenom = ?, email = ?, telephone = ?, adresse = ?, fonction = ?
    """
    values = fields
    if password:
        if len(password) < 6:
            return False, "Le mot de passe doit contenir au moins 6 caractères."
        query += ", password_hash = ?"
        values.append(generate_password_hash(password))
    if profile_image is not None:
        if not profile_image.startswith("data:image/"):
            return False, "Le fichier doit être une image."
        if len(profile_image) > 3_000_000:
            return False, "L'image ne doit pas dépasser 2 Mo."
        query += ", profile_image = ?"
        values.append(profile_image)
    query += " WHERE id = ?"
    values.append(user_id)

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(query, values)
        conn.commit()
        conn.close()
        return True, "Profil mis à jour."
    except sqlite3.IntegrityError: # noqa: BLE001
        return False, "Cet email est déjà utilisé."
    except Exception as e:  # noqa: BLE001
        return False, f"Erreur : {e}"


def get_all_users():
    """Liste tous les utilisateurs (admin)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """SELECT id, nom, prenom, email, telephone, fonction, role, langue, theme,
                  actif, created_at FROM users ORDER BY created_at DESC"""
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0], "nom": r[1], "prenom": r[2], "email": r[3],
            "telephone": r[4], "fonction": r[5], "role": r[6], "langue": r[7],
            "theme": r[8], "actif": bool(r[9]), "created_at": r[10],
        }
        for r in rows
    ]


def update_user_preferences(user_id, langue=None, theme=None):
    """Met à jour langue et/ou thème d'un utilisateur."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if langue:
        cursor.execute("UPDATE users SET langue = ? WHERE id = ?", (langue, user_id))
    if theme:
        cursor.execute("UPDATE users SET theme = ? WHERE id = ?", (theme, user_id))
    conn.commit()
    conn.close()


def update_user_role(user_id, new_role):
    """Change le rôle d'un utilisateur (admin)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    conn.commit()
    conn.close()


def toggle_user_active(user_id):
    """Active/désactive un utilisateur (admin)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET actif = NOT actif WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def delete_user(user_id):
    """Supprime un utilisateur (admin)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def save_batch_import(user_id, filename, results):
    """Enregistre les résultats d'un import CSV pour l'utilisateur."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO batch_imports (user_id, filename, results)
           VALUES (?, ?, ?)""",
        (user_id, filename or "import.csv", json.dumps(results, ensure_ascii=False)),
    )
    conn.commit()
    import_id = cursor.lastrowid
    conn.close()
    return import_id


def get_batch_imports(user_id, limit=5):
    """Retourne les derniers imports CSV de l'utilisateur."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """SELECT id, filename, results, created_at
           FROM batch_imports WHERE user_id = ?
           ORDER BY created_at DESC, id DESC LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    conn.close()

    imports = []
    for import_id, filename, raw_results, created_at in rows:
        try:
            results = json.loads(raw_results)
        except (TypeError, json.JSONDecodeError): # noqa: BLE001
            results = []
        imports.append({
            "id": import_id,
            "filename": filename,
            "results": results,
            "created_at": created_at,
        })
    return imports


# ═════════════════════════════════════════════════════════════
# GESTION DES ALERTES
# ═════════════════════════════════════════════════════════════

def create_alert(user_id, transaction_data, score, decision, niveau_risque="Élevé"):
    """Crée une alerte de fraude."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO alerts (user_id, transaction_data, score, decision, niveau_risque)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, json.dumps(transaction_data), score, decision, niveau_risque))
        conn.commit()
        alert_id = cursor.lastrowid
        conn.close()
        return alert_id
    except Exception as e:   # noqa: BLE001
        print(f"Erreur création alerte : {e}")
        return None


def get_alerts(user_id, unread_only=False, limit=50):
    """Récupère les alertes d'un utilisateur."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = """SELECT id, transaction_data, score, decision, niveau_risque,
                      lu, created_at
               FROM alerts WHERE user_id = ?"""
    if unread_only:
        query += " AND lu = 0"
    query += " ORDER BY created_at DESC LIMIT ?"
    cursor.execute(query, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()

    alerts = []
    for r in rows:
        try:
            data = json.loads(r[1])
        except Exception:  # noqa: BLE001
            data = {}
        alerts.append({
            "id": r[0],
            "transaction_data": data,
            "score": r[2],
            "decision": r[3],
            "niveau_risque": r[4],
            "lu": bool(r[5]),
            "created_at": r[6],
        })
    return alerts


def count_unread_alerts(user_id):
    """Compte les alertes non lues."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM alerts WHERE user_id = ? AND lu = 0",
        (user_id,)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


def mark_alert_read(alert_id):
    """Marque une alerte comme lue."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE alerts SET lu = 1 WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()


def mark_all_alerts_read(user_id):
    """Marque toutes les alertes comme lues."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE alerts SET lu = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def delete_alert(alert_id):
    """Supprime une alerte."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()


# ═════════════════════════════════════════════════════════════
# AUDIT LOGS
# ═════════════════════════════════════════════════════════════

def log_action(user_id, action, details=None, ip_address=None):
    """Enregistre une action dans l'audit log."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_logs (user_id, action, details, ip_address)
            VALUES (?, ?, ?, ?)
        """, (user_id, action, details, ip_address))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erreur log : {e}")


def get_audit_logs(user_id=None, limit=100):
    """Récupère les logs d'audit."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if user_id:
        cursor.execute(
            """SELECT id, user_id, action, details, created_at
               FROM audit_logs WHERE user_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit)
        )
    else:
        cursor.execute(
            """SELECT id, user_id, action, details, created_at
               FROM audit_logs ORDER BY created_at DESC LIMIT ?""",
            (limit,)
        )
    rows = cursor.fetchall()
    conn.close()
    return [
        {"id": r[0], "user_id": r[1], "action": r[2],
         "details": r[3], "created_at": r[4]}
        for r in rows
    ]


# ═════════════════════════════════════════════════════════════
# STATISTIQUES
# ═════════════════════════════════════════════════════════════

def get_stats():
    """Retourne les statistiques globales."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users WHERE actif = 1")
    n_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM alerts")
    n_alerts = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM alerts WHERE lu = 0")
    n_unread = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM alerts WHERE decision = 'FRAUDE'")
    n_frauds = cursor.fetchone()[0]

    conn.close()
    return {
        "n_users": n_users,
        "n_alerts": n_alerts,
        "n_unread": n_unread,
        "n_frauds": n_frauds,
    }