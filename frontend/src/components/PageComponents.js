// src/components/PageComponents.js
import React from "react";
import ReactDOM from "react-dom";
import { useThemeStore } from "../style/useThemeStore";

// Themed button with optional icon and disabled state.
export function Button({
  children,
  onClick,
  disabled,
  icon: Icon,
  className = "",
  iconOnly = false,
  ...props
}) {
  const { theme: c } = useThemeStore();

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`
        inline-flex items-center justify-center
        rounded-xl text-sm font-semibold transition-all duration-300
        ${iconOnly ? "p-2" : "px-4 py-2 gap-2"}
        ${disabled ? "opacity-50 cursor-not-allowed" : "hover:brightness-110 active:brightness-95"}
        ${className}
      `}
      style={{
        background: c.primary,        
        color: c.text,
        boxShadow: disabled ? "none" : c.glow,
      }}
      {...props}
    >
      {Icon && <Icon className="h-4 w-4" />}
      {!iconOnly && children}
    </button>
  );
}

// Portal-based modal popover with backdrop.
export function Popover({ open, onClose, children, title }) {
  const { theme: c } = useThemeStore();

  if (!open) return null;

  return ReactDOM.createPortal(
    <>
      <div
        className="fixed inset-0 z-[999] bg-black/40 backdrop-blur-xl"
        onClick={onClose}
      />

      <div
        className="fixed z-[1000] left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2
                   w-[90vw] max-w-lg rounded-2xl p-6 shadow-2xl"
        style={{
          background: c.card,
          border: `1px solid ${c.border}`,
          boxShadow: c.glow,
        }}
      >
        {title && (
          <h3 className="text-lg font-semibold mb-4" style={{ color: c.text }}>
            {title}
          </h3>
        )}

        <div className="text-sm leading-6" style={{ color: c.text }}>
          {children}
        </div>

        <div className="mt-6 text-right">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-white"
            style={{ background: c.primary }}
          >
            Got it
          </button>
        </div>
      </div>
    </>,
    document.body
  );
}


// Themed textarea with focus styling.
export function TextArea({
  value,
  onChange,
  placeholder,
  className = "",
  ...props
}) {
  const { theme: c } = useThemeStore();

  return (
    <textarea
      rows={3}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      className={`
        w-full rounded-xl px-4 py-3 text-base transition-all duration-300
        backdrop-blur-xl outline-none
        ${className}
      `}
      style={{
        background: c.textAreaBackground,      
        border: `1px solid ${c.border}`,          
        color: c.text,                            
        boxShadow: `0 0 6px ${c.textAreaBoxshadow}`,       
      }}
      onFocus={(e) => {
        e.target.style.border = `1px solid ${c.primary}`;
        e.target.style.boxShadow = c.glow;       
      }}
      onBlur={(e) => {
        e.target.style.border = `1px solid ${c.border}`;
        e.target.style.boxShadow = `0 0 6px ${c.textAreaBoxshadow}`;
      }}
      {...props}
    />
  );
}

// Themed input/textarea with optional number spinner removal.
export function TextInput({
  value,
  onChange,
  placeholder,
  as = "input",   // "input" or "textarea"
  rows = 3,
  type = "text",
  className = "",
  ...props
}) {
  const { theme: c } = useThemeStore();

  const Tag = as; 

  const hideNumberArrows =
  as === "input" && type === "number"
    ? {
        WebkitAppearance: "none",
        MozAppearance: "textfield",
      }
    : {};

  return (
    <Tag
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      rows={as === "textarea" ? rows : undefined}
      type={as === "input" ? type : undefined}
      className={`
        w-full rounded-xl px-4 py-2 text-base transition-all duration-200
        backdrop-blur-xl focus:outline-none
        ${as === "input" && type === "number" ? "no-spinner" : ""}
        ${className}
      `}
      style={{
        background: c.textAreaBackground,
        border: `1px solid ${c.border}`,
        color: c.text,
        boxShadow: `0 0 6px ${c.textAreaBoxshadow}`,
        ...hideNumberArrows,
      }}
      onFocus={(e) => {
        e.target.style.border = `1px solid ${c.primary}`;
        e.target.style.boxShadow = c.glow;
      }}
      onBlur={(e) => {
        e.target.style.border = `1px solid ${c.border}`;
        e.target.style.boxShadow = `0 0 6px ${c.textAreaBoxshadow}`;
      }}
      {...props}
    />
  );
}


// Small inline tip pill for hints or labels.
export function Tip({ children }) {
  const { theme: c } = useThemeStore();

  return (
    <span
      className="
        text-xs px-2 py-1 rounded-lg
        backdrop-blur-md
        inline-flex items-center
      "
      style={{
        background: c.tipBackground, 
        border: `1px solid ${c.border}`,
        color: c.muted,
        boxShadow: `0 0 6px ${c.tipBoxshadow}`, 
      }}
    >
      {children}
    </span>
  );
}
