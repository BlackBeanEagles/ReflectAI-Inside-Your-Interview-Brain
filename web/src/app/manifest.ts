import type { MetadataRoute } from "next";

// A real web app manifest, which is the prerequisite for everything else:
// installability on Android/desktop, and the Trusted Web Activity that a Play
// Store listing would wrap. Bubblewrap reads this file to generate the Android
// project, so the values here become the app's identity on the device.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "ReflectInterview — AI mock interviews",
    short_name: "ReflectInterview",
    description:
      "An adaptive AI mock interview built from your own resume: HR warm-up, technical questions drawn from your projects, and a stress round if your scores dip. Every answer scored, with specific feedback.",
    id: "/",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#faf9f6",
    theme_color: "#faf9f6",
    categories: ["education", "productivity", "business"],
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      // Separate maskable entries, not `purpose: "any maskable"` on the same
      // file. Android crops adaptive icons to a circle/squircle and shaves
      // anything outside the inner ~80%, so a single icon serving both roles
      // comes out clipped in the launcher. These are drawn with the mark
      // pulled into the safe zone and the background bled to the full square.
      { src: "/icon-maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Start an interview", url: "/" },
      { name: "ATS score", url: "/ats" },
      { name: "History", url: "/history" },
    ],
  };
}
