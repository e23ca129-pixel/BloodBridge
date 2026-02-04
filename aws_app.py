from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime
import uuid
import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

app = Flask(__name__)
app.secret_key = os.getenv('HEMALINK_SECRET', 'hemalink-secret-key-2026')

# AWS config via env vars with sane defaults
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
DONORS_TABLE = os.getenv('DONORS_TABLE', 'Donors')
REQUESTORS_TABLE = os.getenv('REQUESTORS_TABLE', 'Requestors')
REQUESTS_TABLE = os.getenv('REQUESTS_TABLE', 'BloodRequests')
DONATIONS_TABLE = os.getenv('DONATIONS_TABLE', 'Donations')
INVENTORY_TABLE = os.getenv('INVENTORY_TABLE', 'BloodInventory')

# Compatibility matrix (copied from local app)
BLOOD_COMPATIBILITY = {
    'A+': ['A+', 'A-', 'O+', 'O-'],
    'A-': ['A-', 'O-'],
    'B+': ['B+', 'B-', 'O+', 'O-'],
    'B-': ['B-', 'O-'],
    'AB+': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
    'AB-': ['A-', 'B-', 'AB-', 'O-'],
    'O+': ['O+', 'O-'],
    'O-': ['O-']
}

# Attempt to initialize AWS resources
use_aws = True
try:
    session = boto3.Session(region_name=AWS_REGION)
    dynamodb = session.resource('dynamodb')

    # Table objects
    donors_table = dynamodb.Table(DONORS_TABLE)
    requestors_table = dynamodb.Table(REQUESTORS_TABLE)
    requests_table = dynamodb.Table(REQUESTS_TABLE)
    donations_table = dynamodb.Table(DONATIONS_TABLE)
    inventory_table = dynamodb.Table(INVENTORY_TABLE)

    # Quick sanity check: call list_tables or describe a table to surface credential issues
    _ = session.client('dynamodb').list_tables(Limit=1)
except (NoCredentialsError, ClientError, Exception) as e:
    print(f"[aws_app] Warning: AWS not available or misconfigured - falling back to local storage. ({e})")
    use_aws = False

# Local in-memory stores as fallback
local_donors = {}
local_requestors = {}
local_requests = {}
local_donations = {}
local_inventory = {
    'A+': {'units': 0, 'donors': []},
    'A-': {'units': 0, 'donors': []},
    'B+': {'units': 0, 'donors': []},
    'B-': {'units': 0, 'donors': []},
    'AB+': {'units': 0, 'donors': []},
    'AB-': {'units': 0, 'donors': []},
    'O+': {'units': 0, 'donors': []},
    'O-': {'units': 0, 'donors': []}
}

# ---------- Helpers ----------

def send_notification(subject, message):
    """Log notification (SNS removed)."""
    print(f"[notify] {subject}: {message}")


def _gen_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# ---------- DynamoDB wrappers with fallback ----------

def put_item(table, item):
    if use_aws:
        try:
            table.put_item(Item=item)
            return True
        except ClientError as e:
            print(f"DynamoDB put_item error: {e}")
            return False
    # fallback
    if table is donors_table or (not use_aws and table == DONORS_TABLE):
        local_donors[item['donor_id']] = item
    elif table is requestors_table or (not use_aws and table == REQUESTORS_TABLE):
        local_requestors[item['requestor_id']] = item
    elif table is requests_table or (not use_aws and table == REQUESTS_TABLE):
        local_requests[item['request_id']] = item
    elif table is donations_table or (not use_aws and table == DONATIONS_TABLE):
        local_donations[item['donation_id']] = item
    elif table is inventory_table or (not use_aws and table == INVENTORY_TABLE):
        local_inventory[item['blood_group']] = item
    return True


def get_item(table, key):
    if use_aws:
        try:
            resp = table.get_item(Key=key)
            return resp.get('Item')
        except ClientError as e:
            print(f"DynamoDB get_item error: {e}")
            return None
    # fallback
    # Figure out which local dict
    if table is donors_table or (not use_aws and table == DONORS_TABLE):
        return local_donors.get(key.get('donor_id'))
    if table is requestors_table or (not use_aws and table == REQUESTORS_TABLE):
        return local_requestors.get(key.get('requestor_id'))
    if table is requests_table or (not use_aws and table == REQUESTS_TABLE):
        return local_requests.get(key.get('request_id'))
    if table is inventory_table or (not use_aws and table == INVENTORY_TABLE):
        return local_inventory.get(key.get('blood_group'))
    return None


