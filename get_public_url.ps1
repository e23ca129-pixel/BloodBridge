Write-Host "========================================" -ForegroundColor Green
Write-Host "  BloodSync Public URL Setup" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Check if Flask is running
Write-Host "Checking if Flask server is running on port 5000..." -ForegroundColor Cyan
$flaskRunning = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue
if ($flaskRunning) {
    Write-Host "✓ Flask server is running!" -ForegroundColor Green
} else {
    Write-Host "✗ Flask server is NOT running on port 5000" -ForegroundColor Red
    Write-Host "Please start Flask first: python app.py" -ForegroundColor Yellow
    exit
}

Write-Host ""
Write-Host "Your local IP: 192.168.1.3" -ForegroundColor Cyan
Write-Host "Local access: http://localhost:5000" -ForegroundColor Cyan
Write-Host ""

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  Choose Public Access Method:" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. ngrok (Most Reliable - Requires Free Account)" -ForegroundColor White
Write-Host "   - Sign up: https://dashboard.ngrok.com/signup" -ForegroundColor Gray
Write-Host "   - Get token: https://dashboard.ngrok.com/get-started/your-authtoken" -ForegroundColor Gray
Write-Host "   - Run: .\ngrok.exe config add-authtoken YOUR_TOKEN" -ForegroundColor Gray
Write-Host "   - Run: .\ngrok.exe http 5000" -ForegroundColor Gray
Write-Host ""

Write-Host "2. serveo (Instant - No Account)" -ForegroundColor White
Write-Host "   - Run: ssh -R 80:localhost:5000 serveo.net" -ForegroundColor Gray
Write-Host ""

Write-Host "3. localtunnel (Requires Node.js)" -ForegroundColor White
Write-Host "   - Install: npm install -g localtunnel" -ForegroundColor Gray
Write-Host "   - Run: lt --port 5000" -ForegroundColor Gray
Write-Host ""

Write-Host "========================================" -ForegroundColor Green
Write-Host ""

$choice = Read-Host "Enter your choice (1, 2, or 3)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "Starting ngrok..." -ForegroundColor Cyan
        if (Test-Path ".\ngrok.exe") {
            Write-Host "ngrok found!" -ForegroundColor Green
            Write-Host ""
            Write-Host "If you haven't added your authtoken yet, run:" -ForegroundColor Yellow
            Write-Host ".\ngrok.exe config add-authtoken YOUR_TOKEN" -ForegroundColor White
            Write-Host ""
            Read-Host "Press Enter to continue with ngrok http 5000"
            .\ngrok.exe http 5000
        } else {
            Write-Host "ngrok.exe not found in current directory!" -ForegroundColor Red
            Write-Host "Download from: https://ngrok.com/download" -ForegroundColor Yellow
        }
    }
    "2" {
        Write-Host ""
        Write-Host "Starting serveo tunnel..." -ForegroundColor Cyan
        Write-Host "You may need to type 'yes' to accept the SSH key" -ForegroundColor Yellow
        Write-Host ""
        ssh -R 80:localhost:5000 serveo.net
    }
    "3" {
        Write-Host ""
        Write-Host "Starting localtunnel..." -ForegroundColor Cyan
        lt --port 5000
    }
    default {
        Write-Host "Invalid choice!" -ForegroundColor Red
    }
}
