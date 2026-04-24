import json
import os
import requests

# Firebase Realtime Database configuration
FIREBASE_CONFIG = {
    "apiKey": "AIzaSyBHIhL_M0J29VbCRuD6aGQYiCdP-twLxAk",
    "authDomain": "neuralpark-a8e76.firebaseapp.com",
    "databaseURL": "https://neuralpark-a8e76-default-rtdb.firebaseio.com",
    "projectId": "neuralpark-a8e76",
    "storageBucket": "neuralpark-a8e76.firebasestorage.app",
}

LOCAL_FALLBACK_FILE = os.path.join(os.path.dirname(__file__), "local_db.json")


class FirebaseDB:
    """Manages car wallets, transactions, and activity logs.
    Uses Firebase Realtime Database REST API, falls back to local JSON."""

    def __init__(self):
        self.db_url = FIREBASE_CONFIG["databaseURL"]
        self.use_firebase = True
        self.local_data = {"wallets": {}, "transactions": [], "activity_logs": [], "slots": {}}

        # Test Firebase connectivity
        try:
            r = requests.get(f"{self.db_url}/.json", timeout=5)
            if r.status_code == 200:
                print("[Firebase] Connected successfully.")
            else:
                print(f"[Firebase] Connection returned {r.status_code}. Using local storage.")
                self.use_firebase = False
        except Exception as e:
            print(f"[Firebase] Could not connect: {e}. Using local storage.")
            self.use_firebase = False

        # Fresh start — clear all previous data
        self._reset_all()

    # ── Firebase REST helpers ──────────────────────────────────────

    def _fb_put(self, path, data):
        if not self.use_firebase:
            return
        try:
            requests.put(f"{self.db_url}/{path}.json", json=data, timeout=5)
        except Exception:
            pass

    def _fb_get(self, path):
        if not self.use_firebase:
            return None
        try:
            r = requests.get(f"{self.db_url}/{path}.json", timeout=5)
            return r.json() if r.status_code == 200 else None
        except Exception:
            return None

    # ── Reset on startup ──────────────────────────────────────────

    def _reset_all(self):
        """Clear all data in Firebase and local file for a fresh start."""
        self.local_data = {"wallets": {}, "transactions": [], "activity_logs": [], "slots": {}}
        # Clear Firebase
        if self.use_firebase:
            try:
                requests.put(f"{self.db_url}/wallets.json", json={}, timeout=5)
                requests.put(f"{self.db_url}/transactions.json", json=[], timeout=5)
                requests.put(f"{self.db_url}/activity_logs.json", json=[], timeout=5)
                print("[Firebase] Data cleared for fresh start.")
            except Exception as e:
                print(f"[Firebase] Could not clear data: {e}")
        # Clear local file
        self._save_local()
        print("[DB] Fresh start — all previous data cleared.")

    # ── Local persistence ──────────────────────────────────────────

    def _load_local(self):
        if os.path.exists(LOCAL_FALLBACK_FILE):
            with open(LOCAL_FALLBACK_FILE, "r") as f:
                saved = json.load(f)
                for k in self.local_data:
                    if k in saved:
                        self.local_data[k] = saved[k]

    def _save_local(self):
        with open(LOCAL_FALLBACK_FILE, "w") as f:
            json.dump(self.local_data, f, indent=2, default=str)

    # ── Wallet operations ──────────────────────────────────────────

    def create_wallet(self, car_id, balance=500):
        wallet = {"balance": balance, "car_id": car_id}
        self.local_data["wallets"][car_id] = wallet
        self._fb_put(f"wallets/{car_id}", wallet)
        self._save_local()

    def get_wallet_balance(self, car_id):
        w = self.local_data["wallets"].get(car_id)
        return w["balance"] if w else 0

    def deduct_wallet(self, car_id, amount):
        w = self.local_data["wallets"].get(car_id)
        if w:
            w["balance"] = round(w["balance"] - amount, 2)
            self._fb_put(f"wallets/{car_id}", w)
            self._save_local()
            return w["balance"]
        return 0

    def get_all_wallets(self):
        return self.local_data["wallets"]

    # ── Transaction operations ─────────────────────────────────────

    def save_transaction(self, txn):
        self.local_data["transactions"].insert(0, txn)
        self._fb_put("transactions", self.local_data["transactions"])
        self._save_local()

    def get_transactions(self):
        return self.local_data["transactions"]

    # ── Activity log operations ────────────────────────────────────

    def add_activity(self, entry):
        self.local_data["activity_logs"].insert(0, entry)
        # Keep last 50
        self.local_data["activity_logs"] = self.local_data["activity_logs"][:50]
        self._fb_put("activity_logs", self.local_data["activity_logs"])
        self._save_local()

    def get_activity_logs(self):
        return self.local_data["activity_logs"]
