from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
import uuid
import json
import os
import boto3
from functools import wraps

app = Flask(__name__)
app.secret_key = 'hemalink-secret-key-2026'

# ============== DATA STORAGE (Local - Will be replaced with AWS later) ==============

# Donors dictionary: {donor_id: donor_data}
donors_db = {}

# Requestors dictionary: {requestor_id: requestor_data}
requestors_db = {}

# Blood requests dictionary: {request_id: request_data}
blood_requests_db = {}

# Donations dictionary: {donation_id: donation_data}
donations_db = {}

# Blood inventory by blood group
blood_inventory = {
    'A+': {'units': 50, 'donors': []},
    'A-': {'units': 30, 'donors': []},
    'B+': {'units': 45, 'donors': []},
    'B-': {'units': 25, 'donors': []},
    'AB+': {'units': 20, 'donors': []},
    'AB-': {'units': 15, 'donors': []},
    'O+': {'units': 60, 'donors': []},
    'O-': {'units': 40, 'donors': []}
}

# ============== BLOOD COMPATIBILITY MATRIX ==============
# Who can receive from whom
BLOOD_COMPATIBILITY = {
    'A+': ['A+', 'A-', 'O+', 'O-'],
    'A-': ['A-', 'O-'],
    'B+': ['B+', 'B-', 'O+', 'O-'],
    'B-': ['B-', 'O-'],
    'AB+': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],  # Universal recipient
    'AB-': ['A-', 'B-', 'AB-', 'O-'],
    'O+': ['O+', 'O-'],
    'O-': ['O-']  # Universal donor
}

# ============== HELPER FUNCTIONS ==============

def generate_donor_id():
    """Generate unique donor ID"""
    return f"DON-{uuid.uuid4().hex[:8].upper()}"

def generate_requestor_id():
    """Generate unique requestor ID"""
    return f"REQ-{uuid.uuid4().hex[:8].upper()}"

def generate_request_id():
    """Generate unique blood request ID"""
    return f"BR-{uuid.uuid4().hex[:8].upper()}"

def generate_donation_id():
    """Generate unique donation ID"""
    return f"DN-{uuid.uuid4().hex[:8].upper()}"

def get_compatible_donors(blood_group, location=None):
    """
    Find compatible donors for a blood group
    Returns list of compatible donor IDs
    """
    compatible_groups = BLOOD_COMPATIBILITY.get(blood_group, [])
    compatible_donors = []
    
    for donor_id, donor in donors_db.items():
        if donor['blood_group'] in compatible_groups:
            if donor['available'] and donor['status'] == 'active':
                # Check location if specified
                if location:
                    if location.lower() in donor['city'].lower() or location.lower() in donor['state'].lower():
                        compatible_donors.append(donor)
                else:
                    compatible_donors.append(donor)
    
    # Sort by last donation date (most recent first)
    compatible_donors.sort(key=lambda x: x.get('last_donation', '1900-01-01'), reverse=True)
    return compatible_donors

def can_donate(last_donation_date):
    """Check if donor can donate (56 days gap required)"""
    if not last_donation_date:
        return True
    last = datetime.strptime(last_donation_date, '%Y-%m-%d')
    return (datetime.now() - last).days >= 56

def calculate_donor_eligibility(donor):
    """Calculate donor eligibility score"""
    score = 100
    
    # Age factor
    age = donor.get('age', 0)
    if 25 <= age <= 45:
        score += 10
    elif age < 18 or age > 65:
        score -= 50
    
    # Availability
    if not donor.get('available', True):
        score -= 100
    
    # Last donation recency
    last_donation = donor.get('last_donation')
    if last_donation:
        days_since = (datetime.now() - datetime.strptime(last_donation, '%Y-%m-%d')).days
        if days_since > 90:
            score += 5
    else:
        score += 10  # New donor bonus
    
    # Donation history
    total_donations = donor.get('total_donations', 0)
    score += min(total_donations * 2, 20)
    
    return max(0, min(score, 150))

