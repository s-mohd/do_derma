export function loadImage(source) {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = reject
    image.src = source
  })
}

export function convertBlobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => resolve(reader.result)
    reader.onerror = reject
    reader.readAsDataURL(blob)
  })
}

export async function convertDataUrlToBlob(dataUrl) {
  const response = await fetch(dataUrl)
  return response.blob()
}

/** Fetches an image and hands back a canvas-ready data URL plus the size it really is. */
export async function imageUrlToRenderableData(url) {
  if (String(url || "").startsWith("data:")) {
    const image = await loadImage(url)
    const mimeType = mimeTypeFromDataUrl(url)
    return {
      dataURL: url,
      width: image.naturalWidth || image.width || 900,
      height: image.naturalHeight || image.height || 620,
      mimeType: mimeType === "image/jpeg" || mimeType === "image/png" ? mimeType : "image/png",
    }
  }
  const response = await fetch(url)
  const blob = await response.blob()
  const sourceURL = await convertBlobToDataUrl(blob)
  const image = await loadImage(sourceURL)
  const canvas = document.createElement("canvas")
  canvas.width = image.naturalWidth || image.width
  canvas.height = image.naturalHeight || image.height
  const context = canvas.getContext("2d")
  context.drawImage(image, 0, 0)
  const mimeType = blob.type && blob.type !== "image/svg+xml" ? blob.type : "image/jpeg"
  return {
    dataURL: canvas.toDataURL(mimeType === "image/png" ? "image/png" : "image/jpeg", 0.92),
    width: canvas.width,
    height: canvas.height,
    mimeType: mimeType === "image/png" ? "image/png" : "image/jpeg",
  }
}

function mimeTypeFromDataUrl(dataURL) {
  const match = String(dataURL || "").match(/^data:([^;]+);/)
  return match?.[1] || "image/png"
}
