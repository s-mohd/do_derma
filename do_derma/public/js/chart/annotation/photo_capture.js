import { describeError } from "../../shared/error_text.js"
import { convertDataUrlToBlob, loadImage } from "../../shared/image_data.js"

const __ = window.__ || ((text) => text)

/** Clinically useful detail without the multi-megabyte payload a modern camera hands over. */
export const PHOTO_MAX_EDGE = 2048
export const PHOTO_JPEG_QUALITY = 0.85
const CAMERA_FACING_MODE = "environment"

/** The camera could not be opened, and the practitioner is told which of these it was. */
export class CameraUnavailableError extends Error {
  constructor(reason) {
    super(reason)
    this.name = "CameraUnavailableError"
    this.reason = reason
  }
}

/**
 * Mirrors frappe.ui.Capture's own branch: the mobile path shoots through a file input with
 * the `capture` attribute and never touches getUserMedia, so preflighting one there would
 * ask for a permission the dialog does not need.
 */
function isWebCaptureMode() {
  const frappe = window.frappe
  if (frappe?.boot?.sysdefaults?.force_web_capture_mode_for_uploads) return true
  return !frappe?.is_mobile?.()
}

function describeCameraError(error) {
  const name = error?.name || ""
  if (name === "NotAllowedError" || name === "SecurityError") return __("camera permission was denied")
  if (name === "NotFoundError" || name === "OverconstrainedError") return __("no camera was found on this device")
  if (name === "NotReadableError") return __("the camera is already in use by another app")
  return error?.message || __("the camera could not be started")
}

/** Fails before the dialog opens, so the fallback names a reason instead of an empty frame. */
async function assertCameraAvailable() {
  if (!window.frappe?.ui?.Capture) throw new CameraUnavailableError(__("this session has no camera dialog"))
  if (!isWebCaptureMode()) return
  if (!window.isSecureContext) throw new CameraUnavailableError(__("this page is not served over HTTPS"))
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new CameraUnavailableError(__("this browser exposes no camera"))
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: CAMERA_FACING_MODE } })
    for (const track of stream.getTracks()) track.stop()
  } catch (error) {
    throw new CameraUnavailableError(describeCameraError(error))
  }
}

/**
 * Opens the camera and resolves with one data URL per shot taken - empty when the dialog is
 * closed without submitting. Throws CameraUnavailableError when the camera never opened.
 */
export async function captureImageDataUrls() {
  await assertCameraAvailable()
  return new Promise((resolve) => {
    const capture = new window.frappe.ui.Capture({ animate: false, error: true })
    let submitted = null
    capture.submit((images) => {
      submitted = images || []
    })
    capture.show()
    // Capture hides the dialog before it calls back, so the resolve waits a tick for the shots.
    capture.dialog.onhide = () => setTimeout(() => resolve(submitted || []), 0)
    // The mobile path shoots through a file input and only shows its dialog once a file is
    // picked. Without this, cancelling the picker would leave the caller waiting forever.
    capture.input?.addEventListener("cancel", () => resolve([]), { once: true })
  })
}

/**
 * The library picker, offered when the camera cannot open. Resolves with the file URLs of
 * whatever was uploaded - the uploader stores privately and needs no re-encoding.
 */
export function pickImageFileUrls() {
  return new Promise((resolve, reject) => {
    if (!window.frappe?.ui?.FileUploader) {
      reject(new Error(__("File uploads are unavailable in this session.")))
      return
    }
    const picked = []
    const uploader = new window.frappe.ui.FileUploader({
      allow_multiple: true,
      restrictions: { allowed_file_types: ["image/*"] },
      on_success(file) {
        if (file?.file_url) picked.push(file.file_url)
      },
    })
    if (!uploader.dialog) {
      reject(new Error(__("File uploads are unavailable in this session.")))
      return
    }
    uploader.dialog.onhide = () => setTimeout(() => resolve(picked.splice(0)), 0)
  })
}

/** Re-encodes a shot to JPEG with its long edge capped, and reports the size it ended up. */
export async function downscaleImageDataUrl(dataUrl) {
  const image = await loadImage(dataUrl)
  const naturalWidth = image.naturalWidth || image.width
  const naturalHeight = image.naturalHeight || image.height
  if (!naturalWidth || !naturalHeight) throw new Error(__("The captured photo could not be read."))
  const scale = Math.min(1, PHOTO_MAX_EDGE / Math.max(naturalWidth, naturalHeight))
  const canvas = document.createElement("canvas")
  canvas.width = Math.round(naturalWidth * scale)
  canvas.height = Math.round(naturalHeight * scale)
  canvas.getContext("2d").drawImage(image, 0, 0, canvas.width, canvas.height)
  return {
    dataUrl: canvas.toDataURL("image/jpeg", PHOTO_JPEG_QUALITY),
    width: canvas.width,
    height: canvas.height,
  }
}

/**
 * Patient imagery is never public, so every capture goes up private and unattached. Answers
 * with the File's name as well as its URL, so a capture that fails later can take it back out.
 */
export async function uploadPrivateImage(dataUrl, fileName) {
  const body = new FormData()
  body.append("file", await convertDataUrlToBlob(dataUrl), fileName)
  body.append("is_private", "1")
  const response = await fetch("/api/method/upload_file", {
    method: "POST",
    headers: { Accept: "application/json", "X-Frappe-CSRF-Token": window.frappe?.csrf_token || "" },
    credentials: "same-origin",
    body,
  })
  const payload = await response.json().catch(() => null)
  if (!response.ok || !payload?.message?.file_url) {
    throw new Error(uploadErrorMessage(response, payload))
  }
  return { fileUrl: payload.message.file_url, file: payload.message.name || "" }
}

function uploadErrorMessage(response, payload) {
  if (payload) return describeError(payload)
  if (response.status === 413) return __("The photo is larger than this site accepts.")
  return `${response.status} ${response.statusText || __("Upload failed.")}`
}

/** Two shots of one burst are taken in the same millisecond, so the name carries a nonce. */
export function capturedPhotoFileName() {
  return `derma-capture-${Date.now()}-${Math.random().toString(36).slice(2, 8)}.jpg`
}
