import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import "./Toast.css";

/**
 * Toast notification system.
 *
 * Usage pattern (no external state lib):
 *   const { toasts, push, dismiss } = useToasts();
 *   push({ kind: "error", message: "Save failed" });
 *   ...
 *   <ToastContainer toasts={toasts} onDismiss={dismiss} />
 *
 * Toasts render top-right, spring-in, auto-dismiss 5s, and are
 * announced via role="status" (default) or role="alert" (errors).
 */

let idSeq = 0;
const nextId = () => `t-${Date.now().toString(36)}-${(idSeq++).toString(36)}`;

export function useToasts() {
  const [toasts, setToasts] = useState([]);
  const timers = useRef({});

  const dismiss = useCallback((id) => {
    setToasts((xs) => xs.filter((t) => t.id !== id));
    if (timers.current[id]) {
      clearTimeout(timers.current[id]);
      delete timers.current[id];
    }
  }, []);

  const push = useCallback(
    (toast) => {
      const id = toast.id || nextId();
      const entry = {
        id,
        kind: toast.kind || "info",
        message: toast.message ?? "",
        duration: toast.duration ?? 5000,
      };
      setToasts((xs) => [...xs, entry]);
      if (entry.duration > 0) {
        timers.current[id] = setTimeout(() => dismiss(id), entry.duration);
      }
      return id;
    },
    [dismiss]
  );

  // Clean up timers on unmount
  useEffect(() => {
    const t = timers.current;
    return () => {
      Object.values(t).forEach((h) => clearTimeout(h));
    };
  }, []);

  return { toasts, push, dismiss };
}

export function ToastContainer({ toasts, onDismiss }) {
  return (
    <div className="toast-container" aria-live="polite" aria-atomic="false">
      <AnimatePresence initial={false}>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            className={`toast toast--${t.kind}`}
            role={t.kind === "error" ? "alert" : "status"}
            initial={{ opacity: 0, x: 24, scale: 0.96 }}
            animate={{
              opacity: 1,
              x: 0,
              scale: 1,
              transition: { type: "spring", stiffness: 360, damping: 26 },
            }}
            exit={{
              opacity: 0,
              x: 32,
              scale: 0.96,
              transition: { duration: 0.18, ease: [0.4, 0, 1, 1] },
            }}
            layout
          >
            <span className="toast__icon" aria-hidden="true">
              {t.kind === "success" && "✓"}
              {t.kind === "error" && "!"}
              {t.kind === "warning" && "!"}
              {t.kind === "info" && "i"}
            </span>
            <span className="toast__message">{t.message}</span>
            <button
              type="button"
              className="toast__close"
              onClick={() => onDismiss(t.id)}
              aria-label="Dismiss notification"
            >
              ×
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
