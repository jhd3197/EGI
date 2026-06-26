import { useRef, useState } from 'react'
import { css } from '../lib/css.js'

// Simple tap/drag-to-add photo slot. Replaces the old design-mockup
// <image-slot> web component with a plain, self-contained React control.
// Holds a local object URL only; wiring the file into the report payload /
// POST /import/paper is a future step.
export default function ImageSlot({ height = 180, radius = 16, placeholder = 'Toca para añadir una foto' }) {
  const inputRef = useRef(null)
  const [url, setUrl] = useState(null)

  const pick = (file) => {
    if (!file) return
    if (url) URL.revokeObjectURL(url)
    setUrl(URL.createObjectURL(file))
  }

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => { e.preventDefault(); pick(e.dataTransfer.files?.[0]) }}
      className="egi-tap"
      style={{
        ...css('width:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;cursor:pointer;overflow:hidden;border:1.5px dashed #D8D2C9;background:#fff;'),
        height,
        borderRadius: radius,
        backgroundImage: url
          ? `url(${url})`
          : 'repeating-linear-gradient(45deg,#F4F1EC,#F4F1EC 9px,#ECE7DF 9px,#ECE7DF 18px)',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      {!url && (
        <>
          <span style={css('width:34px;height:34px;border-radius:10px;background:#F2EFEA;position:relative;')}>
            <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:15px;height:2.6px;background:#A89F94;border-radius:2px;')} />
            <span style={css('position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:2.6px;height:15px;background:#A89F94;border-radius:2px;')} />
          </span>
          <span style={css("font:500 11px 'IBM Plex Mono';color:#A39B90;")}>{placeholder}</span>
        </>
      )}
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        onChange={(e) => pick(e.target.files?.[0])}
        style={{ display: 'none' }}
      />
    </div>
  )
}
