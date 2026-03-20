# LifeFlow

LifeFlow is a modern, responsive blood donation web application built with Python and Flask. It connects blood donors with patients and hospitals in need, providing a streamlined platform for registering as a donor, requesting blood, and finding available donors based on blood group and location.

## Features

- **Donor Registration:** Users can sign up, create a profile, and log their donation history.
- **Find Donors:** Search for available donors by blood group and city.
- **Request Blood:** Hospitals and patients can submit emergency or normal blood requests.
- **Dashboard:** Registered donors have access to a personalized dashboard to track their donations, view upcoming eligibility, and earn badges.
- **Secure Authentication:** User accounts are secured using hashed passwords and session management.

## Tech Stack

- **Backend:** Python, Flask
- **Database:** SQLite (managed via Flask-SQLAlchemy)
- **Frontend:** HTML, CSS via Jinja2 templates (incorporating Tailwind CSS / modern design principles)

## Prerequisites

Make sure you have Python 3.x installed on your system.

## Installation & Setup

1. **Clone or Download the Repository:**
   Navigate to the project folder `LifeFlow`.
   ```bash
   cd /path/to/LifeFlow
   ```

2. **Create a Virtual Environment (Optional but recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. **Install Dependencies:**
   Install the required packages using the previously created `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the Application:**
   Start the Flask development server:
   ```bash
   python app.py
   ```
   *Note: The database (`lifeflow.db`) will be automatically initialized and seeded with sample data upon the first run.*

5. **Access the App:**
   Open your web browser and navigate to: [http://localhost:5000](http://localhost:5000) (or the corresponding URL displayed in your terminal).

## Project Structure

- `app.py`: The main application executable, containing routing, models, and application logic.
- `requirements.txt`: Python package dependencies.
- `templates/`: Directory containing Jinja2 HTML templates for the frontend.
- `lifeflow.db`: SQLite database file (generated automatically).

## License

This project is intended for educational and developmental purposes.
