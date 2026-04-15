import React, { useState, useRef, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { useThemeStore } from "../style/useThemeStore";

// Single nav item with active state and optional dropdown.
export default function NavItem({ item }) {
  const { theme: c } = useThemeStore();
  const location = useLocation();

  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState(false);
  const ref = useRef(null);
  const btnRef = useRef(null);

  const matchPath = item.activePath || item.href; 

  const active = matchPath
    ? (matchPath === "/" 
        ? location.pathname === "/" 
        : location.pathname.startsWith(matchPath))
    : false;

  // Close dropdown when clicking outside the menu item.
  useEffect(() => {
    const handleClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
        setHovered(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Open dropdown on hover if configured.
  const handleMouseEnter = () => {
    setHovered(true);
    if (item.dropdown) setOpen(true);
  };

  // Close dropdown shortly after mouse leaves.
  const handleMouseLeave = () => {
    setHovered(false);
    if (item.dropdown) {
        setTimeout(() => {
            setOpen(false);
        }, 100);
    }
  };

  return (
    <div
      ref={ref}
      className="relative"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {/* Hover Layer */}
      <span
        className="absolute inset-0 rounded-none pointer-events-none"
        style={{
          zIndex: 2,
          opacity: hovered ? 1 : 0,
          background: hovered ? c.navHoverBackground : "transparent",
          boxShadow: hovered
            ? `0 0 25px ${c.navHoverShadow1}, 0 0 50px ${c.navHoverShadow2}`
            : "none",
          transition: "opacity 0.25s ease, box-shadow 0.25s ease",
        }}
      />

      {/* Active Layer */}
      {active && (
        <span
          className="absolute inset-0 rounded-none pointer-events-none z-[1]"
          style={{
            background: c.navActiveBackground,
            boxShadow: `0 0 25px ${c.navHoverShadow1}, 0 0 50px ${c.navHoverShadow2}`,
          }}
        />
      )}

      {/* Navigation Button */}
      <Link
        ref={btnRef}
        to={item.href}
        className="
          relative px-5 py-4 mx-0 rounded-none font-medium text-sm 
          transition-all duration-200 flex items-center justify-center
          no-underline hover:no-underline focus:no-underline active:no-underline
        "
        style={{
          zIndex: 10,
          color: active ? c.navTextActive : c.navText,
        }}
      >
        {item.label}
      </Link>

      {/* Dropdown */}
      {item.dropdown && open && (
        <div
          className="
            absolute left-1/2 top-full
            transform -translate-x-1/2
            min-w-full z-50 rounded-none p-2
            border text-center transition-all
          "
          style={{
            background: c.navcard,
            borderColor: c.border,
            boxShadow: `0 0 25px ${c.navHoverShadow1}`,
            width: btnRef.current ? `${btnRef.current.offsetWidth}px` : "auto",
          }}
        >
        {item.dropdown.map((child, idx) => (
        <React.Fragment key={child.href}>
            {idx > 0 && (
            <div
                style={{
                height: "1px",
                background: c.navBorder,
                margin: "0.25rem 0", 
                }}
            />
            )}

            <Link
            to={child.href}
            className="block px-2 py-3 text-sm transition-all"
            style={{
                color: c.text,
                textDecoration: "none",
            }}
            onMouseEnter={(e) => {
                e.currentTarget.style.background = c.navHoverBackground;
            }}
            onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
            }}
            >
            {child.label}
            </Link>

        </React.Fragment>
        ))}
        </div>
      )}

    </div>
  );
}

