# Step-by-Step Guide to Run the Crowd Anomaly Detection System

## ✅ Prerequisites (Already Done)
- ✅ Python dependencies installed (`pip3 install -r backend/requirements.txt`)
- ✅ Frontend dependencies installed (`npm install` in frontend folder)

## 🚀 How to Start the Application

### Option 1: Using the Start Script (Recommended)
```bash
cd /Users/abhishekdubey/Documents/PublicAnamoly
./start.sh
```

### Option 2: Manual Start (If start.sh doesn't work)

#### Terminal 1 - Start Backend:
```bash
cd /Users/abhishekdubey/Documents/PublicAnamoly/backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### Terminal 2 - Start Frontend:
```bash
cd /Users/abhishekdubey/Documents/PublicAnamoly/frontend
npm run dev
```

## 📝 How to Use the Application

### Step 1: Access the Application
1. Open your web browser
2. Go to: **http://localhost:5173** (Frontend)
3. Backend API docs available at: **http://localhost:8000/docs**

### Step 2: Upload and Analyze Video

#### On the Dashboard:
1. You'll see the **Dashboard** with different sections
2. Look for the **"Upload Video"** or **"Analyze Video"** section
3. Click on the **"Choose File"** or **"Upload"** button
4. Select a video file from your computer (MP4, AVI, MOV formats)
5. Click **"Analyze"** or **"Start Analysis"** button
6. Wait for the analysis to complete
7. View the results showing:
   - Detected anomalies
   - People count
   - Crowd density
   - Suspicious activities

### Step 3: View Live Stream (if available)
1. Click on the **"Live Stream"** tab
2. Enter a camera URL or stream source
3. Click **"Start Monitoring"**
4. View real-time anomaly detection

## 📹 Test Video Recommendations

For testing, use videos with these characteristics:
- **Duration**: 10-30 seconds (for faster processing)
- **Content**: People in public spaces, crowds, CCTV footage
- **Format**: MP4, AVI, or MOV
- **Resolution**: 720p or 1080p

### Where to Find Test Videos:
1. **YouTube** - Search for "CCTV crowd footage" or "public space surveillance"
2. **Pexels Videos** - Free stock videos: https://www.pexels.com/search/videos/crowd/
3. **Pixabay Videos** - Free videos: https://pixabay.com/videos/search/crowd/
4. Use your phone to record a short video of people in a public area

### Example Search Terms:
- "Crowd CCTV footage"
- "Shopping mall surveillance"
- "Pedestrian crossing"
- "Public gathering"

## 🔧 Troubleshooting

### Issue 1: Port Already in Use
If port 8000 or 5173 is busy:
```bash
# Kill process on port 8000 (Backend)
lsof -ti:8000 | xargs kill -9

# Kill process on port 5173 (Frontend)
lsof -ti:5173 | xargs kill -9
```

### Issue 2: Frontend Not Loading
- Make sure both backend and frontend are running
- Check the terminal for error messages
- Try accessing http://localhost:5173 and http://localhost:8000/docs

### Issue 3: 500 Internal Server Error on Video Upload
Common causes and solutions:
1. **Video format not supported** - Use MP4 format
2. **Video too large** - Use videos under 100MB
3. **Missing YOLO model** - The app will auto-download on first use
4. **Backend not running** - Check Terminal 1 for errors

### Issue 4: MongoDB Connection Error (Optional)
The app can work without MongoDB, but if you want to use it:
```bash
# Install MongoDB (macOS)
brew tap mongodb/brew
brew install mongodb-community

# Start MongoDB
brew services start mongodb-community
```

## 📊 Understanding the Results

After video analysis, you'll see:
- **Total People Count**: Number of people detected
- **Crowd Density**: Low/Medium/High
- **Anomalies Detected**: List of unusual activities
- **Timeline**: When anomalies occurred
- **Heatmap**: Areas with most activity

## 🛑 How to Stop the Application

### If using start.sh:
```bash
# Press Ctrl+C in the terminal
```

### If running manually:
```bash
# Press Ctrl+C in both Terminal 1 and Terminal 2
```

## 📁 Project Structure Quick Reference

```
PublicAnamoly/
├── backend/           # FastAPI backend
│   ├── main.py       # Main API file
│   ├── models/       # AI models
│   ├── routes/       # API endpoints
│   └── requirements.txt
├── frontend/         # React frontend
│   ├── src/
│   └── package.json
└── start.sh         # Start script
```

## 💡 Quick Tips

1. **First Run**: The app will download the YOLO model (~6MB) on first use
2. **Performance**: For faster processing, use shorter videos
3. **GPU**: If you have a GPU, PyTorch will automatically use it
4. **Logs**: Check terminal output for detailed processing logs

## 🎯 Next Steps

1. Start the application
2. Upload a test video
3. Review the detection results
4. Adjust settings if needed
5. Try with different video types

---

**Need Help?** Check the terminal output for error messages and refer to the troubleshooting section above.
