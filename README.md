# 🅿️ ParkFlow - Smart Parking Management System

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![YOLOv11](https://img.shields.io/badge/Model-YOLOv11-green.svg)](https://ultralytics.com/)
[![Flask](https://img.shields.io/badge/Backend-Flask-lightgrey.svg)](https://flask.palletsprojects.com/)
[![Firebase](https://img.shields.io/badge/Database-Firebase-orange.svg)](https://firebase.google.com/)

**ParkFlow** is an advanced, real-time parking management system powered by **YOLOv11**. It automates vehicle detection, occupancy monitoring, and billing across multiple camera feeds, providing a seamless experience for both operators and users.

---

## ✨ Key Features

-   🚀 **YOLOv11 Detection**: High-speed, accurate vehicle detection and slot occupancy tracking.
-   📽️ **Multi-Camera Support**: Simultaneous processing of multiple CCTV feeds with unified analytics.
-   📊 **Real-time Dashboard**: Interactive web interface with live occupancy metrics, charts, and activity feeds.
-   💰 **Smart Billing Engine**: Automatic entry/exit tracking with wallet-based payments (Firebase integration).
-   ⚠️ **Violation Detection**: Detects improper parking and automatically applies fines.
-   🏥 **Camera Health Monitoring**: Real-time diagnostic alerts if a camera feed is interrupted.
-   🔌 **WebSocket Integration**: Live updates pushed to the dashboard without page refreshes.

---

## 🛠️ Tech Stack

-   **Computer Vision**: YOLOv11 (Ultralytics), OpenCV, Shapely
-   **Backend**: Flask, Flask-SocketIO, Flask-CORS
-   **Frontend**: Vanilla JS, HTML5 (Semantic), CSS3 (Modern/Glassmorphism), Chart.js
-   **Database**: Firebase (Real-time Database/Firestore) for wallet management and logs.

---

## 📂 Project Structure

```text
├── assets/
│   ├── configs/            # Parking slot JSON configurations
│   ├── images/             # Static images and samples
│   └── videos/             # CCTV video feeds (mp4)
├── backend/
│   ├── server.py           # Flask server entry point
│   ├── detection_engine.py # YOLO processing logic
│   ├── billing_engine.py   # Pricing and transaction logic
│   ├── firebase_config.py  # Firebase database integration
│   └── requirements.txt    # Backend dependencies
├── frontend/
│   ├── static/             # CSS, JS, and UI assets
│   └── templates/          # HTML pages (Dashboard, CCTV, Billing)
├── models/
│   └── yolo11s.pt          # YOLOv11 model weights
├── scripts/                # Utility and standalone scripts
├── README.md
└── LICENSE
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.8+
- [Git](https://git-scm.com/)

### 2. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/YourUsername/ParkFlow.git
cd ParkFlow/backend
pip install -r requirements.txt
```

### 3. Firebase Configuration
Update `backend/firebase_config.py` with your Firebase service account credentials.

### 4. Running the Application
Start the Flask server from the `backend` directory:
```bash
python server.py
```

---

## 📸 Screenshots

| Dashboard | CCTV Monitoring |
| :---: | :---: |
| ![Dashboard Placeholder](https://via.placeholder.com/600x400?text=Dashboard+UI) | ![CCTV Placeholder](https://via.placeholder.com/600x400?text=CCTV+Detection+UI) |

---

## 📝 License

Distributed under the MIT License. See `LICENSE` for more information.

## 🤝 Contributing

Contributions are welcome! Feel free to open an issue or submit a pull request.

---

*Built with ❤️ by NeuralPark Team
