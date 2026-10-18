import { useState, useRef, useEffect, useCallback } from 'react'
import './VideoPlayer.css'

const VideoPlayer = ({
  src,
  frameTracks = {},
  fps = 30,
  onFrameChange,
  activeZones = []
}) => {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const animFrameRef = useRef(null)

  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [currentFrameNum, setCurrentFrameNum] = useState(1)
  const [playbackRate, setPlaybackRate] = useState(1.0)

  // Handle metadata loaded
  const handleLoadedMetadata = () => {
    if (videoRef.current && canvasRef.current) {
      const vid = videoRef.current
      setDuration(vid.duration || 0)
      canvasRef.current.width = vid.videoWidth || 640
      canvasRef.current.height = vid.videoHeight || 480
    }
  }

  // Draw overlay boxes and zones for the current frame
  const drawOverlay = useCallback(() => {
    if (!canvasRef.current || !videoRef.current) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const vid = videoRef.current

    // Sync canvas size if needed
    if (canvas.width !== vid.videoWidth && vid.videoWidth > 0) {
      canvas.width = vid.videoWidth
      canvas.height = vid.videoHeight
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Current frame number based on playback timestamp
    const frameNum = Math.max(1, Math.floor(vid.currentTime * (fps || 30)))
    setCurrentFrameNum(frameNum)
    if (onFrameChange) onFrameChange(frameNum)

    // Draw active restricted zones in translucent red
    if (activeZones && activeZones.length > 0) {
      activeZones.forEach((zone, idx) => {
        if (!zone || zone.length < 3) return
        ctx.beginPath()
        ctx.moveTo(zone[0][0], zone[0][1])
        zone.forEach((pt) => ctx.lineTo(pt[0], pt[1]))
        ctx.closePath()
        ctx.fillStyle = 'rgba(255, 0, 0, 0.18)'
        ctx.fill()
        ctx.strokeStyle = 'rgba(255, 0, 0, 0.7)'
        ctx.lineWidth = 2
        ctx.stroke()
        ctx.fillStyle = 'rgba(255, 100, 100, 0.9)'
        ctx.font = '12px Arial'
        ctx.fillText(`Zone ${idx + 1}`, zone[0][0] + 4, zone[0][1] - 6)
      })
    }

    // Draw bounding boxes for this frame
    const tracks = frameTracks[frameNum] || frameTracks[String(frameNum)] || []
    tracks.forEach((trk) => {
      const bbox = trk.bbox // [x1, y1, x2, y2]
      if (!bbox || bbox.length < 4) return
      const [x1, y1, x2, y2] = bbox
      const w = x2 - x1
      const h = y2 - y1

      // Vehicle vs pedestrian styling
      const isVehicle = trk.class_name === 'motorcycle' || trk.class_name === 'bicycle'
      ctx.strokeStyle = isVehicle ? '#f59e0b' : '#00ff88'
      ctx.lineWidth = 2
      ctx.strokeRect(x1, y1, w, h)

      // Label badge
      const classTag = trk.class_name && trk.class_name !== 'person' ? ` [${trk.class_name}]` : ''
      const label = `ID: ${trk.id}${classTag} | ${trk.speed ? trk.speed + 'px/f' : ''}`
      ctx.font = 'bold 12px Arial'
      const textWidth = ctx.measureText(label).width

      ctx.fillStyle = 'rgba(0, 0, 0, 0.75)'
      ctx.fillRect(x1, Math.max(0, y1 - 20), textWidth + 8, 18)

      ctx.fillStyle = isVehicle ? '#fbbf24' : '#00ff88'
      ctx.fillText(label, x1 + 4, Math.max(14, y1 - 6))
    })

    if (isPlaying) {
      animFrameRef.current = requestAnimationFrame(drawOverlay)
    }
  }, [fps, frameTracks, activeZones, isPlaying, onFrameChange])

  // Continuous animation loop while playing
  useEffect(() => {
    if (isPlaying) {
      animFrameRef.current = requestAnimationFrame(drawOverlay)
    } else {
      drawOverlay()
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    }
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    }
  }, [isPlaying, drawOverlay])

  const togglePlay = () => {
    if (!videoRef.current) return
    if (videoRef.current.paused) {
      videoRef.current.play()
      setIsPlaying(true)
    } else {
      videoRef.current.pause()
      setIsPlaying(false)
    }
  }

  const handleSeek = (e) => {
    const targetTime = parseFloat(e.target.value)
    if (videoRef.current) {
      videoRef.current.currentTime = targetTime
      setCurrentTime(targetTime)
      drawOverlay()
    }
  }

  const handleSpeedChange = (rate) => {
    setPlaybackRate(rate)
    if (videoRef.current) {
      videoRef.current.playbackRate = rate
    }
  }

  return (
    <div className="video-player-container">
      <div className="video-stage">
        <video
          ref={videoRef}
          src={src}
          className="video-media"
          onLoadedMetadata={handleLoadedMetadata}
          onTimeUpdate={() => setCurrentTime(videoRef.current?.currentTime || 0)}
          onEnded={() => setIsPlaying(false)}
          playsInline
        />
        <canvas ref={canvasRef} className="video-canvas-overlay" />
      </div>

      {/* Playback Controls */}
      <div className="player-controls">
        <button className="btn btn-primary btn-play" onClick={togglePlay}>
          {isPlaying ? '⏸ Pause' : '▶ Play'}
        </button>

        <span className="time-display">
          {currentTime.toFixed(1)}s / {duration.toFixed(1)}s (Frame {currentFrameNum})
        </span>

        <input
          type="range"
          min="0"
          max={duration || 100}
          step="0.03"
          value={currentTime}
          onChange={handleSeek}
          className="timeline-slider"
        />

        <div className="speed-buttons">
          {[0.5, 1.0, 2.0].map((rate) => (
            <button
              key={rate}
              className={`btn-speed ${playbackRate === rate ? 'active' : ''}`}
              onClick={() => handleSpeedChange(rate)}
            >
              {rate}x
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

export default VideoPlayer
