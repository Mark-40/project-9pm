"use client";

import { useTheme } from "next-themes";
import { Sun, Moon } from "lucide-react";
import { useEffect, useState } from "react";

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  const isDark = theme === "dark";

  return (
    <button
      onClick={() => setTheme(isDark ? "light" : "dark")}
      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-surface-border bg-surface-card hover:bg-surface-muted text-xs transition-colors"
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
    >
      {isDark ? (
        <Sun className="size-3.5 text-yellow-400" />
      ) : (
        <Moon className="size-3.5 text-blue-400" />
      )}
      <span className="text-gray-400">{isDark ? "Light" : "Dark"}</span>
    </button>
  );
}
