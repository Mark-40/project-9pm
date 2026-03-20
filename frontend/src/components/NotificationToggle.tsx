"use client";

import { Bell, BellOff } from "lucide-react";
import { useNotifications } from "@/hooks/use-notifications";

export default function NotificationToggle() {
  const { enabled, permission, toggle } = useNotifications();

  if (typeof window === "undefined" || !("Notification" in window)) return null;
  if (permission === "denied") return null;

  return (
    <button
      onClick={toggle}
      className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-surface-border bg-surface-card hover:bg-surface-muted text-xs transition-colors"
      title={enabled ? "Disable notifications" : "Enable notifications"}
    >
      {enabled ? (
        <Bell className="size-3.5 text-green-400" />
      ) : (
        <BellOff className="size-3.5 text-gray-500" />
      )}
      <span className="text-gray-400">{enabled ? "Alerts On" : "Alerts Off"}</span>
    </button>
  );
}
