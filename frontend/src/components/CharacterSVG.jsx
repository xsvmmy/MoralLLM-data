/**
 * CharacterSVG — SVG silhouettes inspired by the MIT Moral Machine style.
 * viewBox: 0 0 22 48  (portrait, ~22×48 units)
 *
 * Props:
 *   type   — character type string
 *   size   — rendered height in px (width scales proportionally)
 *   fill   — fill/stroke color (default light gray)
 */

import React from 'react';

const VW = 22;
const VH = 48;

function Char({ size = 44, fill = '#e8e8e8', children, overflow = false }) {
  return (
    <svg
      viewBox={`0 0 ${VW} ${VH}`}
      width={(VW / VH) * size}
      height={size}
      style={{ overflow: overflow ? 'visible' : 'hidden', display: 'block' }}
    >
      <g fill={fill} stroke={fill} strokeWidth="0">
        {children}
      </g>
    </svg>
  );
}

// ── Shared body parts ─────────────────────────────────────────────────────────

const Head     = (p = {}) => <circle cx={p.cx ?? 11} cy={p.cy ?? 8}  r={p.r  ?? 7}   />;
const SmHead   = (p = {}) => <circle cx={p.cx ?? 11} cy={p.cy ?? 7}  r={p.r  ?? 5.5} />;
const BodyM    = ()        => <rect   x="4"  y="15" width="14" height="14" rx="2" />;
const BodyF    = ()        => <path   d="M5,15 h12 l3,14 h-18 z" />;
const BodyWide = ()        => <rect   x="2"  y="15" width="18" height="14" rx="3" />;
const BodyBoy  = ()        => <rect   x="5"  y="13" width="12" height="12" rx="2" />;
const BodyGirl = ()        => <path   d="M6,13 h10 l2.5,12 h-15 z" />;
const LegsM    = ()        => <><rect x="4"  y="29" width="5" height="17" rx="2" /><rect x="13" y="29" width="5" height="17" rx="2" /></>;
const LegsWide = ()        => <><rect x="2"  y="29" width="7" height="17" rx="2" /><rect x="13" y="29" width="7" height="17" rx="2" /></>;
const LegsBoy  = ()        => <><rect x="5"  y="25" width="4" height="14" rx="2" /><rect x="13" y="25" width="4" height="14" rx="2" /></>;
const Cane     = ()        => <line   x1="18" y1="23" x2="21" y2="46" stroke="currentFill" strokeWidth="2" strokeLinecap="round" fill="none" />;

// ── Overlay shapes (dark semi-transparent, drawn over body) ───────────────────

const Cross = () => (
  <>
    <rect x="9" y="18" width="4" height="9"  rx="1" fill="rgba(0,0,0,0.45)" stroke="none" />
    <rect x="7" y="21" width="8" height="3.5" rx="1" fill="rgba(0,0,0,0.45)" stroke="none" />
  </>
);

const Tie = () => (
  <path d="M10,15 l1,-2.5 l1,2.5 l1.5,9 l-4,0 z" fill="rgba(0,0,0,0.4)" stroke="none" />
);

const Stripes = () => (
  <>
    <rect x="4" y="17"   width="14" height="2.5" fill="rgba(0,0,0,0.45)" stroke="none" />
    <rect x="4" y="21.5" width="14" height="2.5" fill="rgba(0,0,0,0.45)" stroke="none" />
    <rect x="4" y="26"   width="14" height="2.5" fill="rgba(0,0,0,0.45)" stroke="none" />
  </>
);

