"use client";

// Score-trend line chart for the history dashboard.
//
// Colour note: the three round series deliberately do NOT reuse the round
// accent colours the rest of the UI uses (iris / orange / crimson). Those are
// chosen to look good as badges and glows; as adjacent lines they fail
// colourblind separation outright (orange vs crimson is ΔE 5.9 under
// deuteranopia, against a target of >= 8) and neither clears 3:1 contrast on a
// white plot surface. --ri-series-* are the re-stepped values that pass, with
// separate steps for dark mode rather than a lightened flip.
//
// Dash patterns are secondary encoding, not decoration: the dark-mode steps
// land in the 6-8 CVD band, which is only legal when something other than hue
// also separates the series.
//
// isAnimationActive={false} is deliberate. Recharts draws each line in by
// animating stroke-dasharray from rAF, and rAF is throttled in a tab that
// isn't painting -- so opening this page in a background tab (a middle-click
// from anywhere) and returning to it leaves the lines frozen part-drawn, with
// no recovery on visibility change. Observed directly during review: all four
// curves stuck at ~17% with a 178px/887px dasharray. A six-point trend loses
// nothing by appearing at once.

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type ScoreTrendPoint = {
  index: number;
  Overall: number | null;
  HR: number | null;
  Technical: number | null;
  Stress: number | null;
};

export default function ScoreTrendChart({ data }: { data: ScoreTrendPoint[] }) {
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
          {/* Grid and axes stay recessive -- they orient, they don't compete
              with the data. */}
          <CartesianGrid strokeDasharray="3 3" stroke="var(--ri-border)" vertical={false} />
          <XAxis
            dataKey="index"
            stroke="var(--ri-border)"
            tick={{ fill: "var(--ri-text-mute)", fontSize: 12 }}
            tickLine={false}
          />
          <YAxis
            domain={[0, 10]}
            ticks={[0, 2, 4, 6, 8, 10]}
            stroke="var(--ri-border)"
            tick={{ fill: "var(--ri-text-mute)", fontSize: 12 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            cursor={{ stroke: "var(--ri-text-mute)", strokeDasharray: "3 3" }}
            contentStyle={{
              background: "var(--ri-surface)",
              border: "1px solid var(--ri-border)",
              borderRadius: 12,
              boxShadow: "var(--ri-card-shadow)",
              fontSize: 12,
            }}
            labelStyle={{ color: "var(--ri-text-mute)" }}
          />
          {/* Four series previously shipped with no legend at all -- identity
              was carried by hue alone, with nothing naming the hues. */}
          <Legend
            verticalAlign="top"
            align="left"
            height={30}
            iconType="plainline"
            wrapperStyle={{ fontSize: 12, color: "var(--ri-text-mute)" }}
          />
          {/* Overall is the aggregate of the other three, so it's the emphasis
              mark in ink rather than a fourth hue competing with its own
              components. */}
          <Line
            type="monotone"
            isAnimationActive={false}
            dataKey="Overall"
            stroke="var(--ri-text)"
            strokeWidth={2.5}
            dot={{ r: 3, strokeWidth: 0, fill: "var(--ri-text)" }}
            activeDot={{ r: 5 }}
          />
          <Line
            type="monotone"
            isAnimationActive={false}
            dataKey="HR"
            stroke="var(--ri-series-hr)"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
          <Line
            type="monotone"
            isAnimationActive={false}
            dataKey="Technical"
            stroke="var(--ri-series-tech)"
            strokeWidth={2}
            strokeDasharray="6 3"
            dot={false}
            activeDot={{ r: 4 }}
          />
          <Line
            type="monotone"
            isAnimationActive={false}
            dataKey="Stress"
            stroke="var(--ri-series-stress)"
            strokeWidth={2}
            strokeDasharray="2 3"
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