def match_blood_request(request_data):
    """
    Blood matching algorithm
    Finds best matching donors for a blood request
    """
    blood_group = request_data['blood_group']
    units_needed = request_data['units_needed']
    location = request_data.get('location', '')
    urgency = request_data.get('urgency', 'normal')
    
    # Get compatible donors
    compatible_donors = get_compatible_donors(blood_group, location)
    
    # Calculate eligibility scores
    scored_donors = []
    for donor in compatible_donors:
        score = calculate_donor_eligibility(donor)
        scored_donors.append({
            **donor,
            'match_score': score,
            'can_donate_now': can_donate(donor.get('last_donation'))
        })
    
    # Sort by match score
    scored_donors.sort(key=lambda x: x['match_score'], reverse=True)
    
    # Check inventory first for exact match
    inventory_available = blood_inventory.get(blood_group, {}).get('units', 0)
    
    return {
        'exact_match_inventory': inventory_available,
        'compatible_donors': scored_donors[:10],  # Top 10 matches
        'total_compatible': len(scored_donors),
        'fulfillable': inventory_available >= units_needed or len(scored_donors) > 0
    }

def update_inventory(blood_group, units, operation='add'):
    """Update blood inventory"""
    if blood_group in blood_inventory:
        if operation == 'add':
            blood_inventory[blood_group]['units'] += units
        elif operation == 'remove':
            blood_inventory[blood_group]['units'] = max(0, blood_inventory[blood_group]['units'] - units)

def get_statistics():
    """Get dashboard statistics"""
    total_donors = len(donors_db)
    total_requestors = len(requestors_db)
    total_requests = len(blood_requests_db)
    
    active_requests = sum(1 for r in blood_requests_db.values() if r['status'] == 'pending')
    fulfilled_requests = sum(1 for r in blood_requests_db.values() if r['status'] == 'fulfilled')
    
    total_units_available = sum(inv['units'] for inv in blood_inventory.values())
    
    # Critical blood groups (less than 20 units)
    critical_groups = [bg for bg, inv in blood_inventory.items() if inv['units'] < 20]
    
    return {
        'total_donors': total_donors,
        'total_requestors': total_requestors,
        'total_requests': total_requests,
        'active_requests': active_requests,
        'fulfilled_requests': fulfilled_requests,
        'total_units': total_units_available,
        'critical_groups': critical_groups,
        'inventory': blood_inventory
    }

# ============== ROUTES ==============

@app.route('/')
def home():
    """Home page"""
    stats = get_statistics()
    recent_requests = sorted(
        blood_requests_db.values(), 
        key=lambda x: x['created_at'], 
        reverse=True
    )[:5]
    return render_template('index.html', stats=stats, recent_requests=recent_requests)

@app.route('/about')
def about():
    """About page"""
    return render_template('about.html')

# ============== DONOR ROUTES ==============

@app.route('/donor/register', methods=['GET', 'POST'])
def donor_register():
    """Donor registration"""
    if request.method == 'POST':
        donor_id = generate_donor_id()
        
        donor_data = {
            'donor_id': donor_id,
            'name': request.form['name'],
            'email': request.form['email'],
            'phone': request.form['phone'],
            'age': int(request.form['age']),
            'gender': request.form['gender'],
            'blood_group': request.form['blood_group'],
            'weight': float(request.form['weight']),
            'address': request.form['address'],
            'city': request.form['city'],
            'state': request.form['state'],
            'pincode': request.form['pincode'],
            'medical_history': request.form.get('medical_history', 'None'),
            'available': True,
            'status': 'active',
            'total_donations': 0,
            'last_donation': None,
            'registered_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'emergency_contact': request.form.get('emergency_contact', ''),
            'preferred_contact_time': request.form.get('preferred_contact_time', 'Anytime')
        }
        
        # Validate age
        if donor_data['age'] < 18 or donor_data['age'] > 65:
            flash('Donor age must be between 18 and 65 years!', 'error')
            return redirect(url_for('donor_register'))
        
        # Validate weight
        if donor_data['weight'] < 50:
            flash('Donor weight must be at least 50kg!', 'error')
            return redirect(url_for('donor_register'))
        
        donors_db[donor_id] = donor_data
        
        # Update inventory donor list
        blood_inventory[donor_data['blood_group']]['donors'].append(donor_id)
        
        flash(f'Registration successful! Your Donor ID is: {donor_id}', 'success')
        return redirect(url_for('donor_dashboard', donor_id=donor_id))
    
    return render_template('donor_register.html')

