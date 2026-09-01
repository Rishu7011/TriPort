import React from "react";
import { SidebarNav } from "../../components/SidebarNav";
import { RequireRole } from "../../lib/auth/RequireRole";

export default function CheckpointLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RequireRole roles={["officer", "supervisor", "admin"]}>
      <div className="min-h-screen flex bg-bg text-text">
        <SidebarNav />
        {/* Main Stage Offset for Left Rail */}
        <div className="flex-1 md:ml-[72px] flex flex-col min-w-0 transition-all duration-300">
          {children}
        </div>
      </div>
    </RequireRole>
  );
}
