"""
Public Anomaly Detection System - Hugging Face Gradio Entrypoint
Provides an interactive web interface for analyzing CCTV videos for
drive-by snatching, falls, fights, panic running, loitering, and overcrowding.
"""
import os
import sys
from pathlib import Path
import cv2
import numpy as np
import tempfile
import pandas as pd
import gradio as gr

# Ensure backend directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Import detection suite from backend
from backend.models.detector import PersonDetector
from backend.tracking.deepsort import DeepSORT
from backend.anomaly.snatching_detection import SnatchingDetector
from backend.anomaly.fall_detection import FallDetector
from backend.anomaly.panic_running import PanicRunningDetector
from backend.anomaly.overcrowding import OvercrowdingDetector
from backend.anomaly.loitering import LoiteringDetector
from backend.anomaly.suspicious_activity import SuspiciousActivityDetector
from backend.anomaly.rule_engine import parse_natural_language_rule, RuleEvaluator

# Initialize global detector
model_path = BACKEND_DIR / "yolov8n.pt"
if not model_path.exists():
    model_path = "yolov8n.pt"
detector = PersonDetector(model_name=str(model_path))

# ZeroGPU support for Hugging Face free GPU tier (duration=25s to fit free quota limits)
try:
    import spaces
    gpu_decorator = spaces.GPU(duration=25)
except Exception:
    def gpu_decorator(fn):
        return fn


