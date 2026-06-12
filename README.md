# FaceAttend — Facial Recognition Attendance System

## Project Overview

FaceAttend is a complete web-based attendance management system built with **Django** and **Python**. It uses real-time facial recognition via the browser webcam to automatically track employee check-ins and check-outs — no cards, PINs, or physical devices required.

---

## Architecture & Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend Framework | Django 6.x (Python 3.12) |
| Face Detection | dlib HOG detector |
| Face Encoding | face_recognition library (128-dim vectors) |
| ML Classifier | scikit-learn SVM (Linear kernel) |
| Frontend | Bootstrap 5.3 + Chart.js 4 |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Static Files | WhiteNoise |
| Image Processing | OpenCV (headless) |

---

## Project Structure

```
attendance_system_facial_recognition/
├── attendance_system_facial_recognition/
│   ├── settings.py          # Django settings
│   ├── urls.py              # URL routing
│   └── wsgi.py              # WSGI entry point
│
├── recognition/             # Core app
│   ├── views.py             # All views + AJAX API endpoints
│   ├── forms.py             # Form definitions
│   ├── templatetags/
│   │   └── dict_filters.py  # Custom template filters
│   └── templates/recognition/
│       ├── base.html        # Base layout (sidebar + navbar)
│       ├── home.html        # Landing page
│       ├── admin_dashboard.html
│       ├── employee_dashboard.html
│       ├── add_photos.html  # Browser webcam photo capture
│       ├── train.html       # Model training
│       ├── mark_attendance.html  # Check-in / Check-out (shared)
│       ├── view_attendance_home.html
│       ├── view_attendance_date.html
│       ├── view_attendance_employee.html
│       └── view_my_attendance.html
│
├── users/                   # Auth app
│   ├── models.py            # Present + Time models
│   ├── views.py             # Employee registration
│   ├── admin.py             # Admin panel config
│   └── templates/users/
│       ├── login.html
│       └── register.html
│
├── face_recognition_data/   # ML data directory
│   ├── training_dataset/    # Per-employee captured photos
│   │   └── <username>/
│   │       ├── 1.jpg
│   │       └── ...
│   ├── svc.sav              # Trained SVM model (generated)
│   ├── classes.npy          # Label encoder classes (generated)
│   └── shape_predictor_68_face_landmarks.dat  # dlib predictor
│
├── requirements.txt
└── db.sqlite3
```

---

## How It Works

### 1. Face Enrollment
- Admin navigates to **Add Photos** page
- Selects an employee username
- Browser webcam activates and auto-captures 200 photos
- Photos saved to `face_recognition_data/training_dataset/<username>/`

### 2. Model Training
- Admin clicks **Train Model**
- For each photo, `face_recognition.face_encodings()` extracts a 128-dimensional vector using dlib's ResNet model
- A **Linear SVM** (`sklearn.svm.SVC`) is trained on all encodings
- Model saved to `face_recognition_data/svc.sav`
- Label classes saved to `face_recognition_data/classes.npy`

### 3. Real-Time Recognition
- Employee opens **Check-In** or **Check-Out** page
- Browser captures webcam frames every 400ms via JavaScript
- Each frame is sent as base64 JPEG to `/api/recognize/` (AJAX POST)
- Server:
  - Decodes base64 → OpenCV image → RGB conversion
  - `face_recognition.face_locations()` detects faces (HOG)
  - `face_recognition.face_encodings()` extracts 128-dim vectors
  - SVM `predict_proba()` returns confidence scores
  - If confidence > 70% → person identified
- After 5 consecutive recognitions → attendance marked via `/api/mark_attendance/`

### 4. Attendance Recording
- `Present` model: one record per employee per day (boolean present/absent)
- `Time` model: each check-in/out event with timestamp
- Hours calculated as: last check-out - first check-in

---

## Database Models

### `Present` (users/models.py)
| Field | Type | Description |
|-------|------|-------------|
| user | FK(User) | Employee |
| date | DateField | Attendance date |
| present | BooleanField | True if present |