def scan_table(table, filter_expression=None):
    if use_aws:
        try:
            resp = table.scan()
            return resp.get('Items', [])
        except ClientError as e:
            print(f"DynamoDB scan error: {e}")
            return []
    # fallback
    if table is donors_table or (not use_aws and table == DONORS_TABLE):
        return list(local_donors.values())
    if table is requestors_table or (not use_aws and table == REQUESTORS_TABLE):
        return list(local_requestors.values())
    if table is requests_table or (not use_aws and table == REQUESTS_TABLE):
        return list(local_requests.values())
    if table is donations_table or (not use_aws and table == DONATIONS_TABLE):
        return list(local_donations.values())
    if table is inventory_table or (not use_aws and table == INVENTORY_TABLE):
        return list(local_inventory.values())
    return []


# ---------- Re-usable Matching & Inventory logic ----------

def can_donate(last_donation_date):
    if not last_donation_date:
        return True
    try:
        last = datetime.strptime(last_donation_date, '%Y-%m-%d')
        return (datetime.now() - last).days >= 56
    except Exception:
        return True


def calculate_donor_eligibility(donor):
    score = 100
    age = donor.get('age', 0)
    if 25 <= age <= 45:
        score += 10
    elif age < 18 or age > 65:
        score -= 50
    if not donor.get('available', True):
        score -= 100
    last_donation = donor.get('last_donation')
    if last_donation:
        try:
            days_since = (datetime.now() - datetime.strptime(last_donation, '%Y-%m-%d')).days
            if days_since > 90:
                score += 5
        except Exception:
            pass
    else:
        score += 10
    score += min(donor.get('total_donations', 0) * 2, 20)
    return max(0, min(score, 150))


def get_compatible_donors(blood_group, location=None):
    donors = scan_table(donors_table)
    compatible_groups = BLOOD_COMPATIBILITY.get(blood_group, [])
    compatible = []
    for donor in donors:
        if donor.get('blood_group') in compatible_groups and donor.get('available') and donor.get('status') == 'active':
            if location:
                if location.lower() in (donor.get('city', '').lower() + donor.get('state', '').lower()):
                    compatible.append(donor)
            else:
                compatible.append(donor)
    compatible.sort(key=lambda x: x.get('last_donation') or '1900-01-01', reverse=True)
    return compatible


def get_inventory_units(blood_group):
    inv = get_item(inventory_table, {'blood_group': blood_group})
    if inv:
        return int(inv.get('units', 0))
    # fallback
    return local_inventory.get(blood_group, {}).get('units', 0)


def update_inventory(blood_group, units, operation='add'):
    # Fetch or create record
    inv = get_item(inventory_table, {'blood_group': blood_group})
    if not inv:
        inv = {'blood_group': blood_group, 'units': 0, 'donors': []}
    if operation == 'add':
        inv['units'] = int(inv.get('units', 0)) + int(units)
    else:
        inv['units'] = max(0, int(inv.get('units', 0)) - int(units))
    put_item(inventory_table, inv)


def match_blood_request(request_data):
    blood_group = request_data['blood_group']
    units_needed = int(request_data.get('units_needed', 1))
    location = request_data.get('location', '')

    compatible = get_compatible_donors(blood_group, location)
    scored = []
    for d in compatible:
        score = calculate_donor_eligibility(d)
        scored.append({**d, 'match_score': score, 'can_donate_now': can_donate(d.get('last_donation'))})
    scored.sort(key=lambda x: x['match_score'], reverse=True)
    inventory_available = get_inventory_units(blood_group)
    return {
        'exact_match_inventory': inventory_available,
        'compatible_donors': scored[:10],
        'total_compatible': len(scored),
        'fulfillable': inventory_available >= units_needed or len(scored) > 0
    }


# ---------- Routes (minimal parity with `app.py`) ----------

