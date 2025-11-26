import React, { useEffect, useRef } from 'react';

/**
 * LiveMjpegPlayer
 * Renders a smooth MJPEG stream via <img> tag.
 * Props:
 * - src: string – MJPEG endpoint URL
 * - onSize: function({ width, height }) – called when intrinsic size known
 * - className: optional string
 */
export default function LiveMjpegPlayer({ src, onSize, className, lockNaturalSize = false }) {
  const imgRef = useRef(null);

  useEffect(() => {
    const img = imgRef.current;
    if (!img) return;

    const handleLoad = () => {
      const w = img.naturalWidth;
      const h = img.naturalHeight;
      if (w && h && typeof onSize === 'function') {
        onSize({ width: w, height: h });
      }
    };

    img.addEventListener('load', handleLoad);
    return () => img.removeEventListener('load', handleLoad);
  }, [onSize]);

  const style = lockNaturalSize
    ? { display: 'block' }
    : { display: 'block', width: '100%', height: 'auto' };
  return <img ref={imgRef} src={src} alt="Live MJPEG" className={className} style={style} />;
}
