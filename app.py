import os
import re
import uuid
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import markupsafe

app = Flask(__name__)
# In a real app, use os.environ.get('SECRET_KEY')
app.secret_key = 'lifeflow123_secure_dev_key_only'

# Configure SQLite Database
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'lifeflow.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELS ---

class User(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='donor')
    donor_profile = db.relationship('Donor', backref='user', uselist=False, lazy=True)

class Donor(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    blood_type = db.Column(db.String(5), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    last_donation = db.Column(db.String(20), nullable=True) # YYYY-MM-DD
    medical_conditions = db.Column(db.Text, nullable=True)
    available = db.Column(db.Boolean, default=True)
    next_eligible = db.Column(db.String(20), nullable=True) # YYYY-MM-DD
    donations_count = db.Column(db.Integer, default=0)

class BloodRequest(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    patient_name = db.Column(db.String(100), nullable=False)
    blood_type = db.Column(db.String(5), nullable=False)
    units = db.Column(db.Integer, nullable=False)
    hospital = db.Column(db.String(150), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    urgency = db.Column(db.String(20), nullable=False) # normal, urgent, critical
    contact = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.String(50), nullable=False)

# Rate limiting store: session_id -> { 'count': int, 'reset_time': datetime }
CONTACT_RATE_LIMITS = {}

# --- SECURITY & UTILITY HELPERS ---

def sanitize_input(text):
    if text is None:
        return ""
    # Strip HTML tags basic validation
    clean_text = markupsafe.escape(str(text).strip())
    return clean_text

def validate_password_strength(password):
    # Minimum 8 chars, at least one number, at least one special character
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"\d", password):
        return False, "Password must include at least one number."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must include at least one special character."
    
    # Calculate strength for UI logic simulation later
    strength = "weak"
    if len(password) >= 12 and re.search(r"[A-Z]", password):
        strength = "strong"
    elif len(password) >= 10:
        strength = "fair"
        
    return True, strength

def mask_phone(phone, is_owner=False):
    if not phone: return ""
    if is_owner: return phone
    # Make sure we have enough digits to mask
    phone_str = str(phone)
    if len(phone_str) < 4: return phone_str
    return "*" * (len(phone_str) - 4) + phone_str[-4:]

def mask_email(email, is_owner=False):
    if not email or '@' not in email: return ""
    if is_owner: return email
    parts = email.split('@')
    name = parts[0]
    domain = parts[1]
    if len(name) <= 1:
        masked_name = name + "***"
    else:
        masked_name = name[0] + "***" + name[-1] if len(name)>2 else name[0]+"***"
    return f"{masked_name}@{domain}"

def check_session_timeout():
    now = datetime.now()
    if 'last_activity' in session:
        last_activity = datetime.fromisoformat(session['last_activity'])
        # 10 minute timeout
        if now - last_activity > timedelta(minutes=10):
            session.clear()
            flash("Your session has expired due to inactivity.", "warning")
            return True
    session['last_activity'] = now.isoformat()
    return False

# --- DECORATORS ---

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        if check_session_timeout():
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Generate CSRF token for forms
def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = str(uuid.uuid4())
    return session['_csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token

@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.get('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            abort(403, description="CSRF token validation failed.")

# Ensure session activity is updated
@app.before_request
def update_activity():
    if 'user_id' in session and request.endpoint != 'static':
        check_session_timeout()

# --- ROUTES ---

@app.route('/')
def index():
    # Filter critical requests for banner
    emergency_requests = BloodRequest.query.filter_by(urgency='critical').order_by(BloodRequest.timestamp.desc()).all()
    
    # Calculate stats
    donor_count = Donor.query.count()
    cities_count = db.session.query(Donor.city).distinct().count()
    
    stats = {
        'donors': donor_count,
        'lives_saved': donor_count * 3, # arbitrary stat logic
        'cities_covered': cities_count
    }
    
    return render_template('home.html', 
                           emergency_requests=emergency_requests,
                           stats=stats)

@app.route('/register', methods=['GET', 'POST'])
def register_donor():
    if request.method == 'POST':
        # Sanitize and collect inputs
        name = sanitize_input(request.form.get('name'))
        age = sanitize_input(request.form.get('age'))
        gender = sanitize_input(request.form.get('gender'))
        blood_type = sanitize_input(request.form.get('blood_type'))
        city = sanitize_input(request.form.get('city'))
        phone = sanitize_input(request.form.get('phone'))
        email = sanitize_input(request.form.get('email'))
        last_donation = sanitize_input(request.form.get('last_donation'))
        medical = sanitize_input(request.form.get('medical_conditions'))
        password = request.form.get('password')
        consent = request.form.get('consent')
        
        # Server-side validation
        if not all([name, age, gender, blood_type, city, phone, email, password, consent]):
            flash("All required fields must be filled out.", "error")
            return redirect(url_for('register_donor'))
            
        try:
            age_int = int(age)
            if age_int < 18 or age_int > 65:
                flash("Donor must be between 18 and 65 years old.", "error")
                return redirect(url_for('register_donor'))
        except ValueError:
            flash("Invalid age format.", "error")
            return redirect(url_for('register_donor'))

        is_valid_pw, pw_msg = validate_password_strength(password)
        if not is_valid_pw:
            flash(pw_msg, "error")
            return redirect(url_for('register_donor'))
            
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered.", "error")
            return redirect(url_for('register_donor'))

        # Create user
        user_id = str(uuid.uuid4())
        password_hash = generate_password_hash(password)
        
        new_user = User(
            id=user_id,
            email=email,
            password_hash=password_hash,
            role='donor'
        )
        db.session.add(new_user)
        
        # Calculate availability
        available = True
        next_eligible_date = ""
        if last_donation:
            try:
                last_dt = datetime.strptime(last_donation, "%Y-%m-%d")
                # Rule: 90 days between donations
                next_eligible = last_dt + timedelta(days=90)
                if datetime.now() < next_eligible:
                    available = False
                    next_eligible_date = next_eligible.strftime("%Y-%m-%d")
            except ValueError:
                pass # Default to available if parsing fails
        
        donor_count = Donor.query.count()
        donor_id = f"D-{donor_count+1000}"
        
        new_donor = Donor(
            id=donor_id,
            user_id=user_id,
            name=name,
            age=age_int,
            gender=gender,
            blood_type=blood_type,
            city=city.title(),
            phone=phone,
            email=email,
            last_donation=last_donation,
            medical_conditions=medical,
            available=available,
            next_eligible=next_eligible_date,
            donations_count=1 if last_donation else 0
        )
        db.session.add(new_donor)
        db.session.commit()
        
        # Log them in automatically
        session['user_id'] = user_id
        session['email'] = email
        session['last_activity'] = datetime.now().isoformat()
        
        flash(f"Registration successful! Your Donor ID is {donor_id}", "success")
        return redirect(url_for('dashboard'))
        
    return render_template('register.html')

@app.route('/donors')
def find_donors():
    blood_group = sanitize_input(request.args.get('blood_group', ''))
    city = sanitize_input(request.args.get('city', ''))
    
    query = Donor.query
    if blood_group:
        query = query.filter_by(blood_type=blood_group)
    if city:
        # Case insensitive like
        query = query.filter(Donor.city.ilike(f"%{city}%"))
        
    filtered_donors = query.all()
        
    # Prepare donor views (mask info)
    display_donors = []
    current_user_id = session.get('user_id')
    
    for d in filtered_donors:
        is_owner = (d.user_id == current_user_id)
        
        display_donor = {
            'id': d.id,
            'name': d.name,
            'age': d.age,
            'gender': d.gender,
            'blood_type': d.blood_type,
            'city': d.city,
            'available': d.available,
            'next_eligible': d.next_eligible,
            'phone_masked': mask_phone(d.phone, is_owner),
            'email_masked': mask_email(d.email, is_owner)
        }
        display_donors.append(display_donor)
        
    return render_template('find_donors.html', 
                           donors=display_donors, 
                           filters={'blood_group': blood_group, 'city': city})

@app.route('/api/contact_donor/<donor_id>', methods=['POST'])
def contact_donor_api(donor_id):
    # Simulated Rate Limiting for Contacting
    session_id = request.cookies.get('session', request.remote_addr)
    now = datetime.now()
    
    if session_id not in CONTACT_RATE_LIMITS:
        CONTACT_RATE_LIMITS[session_id] = {'count': 0, 'reset_time': now + timedelta(minutes=15)}
        
    rl_info = CONTACT_RATE_LIMITS[session_id]
    
    if now > rl_info['reset_time']:
        rl_info['count'] = 0
        rl_info['reset_time'] = now + timedelta(minutes=15)
        
    if rl_info['count'] >= 5:
        remaining_sec = int((rl_info['reset_time'] - now).total_seconds())
        return {"error": "Rate limit exceeded", "cooldown": remaining_sec}, 429
        
    # In a real app we'd trigger SMS/Email here
    donor = Donor.query.get_or_404(donor_id)
        
    rl_info['count'] += 1
    
    # Return unmasked phone if we successfully "contact" them conceptually (for simulation)
    return {"success": True, "phone": donor.phone}

@app.route('/requestBlood', methods=['GET', 'POST'])
def request_blood():
    if request.method == 'POST':
        patient_name = sanitize_input(request.form.get('patient_name'))
        blood_type = sanitize_input(request.form.get('blood_type'))
        units = sanitize_input(request.form.get('units'))
        hospital = sanitize_input(request.form.get('hospital'))
        city = sanitize_input(request.form.get('city'))
        urgency = sanitize_input(request.form.get('urgency'))
        contact = sanitize_input(request.form.get('contact'))
        
        if not all([patient_name, blood_type, units, hospital, city, urgency, contact]):
            flash("All fields are required.", "error")
            return redirect(url_for('request_blood'))
            
        req_id = f"REQ-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        new_req = BloodRequest(
            id=req_id,
            patient_name=patient_name,
            blood_type=blood_type,
            units=int(units),
            hospital=hospital.title(),
            city=city.title(),
            urgency=urgency, # normal, urgent, critical
            contact=contact,
            timestamp=datetime.now().isoformat()
        )
        db.session.add(new_req)
        db.session.commit()
        
        est_times = {
            'critical': '1-2 hours',
            'urgent': '4-12 hours',
            'normal': '24-48 hours'
        }
        
        flash(f"Request submitted successfully! Request ID: {req_id}. Estimated response: {est_times.get(urgency, 'TBD')}", "success")
        return redirect(url_for('index'))
        
    return render_template('request_blood.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session.get('user_id')
    donor = Donor.query.filter_by(user_id=user_id).first()
    
    if not donor:
        flash("Donor profile not found.", "error")
        return redirect(url_for('index'))
        
    badges = []
    if donor.donations_count >= 1: badges.append('First Drop')
    if donor.donations_count >= 3: badges.append('Bronze Saver')
    if donor.donations_count >= 5: badges.append('Silver Hero')
    if donor.donations_count >= 10: badges.append('Golden Lifesaver')
        
    history = []
    if donor.last_donation:
        history.append({
            'date': donor.last_donation,
            'location': donor.city + ' General',
            'units': 1
        })
        
    return render_template('dashboard.html', donor=donor, badges=badges, history=history)

@app.route('/auth', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Simulated auth logic
        email = sanitize_input(request.form.get('email'))
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['email'] = user.email
            session['last_activity'] = datetime.now().isoformat()
            # Regenerate CSRF on login for security
            session.pop('_csrf_token', None)
            
            flash("Welcome back!", "success")
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash("Invalid email or password.", "error")
            return redirect(url_for('login'))
            
    return render_template('login.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('index'))

# --- DB INIT & SEED DATA ---
def init_db():
    with app.app_context():
        db.create_all()
        # Seed only if no donors exist
        if Donor.query.count() > 0:
            return
            
        cities = ["Mumbai", "Delhi", "Bangalore", "Pune"]
        
        # Seed Donors
        fake_donors = [
            ("Rahul Sharma", 28, "Male", "O+", cities[0], "9876543210", "rahul@example.com", "2023-10-15"),
            ("Priya Singh", 25, "Female", "A-", cities[1], "9876543211", "priya@example.com", "2024-01-20"),
            ("Amit Patel", 35, "Male", "B+", cities[0], "9876543212", "amit@example.com", "2023-12-05"),
            ("Sneha Reddi", 30, "Female", "AB+", cities[2], "9876543213", "sneha@example.com", ""),
            ("Vikram Shah", 42, "Male", "O-", cities[3], "9876543214", "vikram@example.com", "2023-08-10"),
            ("Anjali Desai", 22, "Female", "A+", cities[0], "9876543215", "anjali@example.com", "2024-02-01"),
        ]
        
        for i, (n, a, g, bt, c, p, e, ld) in enumerate(fake_donors):
            uid = str(uuid.uuid4())
            new_user = User(
                id=uid,
                email=e,
                password_hash=generate_password_hash('Password@123'),
                role='donor'
            )
            db.session.add(new_user)
            
            av = True
            ned = ""
            if ld:
                last_dt = datetime.strptime(ld, "%Y-%m-%d")
                next_eligible = last_dt + timedelta(days=90)
                if datetime.now() < next_eligible:
                    av = False
                    ned = next_eligible.strftime("%Y-%m-%d")
                    
            new_donor = Donor(
                id=f"D-100{i}",
                user_id=uid,
                name=n,
                age=a,
                gender=g,
                blood_type=bt,
                city=c,
                phone=p,
                email=e,
                last_donation=ld,
                available=av,
                next_eligible=ned,
                donations_count=1 if ld else 0
            )
            db.session.add(new_donor)
            
        # Seed Requests
        fake_reqs = [
            ("Suresh Kumar", "O-", 2, "Max Hospital", cities[1], "critical", "9998887770"),
            ("Manisha Gupta", "B+", 1, "City Care Clinic", cities[0], "urgent", "9998887771"),
            ("Ramesh Pawar", "A+", 3, "Global Hospital", cities[2], "normal", "9998887772")
        ]
        
        for i, (pn, bt, u, h, c, urg, cont) in enumerate(fake_reqs):
            req = BloodRequest(
                id=f"REQ-SIM00{i}",
                patient_name=pn,
                blood_type=bt,
                units=u,
                hospital=h,
                city=c,
                urgency=urg,
                contact=cont,
                timestamp=(datetime.now() - timedelta(hours=i*5)).isoformat()
            )
            db.session.add(req)
            
        db.session.commit()

if __name__ == '__main__':
    # Initialize DB before running
    init_db()
    # Run the app
    app.run(debug=True, port=5000, host="0.0.0.0")
