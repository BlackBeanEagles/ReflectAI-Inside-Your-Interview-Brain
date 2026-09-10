import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { ResumeProvider } from "@/lib/resume-context";
import Nav from "@/components/Nav";
import ServiceWorker from "@/components/ServiceWorker";
import { Grain } from "@/components/Ambience";

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
  icons: {
    icon: [
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" }],
  },
  appleWebApp: {
    capable: true,
    title: "ReflectInterview",
    // "default" keeps the iOS status bar legible against the light ground;
    // "black-translucent" would put dark text on the paper background.
    statusBarStyle: "default",
  },
  twitter: {
    card: "summary_large_image",
    title: "ReflectInterview — Practice the interview before it counts",
    description: DESCRIPTION,
  },
};

// themeColor lives on `viewport`, not `metadata` -- Next warns and drops it
// if it is put on the latter. This is what paints the Android status bar and
// the browser chrome once the app is installed.
export const viewport: Viewport = {
  themeColor: "#faf9f6",
  colorScheme: "light",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <Grain />
        <ServiceWorker />
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
