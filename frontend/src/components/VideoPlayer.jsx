import { useState, useRef } from 'react'
import './VideoPlayer.css'

const VideoPlayer = ({ onFrameUpdate, overlayData }) => {
  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const [isPlaying, setIsPlaying] = useState(false)

  const handleVideoLoad = () => {
    if (videoRef.current && canvasRef.current) {
      const canvas = canvasRef.current
      canvas.width = videoRef.current.videoWidth
      canvas.height = videoRef.current.videoHeight
    }
  }

  const handlePlay = () => {
    setIsPlaying(true)
    if (onFrameUpdate) {
      const interval = setInterval(() => {
        if (videoRef.current && !videoRef.current.paused) {
          onFrameUpdate(videoRef.current.currentTime)
        } else {
          clearInterval(interval)
        }
      }, 100)
    }
  }

  const handlePause = () => {
    setIsPlaying(false)
  }

  return (
    <div className="video-player">
      <div className="video-container">
        <video
          ref={videoRef}
          className="video-element"
          onLoadedMetadata={handleVideoLoad}
          onPlay={handlePlay}
          onPause={handlePause}
          controls
        />
        <canvas ref={canvasRef} className="video-overlay" />
      </div>
    </div>
  )
}

export default VideoPlayer
