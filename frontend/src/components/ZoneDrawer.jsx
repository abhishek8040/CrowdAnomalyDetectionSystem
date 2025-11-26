import { useState, useRef, useEffect, forwardRef, useImperativeHandle } from 'react'
import './ZoneDrawer.css'

const ZoneDrawer = forwardRef(({ onZonesUpdate, initialZones = [], width = 800, height = 600, backgroundImage = null, hideControls = false }, ref) => {
  const [zones, setZones] = useState(initialZones)
  const [currentZone, setCurrentZone] = useState([])
  const [isDrawing, setIsDrawing] = useState(false)
  const canvasRef = useRef(null)
  const bgImgRef = useRef(null)

  // Keep zones in sync when parent updates initialZones
  useEffect(() => {
    setZones(initialZones || [])
  }, [initialZones])

  // Redraw when zones, current zone, background, or size changes
  useEffect(() => {
    redrawCanvas()
  }, [zones, currentZone, backgroundImage, width, height])

  const redrawCanvas = () => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    // Ensure size
    if (canvas.width !== width) canvas.width = width
    if (canvas.height !== height) canvas.height = height

    // Clear
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw background frame if provided
    if (backgroundImage) {
      if (!bgImgRef.current) bgImgRef.current = new Image()
      const img = bgImgRef.current
      const src = backgroundImage.startsWith?.('data:') ? backgroundImage : `data:image/jpeg;base64,${backgroundImage}`
      if (img.src !== src) {
        img.onload = () => {
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
          drawZones(ctx)
        }
        img.src = src
        return
      } else {
        try {
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
        } catch (_) {}
      }
    }

    drawZones(ctx)
  }

  const drawZones = (ctx) => {
    zones.forEach((zone, idx) => {
      drawPolygon(ctx, zone, 'rgba(255, 0, 0, 0.3)', 'rgb(255, 0, 0)', `Zone ${idx + 1}`)
    })
    if (currentZone.length > 0) {
      drawSketch(ctx, currentZone, 'rgb(0, 255, 0)')
    }
  }

  const drawPolygon = (ctx, points, fillColor, strokeColor, label) => {
    if (points.length < 1) return
    ctx.beginPath()
    ctx.moveTo(points[0][0], points[0][1])
    points.forEach((point) => ctx.lineTo(point[0], point[1]))
    ctx.closePath()
    ctx.fillStyle = fillColor
    ctx.fill()
    ctx.strokeStyle = strokeColor
    ctx.lineWidth = 2
    ctx.stroke()
    points.forEach((point) => {
      ctx.beginPath()
      ctx.arc(point[0], point[1], 5, 0, 2 * Math.PI)
      ctx.fillStyle = strokeColor
      ctx.fill()
    })
    ctx.fillStyle = strokeColor
    ctx.font = '14px Arial'
    ctx.fillText(label, points[0][0], points[0][1] - 10)
  }

  // While drawing, show connected lines and points, but don't fill/close
  const drawSketch = (ctx, points, color) => {
    if (points.length < 1) return
    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(points[0][0], points[0][1])
    for (let i = 1; i < points.length; i++) {
      ctx.lineTo(points[i][0], points[i][1])
    }
    ctx.stroke()
    // draw points
    points.forEach((p) => {
      ctx.beginPath()
      ctx.arc(p[0], p[1], 4, 0, 2 * Math.PI)
      ctx.fillStyle = color
      ctx.fill()
    })
    // draw a faint hint from last point back to first if >=2
    if (points.length >= 2) {
      ctx.setLineDash([5, 5])
      ctx.beginPath()
      ctx.moveTo(points[points.length - 1][0], points[points.length - 1][1])
      ctx.lineTo(points[0][0], points[0][1])
      ctx.stroke()
      ctx.setLineDash([])
    }
    // light translucent fill for clarity when >=3 points
    if (points.length >= 3) {
      ctx.beginPath()
      ctx.moveTo(points[0][0], points[0][1])
      for (let i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1])
      ctx.fillStyle = 'rgba(0,255,0,0.12)'
      ctx.fill()
    }
    // status label near first point
    ctx.fillStyle = color
    ctx.font = '13px Arial'
    ctx.fillText(`Drawing (${points.length})`, points[0][0] + 6, points[0][1] - 8)
  }

  const handleCanvasClick = (e) => {
    if (!isDrawing) return
    const canvas = canvasRef.current
    const rect = canvas.getBoundingClientRect()
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    const x = (e.clientX - rect.left) * scaleX
    const y = (e.clientY - rect.top) * scaleY
    setCurrentZone((prev) => [...prev, [x, y]])
  }

  const startDrawing = () => {
    setIsDrawing(true)
    setCurrentZone([])
  }

  const finishZone = () => {
    if (currentZone.length >= 3) {
      const newZones = [...zones, currentZone]
      setZones(newZones)
      onZonesUpdate?.(newZones)
    }
    setCurrentZone([])
    setIsDrawing(false)
  }

  const clearZones = () => {
    setZones([])
    setCurrentZone([])
    setIsDrawing(false)
    onZonesUpdate?.([])
  }

  // Expose imperative API for external controls
  useImperativeHandle(ref, () => ({
    startDrawing,
    finishZone,
    clearZones,
    isDrawing: () => isDrawing,
    getZones: () => zones,
  }))

  return (
    <div
      className="zone-drawer"
      style={hideControls ? { width: '100%', height: '100%' } : undefined}
    >
      {!hideControls && (
        <div className="zone-controls">
          <button className="btn btn-primary" onClick={isDrawing ? finishZone : startDrawing}>
            {isDrawing ? 'Finish Zone' : 'Draw New Zone'}
          </button>
          <button className="btn btn-danger" onClick={clearZones}>
            Clear All Zones
          </button>
          <span className="zone-info">
            {isDrawing ? `Click to add points (${currentZone.length} points)` : `${zones.length} zone(s) defined`}
          </span>
        </div>
      )}
      <canvas
        ref={canvasRef}
        className={`zone-canvas ${hideControls ? 'zone-canvas--overlay' : ''}`}
        width={width}
        height={height}
        style={hideControls ? { width: '100%', height: '100%', cursor: isDrawing ? 'crosshair' : 'default' } : { cursor: isDrawing ? 'crosshair' : 'default' }}
        tabIndex={0}
        onClick={handleCanvasClick}
      />
      {hideControls && (
        <div style={{ position: 'absolute', top: 4, left: 8, background: 'rgba(0,0,0,0.4)', color: '#fff', padding: '2px 6px', fontSize: 12, borderRadius: 4 }}>
          {isDrawing ? `Drawing zone: ${currentZone.length} point(s)` : 'Click "Draw New Zone" to start'}
        </div>
      )}
    </div>
  )
})

export default ZoneDrawer