@app.route('/donor/dashboard/<donor_id>')
def donor_dashboard(donor_id):
    """Donor dashboard"""
    donor = donors_db.get(donor_id)
    if not donor:
        flash('Donor not found!', 'error')
        return redirect(url_for('home'))
    
    # Get donation history
    donation_history = [d for d in donations_db.values() if d['donor_id'] == donor_id]
    
    # Check eligibility
    can_donate_now = can_donate(donor.get('last_donation'))
    
    return render_template('donor_dashboard.html', donor=donor, 
                          donation_history=donation_history, can_donate_now=can_donate_now)

@app.route('/donor/login', methods=['GET', 'POST'])
def donor_login():
    """Donor login"""
    if request.method == 'POST':
        donor_id = request.form['donor_id']
        email = request.form['email']
        
        donor = donors_db.get(donor_id)
        if donor and donor['email'] == email:
            session['donor_id'] = donor_id
            flash('Login successful!', 'success')
            return redirect(url_for('donor_dashboard', donor_id=donor_id))
        else:
            flash('Invalid Donor ID or Email!', 'error')
    
    return render_template('donor_login.html')

@app.route('/donor/update/<donor_id>', methods=['POST'])
def donor_update(donor_id):
    """Update donor information"""
    donor = donors_db.get(donor_id)
    if not donor:
        flash('Donor not found!', 'error')
        return redirect(url_for('home'))
    
    donor['phone'] = request.form.get('phone', donor['phone'])
    donor['address'] = request.form.get('address', donor['address'])
    donor['available'] = request.form.get('available') == 'on'
    donor['city'] = request.form.get('city', donor['city'])
    donor['state'] = request.form.get('state', donor['state'])
    
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('donor_dashboard', donor_id=donor_id))

@app.route('/donor/donate/<donor_id>', methods=['POST'])
def record_donation(donor_id):
    """Record a new donation"""
    donor = donors_db.get(donor_id)
    if not donor:
        flash('Donor not found!', 'error')
        return redirect(url_for('home'))
    
    if not can_donate(donor.get('last_donation')):
        flash('You must wait 56 days between donations!', 'error')
        return redirect(url_for('donor_dashboard', donor_id=donor_id))
    
    donation_id = generate_donation_id()
    units = int(request.form.get('units', 1))
    
    donation_data = {
        'donation_id': donation_id,
        'donor_id': donor_id,
        'donor_name': donor['name'],
        'blood_group': donor['blood_group'],
        'units': units,
        'donation_date': datetime.now().strftime('%Y-%m-%d'),
        'donation_center': request.form.get('donation_center', 'Main Center'),
        'notes': request.form.get('notes', '')
    }
    
    donations_db[donation_id] = donation_data
    
    # Update donor record
    donor['last_donation'] = donation_data['donation_date']
    donor['total_donations'] += 1
    
    # Update inventory
    update_inventory(donor['blood_group'], units, 'add')
    
    flash(f'Donation recorded successfully! Donation ID: {donation_id}', 'success')
    return redirect(url_for('donor_dashboard', donor_id=donor_id))

# ============== REQUESTOR ROUTES ==============

@app.route('/requestor/register', methods=['GET', 'POST'])
def requestor_register():
    """Requestor registration"""
    if request.method == 'POST':
        requestor_id = generate_requestor_id()
        
        requestor_data = {
            'requestor_id': requestor_id,
            'name': request.form['name'],
            'email': request.form['email'],
            'phone': request.form['phone'],
            'organization': request.form.get('organization', 'Individual'),
            'address': request.form['address'],
            'city': request.form['city'],
            'state': request.form['state'],
            'pincode': request.form['pincode'],
            'registered_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_requests': 0
        }
        
        requestors_db[requestor_id] = requestor_data
        
        flash(f'Registration successful! Your Requestor ID is: {requestor_id}', 'success')
        return redirect(url_for('requestor_dashboard', requestor_id=requestor_id))
    
    return render_template('requestor_register.html')

