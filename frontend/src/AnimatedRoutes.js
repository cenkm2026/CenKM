// AnimatedRoutes.js
import React from "react";
import { useLocation, Routes, Route } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";

// Simple slide + fade variants for route transitions.
const variants = {
  initial: { x: 80, opacity: 0 },
  animate: { x: 0, opacity: 1 },
  exit: { x: -80, opacity: 0 }
};

// Animated route container (routes injected elsewhere).
export default function AnimatedRoutes() {
  const location = useLocation();

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={location.pathname}
        variants={variants}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={{ duration: 0.45, ease: [0.22,1,0.36,1] }}
        style={{ width: "100%", minHeight: "100vh" }}
      >
        <Routes location={location}>
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}
