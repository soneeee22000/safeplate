/** Below this width the console stacks, so the trace sits under the picker. */
const STACKED_QUERY = "(max-width: 1023px)";
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/** Smooth scrolling, unless the visitor asked for less motion. */
function scrollBehavior(): ScrollBehavior {
  return window.matchMedia(REDUCED_MOTION_QUERY).matches ? "auto" : "smooth";
}

/**
 * Bring an element into view, but only when the layout is stacked: on wide
 * screens the trace already sits beside the picker.
 */
export function revealWhenStacked(element: HTMLElement | null): void {
  if (!element || !window.matchMedia(STACKED_QUERY).matches) return;
  element.scrollIntoView({ behavior: scrollBehavior(), block: "start" });
}

/**
 * Move focus to an element that needs a person's attention, scrolling it to
 * the middle of the screen so it is not hidden under the sticky header.
 */
export function focusAndReveal(element: HTMLElement | null): void {
  if (!element) return;
  element.focus({ preventScroll: true });
  element.scrollIntoView({ behavior: scrollBehavior(), block: "center" });
}