@app.route('/requestor/dashboard/<requestor_id>')
def requestor_dashboard(requestor_id):
    """Requestor dashboard"""
    requestor = requestors_db.get(requestor_id)
    if not requestor:
        flash('Requestor not found!', 'error')
        return redirect(url_for('home'))
    
    # Get request history
    request_history = [r for r in blood_requests_db.values() if r['requestor_id'] == requestor_id]
    
    return render_template('requestor_dashboard.html', requestor=requestor, 
                          request_history=request_history)

@app.route('/requestor/login', methods=['GET', 'POST'])
def requestor_login():
    """Requestor login"""
    if request.method == 'POST':
        requestor_id = request.form['requestor_id']
        email = request.form['email']
        
        requestor = requestors_db.get(requestor_id)
        if requestor and requestor['email'] == email:
            session['requestor_id'] = requestor_id
            flash('Login successful!', 'success')
            return redirect(url_for('requestor_dashboard', requestor_id=requestor_id))
        else:
            flash('Invalid Requestor ID or Email!', 'error')
    
    return render_template('requestor_login.html')

# ============== BLOOD REQUEST ROUTES ==============

@app.route('/request-blood', methods=['GET', 'POST'])
def request_blood():
    """Create blood request"""
    if request.method == 'POST':
        request_id = generate_request_id()
        
        request_data = {
            'request_id': request_id,
            'requestor_id': request.form.get('requestor_id', 'GUEST'),
            'patient_name': request.form['patient_name'],
            'patient_age': int(request.form['patient_age']),
            'patient_gender': request.form['patient_gender'],
            'blood_group': request.form['blood_group'],
            'units_needed': int(request.form['units_needed']),
            'hospital_name': request.form['hospital_name'],
            'hospital_address': request.form['hospital_address'],
            'location': request.form.get('city', ''),
            'city': request.form.get('city', ''),
            'state': request.form.get('state', ''),
            'contact_name': request.form['contact_name'],
            'contact_phone': request.form['contact_phone'],
            'contact_email': request.form.get('contact_email', ''),
            'urgency': request.form.get('urgency', 'normal'),
            'required_date': request.form['required_date'],
            'reason': request.form.get('reason', ''),
            'status': 'pending',
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'matched_donors': [],
            'fulfilled_units': 0
        }
        
        blood_requests_db[request_id] = request_data
        
        # Update requestor stats if registered
        requestor_id = request_data['requestor_id']
        if requestor_id in requestors_db:
            requestors_db[requestor_id]['total_requests'] += 1
        
        # Run matching algorithm
        match_results = match_blood_request(request_data)
        blood_requests_db[request_id]['matched_donors'] = [d['donor_id'] for d in match_results['compatible_donors']]
        
        flash(f'Blood request created! Request ID: {request_id}', 'success')
        return redirect(url_for('request_details', request_id=request_id))
    
    return render_template('request_blood.html')

@app.route('/request/<request_id>')
def request_details(request_id):
    """View request details with matched donors"""
    request_data = blood_requests_db.get(request_id)
    if not request_data:
        flash('Request not found!', 'error')
        return redirect(url_for('home'))
    
    # Get fresh match results
    match_results = match_blood_request(request_data)
    
    return render_template('request_details.html', request=request_data, 
                          match_results=match_results)

