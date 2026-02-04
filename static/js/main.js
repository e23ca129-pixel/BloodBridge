// BloodSync - Main JavaScript File

// DOM Ready
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-hide alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert-dismissible');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Form validation enhancement
    var forms = document.querySelectorAll('.needs-validation');
    Array.prototype.slice.call(forms).forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });

    // Blood group compatibility checker
    initBloodCompatibilityChecker();

    // Donor eligibility calculator
    initEligibilityCalculator();

    // Location autocomplete (simulated)
    initLocationAutocomplete();

    // Phone number formatter
    initPhoneFormatter();
});

// Blood Group Compatibility Checker
function initBloodCompatibilityChecker() {
    var bloodGroupSelect = document.getElementById('blood_group');
    if (bloodGroupSelect) {
        bloodGroupSelect.addEventListener('change', function() {
            var selectedGroup = this.value;
            if (selectedGroup) {
                showCompatibilityInfo(selectedGroup);
            }
        });
    }
}

function showCompatibilityInfo(bloodGroup) {
    var compatibility = {
        'A+': { canDonateTo: ['A+', 'AB+'], canReceiveFrom: ['A+', 'A-', 'O+', 'O-'] },
        'A-': { canDonateTo: ['A+', 'A-', 'AB+', 'AB-'], canReceiveFrom: ['A-', 'O-'] },
        'B+': { canDonateTo: ['B+', 'AB+'], canReceiveFrom: ['B+', 'B-', 'O+', 'O-'] },
        'B-': { canDonateTo: ['B+', 'B-', 'AB+', 'AB-'], canReceiveFrom: ['B-', 'O-'] },
        'AB+': { canDonateTo: ['AB+'], canReceiveFrom: ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'] },
        'AB-': { canDonateTo: ['AB+', 'AB-'], canReceiveFrom: ['A-', 'B-', 'AB-', 'O-'] },
        'O+': { canDonateTo: ['O+', 'A+', 'B+', 'AB+'], canReceiveFrom: ['O+', 'O-'] },
        'O-': { canDonateTo: ['All Blood Types'], canReceiveFrom: ['O-'] }
    };

    var info = compatibility[bloodGroup];
    if (info && document.getElementById('compatibility-info')) {
        document.getElementById('compatibility-info').innerHTML = 
            '<div class="alert alert-info mt-3">' +
            '<strong>Can donate to:</strong> ' + info.canDonateTo.join(', ') + '<br>' +
            '<strong>Can receive from:</strong> ' + info.canReceiveFrom.join(', ') +
            '</div>';
    }
}

// Donor Eligibility Calculator
function initEligibilityCalculator() {
    var ageInput = document.getElementById('age');
    var weightInput = document.getElementById('weight');
    
    if (ageInput && weightInput) {
        var checkEligibility = function() {
            var age = parseInt(ageInput.value);
            var weight = parseFloat(weightInput.value);
            var eligibilityDiv = document.getElementById('eligibility-result');
            
            if (eligibilityDiv && age && weight) {
                var isEligible = age >= 18 && age <= 65 && weight >= 50;
                eligibilityDiv.innerHTML = isEligible 
                    ? '<div class="alert alert-success"><i class="fas fa-check-circle me-2"></i>You are eligible to donate blood!</div>'
                    : '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle me-2"></i>You may not be eligible. Age: 18-65, Weight: 50+ kg</div>';
            }
        };
        
        ageInput.addEventListener('input', checkEligibility);
        weightInput.addEventListener('input', checkEligibility);
    }
}

// Location Autocomplete (Simulated)
function initLocationAutocomplete() {
    var cityInput = document.getElementById('city');
    if (cityInput) {
        var cities = ['Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Pune', 'Hyderabad', 'Kolkata', 'Ahmedabad'];
        
        cityInput.addEventListener('input', function() {
            var value = this.value.toLowerCase();
            // This is a simplified version - in production, use a proper autocomplete library
        });
    }
}

// Phone Number Formatter
function initPhoneFormatter() {
    var phoneInputs = document.querySelectorAll('input[type="tel"]');
    phoneInputs.forEach(function(input) {
        input.addEventListener('input', function(e) {
            var value = e.target.value.replace(/\D/g, '');
            if (value.length > 10) {
                value = value.substring(0, 10);
            }
            e.target.value = value;
        });
    });
}

// Date validation for blood requests
function validateRequestDate() {
    var dateInput = document.getElementById('required_date');
    if (dateInput) {
        var today = new Date().toISOString().split('T')[0];
        dateInput.setAttribute('min', today);
        
        dateInput.addEventListener('change', function() {
            var selectedDate = new Date(this.value);
            var currentDate = new Date();
            
            if (selectedDate < currentDate) {
                alert('Please select a future date');
                this.value = '';
            }
        });
    }
}

// Calculate days since last donation
function calculateDaysSinceDonation(lastDonationDate) {
    if (!lastDonationDate) return null;
    
    var last = new Date(lastDonationDate);
    var today = new Date();
    var diffTime = Math.abs(today - last);
    var diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    return diffDays;
}

// Check if donor can donate (56 days gap)
function canDonate(lastDonationDate) {
    var daysSince = calculateDaysSinceDonation(lastDonationDate);
    if (daysSince === null) return true;
    return daysSince >= 56;
}

// AJAX function for API calls
function makeAPICall(url, method, data, callback) {
    var xhr = new XMLHttpRequest();
    xhr.open(method, url, true);
    xhr.setRequestHeader('Content-Type', 'application/json');
    xhr.onreadystatechange = function() {
        if (xhr.readyState === 4) {
            if (xhr.status === 200) {
                callback(null, JSON.parse(xhr.responseText));
            } else {
                callback(new Error('API call failed'), null);
            }
        }
    };
    xhr.send(data ? JSON.stringify(data) : null);
}

// Fetch statistics
function fetchStatistics() {
    makeAPICall('/api/statistics', 'GET', null, function(err, data) {
        if (!err && data) {
            updateStatisticsDisplay(data);
        }
    });
}

// Update statistics on page
function updateStatisticsDisplay(stats) {
    var elements = {
        'total-donors': stats.total_donors,
        'total-requestors': stats.total_requestors,
        'total-requests': stats.total_requests,
        'active-requests': stats.active_requests,
        'fulfilled-requests': stats.fulfilled_requests,
        'total-units': stats.total_units
    };
    
    for (var id in elements) {
        var element = document.getElementById(id);
        if (element) {
            element.textContent = elements[id];
        }
    }
}

// Refresh statistics every 30 seconds if on dashboard
if (window.location.pathname === '/dashboard') {
    setInterval(fetchStatistics, 30000);
}

// Confirm before critical actions
function confirmAction(message) {
    return confirm(message || 'Are you sure you want to proceed?');
}

// Print functionality
function printPage() {
    window.print();
}

// Export to CSV (for data tables)
function exportToCSV(tableId, filename) {
    var table = document.getElementById(tableId);
    if (!table) return;
    
    var csv = [];
    var rows = table.querySelectorAll('tr');
    
    rows.forEach(function(row) {
        var cols = row.querySelectorAll('td, th');
        var rowData = [];
        cols.forEach(function(col) {
            rowData.push('"' + col.innerText.replace(/"/g, '""') + '"');
        });
        csv.push(rowData.join(','));
    });
    
    var csvContent = 'data:text/csv;charset=utf-8,' + csv.join('\n');
    var encodedUri = encodeURI(csvContent);
    var link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', filename + '.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Smooth scroll to element
function scrollToElement(elementId) {
    var element = document.getElementById(elementId);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth' });
    }
}

// Show loading spinner
function showLoading(elementId) {
    var element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = '<div class="text-center"><i class="fas fa-spinner fa-spin fa-2x text-danger"></i><p class="mt-2">Loading...</p></div>';
    }
}

// Hide loading spinner
function hideLoading(elementId, content) {
    var element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = content;
    }
}

// Blood matching algorithm visualization
function visualizeMatching(donors, requestBloodGroup) {
    var compatibility = {
        'A+': ['A+', 'A-', 'O+', 'O-'],
        'A-': ['A-', 'O-'],
        'B+': ['B+', 'B-', 'O+', 'O-'],
        'B-': ['B-', 'O-'],
        'AB+': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
        'AB-': ['A-', 'B-', 'AB-', 'O-'],
        'O+': ['O+', 'O-'],
        'O-': ['O-']
    };
    
    var compatibleGroups = compatibility[requestBloodGroup] || [];
    var matchedDonors = [];
    
    donors.forEach(function(donor) {
        if (compatibleGroups.includes(donor.blood_group) && donor.available) {
            matchedDonors.push(donor);
        }
    });
    
    return matchedDonors;
}

// Initialize on page load
window.addEventListener('load', function() {
    validateRequestDate();
});
