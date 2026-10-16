/**
 * CrossingSignalSVG — pedestrian crossing signal box, MIT Moral Machine style.
 *
 * Props:
 *   state  — 'green' | 'red' | 'none'
 *   height — rendered height in px (width scales proportionally)
 */

import React from 'react';

// viewBox: 0 0 28 52  (housing + post)
export default function CrossingSignalSVG({ state = 'none', height = 72 }) {
  const width = Math.round(height * 28 / 52);

  const isGreen = state === 'green';
  const isRed   = state === 'red';
  const isOff   = state === 'none';

  // Housing background
  const housingFill  = isOff ? '#1a1a1a' : '#111111';
  const housingBorder = isOff ? '#333' : '#222';

  // Active glow color
  const glowColor = isGreen ? 'rgba(34,197,94,0.45)' : isRed ? 'rgba(239,68,68,0.45)' : 'none';

  // Figure colors
  const greenFig  = isGreen ? '#22c55e' : '#1a3a1a';
  const redFig    = isRed   ? '#ef4444' : '#3a1a1a';

  return (
    <svg
      viewBox="0 0 28 52"
      width={width}
      height={height}
      style={{ display: 'block', overflow: 'visible' }}
    >
      {/* Post */}
      <rect x="12.5" y="38" width="3" height="14" rx="1.5" fill="#555" />
      <rect x="10"  y="50" width="8"  height="2"  rx="1"   fill="#444" />

      {/* Housing glow (active state only) */}
      {!isOff && (
        <rect x="1" y="1" width="26" height="38" rx="4"
          fill={glowColor}
          style={{ filter: `blur(4px)` }}
        />
      )}

      {/* Housing box */}
      <rect x="1" y="1" width="26" height="38" rx="4"
        fill={housingFill} stroke={housingBorder} strokeWidth="1.5"
      />

      {/* ── Green panel: walking figure ── */}
      {/* Head */}
      <circle cx="14" cy="8" r="3" fill={greenFig} />
      {/* Body */}
      <rect x="12" y="12" width="4" height="7" rx="1" fill={greenFig} />
      {/* Left arm (swinging forward) */}
      <line x1="12" y1="14" x2="7"  y2="17" stroke={greenFig} strokeWidth="2" strokeLinecap="round" />
      {/* Right arm (swinging back) */}
      <line x1="16" y1="14" x2="21" y2="12" stroke={greenFig} strokeWidth="2" strokeLinecap="round" />
      {/* Left leg (stride) */}
      <line x1="13" y1="19" x2="9"  y2="26" stroke={greenFig} strokeWidth="2" strokeLinecap="round" />
      {/* Right leg (stride) */}
      <line x1="15" y1="19" x2="19" y2="26" stroke={greenFig} strokeWidth="2" strokeLinecap="round" />

      {/* ── Red panel: standing/hand-raised figure ── */}
      {/* Head */}
      <circle cx="14" cy="28" r="3" fill={redFig} />
      {/* Body */}
      <rect x="12" y="32" width="4" height="7" rx="1" fill={redFig} />
      {/* Arms raised out (stop gesture) */}
      <line x1="12" y1="34" x2="7"  y2="31" stroke={redFig} strokeWidth="2" strokeLinecap="round" />
      <line x1="16" y1="34" x2="21" y2="31" stroke={redFig} strokeWidth="2" strokeLinecap="round" />
      {/* Legs together */}
      <line x1="13" y1="39" x2="11" y2="46" stroke={redFig} strokeWidth="2" strokeLinecap="round" />
      <line x1="15" y1="39" x2="17" y2="46" stroke={redFig} strokeWidth="2" strokeLinecap="round" />

      {/* Divider between green and red panels */}
      <line x1="3" y1="21" x2="25" y2="21" stroke="#222" strokeWidth="1" />

      {/* Active-panel highlight border */}
      {isGreen && (
        <rect x="2" y="2" width="24" height="19" rx="3"
          fill="none" stroke="#22c55e" strokeWidth="1.5" opacity="0.7"
        />
      )}
      {isRed && (
        <rect x="2" y="21" width="24" height="17" rx="3"
          fill="none" stroke="#ef4444" strokeWidth="1.5" opacity="0.7"
        />
      )}
    </svg>
  );
}
