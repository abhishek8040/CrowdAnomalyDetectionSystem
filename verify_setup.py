#!/usr/bin/env python3
"""
Setup Verification Script
Checks that all required files and directories are present
"""
import os
import sys
from pathlib import Path

def check_structure():
    """Verify project structure"""
    print("🔍 Verifying Crowd Anomaly Detection System Setup...\n")
    
    required_structure = {
        'backend': [
            'models/__init__.py',
            'models/detector.py',
            'tracking/__init__.py',
            'tracking/deepsort.py',
            'anomaly/__init__.py',
            'anomaly/overcrowding.py',
            'anomaly/loitering.py',
            'anomaly/zone_violation.py',
            'anomaly/suspicious_activity.py',
            'utils/__init__.py',
            'utils/video_stream.py',
            'routes/__init__.py',
            'routes/analyze.py',
            'routes/stream.py',
            'main.py',
            'requirements.txt',
            'tests/__init__.py',
            'tests/conftest.py',
            'tests/test_anomaly.py',
        ],
        'frontend': [
            'src/App.jsx',
            'src/main.jsx',
            'src/index.css',
            'src/components/VideoPlayer.jsx',
            'src/components/BoxesOverlay.jsx',
            'src/components/ZoneDrawer.jsx',
            'src/components/AlertPanel.jsx',
            'src/pages/Dashboard.jsx',
            'src/pages/Events.jsx',
            'src/hooks/useWebSocket.js',
            'package.json',
            'vite.config.js',
            'index.html',
        ],
        'notebooks': [
            'dataset_experiments.ipynb',
        ],
        'scripts': [
            'eval_metrics.py',
            'example_ground_truth.json',
        ],
        '.': [
            'README.md',
            'PROJECT_SUMMARY.md',
            'docker-compose.yml',
            'Dockerfile.backend',
            'Dockerfile.frontend',
            '.gitignore',
            'LICENSE',
            '.env.example',
        ]
    }
    
    all_good = True
    total_files = 0
    found_files = 0
    
    for directory, files in required_structure.items():
        print(f"📁 Checking {directory}/")
        for file_path in files:
            total_files += 1
            full_path = Path(directory) / file_path
            if full_path.exists():
                print(f"  ✅ {file_path}")
                found_files += 1
            else:
                print(f"  ❌ {file_path} - MISSING")
                all_good = False
        print()
    
    print(f"\n{'='*60}")
    print(f"📊 Verification Results:")
    print(f"{'='*60}")
    print(f"Total files expected: {total_files}")
    print(f"Files found: {found_files}")
    print(f"Missing: {total_files - found_files}")
    print(f"{'='*60}\n")
    
    if all_good:
        print("✅ All required files are present!")
        print("\n🚀 Next Steps:")
        print("1. Review README.md for setup instructions")
        print("2. Run './start.sh' (Linux/Mac) or 'start.bat' (Windows)")
        print("3. Access frontend at http://localhost:3000")
        print("4. Access backend API at http://localhost:8000")
        print("5. View API docs at http://localhost:8000/docs")
        return 0
    else:
        print("❌ Some files are missing. Please check the output above.")
        return 1

if __name__ == '__main__':
    sys.exit(check_structure())
