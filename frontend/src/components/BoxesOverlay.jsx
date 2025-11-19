import { useEffect, useRef } from 'react'
import './BoxesOverlay.css'

const BoxesOverlay = ({ detections, width, height }) => {
  const canvasRef = useRef(null)

  useEffect(() => {
    if (!canvasRef.current || !detections) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw detection boxes
    detections.forEach((detection) => {
      const { bbox, id, confidence } = detection

      // Draw bounding box
      ctx.strokeStyle = '#00ff00'
      ctx.lineWidth = 2
      ctx.strokeRect(bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])

      // Draw label
      ctx.fillStyle = '#00ff00'
      ctx.font = '14px Arial'
      const label = `ID: ${id} (${(confidence * 100).toFixed(0)}%)`
      ctx.fillText(label, bbox[0], bbox[1] - 5)
    })
  }, [detections])

  return (
    <canvas
      ref={canvasRef}
      className="boxes-overlay"
      width={width}
      height={height}
    />
  )
}

export default BoxesOverlay