// Cane using fill color passed in — rendered as a separate path using stroke
function CaneEl({ fill }) {
  return (
    <line
      x1="18" y1="23" x2="21" y2="46"
      stroke={fill}
      strokeWidth="2.2"
      strokeLinecap="round"
    />
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function CharacterSVG({ type, size = 44, fill = '#e8e8e8' }) {
  switch (type) {

    case 'Man':
      return <Char size={size} fill={fill}><Head /><BodyM /><LegsM /></Char>;

    case 'Woman':
      return <Char size={size} fill={fill}><Head /><BodyF /><LegsM /></Char>;

    case 'Boy':
      return <Char size={size} fill={fill}><SmHead /><BodyBoy /><LegsBoy /></Char>;

    case 'Girl':
      return <Char size={size} fill={fill}><SmHead /><BodyGirl /><LegsBoy /></Char>;

    case 'OldMan':
      return (
        <Char size={size} fill={fill} overflow>
          <Head cy={8} />
          <BodyM />
          <LegsM />
          <CaneEl fill={fill} />
        </Char>
      );

    case 'OldWoman':
      return (
        <Char size={size} fill={fill} overflow>
          <Head cy={8} />
          <BodyF />
          <LegsM />
          <CaneEl fill={fill} />
        </Char>
      );

    case 'Pregnant':
      return (
        <Char size={size} fill={fill}>
          <Head />
          {/* Belly bump */}
          <path d="M4,15 h14 l0,6 q5,5 0,8 l0,0 h-14 z" />
          <LegsM />
        </Char>
      );

    case 'Stroller':
      return (
        <Char size={size} fill={fill}>
          {/* Handle */}
          <path d="M3,15 Q11,10 19,15" stroke={fill} strokeWidth="2.5" fill="none" strokeLinecap="round" />
          {/* Body */}
          <path d="M5,15 l-2,13 h16 l-2,-13 z" />
          {/* Baby */}
          <circle cx="11" cy="21" r="4" />
          {/* Wheels */}
          <circle cx="7"  cy="31" r="3.5" />
          <circle cx="16" cy="31" r="3.5" />
        </Char>
      );

    case 'MaleDoctor':
      return <Char size={size} fill={fill}><Head /><BodyM /><LegsM /><Cross /></Char>;

    case 'FemaleDoctor':
      return <Char size={size} fill={fill}><Head /><BodyF /><LegsM /><Cross /></Char>;

    case 'MaleExecutive':
      return <Char size={size} fill={fill}><Head /><BodyM /><LegsM /><Tie /></Char>;

    case 'FemaleExecutive':
      return <Char size={size} fill={fill}><Head /><BodyF /><LegsM /><Tie /></Char>;

    case 'Criminal':
      return <Char size={size} fill={fill}><Head /><BodyM /><LegsM /><Stripes /></Char>;

    case 'Homeless':
      return (
        <Char size={size} fill={fill}>
          <Head cy={9} />
          {/* Slouched/irregular body */}
          <path d="M5,17 q6,1 12,0 l3,13 q-7,4 -15,0 z" />
          <LegsM />
        </Char>
      );

    case 'LargeMan':
      return <Char size={size} fill={fill}><Head /><BodyWide /><LegsWide /></Char>;

    case 'LargeWoman':
      return (
        <Char size={size} fill={fill}>
          <Head />
          <path d="M3,15 h16 l4,14 h-24 z" />
          <LegsWide />
        </Char>
      );

    case 'MaleAthlete':
      return (
        <Char size={size} fill={fill}>
          <Head />
          <BodyM />
          {/* Running pose — legs splayed */}
          <rect x="4"  y="29" width="5" height="17" rx="2" transform="rotate(-10 6 29)" />
          <rect x="13" y="29" width="5" height="17" rx="2" transform="rotate(10 16 29)" />
        </Char>
      );

    case 'FemaleAthlete':
      return (
        <Char size={size} fill={fill}>
          <Head />
          <BodyF />
          <rect x="4"  y="29" width="5" height="17" rx="2" transform="rotate(-10 6 29)" />
          <rect x="13" y="29" width="5" height="17" rx="2" transform="rotate(10 16 29)" />
        </Char>
      );

    case 'Dog':
      return (
        <Char size={size} fill={fill}>
          {/* Body */}
          <ellipse cx="10" cy="30" rx="9"   ry="6.5" />
          {/* Head */}
          <circle  cx="20" cy="26" r="5.5" />
          {/* Ear */}
          <ellipse cx="22" cy="22" rx="2.5" ry="4" />
          {/* Legs */}
          <rect x="3"  y="35" width="3" height="10" rx="1.5" />
          <rect x="7"  y="35" width="3" height="10" rx="1.5" />
          <rect x="12" y="35" width="3" height="10" rx="1.5" />
          <rect x="16" y="35" width="3" height="10" rx="1.5" />
          {/* Tail */}
          <path d="M2,27 Q-2,19 1,16" stroke={fill} strokeWidth="2.5" fill="none" strokeLinecap="round" />
        </Char>
      );

    case 'Cat':
      return (
        <Char size={size} fill={fill}>
          {/* Body */}
          <ellipse cx="10" cy="33" rx="7.5" ry="5.5" />
          {/* Head */}
          <circle  cx="19" cy="29" r="5" />
          {/* Ears */}
          <polygon points="16,25 14,20 18,23" />
          <polygon points="21,25 23,20 19,23" />
          {/* Legs */}
          <rect x="4"  y="37" width="2.5" height="9" rx="1.5" />
          <rect x="8"  y="37" width="2.5" height="9" rx="1.5" />
          <rect x="13" y="37" width="2.5" height="9" rx="1.5" />
          <rect x="16" y="37" width="2.5" height="9" rx="1.5" />
          {/* Tail */}
          <path d="M3,31 Q-1,22 2,19" stroke={fill} strokeWidth="2" fill="none" strokeLinecap="round" />
        </Char>
      );

    case 'Barricade':
      return (
        <svg
          viewBox={`0 0 ${VW} ${VH}`}
          width={(VW / VH) * size}
          height={size}
          style={{ display: 'block' }}
        >
          {/* Main bar */}
          <rect x="1" y="16" width="20" height="11" rx="2" fill="#f59e0b" />
          {/* Diagonal warning stripes */}
          <line x1="4"  y1="16" x2="8"  y2="27" stroke="rgba(0,0,0,0.5)" strokeWidth="2.5" />
          <line x1="10" y1="16" x2="14" y2="27" stroke="rgba(0,0,0,0.5)" strokeWidth="2.5" />
          <line x1="16" y1="16" x2="20" y2="27" stroke="rgba(0,0,0,0.5)" strokeWidth="2.5" />
          {/* Left post */}
          <rect x="3"  y="27" width="3.5" height="15" rx="1" fill="#d97706" />
          <rect x="1"  y="41" width="7.5" height="4"  rx="1" fill="#d97706" />
          {/* Right post */}
          <rect x="15.5" y="27" width="3.5" height="15" rx="1" fill="#d97706" />
          <rect x="13.5" y="41" width="7.5" height="4"  rx="1" fill="#d97706" />
        </svg>
      );

    default:
      return <Char size={size} fill={fill}><Head /><BodyM /><LegsM /></Char>;
  }
}
