import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { ResumeProvider } from "@/lib/resume-context";
import Nav from "@/components/Nav";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800", "900"],
});

export const metadata: Metadata = {
  title: "ReflectInterview — Practice the interview before it counts",
  description:
    "AI mock interviews with adaptive difficulty, voice input, and behavioural feedback.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        {/* Ambient layer: a slow conic prism, eight drifting colour fields
            that blend into each other, and grain -- fixed behind every
            route. Purely decorative and non-interactive, so it is hidden
            from assistive tech entirely. All geometry and motion live in
            globals.css; these divs are just the surfaces to paint on. */}
        <div className="ri-aurora" aria-hidden="true">
          <div className="ri-aurora__prism" />
          <div className="ri-aurora__blob ri-aurora__blob--1" />
          <div className="ri-aurora__blob ri-aurora__blob--2" />
          <div className="ri-aurora__blob ri-aurora__blob--3" />
          <div className="ri-aurora__blob ri-aurora__blob--4" />
          <div className="ri-aurora__blob ri-aurora__blob--5" />
          <div className="ri-aurora__blob ri-aurora__blob--6" />
          <div className="ri-aurora__blob ri-aurora__blob--7" />
          <div className="ri-aurora__blob ri-aurora__blob--8" />
          <div className="ri-aurora__grain" />
        </div>

        <AuthProvider>
          <ResumeProvider>
            <Nav />
            <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-8">{children}</main>
            <footer className="mt-4 border-t border-ri-border/60 py-6 text-center text-xs text-ri-text-mute">
              <span className="ri-gradient-text font-semibold">ReflectInterview</span>
              <span className="mx-2 opacity-40">·</span>
              Adaptive multi-round interview + session report
            </footer>
          </ResumeProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
