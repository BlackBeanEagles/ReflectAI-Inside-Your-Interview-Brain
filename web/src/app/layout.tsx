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

const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://reflect-ai-inside-your-interview-br.vercel.app";

const DESCRIPTION =
  "An adaptive AI mock interview built from your own resume: HR warm-up, technical questions drawn from your projects, and a stress round if your scores dip. Every answer scored, with specific feedback.";

export const metadata: Metadata = {
  // metadataBase is what lets Next resolve the generated opengraph-image to an
  // absolute URL. Without it the card silently ships a relative path, which
  // every scraper ignores -- so the link previews as a bare URL.
  metadataBase: new URL(SITE_URL),
  title: "ReflectInterview — Practice the interview before it counts",
  description: DESCRIPTION,
  openGraph: {
    type: "website",
    siteName: "ReflectInterview",
    url: SITE_URL,
    title: "ReflectInterview — Practice the interview before it counts",
    description: DESCRIPTION,
  },
  twitter: {
    card: "summary_large_image",
    title: "ReflectInterview — Practice the interview before it counts",
    description: DESCRIPTION,
  },
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
