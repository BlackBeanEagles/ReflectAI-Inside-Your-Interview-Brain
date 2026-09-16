import Link from "next/link";
import { Card } from "@/components/ui";
import { NAV_ITEMS } from "@/lib/nav-items";

// A 404 that offers somewhere to go. Reached by mistyped URLs and by stale
// links -- including the installed PWA's own shortcuts if a route is ever
// renamed, which is the case where a dead end is least forgivable because
// there is no browser address bar to recover from.

export const metadata = { title: "Page not found — ReflectInterview" };

export default function NotFound() {
  return (
    <div className="ri-enter mx-auto max-w-lg pt-6">
      <Card>
        <h1 className="ri-title text-xl">That page doesn&apos;t exist</h1>
        <p className="ri-prose mt-2 text-sm text-ri-text-mute">
          The link may be out of date. Everything the app does is one of these:
        </p>
        <ul className="mt-4 space-y-1">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
            <li key={href}>
              <Link
                href={href}
                className="ri-focus flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-ri-text-mute transition-colors hover:bg-ri-surface-alt hover:text-ri-text"
              >
                <Icon size={15} strokeWidth={1.75} aria-hidden />
                {label}
              </Link>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
