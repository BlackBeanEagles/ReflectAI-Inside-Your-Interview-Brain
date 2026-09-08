import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { ResumeProvider } from "@/lib/resume-context";
import Nav from "@/components/Nav";

// No `weight` array on purpose: that loads static instances, and the type
// scale here uses intermediate weights (640, 680) that would otherwise snap
// to 700. Omitting it gives the variable font, where those render exactly.
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ReflectInterview — Practice the interview before it counts",
  description:
    "AI mock interviews with adaptive difficulty, voice input, and behavioural feedback.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <AuthProvider>
          <ResumeProvider>
            <Nav />
            <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10 sm:px-6">{children}</main>
            <footer className="mt-8 border-t border-ri-border py-6 text-center text-xs text-ri-text-mute">
              Adaptive multi-round interview and session report
            </footer>
          </ResumeProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
