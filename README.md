
```markdown
# Smart AI Attendance & Shift Management System 🎯

An enterprise-level, AI-powered attendance and human resource management system. This application utilizes state-of-the-art deep learning models for real-time face recognition and provides a comprehensive dashboard for shift management, dynamic thresholding, and smart absence analytics.

## 🌟 Key Features

* **Real-Time Face Recognition:** Uses the `buffalo_l` (InsightFace/ONNX) model for highly accurate, multi-face detection and identification via IP Cameras (RTSP), Webcams, or Video files.
* **Advanced Shift Management:**
  * Supports multiple overlapping shifts per person.
  * Smart detection of overnight shifts crossing midnight.
  * Real-time logic validation to prevent shift overlaps and scheduling conflicts.
* **Smart Absence Analytics (Noise Reduction):**
  * **Ignore Threshold:** Automatically filters out short, temporary absences (e.g., under 2 minutes).
  * **Danger Threshold:** Highlights prolonged absences (e.g., over 15 minutes) for immediate HR action.
  * **Shift-Cap Logic:** Automatically stops the absence timer when an employee's official shift ends.
* **Dynamic Terminology:** Fully customizable UI terms (e.g., switch between "Worker/Workers" or "Student/Students" globally) without altering the database.
* **Rich Desktop UI (PyQt5):** Modern, RTL-supported graphical interface with interactive thumbnail galleries, smart date-pickers (Jalali/Shamsi calendar), and dark/light modes.
* **Export & Reporting:** Generate precise attendance reports in Excel (CSV) and print-ready PDF formats.

## 🛠️ Tech Stack

* **Backend:** FastAPI, SQLAlchemy, SQLite 
* **Frontend:** PyQt5, QSettings (Local Caching)
* **AI & Computer Vision:** OpenCV, InsightFace, ONNX Runtime, Pillow (for dynamic Persian text rendering)
* **Time Management:** `jdatetime` for full Persian (Jalali) calendar integration.

## 🚀 Getting Started

### Prerequisites
Ensure you have Python 3.9+ installed. It is highly recommended to use a virtual environment.

### 1. Install Dependencies
```bash
pip install -r requirements.txt

```

*(Make sure `onnxruntime` or `onnxruntime-gpu` is installed based on your hardware capabilities).*

### 2. Add the AI Model

Place the `buffalo_l` model folder inside the `ai/models/` directory or the default `~/.insightface/models/` path.

### 3. Run the Backend Server

Navigate to the `backend` directory and start the FastAPI server:

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

```

### 4. Launch the Desktop Application

Open a new terminal, navigate to the project root, and run the client:

```bash
python main.py

```

## 🖥️ System Modules

* **Overview Dashboard:** Live statistics of active cameras, total personnel, and current absentees.
* **Live Dashboard:** Real-time video feed with bounding boxes, dynamic statuses (Inside/Outside), and Persian text overlay.
* **Personnel Management:** Register new identities, manage face galleries (upload/remove photos), and assign complex shifts.
* **Events & Reports:** Smart data grid applying logical thresholds to raw camera logs to extract actionable absence reports.
* **Settings:** Tweak AI thresholds and UI terminology dynamically.

```

```