// The app's top-level destinations, in one place.
//
// Shared by the header nav and the command palette so the two cannot drift
// apart -- a page reachable from one but not the other is the kind of gap
// nobody notices until someone can't find a feature they already used.

import { BarChart3, FileText, ListChecks, MessagesSquare, Sparkles } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Extra words the palette matches on. "cv" should find the resume page
   *  even though that word appears nowhere in the label. */
  keywords?: string;
};

// Real icons rather than emoji. Emoji render as a different typeface on every
// platform, can't inherit colour or stroke weight, and sit on their own
// baseline -- so a row of them never optically aligns with the labels beside
// them. lucide-react was already a dependency and previously went unused.
export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Interview", icon: MessagesSquare, keywords: "mock practice answer session start" },
  { href: "/resume", label: "Resume", icon: FileText, keywords: "cv analyse parse skills projects" },
  { href: "/ats", label: "ATS Score", icon: ListChecks, keywords: "applicant tracking keywords match job" },
  { href: "/predict", label: "Questions", icon: Sparkles, keywords: "predict prep likely study list" },
  { href: "/history", label: "History", icon: BarChart3, keywords: "past reports progress trend scores" },
];