@app.route('/')
def index():
    # show top level stats
    donors = scan_table(donors_table)
    requests = scan_table(requests_table)
    donations = scan_table(donations_table)
    inventory = {item['blood_group']: item for item in scan_table(inventory_table)}
    stats = {
        'total_donors': len(donors),
        'total_requests': len(requests),
        'total_donations': len(donations),
        'inventory': inventory
    }
    recent_requests = sorted(requests, key=lambda x: x.get('created_at', ''), reverse=True)[:5]
    return render_template('index.html', stats=stats, recent_requests=recent_requests)


@app.route('/donor/register', methods=['GET', 'POST'])
def donor_register():
    if request.method == 'POST':
        donor_id = _gen_id('DON')
        donor = {
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
            'registered_at': _now(),
            'emergency_contact': request.form.get('emergency_contact', ''),
            'preferred_contact_time': request.form.get('preferred_contact_time', 'Anytime')
        }
        # basic validations
        if donor['age'] < 18 or donor['age'] > 65:
            flash('Donor age must be between 18 and 65 years!', 'error')
            return redirect(url_for('donor_register'))
        if donor['weight'] < 50:
            flash('Donor weight must be at least 50kg!', 'error')
            return redirect(url_for('donor_register'))

        put_item(donors_table, donor)
        # update inventory donor list
        inv = get_item(inventory_table, {'blood_group': donor['blood_group']}) or {'blood_group': donor['blood_group'], 'units': 0, 'donors': []}
        inv['donors'] = list(set(inv.get('donors', []) + [donor_id]))
        put_item(inventory_table, inv)

        send_notification('New Donor Registered', f"Donor {donor['name']} ({donor_id}) registered.")
        flash(f'Registration successful! Your Donor ID is: {donor_id}', 'success')
        return redirect(url_for('donor_dashboard', donor_id=donor_id))

    return render_template('donor_register.html')


@app.route('/donor/login', methods=['GET', 'POST'])
def donor_login():
    if request.method == 'POST':
        donor_id = request.form['donor_id']
        email = request.form['email']
        donor = get_item(donors_table, {'donor_id': donor_id})
        if donor and donor.get('email') == email:
            session['donor_id'] = donor_id
            flash('Login successful!', 'success')
            return redirect(url_for('donor_dashboard', donor_id=donor_id))
        else:
            flash('Invalid Donor ID or Email!', 'error')
    return render_template('donor_login.html')


@app.route('/donor/dashboard/<donor_id>')
def donor_dashboard(donor_id):
    donor = get_item(donors_table, {'donor_id': donor_id})
    if not donor:
        flash('Donor not found!', 'error')
        return redirect(url_for('index'))
    # donations
    donations = [d for d in scan_table(donations_table) if d.get('donor_id') == donor_id]
    can_d = can_donate(donor.get('last_donation'))
    return render_template('donor_dashboard.html', donor=donor, donation_history=donations, can_donate_now=can_d)


@app.route('/donor/donate/<donor_id>', methods=['POST'])
def donor_donate(donor_id):
    donor = get_item(donors_table, {'donor_id': donor_id})
    if not donor:
        flash('Donor not found!', 'error')
        return redirect(url_for('index'))
    if not can_donate(donor.get('last_donation')):
        flash('You must wait 56 days between donations!', 'error')
        return redirect(url_for('donor_dashboard', donor_id=donor_id))
    donation_id = _gen_id('DN')
    units = int(request.form.get('units', 1))
    donation = {
        'donation_id': donation_id,
        'donor_id': donor_id,
        'donor_name': donor['name'],
        'blood_group': donor['blood_group'],
        'units': units,
        'donation_date': datetime.now().strftime('%Y-%m-%d'),
        'donation_center': request.form.get('donation_center', 'Main Center'),
        'notes': request.form.get('notes', '')
    }
    put_item(donations_table, donation)
    # update donor
    donor['last_donation'] = donation['donation_date']
    donor['total_donations'] = donor.get('total_donations', 0) + 1
    put_item(donors_table, donor)
    # update inventory
    update_inventory(donor['blood_group'], units, 'add')

    flash(f'Donation recorded successfully! Donation ID: {donation_id}', 'success')
    return redirect(url_for('donor_dashboard', donor_id=donor_id))


