import { useRef, useState } from "react"
import { describeError } from "../../shared/error_text.js"
import { imageUrlToRenderableData } from "../../shared/image_data.js"
import {
  CameraUnavailableError,
  capturedPhotoFileName,
  captureImageDataUrls,
  downscaleImageDataUrl,
  pickImageFileUrls,
  uploadPrivateImage,
} from "./photo_capture.js"

const __ = window.__ || ((text) => text)

/**
 * Owns the studio's photos: the camera, the upload, the Derma Photo Set behind them, and the
 * reconciliation that makes deleting a photo element delete the photo when the drawing saves.
 */
export function usePhotoCapture({ context, bodyTemplate, chartMarkName, embeddedRef }) {
  const [isBusy, setIsBusy] = useState(false)
  // Photos the drawing carried when it opened, plus everything captured since. Whatever is
  // missing from the canvas at save time is what the practitioner deleted.
  const knownPhotos = useRef(new Set())
  // Captured before any save, so discarding the drawing has to take them with it.
  const sessionPhotos = useRef(new Set())

  /**
   * The photos the canvas is holding right now. Never an empty list when the canvas is simply
   * not there to ask: reconciliation reads "gone from the canvas" as "delete it", so a silent
   * empty answer would take every photo on the drawing with it.
   */
  function readCanvasPhotos() {
    const canvas = embeddedRef.current
    if (!canvas?.getPhotoNames) throw new Error(__("The drawing surface is not ready."))
    return new Set(canvas.getPhotoNames())
  }

  /**
   * The canvas signals a settled scene on every template load, not only the first. Union rather
   * than replace: re-reading would forget a photo the practitioner had already deleted, and the
   * save would then leave it on the chart.
   */
  function rememberLoadedPhotos() {
    knownPhotos.current = new Set([...knownPhotos.current, ...readCanvasPhotos()])
  }

  function sessionPhotoCount() {
    return sessionPhotos.current.size
  }

  async function capture() {
    if (isBusy) return
    let shots = []
    try {
      shots = await collectShots()
    } catch (error) {
      reportFailure(__("Unable to capture the photo"), error)
      return
    }
    if (!shots.length) return
    setIsBusy(true)
    try {
      await storeCapturedPhotos(shots)
    } catch (error) {
      // No element is placed and no set is kept: a photo the record does not have must not
      // sit on the canvas looking saved.
      reportFailure(__("Unable to save the photo"), error)
    } finally {
      setIsBusy(false)
    }
  }

  /** The camera first; the library only after saying out loud why the camera did not open. */
  async function collectShots() {
    try {
      const images = await captureImageDataUrls()
      return Promise.all(images.map((image) => downscaleImageDataUrl(image)))
    } catch (error) {
      if (!(error instanceof CameraUnavailableError)) throw error
      if (!(await confirmLibraryFallback(error.reason))) return []
      const fileUrls = await pickImageFileUrls()
      return Promise.all(fileUrls.map((fileUrl) => readUploadedShot(fileUrl)))
    }
  }

  /** A library pick is already stored, so it carries its file URL and skips the upload. */
  async function readUploadedShot(fileUrl) {
    const { dataURL, width, height } = await imageUrlToRenderableData(fileUrl)
    return { dataUrl: dataURL, width, height, fileUrl }
  }

  async function storeCapturedPhotos(shots) {
    const uploads = await uploadShots(shots)
    let photoSet = null
    try {
      photoSet = await createPhotoSet(uploads.map((upload) => upload.fileUrl))
    } catch (error) {
      // A set that was never created leaves its uploads owned by nothing. Take them back out
      // rather than leaving unreferenced patient imagery on the server.
      await discardUploads(uploads)
      throw error
    }
    // The set answers with its rows in the order they were sent, which is the order of the
    // shots. Matching on the file URL instead would collapse two identical shots into one.
    const placed = (photoSet.photos || [])
      .map((photo, index) => {
        const shot = shots[index]
        if (!shot) return null
        return {
          photo: photo.name,
          photoSet: photoSet.name,
          fileUrl: photo.image,
          dataUrl: shot.dataUrl,
          width: shot.width,
          height: shot.height,
        }
      })
      .filter(Boolean)
    embeddedRef.current?.insertPhotos?.(placed)
    const names = placed.map((photo) => photo.photo)
    knownPhotos.current = new Set([...knownPhotos.current, ...names])
    sessionPhotos.current = new Set([...sessionPhotos.current, ...names])
    window.frappe?.show_alert?.({
      message: __("{0} photo(s) saved to this visit").replace("{0}", placed.length),
      indicator: "green",
    })
  }

  /**
   * One upload per shot, in order. A library pick arrives already stored, so it is passed
   * through and never deleted on failure - the practitioner uploaded it themselves.
   */
  async function uploadShots(shots) {
    const uploads = []
    for (const shot of shots) {
      if (shot.fileUrl) {
        uploads.push({ fileUrl: shot.fileUrl, file: "" })
        continue
      }
      try {
        uploads.push(await uploadPrivateImage(shot.dataUrl, capturedPhotoFileName()))
      } catch (error) {
        await discardUploads(uploads)
        throw error
      }
    }
    return uploads
  }

  /** Best effort: the capture already failed, and a stranded file must not hide that. */
  async function discardUploads(uploads) {
    for (const upload of uploads.filter((row) => row.file)) {
      try {
        await window.frappe.call({
          method: "frappe.client.delete",
          args: { doctype: "File", name: upload.file },
        })
      } catch {
        // Nothing further to offer the practitioner; the capture error is the one that matters.
      }
    }
  }

  async function createPhotoSet(images) {
    const view = bodyTemplate?.title || ""
    const region = bodyTemplate?.template_type || ""
    const response = await window.frappe.call({
      method: "do_derma.api.create_photo_set",
      args: {
        values: {
          patient: context.patient,
          appointment: context.appointment,
          encounter: context.encounter,
          clinical_procedure: context.clinicalProcedure || "",
          chart_mark: chartMarkName || "",
          body_view: view,
          body_region: region,
          photos: images.map((image) => ({ image, view, body_region: region })),
        },
      },
    })
    if (!response.message?.name) throw new Error(__("The photo set could not be created."))
    return response.message
  }

  /**
   * Deleting a photo element deletes the photo, but only once the drawing is saved - undo
   * before saving has to give both back. Returns how many photos the save removed.
   */
  async function reconcileDeletedPhotos() {
    const present = readCanvasPhotos()
    const removed = [...knownPhotos.current].filter((name) => !present.has(name))
    const kept = await deletePhotos(removed)
    knownPhotos.current = present
    // Saved photos belong to the annotation now; a later discard must not reach for them.
    sessionPhotos.current = new Set()
    return removed.length - kept.length
  }

  /** Discarding the drawing discards the photos it captured, as it does its marks. */
  async function discardSessionPhotos() {
    const kept = await deletePhotos([...sessionPhotos.current])
    sessionPhotos.current = new Set(kept)
    return kept
  }

  /** Deletes one at a time and reports what survived, rather than failing the whole save. */
  async function deletePhotos(names) {
    const kept = []
    for (const photo of names) {
      try {
        await window.frappe.call({ method: "do_derma.api.delete_photo", args: { photo } })
      } catch (error) {
        kept.push(photo)
        reportFailure(__("Unable to delete a photo"), error)
      }
    }
    return kept
  }

  return {
    isBusy,
    capture,
    rememberLoadedPhotos,
    sessionPhotoCount,
    reconcileDeletedPhotos,
    discardSessionPhotos,
  }
}

function confirmLibraryFallback(reason) {
  return new Promise((resolve) => {
    window.frappe.confirm(
      __("The camera could not be opened because {0}. Choose a photo from this device instead?").replace(
        "{0}",
        reason
      ),
      () => resolve(true),
      () => resolve(false)
    )
  })
}

function reportFailure(title, error) {
  window.frappe?.msgprint?.({ title, message: describeError(error), indicator: "red" })
}
