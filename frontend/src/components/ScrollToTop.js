import { useEffect } from "react";
import { useLocation } from "react-router-dom";

// Scroll window to top on route changes.
export default function ScrollToTop() {
  const { pathname } = useLocation();

  // Smooth-scroll to top whenever pathname changes.
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" }); 
  }, [pathname]);

  return null;
}
