import { useCallback, useEffect, useRef, useState } from "react";

interface Options {
  storageKey: string;
  defaultWidth: number;
  min: number;
  max: number;
  /** "left" = handle on the right edge (drag right grows). "right" = handle on the left edge (drag left grows). */
  side: "left" | "right";
}

export function useResizableWidth({ storageKey, defaultWidth, min, max, side }: Options) {
  const [width, setWidth] = useState<number>(() => {
    if (typeof window === "undefined") return defaultWidth;
    const raw = localStorage.getItem(storageKey);
    const n = raw ? Number(raw) : NaN;
    return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : defaultWidth;
  });
  const dragging = useRef(false);
  const startX = useRef(0);
  const startW = useRef(0);

  useEffect(() => {
    localStorage.setItem(storageKey, String(width));
  }, [storageKey, width]);

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      dragging.current = true;
      startX.current = e.clientX;
      startW.current = width;
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [width],
  );

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      const dx = e.clientX - startX.current;
      const next = side === "left" ? startW.current + dx : startW.current - dx;
      setWidth(Math.min(max, Math.max(min, next)));
    };
    const onUp = () => {
      if (!dragging.current) return;
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [min, max, side]);

  const reset = useCallback(() => setWidth(defaultWidth), [defaultWidth]);

  return { width, onMouseDown, reset };
}
