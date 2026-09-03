import type { Metadata } from "next";
import { LoginForm } from "../../components/auth/LoginForm";

export const metadata: Metadata = {
  title: "Officer Authentication Portal — TriPort",
  description:
    "Tactical authentication gateway for border control officers, supervisors, auditors, and administrators.",
};

export default function LoginPage() {
  return (
    <main className="min-h-screen w-full flex flex-col justify-between items-center px-4 py-8 overflow-hidden bg-[#0B0C0E] text-[#e3e2e5] relative">
      {/* Ambient Tactical Grid & Scanner Background */}
      <div className="absolute inset-0 pointer-events-none opacity-20 bg-[radial-gradient(#c0f500_1px,transparent_1px)] [background-size:24px_24px]"></div>
      <div className="absolute -top-32 -left-32 w-96 h-96 bg-[#c0f500]/5 blur-[120px] rounded-full pointer-events-none"></div>
      <div className="absolute -bottom-32 -right-32 w-96 h-96 bg-[#c0f500]/5 blur-[120px] rounded-full pointer-events-none"></div>

      {/* Top Telemetry Ribbon */}
      <div className="w-full max-w-4xl flex flex-wrap items-center justify-between text-[#8e9479] font-mono text-xs z-10 mb-6 px-2 gap-4">
        <div className="flex items-center gap-3">
          <span className="tracking-widest text-[#c0f500] font-bold flex items-center gap-1.5 uppercase">
            <span className="w-2 h-2 bg-[#c0f500] animate-ping"></span>
            SYS.NODE: STATION-04 / DEL-T3
          </span>
          <span>/</span>
          <span>FIPS 140-3 LEVEL 4</span>
        </div>
        <div className="flex items-center gap-4">
          <div>
            HSM LATENCY: <span className="text-[#c0f500] font-bold">1.2ms</span>
          </div>
          <div className="h-3 w-px bg-[#2D3135]"></div>
          <div>
            GATEWAY NONCE: <span className="text-white">#0x8E29A...41C</span>
          </div>
        </div>
      </div>

      {/* Centered Tactical Auth Module (480px) */}
      <LoginForm />

      {/* Bottom Telemetry Footer */}
      <div className="w-full max-w-4xl flex items-center justify-between text-[#8e9479] font-mono text-[10px] z-10 mt-6 px-2">
        <span>TRIPORT SECURE TERMINAL GATEWAY v2.4.9</span>
        <span>ENCRYPTED VIA TLS 1.3 / ED25519</span>
      </div>
    </main>
  );
}
