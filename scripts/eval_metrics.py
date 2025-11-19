"""
Evaluation Metrics Script
Computes precision, recall, F1, and MAE for crowd counting
"""
import numpy as np
from typing import List, Tuple, Dict
import json
import argparse


def calculate_iou(box1: List[float], box2: List[float]) -> float:
    """Calculate Intersection over Union"""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    
    inter_area = max(0, x2 - x1) * max(0, y2 - y1)
    
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    
    union_area = box1_area + box2_area - inter_area
    
    return inter_area / (union_area + 1e-6)


def match_detections(
    predictions: List[List[float]], 
    ground_truths: List[List[float]], 
    iou_threshold: float = 0.5
) -> Tuple[int, int, int]:
    """
    Match predicted detections with ground truth
    
    Returns:
        (true_positives, false_positives, false_negatives)
    """
    matched_gt = set()
    true_positives = 0
    
    for pred in predictions:
        best_iou = 0
        best_gt_idx = -1
        
        for gt_idx, gt in enumerate(ground_truths):
            if gt_idx in matched_gt:
                continue
            
            iou = calculate_iou(pred, gt)
            if iou > best_iou:
                best_iou = iou
                best_gt_idx = gt_idx
        
        if best_iou >= iou_threshold:
            true_positives += 1
            matched_gt.add(best_gt_idx)
    
    false_positives = len(predictions) - true_positives
    false_negatives = len(ground_truths) - true_positives
    
    return true_positives, false_positives, false_negatives


def calculate_metrics(
    all_predictions: List[List[List[float]]], 
    all_ground_truths: List[List[List[float]]],
    iou_threshold: float = 0.5
) -> Dict:
    """
    Calculate detection metrics
    
    Args:
        all_predictions: List of predictions for each frame
        all_ground_truths: List of ground truths for each frame
        iou_threshold: IOU threshold for matching
        
    Returns:
        Dictionary with metrics
    """
    total_tp = 0
    total_fp = 0
    total_fn = 0
    
    for preds, gts in zip(all_predictions, all_ground_truths):
        tp, fp, fn = match_detections(preds, gts, iou_threshold)
        total_tp += tp
        total_fp += fp
        total_fn += fn
    
    # Calculate precision, recall, F1
    precision = total_tp / (total_tp + total_fp + 1e-6)
    recall = total_tp / (total_tp + total_fn + 1e-6)
    f1 = 2 * (precision * recall) / (precision + recall + 1e-6)
    
    return {
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'true_positives': total_tp,
        'false_positives': total_fp,
        'false_negatives': total_fn
    }


def calculate_counting_metrics(
    predicted_counts: List[int], 
    ground_truth_counts: List[int]
) -> Dict:
    """
    Calculate crowd counting metrics
    
    Args:
        predicted_counts: List of predicted counts per frame
        ground_truth_counts: List of ground truth counts per frame
        
    Returns:
        Dictionary with MAE, MSE, RMSE
    """
    predicted_counts = np.array(predicted_counts)
    ground_truth_counts = np.array(ground_truth_counts)
    
    mae = np.mean(np.abs(predicted_counts - ground_truth_counts))
    mse = np.mean((predicted_counts - ground_truth_counts) ** 2)
    rmse = np.sqrt(mse)
    
    return {
        'mae': float(mae),
        'mse': float(mse),
        'rmse': float(rmse)
    }


def evaluate_anomaly_detection(
    predicted_anomalies: List[Dict],
    ground_truth_anomalies: List[Dict],
    frame_tolerance: int = 30
) -> Dict:
    """
    Evaluate anomaly detection performance
    
    Args:
        predicted_anomalies: List of predicted anomaly events
        ground_truth_anomalies: List of ground truth anomaly events
        frame_tolerance: Frame tolerance for matching events
        
    Returns:
        Dictionary with anomaly detection metrics
    """
    matched_predictions = set()
    matched_gt = set()
    
    for pred_idx, pred in enumerate(predicted_anomalies):
        for gt_idx, gt in enumerate(ground_truth_anomalies):
            if gt_idx in matched_gt:
                continue
            
            # Check if same type and within frame tolerance
            if (pred['event_type'] == gt['event_type'] and
                abs(pred['frame_number'] - gt['frame_number']) <= frame_tolerance):
                matched_predictions.add(pred_idx)
                matched_gt.add(gt_idx)
                break
    
    tp = len(matched_predictions)
    fp = len(predicted_anomalies) - tp
    fn = len(ground_truth_anomalies) - len(matched_gt)
    
    precision = tp / (tp + fp + 1e-6)
    recall = tp / (tp + fn + 1e-6)
    f1 = 2 * (precision * recall) / (precision + recall + 1e-6)
    
    return {
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'true_positives': tp,
        'false_positives': fp,
        'false_negatives': fn
    }


def main():
    parser = argparse.ArgumentParser(description='Evaluate crowd detection system')
    parser.add_argument('--predictions', type=str, required=True, help='Path to predictions JSON file')
    parser.add_argument('--ground_truth', type=str, required=True, help='Path to ground truth JSON file')
    parser.add_argument('--iou_threshold', type=float, default=0.5, help='IOU threshold for detection matching')
    parser.add_argument('--output', type=str, default='evaluation_results.json', help='Output file for results')
    
    args = parser.parse_args()
    
    # Load predictions and ground truth
    with open(args.predictions, 'r') as f:
        predictions_data = json.load(f)
    
    with open(args.ground_truth, 'r') as f:
        ground_truth_data = json.load(f)
    
    print("Evaluating detection performance...")
    
    # Calculate detection metrics
    if 'detections' in predictions_data and 'detections' in ground_truth_data:
        detection_metrics = calculate_metrics(
            predictions_data['detections'],
            ground_truth_data['detections'],
            args.iou_threshold
        )
        print(f"\nDetection Metrics:")
        print(f"  Precision: {detection_metrics['precision']:.4f}")
        print(f"  Recall: {detection_metrics['recall']:.4f}")
        print(f"  F1 Score: {detection_metrics['f1_score']:.4f}")
    else:
        detection_metrics = None
        print("No detection data found")
    
    # Calculate counting metrics
    if 'counts' in predictions_data and 'counts' in ground_truth_data:
        counting_metrics = calculate_counting_metrics(
            predictions_data['counts'],
            ground_truth_data['counts']
        )
        print(f"\nCounting Metrics:")
        print(f"  MAE: {counting_metrics['mae']:.2f}")
        print(f"  MSE: {counting_metrics['mse']:.2f}")
        print(f"  RMSE: {counting_metrics['rmse']:.2f}")
    else:
        counting_metrics = None
        print("No counting data found")
    
    # Calculate anomaly detection metrics
    if 'anomalies' in predictions_data and 'anomalies' in ground_truth_data:
        anomaly_metrics = evaluate_anomaly_detection(
            predictions_data['anomalies'],
            ground_truth_data['anomalies']
        )
        print(f"\nAnomaly Detection Metrics:")
        print(f"  Precision: {anomaly_metrics['precision']:.4f}")
        print(f"  Recall: {anomaly_metrics['recall']:.4f}")
        print(f"  F1 Score: {anomaly_metrics['f1_score']:.4f}")
    else:
        anomaly_metrics = None
        print("No anomaly data found")
    
    # Save results
    results = {
        'detection_metrics': detection_metrics,
        'counting_metrics': counting_metrics,
        'anomaly_metrics': anomaly_metrics
    }
    
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to {args.output}")


if __name__ == '__main__':
    main()
