import React from "react";

export const ANNOUNCE_VERSION = "1.0.1";   // â†?This release only touches this part.
const ANNOUNCE_KEY = `CEN-KM-announce:${ANNOUNCE_VERSION}`;

// Announcement state hook with localStorage persistence.
export function useAnnouncement() {
  const [openBar, setOpenBar] = React.useState(false);
  const [openModal, setOpenModal] = React.useState(false);

  // Show bar if current version has not been dismissed.
  React.useEffect(() => {
    const dismissed = localStorage.getItem(ANNOUNCE_KEY) === "dismissed";
    if (!dismissed) setOpenBar(true);
  }, []);

  // Persist dismissal and close UI.
  const dismiss = () => {
    localStorage.setItem(ANNOUNCE_KEY, "dismissed");
    setOpenBar(false);
    setOpenModal(false);
  };

  return { openBar, setOpenBar, openModal, setOpenModal, dismiss };
}

// Top announcement bar with open/dismiss actions.
export function AnnouncementBar({ onOpen, onClose }) {
  return (
    <div role="region" aria-label="Update announcement" className="sticky top-0 z-50">
      <div className="mx-auto max-w-6xl">
        <div className="mt-3 rounded-xl border shadow-sm bg-amber-50 text-amber-900">
          <div className="flex items-center gap-3 px-4 h-11">
            <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M3 10v4h3l5 5V5L6 10H3zm13 1a2 2 0 100 2 2 2 0 000-2z"></path>
            </svg>
            <p className="text-sm leading-[1.2] m-0 align-middle">
              <b>CEN-KM v1.0.1</b> â€?We are currently experiencing high traffic, which may cause occasional 524 timeout errors.
            </p>
            <button
              className="ml-auto inline-flex items-center h-7 px-2 text-sm text-blue-700 hover:underline"
              onClick={onOpen}
            >
              View Past Updates
            </button>
            <button
              aria-label="Dismiss"
              className="ml-2 inline-flex items-center justify-center h-7 w-7 rounded-md text-sm hover:bg-amber-100"
              onClick={onClose}
            >
              Ã—
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Modal listing version updates.
export function ChangelogModal({ open, onClose }) {
  if (!open) return null;
  return (
    <>
      <div className="fixed inset-0 z-50 bg-black/40" onClick={onClose} />
      <div role="dialog" aria-modal="true" aria-label="What's new"
           className="fixed z-50 left-1/2 top-24 w-[92vw] max-w-xl -translate-x-1/2 rounded-2xl border bg-white p-5 shadow-xl">
        <h3 className="text-lg font-semibold">Whatâ€™s new in v{ANNOUNCE_VERSION}</h3>
        <p className="mt-1 text-xs text-gray-500">2025-09-24</p>
        <ul className="mt-4 space-y-2 text-sm list-disc pl-5">
          <li>Added update announcement bar & changelog modal (versioned, closable).</li>
          <li>Adjustable eraser size & fix for unintended connecting strokes.</li>
          <li>â€œClick to Reuploadâ€?for each slot; cleaner inline tip placement.</li>
        </ul>
        {/* <div className="mt-4 rounded-lg bg-gray-50 p-3 text-xs text-gray-600">
          Tip: Export is PNG (alpha). Need solid background? Flatten on export.
        </div> */}
        <div className="mt-5 flex justify-end gap-2">
          <button className="rounded-xl border px-3 py-1.5 text-sm hover:bg-gray-50" onClick={onClose}>Close</button>
          {/* <a href="/changelog" className="rounded-xl bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700">Full changelog</a> */}
        </div>
      </div>
    </>
  );
}

