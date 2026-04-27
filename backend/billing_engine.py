import time
from datetime import datetime


class BillingEngine:
    """Handles parking billing: timers, rate calculation, fines, wallet deduction."""

    RATE_PER_SECOND = 1    # ₹1 per second
    IMPROPER_FINE = 50     # ₹50 fine
    INITIAL_BALANCE = 500  # ₹500 starting wallet

    def __init__(self, firebase_db):
        self.db = firebase_db
        self.active_sessions = {}  # car_id -> {slot_id, entry_time, is_improper}
        self.transactions = []
        self.activity_logs = []
        self.total_cars_today = 0
        self.total_revenue_today = 0.0

    def car_entered(self, car_id, slot_id, is_improper):
        now = datetime.now()
        self.active_sessions[car_id] = {
            "slot_id": slot_id,
            "entry_time": now,
            "is_improper": is_improper,
        }

        # Create wallet with ₹500
        self.db.create_wallet(car_id, self.INITIAL_BALANCE)
        self.total_cars_today += 1

        # Activity log
        log = {"type": "car_entered", "car_id": car_id, "slot_id": slot_id,
               "timestamp": now.strftime("%I:%M %p"), "time_ago": "Just now"}
        self.activity_logs.insert(0, log)
        self.db.add_activity(log)

        if is_improper:
            vlog = {"type": "violation", "car_id": car_id, "slot_id": slot_id,
                    "alert": "Improper Parking", "timestamp": now.strftime("%I:%M %p"),
                    "time_ago": "Just now"}
            self.activity_logs.insert(0, vlog)
            self.db.add_activity(vlog)

    def car_exited(self, car_id, slot_id, duration_seconds, is_improper):
        session = self.active_sessions.pop(car_id, None)
        now = datetime.now()

        base_bill = round(duration_seconds * self.RATE_PER_SECOND, 2)
        fine = self.IMPROPER_FINE if is_improper else 0
        total_bill = base_bill + fine

        remaining = self.db.deduct_wallet(car_id, total_bill)
        self.total_revenue_today += total_bill

        entry_time = session["entry_time"] if session else now

        txn = {
            "car_id": car_id,
            "plate": car_id.replace("CAR-", "PLT-"),
            "slot_id": slot_id,
            "entry_time": entry_time.strftime("%I:%M %p"),
            "exit_time": now.strftime("%I:%M %p"),
            "date": now.strftime("%b %d, %Y"),
            "duration_sec": round(duration_seconds),
            "base_bill": base_bill,
            "fine": fine,
            "total_bill": total_bill,
            "extra_charges": "IMPROPER PARKING" if is_improper else "NONE",
            "wallet_remaining": remaining,
        }
        self.transactions.insert(0, txn)
        self.db.save_transaction(txn)

        log = {"type": "car_exited", "car_id": car_id, "slot_id": slot_id,
               "payment": total_bill, "wallet_remaining": remaining,
               "timestamp": now.strftime("%I:%M %p"), "time_ago": "Just now"}
        self.activity_logs.insert(0, log)
        self.db.add_activity(log)

        return {"total_bill": total_bill, "fine": fine,
                "duration": round(duration_seconds), "wallet_remaining": remaining}

    def manual_entered(self, plate_number):
        car_id = "CAR-" + plate_number
        now = datetime.now()
        self.active_sessions[car_id] = {
            "slot_id": "MANUAL",
            "entry_time": now,
            "is_improper": False,
        }
        self.total_cars_today += 1
        log = {"type": "car_entered", "car_id": car_id, "slot_id": "MANUAL",
               "timestamp": now.strftime("%I:%M %p"), "time_ago": "Just now"}
        self.activity_logs.insert(0, log)
        self.db.add_activity(log)

    def manual_checkout(self, plate_number):
        car_id = "CAR-" + plate_number
        session = self.active_sessions.pop(car_id, None)
        if not session:
            raise ValueError("Car not found in active sessions")
        
        now = datetime.now()
        duration_seconds = (now - session["entry_time"]).total_seconds()
        total_bill = round(duration_seconds * self.RATE_PER_SECOND, 2)
        
        self.total_revenue_today += total_bill
        
        txn = {
            "car_id": car_id,
            "plate": plate_number,
            "slot_id": "MANUAL",
            "entry_time": session["entry_time"].strftime("%I:%M %p"),
            "exit_time": now.strftime("%I:%M %p"),
            "date": now.strftime("%b %d, %Y"),
            "duration_sec": round(duration_seconds),
            "base_bill": total_bill,
            "fine": 0,
            "total_bill": total_bill,
            "extra_charges": "NONE",
            "wallet_remaining": "CASH/CARD",
        }
        self.transactions.insert(0, txn)
        self.db.save_transaction(txn)
        
        log = {"type": "car_exited", "car_id": car_id, "slot_id": "MANUAL",
               "payment": total_bill, "timestamp": now.strftime("%I:%M %p"),
               "time_ago": "Just now"}
        self.activity_logs.insert(0, log)
        self.db.add_activity(log)
        
        return {"total_bill": total_bill, "duration": round(duration_seconds)}

    def get_transactions(self):
        """Returns completed transactions + in-progress sessions."""
        result = list(self.transactions)
        for car_id, sess in self.active_sessions.items():
            dur = time.time() - sess["entry_time"].timestamp()
            current_bill = round(dur * self.RATE_PER_SECOND, 2)
            result.append({
                "car_id": car_id,
                "plate": car_id.replace("CAR-", "PLT-"),
                "slot_id": sess["slot_id"],
                "entry_time": sess["entry_time"].strftime("%I:%M %p"),
                "exit_time": "---",
                "date": datetime.now().strftime("%b %d, %Y"),
                "duration_sec": round(dur),
                "total_bill": current_bill,
                "extra_charges": "IMPROPER PARKING" if sess["is_improper"] else "NONE",
                "status": "In Progress",
            })
        return result

    def get_activity_logs(self):
        return self.activity_logs[:30]

    def get_summary(self):
        return {
            "total_cars_today": self.total_cars_today,
            "total_revenue_today": round(self.total_revenue_today, 2),
            "weekly_revenue": round(self.total_revenue_today + 14500, 2),
            "monthly_revenue": round(self.total_revenue_today + 62300, 2),
        }

    def get_weekly_stats(self):
        """Returns cars parked per day for the last 7 days."""
        from datetime import timedelta
        today = datetime.now().date()

        # Count real transactions per day from this session
        counts = {}
        for txn in self.transactions:
            try:
                d = datetime.strptime(txn["date"], "%b %d, %Y").date()
                counts[d] = counts.get(d, 0) + 1
            except Exception:
                pass

        # Build 7-day dataset (Mon–today), filling past days with realistic demo data
        base_demo = [38, 52, 47, 61, 55, 43, self.total_cars_today]
        result = []
        for i in range(6, -1, -1):
            day = today - timedelta(days=i)
            day_name = day.strftime("%a")  # Mon, Tue, etc.
            count = counts.get(day, base_demo[6 - i])
            result.append({"day": day_name, "date": day.strftime("%b %d"), "cars": count})

        return result

    def get_hourly_occupancy(self):
        """Returns entries per hour for today."""
        # Demo data + real session entries
        hours = ["8am", "10am", "12pm", "2pm", "4pm", "6pm", "8pm", "10pm"]
        counts = [12, 28, 45, 38, 42, 58, 35, 15] # Demo
        
        # Add real entries from active sessions if they happened today
        now_hour = datetime.now().hour
        # Simplified: just return demo + a bit of real data for now
        if now_hour >= 8:
            idx = (now_hour - 8) // 2
            if idx < len(counts):
                counts[idx] += len(self.active_sessions)
                
        return [{"hour": h, "count": c} for h, c in zip(hours, counts)]

    def get_zone_distribution(self):
        """Returns car count per zone (Row A, B, C, etc.)"""
        zones = {"Row A": 0, "Row B": 0, "Row C": 0, "Row D": 0}
        # In a real app, we'd count based on detection.get_slots()
        # For now, let's distribute active sessions or use demo
        zones["Row A"] = 12
        zones["Row B"] = 8
        zones["Row C"] = 15
        zones["Row D"] = 5
        
        return [{"zone": k, "value": v} for k, v in zones.items()]

