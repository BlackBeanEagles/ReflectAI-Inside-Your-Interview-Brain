"use client";

// Last resort: an error thrown by the root layout itself.
//
// error.tsx cannot catch those, because it renders *inside* the layout that
// failed. This one replaces the document, so it has to supply its own
// <html> and <body> -- and it cannot use the app's components, fonts or
// stylesheet, since a layout failure may well be the reason those are
// unavailable. Hence the inline styles, which is the one place in this
// codebase where they are the correct answer rather than a shortcut.
//
// The colours are the light palette's literal values rather than the CSS
// variables that normally carry them: globals.css is exactly what might not
// have loaded.

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "1.5rem",
          background: "#faf9f6",
          color: "#1c1a17",
          fontFamily:
            "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
        }}
      >
        <div style={{ maxWidth: "26rem" }}>
          <h1 style={{ fontSize: "1.25rem", fontWeight: 600, margin: 0 }}>
            ReflectInterview failed to load
          </h1>
          <p style={{ marginTop: "0.75rem", fontSize: "0.875rem", color: "#6a645a", lineHeight: 1.6 }}>
            Something went wrong before the app could start. Reloading usually fixes it.
          </p>
          {error.digest && (
            <p style={{ marginTop: "0.75rem", fontSize: "0.75rem", color: "#6a645a" }}>
              Reference: {error.digest}
            </p>
          )}
          <button
            type="button"
            onClick={reset}
            style={{
              marginTop: "1.25rem",
              padding: "0.5rem 1rem",
              borderRadius: "0.5rem",
              border: "none",
              background: "#4f46e5",
              color: "#ffffff",
              fontSize: "0.875rem",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Reload
          </button>
        </div>
      </body>
    </html>
  );
}
