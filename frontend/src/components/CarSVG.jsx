/**
 * CarSVG — top-down view of the autonomous vehicle.
 * Front of the car faces DOWN (matching the road direction).
 *
 * Props:
 *   width     — rendered width in px (height scales proportionally)
 *   harmed    — if true, tints the car red (barrier collision)
 *   passengers — array of character type strings shown inside
 */

import React from 'react';
import CharacterSVG from './CharacterSVG';

export default function CarSVG({ width = 52, harmed = false }) {
  const h = Math.round(width * 90 / 52);
  const bodyColor = harmed ? '#991b1b' : '#1d4ed8';
  const glassColor = harmed ? '#fca5a5' : '#bfdbfe';

  return (
    <svg
      viewBox="0 0 52 90"
      width={width}
      height={h}
      style={{ display: 'block', filter: harmed ? 'drop-shadow(0 0 8px rgba(239,68,68,0.8))' : 'drop-shadow(0 4px 10px rgba(0,0,0,0.6))' }}
    >
      {/* ── Car body ── */}
      <rect x="5" y="4" width="42" height="82" rx="11" fill={bodyColor} />

      {/* ── Roof panel (slightly lighter) ── */}
      <rect x="11" y="20" width="30" height="46" rx="5" fill={harmed ? '#b91c1c' : '#2563eb'} />

      {/* ── Rear window (top = rear since car moves downward) ── */}
      <rect x="12" y="7"  width="28" height="15" rx="4" fill={glassColor} opacity="0.55" />

      {/* ── Front windshield (bottom = front) ── */}
      <rect x="11" y="62" width="30" height="18" rx="4" fill={glassColor} opacity="0.85" />

      {/* ── Center console line ── */}
      <line x1="26" y1="24" x2="26" y2="60" stroke="rgba(255,255,255,0.15)" strokeWidth="2" />

      {/* ── Rear wheels ── */}
      <rect x="0"  y="9"  width="7" height="16" rx="3" fill="#111827" />
      <rect x="45" y="9"  width="7" height="16" rx="3" fill="#111827" />

      {/* ── Front wheels ── */}
      <rect x="0"  y="65" width="7" height="16" rx="3" fill="#111827" />
      <rect x="45" y="65" width="7" height="16" rx="3" fill="#111827" />

      {/* ── Headlights (front = bottom) ── */}
      <rect x="10" y="78" width="12" height="6" rx="2" fill="#fef9c3" opacity="0.95" />
      <rect x="30" y="78" width="12" height="6" rx="2" fill="#fef9c3" opacity="0.95" />

      {/* ── Taillights (rear = top) ── */}
      <rect x="10" y="5"  width="10" height="4" rx="1.5" fill="#fca5a5" opacity="0.8" />
      <rect x="32" y="5"  width="10" height="4" rx="1.5" fill="#fca5a5" opacity="0.8" />

      {/* ── AV badge ── */}
      <rect x="16" y="37" width="20" height="10" rx="3" fill="rgba(255,255,255,0.12)" />
      <text
        x="26" y="46"
        textAnchor="middle"
        fontSize="7"
        fontWeight="bold"
        fill="rgba(255,255,255,0.7)"
        fontFamily="sans-serif"
        letterSpacing="1"
      >AV</text>
    </svg>
  );
}
