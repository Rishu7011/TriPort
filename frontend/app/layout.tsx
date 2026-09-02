import type { Metadata } from "next";
import { Space_Grotesk, Inter, JetBrains_Mono, Chivo } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "../lib/auth/AuthContext";

const spaceGrotesk = Space_Grotesk({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const inter = Inter({
  variable: "--font-body",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const chivo = Chivo({
  variable: "--font-chivo",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800", "900"],
});

export const metadata: Metadata = {
  title: "TriPort — Border AI Screening Console",
  description:
    "AI-powered multi-modal border document screening, biometric facial verification, and forensic audit ledger console.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${inter.variable} ${jetbrainsMono.variable} ${chivo.variable} h-full antialiased dark`}
    >
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-full flex flex-col bg-bg text-text selection:bg-brand selection:text-bg">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
