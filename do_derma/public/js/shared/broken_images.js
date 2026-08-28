import { reactive } from "vue"

/**
 * Remembers the image URLs that failed to load this session, so a deleted or unreadable
 * file degrades to whatever placeholder the caller renders instead of a broken thumbnail.
 */
export function useBrokenImages() {
  const broken = reactive(new Set())
  return {
    isBroken: (source) => broken.has(source),
    markBroken: (source) => {
      if (source) broken.add(source)
    },
  }
}
