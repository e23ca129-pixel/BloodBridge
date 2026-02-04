# 🌐 Get Public IP Address for BloodSync

## ✅ Your Flask Server Status
- **Running**: Yes, on port 5000
- **Local URL**: http://localhost:5000
- **Network URL**: http://192.168.1.3:5000

---

## 🚀 Get Public URL (3 Easy Options)

### Option 1: ngrok (Recommended) ⭐

**Steps:**
1. Sign up (free): https://dashboard.ngrok.com/signup
2. Get your authtoken: https://dashboard.ngrok.com/get-started/your-authtoken
3. Open PowerShell and run:

```powershell
cd C:\Users\acer\Desktop\bloodsync
.\ngrok.exe config add-authtoken YOUR_TOKEN_HERE
.\ngrok.exe http 5000
```

**Result**: You'll get a public URL like `https://abc123.ngrok-free.app`

---

### Option 2: serveo (Fastest - No Account) ⚡

**One command:**
```powershell
ssh -R 80:localhost:5000 serveo.net
```

Type `yes` when prompted.

**Result**: You'll get a URL like `https://random.serveo.net`

---

### Option 3: Use the Helper Script

**Run:**
```powershell
cd C:\Users\acer\Desktop\bloodsync
.\get_public_url.ps1
```

Follow the menu to choose your preferred method.

---

## 📱 After Getting Your Public URL

1. **Copy the URL** (e.g., `https://abc123.ngrok-free.app`)
2. **Test it**: Open in your browser
3. **Share it**: Anyone can access your app!

---

## 🎯 Quick Access Pages

Once you have your public URL, share these:

- Home: `https://your-url/`
- Donor Registration: `https://your-url/donor/register`
- Request Blood: `https://your-url/request-blood`
- Admin Dashboard: `https://your-url/dashboard`

---

## ⚠️ Important

- Keep Flask server running (current terminal)
- Keep tunnel running (new terminal)
- Free URLs change when you restart
- This is for testing/demo only

---

## 🎓 Recommended: Use serveo Right Now

**Fastest way to get public URL:**

1. Open **NEW** PowerShell window
2. Run: `ssh -R 80:localhost:5000 serveo.net`
3. Type `yes`
4. Get your public URL instantly!

No account, no installation, just works! 🚀
