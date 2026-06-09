# 🏢 HRM Pro — AI-Powered Human Resource Management System

A full-featured, production-ready **Human Resource Management System** built with FastAPI and Supabase, enhanced with **Google Gemini AI** for automated recruitment screening.

---

## ✨ Features

### 👥 Employee Management
- Employee directory with full CRUD operations
- Department & position management
- Role-based access control (Boss, HR Manager, Admin, Employee)

### 📅 Attendance & Leave
- QR code-based check-in / check-out
- Biometric device integration
- Leave request & approval workflow
- Leave balance tracking

### 💰 Payroll
- Monthly payroll generation in **Myanmar Kyat (MMK)**
- Payroll history and reporting

### 📊 Performance (KPI)
- KPI assignment and tracking
- Boss-level KPI oversight
- Peer voting / recognition system

### 🤖 AI-Powered Recruitment *(Powered by Google Gemini)*
- **Public career portal** (`/careers`) for candidates to apply
- **Automated resume scoring** — AI reads the PDF resume and scores candidates 1-10
- **Auto-routing** — High scorers (≥8) move to Screening automatically
- **HR alert notifications** when a high-scoring candidate is detected
- **AI Interview Guide** — Auto-generated in Burmese when a candidate reaches Interview stage
- **Automated Offer Letter** — Generated in MMK when moving candidate to Offer stage

### 📝 Document Management
- Document vault with signature workflow
- Boss → HR → Employee signature chain

### 🎂 Onboarding / Offboarding
- Structured onboarding task assignments
- Exit interview & offboarding workflow
- Birthday notifications

### 🔔 Notifications
- Real-time in-app notification bell
- Role-based notifications (Boss, HR Manager, All)

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI, Uvicorn |
| Database | Supabase (PostgreSQL) |
| Frontend | Jinja2 Templates, Vanilla CSS, JavaScript |
| AI | Google Gemini 2.5 Flash |
| Auth | Session-based with bcrypt password hashing |

---

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/hrm-pro.git
cd hrm-pro
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file (or set these directly in `app.py`):
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
GEMINI_API_KEY=your_gemini_api_key
SECRET_KEY=your_session_secret_key
```

### 4. Run the server
```bash
python app.py
```

Visit `http://localhost:5000` in your browser.

---

## 🔐 Default Roles

| Role | Access |
|------|--------|
| `boss` | Full access, KPI oversight, signature authority |
| `hr_manager` | Recruitment, employees, payroll, leave approval |
| `admin` | System settings, user management |
| `employee` | Self-service portal (attendance, leave, payroll view) |

---

## 📁 Project Structure

```
hrm-pro/
├── app.py                  # Main FastAPI application
├── requirements.txt        # Python dependencies
├── static/
│   ├── css/               # Custom stylesheets
│   └── js/                # JavaScript files
├── templates/             # Jinja2 HTML templates
│   ├── base.html
│   ├── dashboard.html
│   ├── recruitment.html
│   ├── careers.html
│   └── ...
└── setup_db.py            # Database schema setup script
```

---

## 📄 License

MIT License — feel free to use and modify for your own projects.
