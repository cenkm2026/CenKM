// CenKM.js
import React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useThemeStore } from "../style/useThemeStore";
import Digitizer from "./Digitizer";
import ReconstructionPage from "./ReconstructionPage";

import { motion, AnimatePresence } from "framer-motion";

// Small SVG icon for the Digitizer tab.
const IconDigitizer = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
    <circle cx="8.5" cy="8.5" r="1.5"></circle>
    <polyline points="21 15 16 10 5 21"></polyline>
  </svg>
);

// Small SVG icon for the Reconstruction tab.
const IconExcel = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
    <polyline points="14 2 14 8 20 8"></polyline>
    <line x1="16" y1="13" x2="8" y2="13"></line>
    <line x1="16" y1="17" x2="8" y2="17"></line>
    <polyline points="10 9 9 9 8 9"></polyline>
  </svg>
);

// Tabbed container that switches between Digitizer and Reconstruction pages.
export default function CenKM() {
  const navigate = useNavigate();
  const location = useLocation();
  const { theme: c, themeMode } = useThemeStore();

  const digitizerRef = React.useRef(null);
  const reconstructionRef = React.useRef(null);

  const [digitizerWidth, setDigitizerWidth] = React.useState(0);
  const [reconstructionWidth, setReconstructionWidth] = React.useState(0);

  // Measure button widths after first render for slider sizing.
  React.useEffect(() => {
    if (digitizerRef.current && reconstructionRef.current) {
        setDigitizerWidth(digitizerRef.current.offsetWidth);
        setReconstructionWidth(reconstructionRef.current.offsetWidth);
    }
    }, []);

  const activeTab = location.pathname.includes("reconstruction")
    ? "reconstruction"
    : "digitizer";

  const handleSwitch = (key) => {
    navigate(key === "digitizer" ? "/cenkm/digitizer" : "/cenkm/reconstruction");
  };

  return (
    <div
      className="min-h-screen flex flex-col items-center px-6 py-10"
      style={{ background: c.pageBackground, color: c.text }}
    >
      <div className="w-full max-w-5xl mb-6">
        <h1
          className="text-center text-3xl md:text-4xl font-semibold tracking-wide"
          style={{
            backgroundImage:
              themeMode === "dark"
                ? "linear-gradient(90deg, #FFFFFF 0%, #A0C4FF 100%)"
                : "none",
            WebkitBackgroundClip: "text",
            backgroundClip: "text",
            color: themeMode === "dark" ? "transparent" : "#000000",
          }}
        >
          CEN-KM: Patient Data Reconstruction
        </h1>
        <div
          className="mt-4 h-px w-full"
          style={{ background: "rgba(255, 255, 255, 0.22)" }}
        />
      </div>

      {/* Main Card */}
      <div
        className="w-full max-w-5xl rounded-3xl p-3 flex flex-col gap-3"
        style={{
          background: c.card,
          border: `1px solid ${c.border}`,
          boxShadow: c.glow,
          backdropFilter: "blur(24px) saturate(180%)",
          WebkitBackdropFilter: "blur(24px) saturate(180%)",
        }}
      >
    {/* Switcher */}
    <div className="flex justify-center">
    <div
        className="relative inline-flex border-b"
        style={{ borderColor: "rgba(255, 255, 255, 0.18)" }}
    >

        {/* Sliding underline */}
        <motion.div
        layout
        className="absolute bottom-0 h-[2px]"
        style={{
            background: "linear-gradient(90deg, #FFFFFF 0%, #A0C4FF 100%)",
        }}
        initial={false}
        animate={{
            x: activeTab === "digitizer" ? 0 : digitizerWidth,
            width: activeTab === "digitizer" ? digitizerWidth : reconstructionWidth,
        }}
        transition={{ duration: 0.25, ease: "easeOut" }}
        />

        {/* Digitizer Button */}
        <button
        ref={digitizerRef}
        onClick={() => handleSwitch("digitizer")}
        className="relative z-10 flex items-center gap-2 px-6 py-3 font-semibold text-sm transition-all duration-300"
        style={{
            color: activeTab === "digitizer" ? c.navTextActive : c.muted,
        }}
        >
        <IconDigitizer />
        Digitizer
        </button>

        {/* Reconstruction Button */}
        <button
        ref={reconstructionRef}
        onClick={() => handleSwitch("reconstruction")}
        className="relative z-10 flex items-center gap-2 px-6 py-3 font-semibold text-sm transition-all duration-300"
        style={{
            color: activeTab === "reconstruction" ? c.navTextActive : c.muted,
        }}
        >
        <IconExcel />
        Reconstruction 
        </button>

    </div>
    </div>



        {/* Content Area */}
            <div className="w-full min-h-[600px] overflow-hidden">
            <AnimatePresence mode="wait">
                {activeTab === "digitizer" ? (
                <motion.div
                    key="digitizer"
                    initial={{ x: -40, opacity: 0 }}
                    animate={{ x: 0, opacity: 1 }}
                    exit={{ x: -40, opacity: 0 }}     
                    transition={{ duration: 0.28, ease: "easeOut" }}
                >
                    <Digitizer />
                </motion.div>
                ) : (
                <motion.div
                    key="reconstruction"
                    initial={{ x: 40, opacity: 0 }}    
                    animate={{ x: 0, opacity: 1 }}
                    exit={{ x: 40, opacity: 0 }}
                    transition={{ duration: 0.28, ease: "easeOut" }}
                >
                    <ReconstructionPage />
                </motion.div>
                )}
            </AnimatePresence>
            </div>
      </div>
    </div>
  );
}