@app.route('/search-donors', methods=['GET', 'POST'])
def search_donors():
    """Search for donors"""
    results = []
    search_performed = False
    
    if request.method == 'POST':
        blood_group = request.form.get('blood_group', '')
        location = request.form.get('location', '')
        
        search_performed = True
        
        for donor in donors_db.values():
            match = True
            
            if blood_group and donor['blood_group'] != blood_group:
                match = False
            
            if location:
                loc_match = (location.lower() in donor['city'].lower() or 
                           location.lower() in donor['state'].lower() or
                           location.lower() in donor['pincode'])
                if not loc_match:
                    match = False
            
            if match and donor['available'] and donor['status'] == 'active':
                results.append(donor)
    
    return render_template('search_donors.html', results=results, 
                          search_performed=search_performed)

@app.route('/blood-inventory')
def blood_inventory_view():
    """View blood inventory"""
    stats = get_statistics()
    return render_template('blood_inventory.html', inventory=blood_inventory, stats=stats)

# ============== ADMIN/UTILITY ROUTES ==============

@app.route('/dashboard')
def admin_dashboard():
    """Admin dashboard"""
    stats = get_statistics()
    
    # Get all data for admin view
    all_donors = list(donors_db.values())
    all_requests = sorted(blood_requests_db.values(), 
                         key=lambda x: x['created_at'], reverse=True)
    all_donations = sorted(donations_db.values(),
                          key=lambda x: x['donation_date'], reverse=True)
    
    return render_template('admin_dashboard.html', stats=stats, 
                          donors=all_donors, requests=all_requests,
                          donations=all_donations)

@app.route('/api/statistics')
def api_statistics():
    """API endpoint for statistics"""
    return jsonify(get_statistics())

@app.route('/api/donors')
def api_donors():
    """API endpoint for donors"""
    return jsonify(list(donors_db.values()))

@app.route('/api/requests')
def api_requests():
    """API endpoint for blood requests"""
    return jsonify(list(blood_requests_db.values()))

@app.route('/request/<request_id>/fulfill', methods=['POST'])
def fulfill_request(request_id):
    """Mark request as fulfilled"""
    request_data = blood_requests_db.get(request_id)
    if not request_data:
        flash('Request not found!', 'error')
        return redirect(url_for('home'))
    
    units_fulfilled = int(request.form.get('units_fulfilled', 0))
    
    request_data['fulfilled_units'] += units_fulfilled
    
    if request_data['fulfilled_units'] >= request_data['units_needed']:
        request_data['status'] = 'fulfilled'
        flash('Request fully fulfilled!', 'success')
    else:
        request_data['status'] = 'partial'
        remaining = request_data['units_needed'] - request_data['fulfilled_units']
        flash(f'Partially fulfilled! {remaining} units still needed.', 'info')
    
    # Update inventory
    update_inventory(request_data['blood_group'], units_fulfilled, 'remove')
    
    return redirect(url_for('request_details', request_id=request_id))

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('home'))

# ============== ERROR HANDLERS ==============

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

# ============== INITIALIZE SAMPLE DATA ==============