@app.route('/requestor/register', methods=['GET', 'POST'])
def requestor_register():
    if request.method == 'POST':
        requestor_id = _gen_id('REQ')
        requestor = {
            'requestor_id': requestor_id,
            'name': request.form['name'],
            'email': request.form['email'],
            'phone': request.form['phone'],
            'organization': request.form.get('organization', 'Individual'),
            'address': request.form['address'],
            'city': request.form['city'],
            'state': request.form['state'],
            'pincode': request.form['pincode'],
            'registered_at': _now(),
            'total_requests': 0
        }
        put_item(requestors_table, requestor)
        flash(f'Registration successful! Your Requestor ID is: {requestor_id}', 'success')
        return redirect(url_for('requestor_dashboard', requestor_id=requestor_id))
    return render_template('requestor_register.html')


@app.route('/requestor/dashboard/<requestor_id>')
def requestor_dashboard(requestor_id):
    requestor = get_item(requestors_table, {'requestor_id': requestor_id})
    if not requestor:
        flash('Requestor not found!', 'error')
        return redirect(url_for('index'))
    history = [r for r in scan_table(requests_table) if r.get('requestor_id') == requestor_id]
    return render_template('requestor_dashboard.html', requestor=requestor, request_history=history)


@app.route('/request-blood', methods=['GET', 'POST'])
def request_blood():
    if request.method == 'POST':
        request_id = _gen_id('BR')
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
            'created_at': _now(),
            'matched_donors': [],
            'fulfilled_units': 0
        }
        put_item(requests_table, request_data)
        # update requestor stats
        reqid = request_data['requestor_id']
        reqor = get_item(requestors_table, {'requestor_id': reqid}) if reqid != 'GUEST' else None
        if reqor:
            reqor['total_requests'] = reqor.get('total_requests', 0) + 1
            put_item(requestors_table, reqor)

        matches = match_blood_request(request_data)
        request_data['matched_donors'] = [d['donor_id'] for d in matches['compatible_donors']]
        put_item(requests_table, request_data)

        send_notification('New Blood Request', f"Request {request_id} for {request_data['blood_group']} registered.")
        flash(f'Blood request created! Request ID: {request_id}', 'success')
        return redirect(url_for('request_details', request_id=request_id))
    return render_template('request_blood.html')


@app.route('/request/<request_id>')
def request_details(request_id):
    req = get_item(requests_table, {'request_id': request_id})
    if not req:
        flash('Request not found!', 'error')
        return redirect(url_for('index'))
    matches = match_blood_request(req)
    return render_template('request_details.html', request=req, match_results=matches)


@app.route('/search-donors', methods=['GET', 'POST'])
def search_donors():
    results = []
    search_performed = False
    if request.method == 'POST':
        blood_group = request.form.get('blood_group', '')
        location = request.form.get('location', '')
        search_performed = True
        donors = scan_table(donors_table)
        for d in donors:
            match = True
            if blood_group and d.get('blood_group') != blood_group:
                match = False
            if location:
                loc = (d.get('city', '') + d.get('state', '') + d.get('pincode', ''))
                if location.lower() not in loc.lower():
                    match = False
            if match and d.get('available') and d.get('status') == 'active':
                results.append(d)
    return render_template('search_donors.html', results=results, search_performed=search_performed)


@app.route('/blood-inventory')
def blood_inventory_view():
    inv_items = scan_table(inventory_table)
    inv = {item['blood_group']: item for item in inv_items}
    stats = {'inventory': inv}
    return render_template('blood_inventory.html', inventory=inv, stats=stats)


@app.route('/dashboard')
def admin_dashboard():
    donors = scan_table(donors_table)
    requests = sorted(scan_table(requests_table), key=lambda x: x.get('created_at', ''), reverse=True)
    donations = sorted(scan_table(donations_table), key=lambda x: x.get('donation_date', ''), reverse=True)
    return render_template('admin_dashboard.html', stats=getattr(__import__('builtins'), 'dict')(), donors=donors, requests=requests, donations=donations)


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))


# ---------- Error handlers ----------
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