@gpu_decorator
def process_cctv_video(
    video_file,
    nl_rule_text: str,
    overcrowding_threshold: int,
    loitering_seconds: int,
    progress=gr.Progress()
):
    """
    Process an uploaded CCTV video through the full anomaly detection suite.
    """
    if not video_file:
        return None, "⚠️ Please upload a video file first.", pd.DataFrame()

    cap = cv2.VideoCapture(video_file)
    if not cap.isOpened():
        return None, "❌ Failed to open video file.", pd.DataFrame()

    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 25
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480

    # Output video file
    out_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    out_temp.close()
    
    # Try H264 or mp4v codec
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(out_temp.name, fourcc, fps, (width, height))

    # Initialize per-video trackers and anomaly detectors
    tracker = DeepSORT(max_age=30, min_hits=2)
    snatching_detector = SnatchingDetector()
    fall_detector = FallDetector()
    panic_detector = PanicRunningDetector()
    overcrowding = OvercrowdingDetector(threshold=overcrowding_threshold, confirmation_frames=4)
    loitering = LoiteringDetector(time_threshold=loitering_seconds, fps=fps)
    suspicious = SuspiciousActivityDetector()

    # Parse optional natural language rule
    rule_evaluator = None
    rule_info_text = ""
    if nl_rule_text and nl_rule_text.strip():
        parsed_rule = parse_natural_language_rule(nl_rule_text.strip())
        if parsed_rule.get('is_supported'):
            rule_evaluator = RuleEvaluator([parsed_rule])
            rule_info_text = f"✅ Active Custom Rule: **{parsed_rule.get('name')}**"
        else:
            rule_info_text = f"⚠️ Rule not supported: {parsed_rule.get('unsupported_reason')}"

    events_list = []
    frame_num = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_num += 1

        if frame_num % 5 == 0:
            progress(frame_num / max(1, total_frames), desc=f"Analyzing frame {frame_num}/{total_frames}...")

        # 1. Detection and Tracking
        detection_list, features = detector.detect_people_with_features(frame)
        tracks = tracker.update(detection_list, frame=frame, features=features)
        count = len(tracks)

        # 2. Anomaly Checks
        overcrowd_res = overcrowding.detect_overcrowding(count)
        panic_res = panic_detector.detect_motion_anomalies(tracks, frame_num)
        snatch_res = snatching_detector.update_and_detect(tracks, frame_num)

        active_track_ids = []
        recent_alert_str = None
        alert_color = (0, 0, 255)

        if snatch_res['alert_triggered']:
            events_list.append({
                'Frame': frame_num,
                'Timestamp': f"{round(frame_num / fps, 1)}s",
                'Category': 'Snatching / Theft',
                'Severity': 'CRITICAL',
                'Confidence': f"{round(snatch_res.get('confidence', 0.9) * 100)}%",
                'Details': snatch_res.get('message', 'Drive-by snatching detected')
            })
            recent_alert_str = f"ALERT: DRIVE-BY SNATCHING (Suspect #{snatch_res.get('suspect_id')} -> Victim #{snatch_res.get('victim_id')})"

        if overcrowd_res['alert_triggered']:
            events_list.append({
                'Frame': frame_num,
                'Timestamp': f"{round(frame_num / fps, 1)}s",
                'Category': 'Overcrowding',
                'Severity': 'HIGH',
                'Confidence': '90%',
                'Details': f"Crowd count {count} exceeded threshold {overcrowding_threshold}"
            })
            recent_alert_str = f"ALERT: OVERCROWDING ({count} people)"
            alert_color = (0, 165, 255)

        if panic_res['alert_triggered']:
            ename = 'Panic' if panic_res.get('is_panic') else 'Running'
            events_list.append({
                'Frame': frame_num,
                'Timestamp': f"{round(frame_num / fps, 1)}s",
                'Category': ename,
                'Severity': 'HIGH',
                'Confidence': '85%',
                'Details': 'Sudden rapid dispersion or sprinting motion detected'
            })
            recent_alert_str = f"ALERT: {ename.upper()} MOTION"

        # Per-track checks
        for trk in tracks:
            t_id = trk['id']
            bbox = trk['bbox']
            active_track_ids.append(t_id)

            cx = (bbox[0] + bbox[2]) / 2.0
            cy = (bbox[1] + bbox[3]) / 2.0

            # Fall
            fall_res = fall_detector.update_and_detect(t_id, bbox, frame_num)
            if fall_res['alert_triggered']:
                events_list.append({
                    'Frame': frame_num,
                    'Timestamp': f"{round(frame_num / fps, 1)}s",
                    'Category': 'Fall / Person Down',
                    'Severity': 'HIGH',
                    'Confidence': '85%',
                    'Details': f"Individual #{t_id} collapsed to horizontal orientation"
                })
                recent_alert_str = f"ALERT: PERSON DOWN (ID #{t_id})"

            # Loitering
            loitering.update_track(t_id, (cx, cy), frame_num)
            loiter_res = loitering.detect_loitering(t_id)
            if loiter_res['alert_triggered']:
                events_list.append({
                    'Frame': frame_num,
                    'Timestamp': f"{round(frame_num / fps, 1)}s",
                    'Category': 'Loitering',
                    'Severity': 'MEDIUM',
                    'Confidence': '85%',
                    'Details': f"Individual #{t_id} stationary for > {loitering_seconds}s"
                })
                recent_alert_str = f"ALERT: LOITERING (ID #{t_id})"
                alert_color = (0, 255, 255)

            # Draw Bounding Box on Frame
            x1, y1, x2, y2 = map(int, bbox)
            cname = trk.get('class_name', 'person')
            is_veh = cname in ('motorcycle', 'bicycle')
            box_col = (0, 165, 255) if is_veh else (0, 255, 120)  # Amber for bike, Green for person
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_col, 2)

            label = f"#{t_id} {cname} {round(trk.get('speed', 0), 1)}px/f"
            cv2.putText(frame, label, (x1, max(15, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, box_col, 2)

        # Draw Alert Banner on top of frame if active
        if recent_alert_str:
            cv2.rectangle(frame, (0, 0), (width, 36), alert_color, -1)
            cv2.putText(frame, recent_alert_str, (15, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

        out.write(frame)

        # Cleanup
        loitering.cleanup_old_tracks(active_track_ids)
        fall_detector.cleanup_old_tracks(active_track_ids)
        snatching_detector.cleanup_old_tracks(active_track_ids)

    cap.release()
    out.release()

    # Generate Summary Metrics
    df_events = pd.DataFrame(events_list)
    snatching_cnt = sum(1 for e in events_list if e['Category'] == 'Snatching / Theft')
    fall_cnt = sum(1 for e in events_list if e['Category'] == 'Fall / Person Down')
    panic_cnt = sum(1 for e in events_list if e['Category'] in ('Panic', 'Running'))
    overcrowd_cnt = sum(1 for e in events_list if e['Category'] == 'Overcrowding')
    loiter_cnt = sum(1 for e in events_list if e['Category'] == 'Loitering')

    banner = ""
    if snatching_cnt > 0:
        banner = (
            f"### 🚨 CRITICAL: Drive-by Snatching / Theft Detected ({snatching_cnt} incident(s))\n"
            f"> The system detected high-speed drive-by intercepts matching motorcycle/bicycle snatching kinematics.\n\n"
        )

    summary_md = f"""
{banner}
### 📊 Video Analysis Summary
* **Total Frames Analyzed**: `{frame_num}` ({round(frame_num / fps, 1)}s @ {fps}fps)
* **Total Incidents Logged**: `{len(events_list)}`
* **🏍️ Snatching / Theft**: `{snatching_cnt}`
* **🩹 Falls / Person Down**: `{fall_cnt}`
* **🏃 Panic & Running**: `{panic_cnt}`
* **👥 Overcrowding**: `{overcrowd_cnt}`
* **⏱️ Loitering**: `{loiter_cnt}`

{rule_info_text}
"""

    return out_temp.name, summary_md, df_events


# Build Gradio UI
with gr.Blocks(title="Public Anomaly Detection System", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # 🛡️ Public Anomaly Detection System
    ### AI-Powered Multi-Anomaly CCTV Analysis (Snatching, Falls, Fights, Panic & Overcrowding)
    Upload a CCTV surveillance clip or recorded video to detect anomalies with YOLOv8 & DeepSORT tracking.
    """)

    with gr.Row():
        with gr.Column(scale=1):
            input_video = gr.Video(label="Upload CCTV / Surveillance Video", sources=["upload"])
            
            with gr.Accordion("⚙️ Anomaly Settings & Custom Rules", open=True):
                nl_rule_input = gr.Textbox(
                    label="Optional Natural-Language Security Rule",
                    placeholder='e.g. "Alert if two bike riders snatch from a pedestrian" or "Alert if someone falls"'
                )
                overcrowd_slider = gr.Slider(minimum=2, maximum=50, value=10, step=1, label="Overcrowding Threshold (people)")
                loiter_slider = gr.Slider(minimum=10, maximum=300, value=60, step=10, label="Loitering Threshold (seconds)")

            analyze_btn = gr.Button("🚀 Analyze Video Footage", variant="primary", size="lg")

        with gr.Column(scale=1):
            output_video = gr.Video(label="Annotated Video (Real-Time Overlays)")
            summary_output = gr.Markdown("### Awaiting video upload...")

    gr.Markdown("### 📋 Detected Incidents Log")
    events_table = gr.DataFrame(
        headers=["Frame", "Timestamp", "Category", "Severity", "Confidence", "Details"],
        label="Incident Evidence Table"
    )

    analyze_btn.click(
        fn=process_cctv_video,
        inputs=[input_video, nl_rule_input, overcrowd_slider, loiter_slider],
        outputs=[output_video, summary_output, events_table]
    )

if __name__ == "__main__":
    demo.queue().launch(server_name="0.0.0.0", server_port=7860)