def init_sample_data():
    """Initialize sample data for testing"""
    # Sample donors
    sample_donors = [
        {
            'donor_id': 'DON-A1B2C3D4',
            'name': 'Rahul Sharma',
            'email': 'rahul@example.com',
            'phone': '9876543210',
            'age': 28,
            'gender': 'Male',
            'blood_group': 'O+',
            'weight': 70,
            'address': '123 Main Street',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'pincode': '400001',
            'medical_history': 'None',
            'available': True,
            'status': 'active',
            'total_donations': 5,
            'last_donation': '2024-12-01',
            'registered_at': '2024-01-15 10:30:00',
            'emergency_contact': '9876543211',
            'preferred_contact_time': 'Evening'
        },
        {
            'donor_id': 'DON-E5F6G7H8',
            'name': 'Priya Patel',
            'email': 'priya@example.com',
            'phone': '8765432109',
            'age': 32,
            'gender': 'Female',
            'blood_group': 'A+',
            'weight': 58,
            'address': '456 Park Avenue',
            'city': 'Delhi',
            'state': 'Delhi',
            'pincode': '110001',
            'medical_history': 'None',
            'available': True,
            'status': 'active',
            'total_donations': 3,
            'last_donation': '2025-01-10',
            'registered_at': '2024-03-20 14:15:00',
            'emergency_contact': '8765432110',
            'preferred_contact_time': 'Morning'
        },
        {
            'donor_id': 'DON-I9J0K1L2',
            'name': 'Amit Kumar',
            'email': 'amit@example.com',
            'phone': '7654321098',
            'age': 25,
            'gender': 'Male',
            'blood_group': 'B-',
            'weight': 72,
            'address': '789 Gandhi Road',
            'city': 'Bangalore',
            'state': 'Karnataka',
            'pincode': '560001',
            'medical_history': 'None',
            'available': True,
            'status': 'active',
            'total_donations': 2,
            'last_donation': None,
            'registered_at': '2024-06-10 09:00:00',
            'emergency_contact': '7654321099',
            'preferred_contact_time': 'Anytime'
        },
        {
            'donor_id': 'DON-M3N4O5P6',
            'name': 'Sneha Gupta',
            'email': 'sneha@example.com',
            'phone': '6543210987',
            'age': 29,
            'gender': 'Female',
            'blood_group': 'O-',
            'weight': 55,
            'address': '321 Lake View',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'pincode': '600001',
            'medical_history': 'None',
            'available': True,
            'status': 'active',
            'total_donations': 8,
            'last_donation': '2025-01-15',
            'registered_at': '2023-08-05 16:45:00',
            'emergency_contact': '6543210988',
            'preferred_contact_time': 'Afternoon'
        },
        {
            'donor_id': 'DON-Q7R8S9T0',
            'name': 'Vikram Singh',
            'email': 'vikram@example.com',
            'phone': '5432109876',
            'age': 35,
            'gender': 'Male',
            'blood_group': 'AB+',
            'weight': 80,
            'address': '654 Hillside',
            'city': 'Pune',
            'state': 'Maharashtra',
            'pincode': '411001',
            'medical_history': 'None',
            'available': True,
            'status': 'active',
            'total_donations': 4,
            'last_donation': '2024-11-20',
            'registered_at': '2024-02-28 11:20:00',
            'emergency_contact': '5432109877',
            'preferred_contact_time': 'Evening'
        }
    ]
    
    for donor in sample_donors:
        donors_db[donor['donor_id']] = donor
        blood_inventory[donor['blood_group']]['donors'].append(donor['donor_id'])
    
    # Sample requestors
    sample_requestors = [
        {
            'requestor_id': 'REQ-X1Y2Z3A4',
            'name': 'Dr. Meera Reddy',
            'email': 'meera@hospital.com',
            'phone': '4321098765',
            'organization': 'City General Hospital',
            'address': 'Hospital Road',
            'city': 'Hyderabad',
            'state': 'Telangana',
            'pincode': '500001',
            'registered_at': '2024-04-10 08:30:00',
            'total_requests': 2
        }
    ]
    
    for requestor in sample_requestors:
        requestors_db[requestor['requestor_id']] = requestor
    
    # Sample blood requests
    sample_requests = [
        {
            'request_id': 'BR-B5C6D7E8',
            'requestor_id': 'REQ-X1Y2Z3A4',
            'patient_name': 'Ramesh Iyer',
            'patient_age': 45,
            'patient_gender': 'Male',
            'blood_group': 'O+',
            'units_needed': 2,
            'hospital_name': 'City General Hospital',
            'hospital_address': 'Hospital Road, Hyderabad',
            'location': 'Hyderabad',
            'city': 'Hyderabad',
            'state': 'Telangana',
            'contact_name': 'Dr. Meera Reddy',
            'contact_phone': '4321098765',
            'contact_email': 'meera@hospital.com',
            'urgency': 'high',
            'required_date': '2025-02-05',
            'reason': 'Surgery',
            'status': 'pending',
            'created_at': '2025-02-01 09:00:00',
            'matched_donors': ['DON-A1B2C3D4'],
            'fulfilled_units': 0
        }
    ]
    
    for req in sample_requests:
        blood_requests_db[req['request_id']] = req

# Initialize sample data
init_sample_data()

# ============== MAIN ==============


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
