# Getting Started with Crowd Anomaly Detection System

Welcome! This guide will help you get the system up and running quickly.

## 🎯 What You'll Build

A complete AI-powered video surveillance system that:
- Detects and tracks people in real-time
- Identifies overcrowding situations
- Detects loitering behavior
- Monitors restricted zones
- Identifies suspicious activities (fights)

## 📋 Prerequisites

### Option 1: Docker (Easiest)
- Docker Desktop (Docker + Docker Compose)
- 4GB+ RAM available
- 10GB+ disk space

### Option 2: Local Development
- Python 3.10+
- Node.js 18+
- pip and npm
- 8GB+ RAM recommended

## 🚀 5-Minute Quick Start

### Step 1: Verify Setup
```bash
python3 verify_setup.py
```

You should see all files marked with ✅

### Step 2: Start the System

**On Linux/Mac:**
```bash
./start.sh
```

**On Windows:**
```bash
start.bat
```

**Or manually with Docker:**
```bash
docker-compose up --build
```

### Step 3: Access the Application

Once you see "System is ready!", open:
- **Frontend Dashboard**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## 📖 First-Time Usage Tutorial

### 1. Prepare a Test Video
- Download a crowd video or use your own
- Supported formats: MP4, AVI, MOV, MKV
- Recommended: Short clips (30-60 seconds) for testing

### 2. Upload and Configure
1. Go to http://localhost:3000
2. Click "Choose video file..."
3. Select your test video
4. Adjust detection parameters:
   - **Overcrowding Threshold**: 10 (default)
   - **Loitering Time**: 300 seconds (5 minutes)
   - **Loitering Distance**: 50 pixels
   - **Velocity Threshold**: 15.0

### 3. Define Restricted Zones (Optional)
1. Scroll to "Define Restricted Zones"
2. Click "Draw New Zone"
3. Click on the canvas to create polygon points
4. Click "Finish Zone" when done
5. Repeat for multiple zones

### 4. Run Analysis
1. Click "Start Analysis"
2. Wait for processing (progress shown)
3. View results in "Analysis Summary"

### 5. Review Alerts
- Check the "Alert Panel" on the right
- View event types, timestamps, and details
- Click events to see snapshots

### 6. Browse Event History
1. Click "Events" in the navigation
2. Filter by event type
3. Click events to see details
4. Review snapshots and metadata

## 🔧 Configuration Guide

### Adjust Detection Sensitivity

**For Crowded Environments:**
```javascript
overcrowding_threshold: 20  // More people allowed
loitering_time: 600        // 10 minutes
```

**For Sensitive Areas:**
```javascript
overcrowding_threshold: 5   // Fewer people
loitering_time: 180        // 3 minutes
velocity_threshold: 10.0   // More sensitive
```

### Optimize Performance

**For Faster Processing:**
- Use `yolov8n.pt` (nano model)
- Process every 2nd or 3rd frame
- Reduce video resolution

**For Better Accuracy:**
- Use `yolov8m.pt` or `yolov8l.pt`
- Process all frames
- Keep original resolution

## 🎓 Understanding the Results

### Event Types Explained

**Overcrowding (👥)**
- Triggered when: People count > threshold
- Use case: Managing venue capacity
- Action: Crowd control measures

**Loitering (⏱️)**
- Triggered when: Person stays stationary too long
- Use case: Security monitoring
- Action: Investigation required

**Zone Violation (🚫)**
- Triggered when: Person enters restricted area
- Use case: Access control
- Action: Immediate response

**Suspicious Activity (⚠️)**
- Triggered when: Rapid erratic movements detected
- Use case: Fight/altercation detection
- Action: Security intervention

### Reading the Analysis Summary

```
Total Frames: 900          # Number of frames processed
Total Events: 12           # Anomalies detected
Overcrowding: 3           # Times threshold exceeded
Loitering: 5              # Loitering incidents
Zone Violations: 2        # Unauthorized access
Suspicious Activity: 2    # Potential fights
```

## 🐛 Troubleshooting

### Backend Won't Start
```bash
# Check if port 8000 is in use
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# View backend logs
docker-compose logs backend
```

### Frontend Won't Start
```bash
# Check if port 3000 is in use
lsof -i :3000  # Mac/Linux
netstat -ano | findstr :3000  # Windows

# View frontend logs
docker-compose logs frontend
```

### Video Upload Fails
- Check file size (max 500MB recommended)
- Ensure format is supported
- Check backend logs for errors
- Try with a smaller test video

### No Detections Appearing
- Lower confidence threshold in code
- Check video quality
- Ensure people are visible
- Try different YOLO model

### WebSocket Not Connecting
- Verify backend is running
- Check browser console for errors
- Ensure correct WebSocket URL
- Check firewall settings

## 📊 Sample Datasets

### For Testing

**UCSD Pedestrian Dataset**
```bash
wget http://www.svcl.ucsd.edu/projects/anomaly/UCSD_Anomaly_Dataset.tar.gz
```

**Sample Videos** (free sources)
- Pexels: https://www.pexels.com/search/videos/crowd/
- Pixabay: https://pixabay.com/videos/search/crowd/
- YouTube Creative Commons videos

### For Production

**ShanghaiTech** - Crowd counting
**UCF-Crime** - Anomaly detection
**MOT Challenge** - Tracking benchmarks

See README.md for full dataset list.

## 🔐 Security Notes

**Before Production Deployment:**

1. Change all default credentials
2. Enable HTTPS (TLS/SSL)
3. Configure authentication
4. Restrict CORS origins
5. Set up rate limiting
6. Enable logging
7. Regular security updates

## 🎯 Next Steps

### Learn More
- Read [README.md](README.md) for comprehensive documentation
- Review [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) for architecture
- Explore API at http://localhost:8000/docs
- Check out [notebooks/dataset_experiments.ipynb](notebooks/dataset_experiments.ipynb)

### Customize
- Modify detection thresholds
- Add custom anomaly detectors
- Customize UI theme
- Integrate with your systems

### Deploy
- Set up production environment
- Configure monitoring
- Set up alerting (email/SMS)
- Scale with multiple cameras

## 💡 Tips & Best Practices

1. **Start Small**: Test with short videos first
2. **Tune Parameters**: Adjust thresholds for your environment
3. **Define Zones Carefully**: Be precise with restricted areas
4. **Monitor Performance**: Check CPU/memory usage
5. **Regular Updates**: Keep dependencies updated
6. **Backup Events**: Export event history regularly
7. **Document Changes**: Track configuration changes

## 📞 Getting Help

- **Issues**: Check troubleshooting section above
- **API Questions**: Review http://localhost:8000/docs
- **Examples**: See notebooks/dataset_experiments.ipynb
- **Code**: Review inline comments in source files

## ✅ Checklist

Before going to production:

- [ ] System runs without errors
- [ ] Tested with sample videos
- [ ] Thresholds tuned for your use case
- [ ] Zones defined correctly
- [ ] Performance is acceptable
- [ ] Alerts are working
- [ ] Event history is accessible
- [ ] Security measures implemented
- [ ] Monitoring set up
- [ ] Documentation reviewed

## 🎉 You're Ready!

Congratulations! You now have a fully functional crowd anomaly detection system.

Start experimenting, tune the parameters, and adapt it to your specific needs.

**Happy Monitoring!** 🎥🔍✨
