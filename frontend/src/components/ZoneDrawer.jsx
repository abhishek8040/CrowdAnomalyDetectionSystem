import { useState, useRef, useEffect } from 'react'
import './ZoneDrawer.css'

const ZoneDrawer = ({ onZonesUpdate, initialZones = [] }) => {
  const [zones, setZones] = useState(initialZones)
  const [currentZone, setCurrentZone] = useState([])
  const [isDrawing, setIsDrawing] = useState(false)
  const canvasRef = useRef(null)

  useEffect(() => {
    redrawCanvas()
  }, [zones, currentZone])

  const redrawCanvas = () => {
    if (!canvasRef.current) return

    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw existing zones
    zones.forEach((zone, idx) => {
      drawPolygon(ctx, zone, `rgba(255, 0, 0, 0.3)`, `rgb(255, 0, 0)`, `Zone ${idx + 1}`)
    })

    // Draw current zone being drawn
    if (currentZone.length > 0) {
      drawPolygon(ctx, currentZone, `rgba(0, 255, 0, 0.3)`, `rgb(0, 255, 0)`, 'Drawing...')
    }
  }

  const drawPolygon = (ctx, points, fillColor, strokeColor, label) => {
    if (points.length < 1) return

    ctx.beginPath()
    ctx.moveTo(points[0][0], points[0][1])
    points.forEach((point) => {
      ctx.lineTo(point[0], point[1])
    })
    ctx.closePath()

    ctx.fillStyle = fillColor
    ctx.fill()
    ctx.strokeStyle = strokeColor
    ctx.lineWidth = 2
    ctx.stroke()

    // Draw points
    points.forEach((point, idx) => {
      ctx.beginPath()
      ctx.arc(point[0], point[1], 5, 0, 2 * Math.PI)
      ctx.fillStyle = strokeColor
      ctx.fill()
    })

    // Draw label
    if (points.length > 0) {
      ctx.fillStyle = strokeColor
      ctx.font = '14px Arial'
      ctx.fillText(label, points[0][0], points[0][1] - 10)
    }
  }

  const handleCanvasClick = (e) => {
    if (!isDrawing) return

    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top

    setCurrentZone([...currentZone, [x, y]])
  }

  const startDrawing = () => {
    setIsDrawing(true)
    setCurrentZone([])
  }

  const finishZone = () => {
    if (currentZone.length >= 3) {
      const newZones = [...zones, currentZone]
      setZones(newZones)
      if (onZonesUpdate) {
        onZonesUpdate(newZones)
      }
    }
    setCurrentZone([])
    setIsDrawing(false)
  }

  const clearZones = () => {
    setZones([])
    setCurrentZone([])
    setIsDrawing(false)
    if (onZonesUpdate) {
      onZonesUpdate([])
    }
  }

  return (
    <div className="zone-drawer">
      <div className="zone-controls">
        <button
          className="btn btn-primary"
          onClick={isDrawing ? finishZone : startDrawing}
        >
          {isDrawing ? 'Finish Zone' : 'Draw New Zone'}
        </button>
        <button className="btn btn-danger" onClick={clearZones}>
          Clear All Zones
        </button>
        <span className="zone-info">
          {isDrawing && `Click to add points (${currentZone.length} points)`}
          {!isDrawing && `${zones.length} zone(s) defined`}
        </span>
      </div>
      <canvas
        ref={canvasRef}
        className="zone-canvas"
        width={800}
        height={600}
        onClick={handleCanvasClick}
      />
    </div>
  )
}

export default ZoneDrawer
