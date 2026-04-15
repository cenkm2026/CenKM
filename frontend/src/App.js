// App.js
import { useRef, useEffect }  from "react";
import "bootstrap/dist/css/bootstrap.min.css";
import { BrowserRouter as Router, Navigate  } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";

import Header from "./components/Header";
import ScrollToTop from "./components/ScrollToTop";
import { useThemeStore } from "./style/useThemeStore";

import CenKM from "./pages/CenKM"

import { menuConfig } from "./config/menuConfig";

import { Routes, Route, useLocation } from "react-router-dom";

// Route container with animated transitions based on nav order.
function AnimatedRoutes() {
  const { theme: c } = useThemeStore();
  const location = useLocation();
  // Build a stable path->index map from the menu config for direction calc.
  const pathIndexMap = useRef(
    menuConfig.reduce((acc, item, idx) => {
      acc[item.href] = idx;
      if (item.dropdown) {
        item.dropdown.forEach(sub => {
          acc[sub.href] = idx;  
        });
      }
      return acc;
    }, {})
  );

  // Track previous route index to decide slide direction.
  const prevIndexRef = useRef(pathIndexMap.current[location.pathname] || 0);
  const currentIndex = pathIndexMap.current[location.pathname] ?? 0;
  const prevIndex = prevIndexRef.current;

  // Compute motion direction: 1 forward, -1 backward, 0 stay.
  const direction = currentIndex > prevIndex ? 1 : currentIndex < prevIndex ? -1 : 0;

  // Paths that should not animate between states.
  const noAnimPaths = [
    "/cenkm/digitizer",
    "/cenkm/reconstruction"
  ];

  // Use a fixed key to disable re-mount animation for those paths.
  const motionKey = noAnimPaths.includes(location.pathname)
  ? "cenkm-static"
  : location.pathname;

  // Update previous index after each route change.
  useEffect(() => {
    prevIndexRef.current = currentIndex;
  }, [location.pathname]);

  // Framer-motion variants with directional slide + fade.
  const variants = {
    initial: (dir) => ({ x: dir * 80 || 0, opacity: 0 }),
    animate:        { x: 0, opacity: 1 },
    exit:    (dir) => ({ x: dir ? dir * -80 : 0, opacity: 0 })
  };

  return (
    <AnimatePresence mode="wait" initial={false} custom={direction}>
      <motion.div
        key={motionKey}
        variants={variants}
        initial="initial"
        animate="animate"
        exit="exit"
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        style={{ width: "100%", minHeight: "100vh", background: c.pageBackground}}
      >
        <Routes location={location}>
          <Route path="/" element={<Navigate to="/cenkm/digitizer" replace />} />
          <Route path="/Home" element={<Navigate to="/cenkm/digitizer" replace />} />
          <Route path="/cenkm" element={<Navigate to="/cenkm/digitizer" replace />} />
          <Route path="/cenkm/digitizer" element={<CenKM />} />
          <Route path="/cenkm/reconstruction" element={<CenKM />} />
          <Route path="*" element={<Navigate to="/cenkm/digitizer" replace />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

// App shell with router + global layout wrappers.
export default function App() {
  const { theme: c } = useThemeStore();
  return (
    <Router>
      <ScrollToTop />
      <Header />
      <div style={{ position: "relative", overflow: "hidden", minHeight: "100vh", background: c.pageBackground }}>
        <AnimatedRoutes />
      </div>
    </Router>
  );
}