### `Time` (users/models.py)
| Field | Type | Description |
|-------|------|-------------|
| user | FK(User) | Employee |
| date | DateField | Record date |
| time | DateTimeField | Exact timestamp |
| out | BooleanField | True=check-out, False=check-in |

---

## URL Reference

| URL | Name | Description |
|-----|------|-------------|
| `/` | home | Landing page |
| `/login/` | login | Login form |
| `/logout/` | logout | Logout |
| `/dashboard/` | dashboard | Admin or employee dashboard |
| `/register/` | register | Register new employee (admin) |
| `/add_photos/` | add-photos | Capture training photos (admin) |
| `/train/` | train | Train SVM model (admin) |
| `/mark_attendance_in/` | mark-attendance-in | Check-in page |
| `/mark_attendance_out/` | mark-attendance-out | Check-out page |
| `/view_attendance/` | view-attendance-home | Attendance overview |
| `/view_attendance/date/` | view-attendance-date | Filter by date (admin) |
| `/view_attendance/employee/` | view-attendance-employee | Filter by employee (admin) |
| `/view_my_attendance/` | view-my-attendance | Employee self-view |
| `/export_csv/` | export-csv | Download CSV report (admin) |
| `/api/recognize/` | api-recognize | AJAX: face recognition |
| `/api/capture_photo/` | api-capture-photo | AJAX: save training photo |
| `/api/mark_attendance/` | api-mark-attendance | AJAX: record attendance |
| `/api/model_status/` | api-model-status | AJAX: model info |

---

## Setup Instructions

### Prerequisites
- Python 3.9+
- CMake (required for dlib)
- A webcam

### Windows Setup (VS Code)

```bash
# 1. Install CMake (required for dlib)
# Download from https://cmake.org/download/ and add to PATH

# 2. Install Visual C++ Build Tools
# Download from https://visualstudio.microsoft.com/visual-cpp-build-tools/

# 3. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 4. Install dependencies
pip install cmake
pip install dlib
pip install -r requirements.txt

# 5. Apply migrations
python manage.py migrate

# 6. Create admin user
python manage.py createsuperuser
# When prompted, use username: admin (or any name — admin access uses is_staff=True)

# 7. Run the server
python manage.py runserver 0.0.0.0:5000
# Open http://localhost:5000
```

### Linux / Replit Setup

```bash
# Install system dependencies
apt-get install cmake libboost-all-dev  # or use Nix

# Install Python packages
pip install -r requirements.txt

# Setup database
python manage.py migrate

# Create admin
python manage.py createsuperuser

# Run
python manage.py runserver 0.0.0.0:5000
```

---

## Usage Workflow

### Admin Steps
1. **Login** with your superuser account
2. **Register Employees**: Dashboard → Register Employee
3. **Add Photos**: Dashboard → Add Photos → select employee → Start Auto-Capture (200 photos)
4. **Train Model**: Dashboard → Train Model → Train Now (takes 1-5 minutes)
5. **Mark Attendance**: Check-In / Check-Out pages (or let employees use them)
6. **View Reports**: Dashboard → Reports, By Date, By Employee
7. **Export**: Download CSV for any date range

### Employee Steps
1. **Check-In**: Go to home page → Mark Attendance — In → face camera → wait for confirmation
2. **Check-Out**: Go to home page → Mark Attendance — Out → face camera → wait for confirmation
3. **View Records**: Login → My Attendance → select date range

---

## Common Issues

| Issue | Solution |
|-------|----------|
| `dlib` install fails | Install CMake first: `pip install cmake` |
| Camera not accessible | Allow browser camera permission; use HTTPS |
| "Model not trained" error | Go to Train Model page and run training |
| Face not recognized | Ensure good lighting; retrain with more photos |
| `shape_predictor_68_face_landmarks.dat` missing | Download from dlib model zoo |

---

## Security Notes

- Change `SECRET_KEY` in production (use environment variable `DJANGO_SECRET_KEY`)
- Set `DEBUG = False` in production
- Admin access is controlled by `is_staff=True` (set via Django admin or `createsuperuser`)
- CSRF protection enabled on all forms
- API endpoints use CSRF tokens for POST requests

