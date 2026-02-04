# BloodSync - Blood Bank Management System

BloodSync is a comprehensive web application that connects blood donors with recipients. It provides real-time donor matching, blood inventory management, and request tracking.

## Features

### For Donors
- **Registration**: Easy donor registration with unique Donor ID
- **Profile Management**: Update personal information and availability status
- **Donation History**: Track all donations and eligibility
- **Eligibility Calculator**: Automatic eligibility checking based on age, weight, and donation interval

### For Requestors
- **Blood Requests**: Create urgent or normal blood requests
- **Request Tracking**: Track request status and fulfillment
- **Donor Matching**: Automatic matching with compatible donors
- **Contact Management**: Direct contact with matched donors

### General Features
- **Blood Inventory**: Real-time blood availability across all blood groups
- **Search Functionality**: Find donors by blood group and location
- **Compatibility Chart**: Blood group compatibility reference
- **Admin Dashboard**: Complete system overview and management
- **Emergency Contacts**: 24/7 helpline information

## Technology Stack

- **Backend**: Flask (Python)
- **Frontend**: HTML5, CSS3, Bootstrap 5, JavaScript
- **Data Storage**: Python Dictionaries (Local - will be replaced with AWS services)
- **Icons**: Font Awesome

## Blood Matching Algorithm

The system uses a sophisticated matching algorithm that considers:
1. **Blood Group Compatibility**: Based on medical compatibility charts
2. **Location Proximity**: City and state matching
3. **Donor Availability**: Real-time availability status
4. **Eligibility Score**: Based on age, donation history, and last donation date
5. **Urgency Level**: Priority handling for critical requests

## Installation (Windows 10/11)

### Step 1: Install Python
1. Download Python 3.8+ from [python.org](https://python.org)
2. Run the installer
3. **IMPORTANT**: Check "Add Python to PATH" during installation
4. Click "Install Now"

### Step 2: Extract BloodSync
1. Extract the `bloodsync.zip` file to a folder (e.g., `C:\BloodSync`)
2. Open Command Prompt (CMD) or PowerShell
3. Navigate to the BloodSync folder:
   ```
   cd C:\BloodSync
   ```

### Step 3: Create Virtual Environment (Recommended)
```
python -m venv venv
```

Activate the virtual environment:
- **CMD**: `venv\Scripts\activate`
- **PowerShell**: `venv\Scripts\Activate.ps1`

### Step 4: Install Dependencies
```
pip install -r requirements.txt
```

### Step 5: Run the Application
```
python app.py
```

### Step 6: Access the Website
1. Open your web browser
2. Go to: `http://localhost:5000`
3. BloodSync is now running!

## Sample Login Credentials

### Donor Login
- **Donor ID**: `DON-A1B2C3D4`
- **Email**: `rahul@example.com`

### Requestor Login
- **Requestor ID**: `REQ-X1Y2Z3A4`
- **Email**: `meera@hospital.com`

## Project Structure

```
bloodsync/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── static/
│   ├── css/
│   │   └── style.css     # Custom styles
│   ├── js/
│   │   └── main.js       # JavaScript functionality
│   └── images/           # Image assets
└── templates/            # HTML templates
    ├── base.html         # Base template
    ├── index.html        # Home page
    ├── donor_register.html
    ├── donor_login.html
    ├── donor_dashboard.html
    ├── requestor_register.html
    ├── requestor_login.html
    ├── requestor_dashboard.html
    ├── request_blood.html
    ├── request_details.html
    ├── search_donors.html
    ├── blood_inventory.html
    ├── admin_dashboard.html
    ├── about.html
    ├── 404.html
    └── 500.html
```

## Blood Group Compatibility

| Blood Type | Can Donate To | Can Receive From |
|------------|---------------|------------------|
| A+ | A+, AB+ | A+, A-, O+, O- |
| A- | A+, A-, AB+, AB- | A-, O- |
| B+ | B+, AB+ | B+, B-, O+, O- |
| B- | B+, B-, AB+, AB- | B-, O- |
| AB+ | AB+ Only | All Blood Types |
| AB- | AB+, AB- | A-, B-, AB-, O- |
| O+ | O+, A+, B+, AB+ | O+, O- |
| O- | All Blood Types | O- Only |

## Key Algorithms

### 1. Donor Matching Algorithm
```python
def get_compatible_donors(blood_group, location=None):
    compatible_groups = BLOOD_COMPATIBILITY.get(blood_group, [])
    compatible_donors = []
    
    for donor_id, donor in donors_db.items():
        if donor['blood_group'] in compatible_groups:
            if donor['available'] and donor['status'] == 'active':
                if location:
                    if location in donor['city'] or location in donor['state']:
                        compatible_donors.append(donor)
                else:
                    compatible_donors.append(donor)
    
    return compatible_donors
```

### 2. Eligibility Calculator
```python
def calculate_donor_eligibility(donor):
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
```

### 3. Donation Interval Check
```python
def can_donate(last_donation_date):
    if not last_donation_date:
        return True
    last = datetime.strptime(last_donation_date, '%Y-%m-%d')
    return (datetime.now() - last).days >= 56
```

## AWS Integration (Milestone 2)

When AWS access is provided, the following changes will be made:

1. **Database Migration**:
   - Replace Python dictionaries with DynamoDB tables
   - Create tables: `donors`, `requestors`, `blood_requests`, `donations`

2. **AWS Services**:
   - **DynamoDB**: Primary database for all entities
   - **S3**: Store donor documents and medical records
   - **Lambda**: Serverless functions for notifications
   - **API Gateway**: RESTful API endpoints

3. **Configuration**:
   ```python
   import boto3
   
   # DynamoDB client
   dynamodb = boto3.resource('dynamodb', 
       aws_access_key_id='YOUR_KEY',
       aws_secret_access_key='YOUR_SECRET',
       region_name='us-east-1'
   )
   ```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Home page |
| `/donor/register` | GET/POST | Donor registration |
| `/donor/login` | GET/POST | Donor login |
| `/donor/dashboard/<id>` | GET | Donor dashboard |
| `/requestor/register` | GET/POST | Requestor registration |
| `/requestor/login` | GET/POST | Requestor login |
| `/request-blood` | GET/POST | Create blood request |
| `/request/<id>` | GET | View request details |
| `/search-donors` | GET/POST | Search donors |
| `/blood-inventory` | GET | View blood inventory |
| `/dashboard` | GET | Admin dashboard |
| `/api/statistics` | GET | Get statistics (JSON) |
| `/api/donors` | GET | Get all donors (JSON) |
| `/api/requests` | GET | Get all requests (JSON) |

## Troubleshooting

### Issue: "python" command not found
**Solution**: Use `py` instead of `python` or add Python to your PATH

### Issue: Port 5000 already in use
**Solution**: Change the port in `app.py`:
```python
app.run(debug=True, host='0.0.0.0', port=5001)
```

### Issue: Virtual environment activation fails in PowerShell
**Solution**: Run PowerShell as Administrator and execute:
```
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Emergency Contacts

- **BloodSync Helpline**: 1800-BLOOD-HELP
- **National Blood Bank**: 1910
- **Emergency Services**: 108

## License

This project is created for educational purposes.

## Support

For any issues or questions, please contact:
- Email: help@bloodsync.org
- Phone: 1800-BLOOD-HELP

---

**BloodSync - Saving Lives, One Drop at a Time** ❤️
