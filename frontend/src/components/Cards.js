// src/components/NeoCard.jsx
import React from "react";
import { useThemeStore } from "../style/useThemeStore";

// Themed card container with consistent padding and chrome.
export function Card({
  children,
  className = "",
  style = {},
}) {
  const { theme: c } = useThemeStore();

  return (
    <section
      className={`rounded-2xl backdrop-blur-xl shadow-lg ${className}`}
      style={{
        background: c.card,
        border: `1px solid ${c.border}`,
        boxShadow: c.glow,
        ...style,
      }}
    >

      {/* 内容 */}
      <div className="px-6 py-6" style={{ color: c.text }}>
        {children}
      </div>
    </section>
  );
}

// Section header with optional icon and action slot.
export function SectionHeader({ icon: Icon, title, action }) {
  const { theme: c } = useThemeStore();

  return (
    <div className="mb-4 relative z-20">
      <div
        className="flex items-center justify-between pb-3 relative"
        style={{
          borderBottom: `1px solid ${c.border}`,
          color: c.text,
        }}
      >
        {/* 左侧标题 */}
        <h3 className="flex items-center gap-2 text-lg font-semibold">
          {Icon && <Icon className="h-5 w-5" />}
          {title}
        </h3>

        {/* 右侧 Close / Link / Action */}
        {action && (
          <div className="ml-4 text-right">
            {action}
          </div>
        )}

        {/* 🔵 霓虹条放在标题栏底部，不单独占一行 */}
        <div
          className="absolute left-0 bottom-[-3px] w-full h-[3px] rounded-md"
          style={{
            background: c.gradientBar,
            boxShadow: `0 0 10px ${c.barshadow}`,
          }}
        />
      </div>
    </div>
  );
}
