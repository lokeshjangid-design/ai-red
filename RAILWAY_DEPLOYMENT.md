# 🚂 Railway Deployment Guide - Traffic Vision System

## Prerequisites
- GitHub account
- Railway account (free tier available)
- Git installed on your PC

## Step 1: Push Code to GitHub

```bash
# Initialize git (if not already done)
cd "d:\AI - TS"
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - Traffic Vision System"

# Create GitHub repository and push
git remote add origin https://github.com/YOUR_USERNAME/traffic-vision.git
git branch -M main
git push -u origin main
```

## Step 2: Deploy on Railway

### Option A: Using Railway CLI (Recommended)

1. **Install Railway CLI:**
```bash
npm install -g @railway/cli
```

2. **Login to Railway:**
```bash
railway login
```

3. **Initialize and Deploy:**
```bash
cd "d:\AI - TS"
railway init
railway up
```

### Option B: Using Railway Dashboard (Easier)

1. **Go to Railway:** https://railway.app/

2. **Click "New Project"**

3. **Select "Deploy from GitHub repo"**

4. **Connect your GitHub account** and select `traffic-vision` repository

5. **Railway will auto-detect Python** and start deployment

6. **Wait for deployment** (5-10 minutes for first time)

## Step 3: Configure Environment Variables (Optional)

In Railway dashboard:
- Go to your project
- Click "Variables" tab
- Add any custom variables if needed

## Step 4: Get Your Live URL

After deployment:
- Railway will provide a URL like: `https://traffic-vision-production.up.railway.app`
- This is your live app URL!

## Step 5: Test Your Deployed App

1. **Open the URL** in browser
2. **Allow camera permissions**
3. **Start live detection!**

## Features on Railway:

✅ **Live Camera Detection** - Works on mobile & PC
✅ **WebSocket Support** - Real-time processing
✅ **Auto HTTPS** - Railway provides SSL certificate
✅ **Automatic Restarts** - If app crashes
✅ **Logs & Monitoring** - View logs in dashboard

## Important Notes:

### Free Tier Limits:
- **$5 credit/month** (usually enough for testing)
- **500 hours** of usage
- **1GB RAM** (sufficient for YOLO nano model)

### If You Exceed Limits:
- Upgrade to Hobby plan ($5/month)
- Or use Render.com (better free tier)

## Troubleshooting:

### Build Failed?
- Check logs in Railway dashboard
- Ensure `requirements.txt` is correct
- YOLO model will download automatically

### App Crashes?
- Check memory usage (YOLO needs ~500MB RAM)
- Reduce `imgsz` in server.py if needed

### Camera Not Working?
- Railway provides HTTPS automatically
- Camera permissions should work on all devices

## Alternative: Render.com

If Railway limits are too restrictive:

1. Go to https://render.com
2. Create "New Web Service"
3. Connect GitHub repo
4. Select "Python" environment
5. Build command: `pip install -r requirements.txt`
6. Start command: `cd backend && python server.py`
7. Deploy!

**Render Free Tier:**
- ✅ 750 hours/month
- ✅ Better for AI models
- ⚠️ Slower cold starts

## Cost Comparison:

| Platform | Free Tier | Best For |
|----------|-----------|----------|
| **Railway** | $5 credit | Quick deploy, testing |
| **Render** | 750hrs/month | Production, AI apps |
| **Heroku** | Deprecated | ❌ Not recommended |

## Support:

If deployment fails, check:
1. Railway logs
2. GitHub repository structure
3. requirements.txt dependencies

---

**Your app will be live at:** `https://YOUR-APP.up.railway.app`

**Camera URL:** `https://YOUR-APP.up.railway.app/camera`

🚦 Happy Deploying! 🚀
