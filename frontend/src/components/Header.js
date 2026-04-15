// src/components/Header.jsx
import React from "react";
//import theme from "../style/theme";
import { Link, useLocation } from "react-router-dom";
import { Sun, Moon } from "lucide-react";

import { useThemeStore } from "../style/useThemeStore";
import NavItem from "./NavItem";
import { menuConfig } from "../config/menuConfig";

// App header with logo, nav, and theme toggle.
export default function Header() {
  const { theme: c, themeMode, toggleTheme } = useThemeStore();

  return (
    <header
      className="relative backdrop-blur-xl sticky top-0 z-50 shadow-lg h-18 flex items-center"
      style={{
        background: c.pageBackground,
        borderBottom: `1px solid ${c.border}`,
      }}
    >
      {/* Top glowing bar */}
      <div
        className="absolute inset-x-0 top-0 h-[3px] pointer-events-none"
        style={{
          background: c.gradientBar,
          boxShadow: `0 0 12px ${c.barshadow}`,
        }}
      />

      {/* Main row */}
      <div className="container mx-auto px-6 flex items-center justify-between">

        {/* Logo */}
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-full"
            style={{
              background: c.logoBackground,
              boxShadow: c.glow,
            }}
          />
          <Link
            to="/"
            className="font-bold text-lg"
            style={{ color: c.text, textDecoration: "none" }}
          >
            CEN-KM
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex items-center gap-2 h-20">
          {/* {menuConfig.map((item) => (
            <NavItem key={item.label} item={item} />
          ))} */}
        </nav>

        {/* Theme Switch */}
        <button
          onClick={toggleTheme}
          className="px-4 py-2 rounded-xl text-sm font-medium flex items-center gap-2 transition-all"
          style={{
            borderColor: c.border,
            background: "transparent",
            color: c.text,
          }}
        >
          {themeMode === "dark" ? (
            <>
              <Sun size={16} /> Daylight
            </>
          ) : (
            <>
              <Moon size={16} /> Night
            </>
          )}
        </button>
      </div>
    </header>
  );
}

