import { ImageResponse } from "next/og";

// Generated at build time rather than shipped as a binary asset, so the card
// can't drift out of sync with the product's copy the way a hand-exported PNG
// does. Satori (what ImageResponse runs on) supports a flexbox subset only:
// every element with more than one child needs an explicit display:flex, and
// there is no Tailwind here — inline styles only.

export const alt = "ReflectInterview — practice the interview before it counts";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#101216",
          padding: 80,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div
            style={{
              width: 10,
              height: 10,
              borderRadius: 999,
              background: "#8b9bff",
              display: "flex",
            }}
          />
          <div style={{ fontSize: 26, color: "#98a0ae", letterSpacing: 2 }}>
            REFLECTINTERVIEW
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div
            style={{
              fontSize: 82,
              lineHeight: 1.05,
              color: "#e8eaf0",
              letterSpacing: -2.5,
              maxWidth: 900,
              display: "flex",
            }}
          >
            Practice the interview before it counts.
          </div>
          <div style={{ fontSize: 30, color: "#98a0ae", marginTop: 28, maxWidth: 820, display: "flex" }}>
            An adaptive mock interview built from your own resume — scored, with
            specific feedback on every answer.
          </div>
        </div>

        {/* The three rounds, in their real colours: the same escalation the
            product uses, so the card previews the actual thing. */}
        <div style={{ display: "flex", alignItems: "center", gap: 40 }}>
          {[
            { label: "HR round", color: "#8b9bff" },
            { label: "Technical round", color: "#e08b3c" },
            { label: "Stress round", color: "#f07185" },
          ].map((r) => (
            <div key={r.label} style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{ width: 34, height: 3, borderRadius: 999, background: r.color, display: "flex" }}
              />
              <div style={{ fontSize: 25, color: "#98a0ae" }}>{r.label}</div>
            </div>
          ))}
        </div>
      </div>
    ),
    size,
  );
}
