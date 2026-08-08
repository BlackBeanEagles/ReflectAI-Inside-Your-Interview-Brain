import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
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
        <AuthProvider>
          <Nav />
          <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-8">{children}</main>
          <footer className="border-t border-ri-border py-6 text-center text-xs text-ri-text-mute">
            ReflectInterview · Adaptive multi-round interview + session report
          </footer>
        </AuthProvider>
      </body>
    </html>
  );
}
