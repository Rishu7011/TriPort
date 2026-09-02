import React from "react";
import { RequireRole } from "../../lib/auth/RequireRole";

export default function CheckpointLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <RequireRole roles={["officer", "supervisor", "admin"]}>
      {children}
    </RequireRole>
  );
}
