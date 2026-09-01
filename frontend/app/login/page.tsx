import type { Metadata } from "next";
import { LoginForm } from "../../components/auth/LoginForm";

export const metadata: Metadata = {
  title: "Officer Authentication — TriPort",
  description:
    "Secure terminal login for border control officers, supervisors, auditors, and administrators.",
};

export default function LoginPage() {
  return (
    <main className="min-h-screen w-full flex items-center justify-center p-4 bg-bg relative overflow-hidden">
      {/* Tactical background grid & glow */}
      <div
        className="absolute inset-0 pointer-events-none opacity-20"
        style={{
          backgroundImage: "radial-gradient(#263025 1px, transparent 1px)",
          backgroundSize: "32px 32px",
        }}
      />
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[500px] h-[500px] bg-brand/5 rounded-full blur-3xl pointer-events-none" />

      {/* Login Card */}
      <div className="relative z-10 w-full py-8">
        <LoginForm />
      </div>
    </main>
  );
}
