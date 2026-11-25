import type { ReactElement, SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;

function base(props: P, children: ReactElement | ReactElement[]) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  );
}

export const Check = (p: P) => base(p, <path d="M5 12.5l4.5 4.5L19 7.5" />);
export const Close = (p: P) => base(p, <path d="M6 6l12 12M18 6L6 18" />);
export const Menu = (p: P) => base(p, <path d="M4 7h16M4 12h16M4 17h16" />);
export const Arrow = (p: P) => base(p, <path d="M5 12h14M13 6l6 6-6 6" />);
export const Back = (p: P) => base(p, <path d="M19 12H5M11 6l-6 6 6 6" />);
export const Compass = (p: P) =>
  base(p, [<circle key="a" cx="12" cy="12" r="9" />, <path key="b" d="M15.5 8.5l-2 5-5 2 2-5z" />]);
export const Route = (p: P) =>
  base(p, [<circle key="a" cx="6" cy="18" r="2" />, <circle key="b" cx="18" cy="6" r="2" />, <path key="c" d="M8 18h6a3 3 0 000-6h-4a3 3 0 010-6h6" />]);
export const Wallet = (p: P) =>
  base(p, [<path key="a" d="M4 7a2 2 0 012-2h11v4" />, <rect key="b" x="4" y="7" width="16" height="12" rx="2" />, <circle key="c" cx="16" cy="13" r="1" />]);
export const Sliders = (p: P) =>
  base(p, [<path key="a" d="M5 6h9M18 6h1M5 12h3M12 12h7M5 18h11M20 18h-1" />, <circle key="b" cx="16" cy="6" r="2" />, <circle key="c" cx="10" cy="12" r="2" />, <circle key="d" cx="18" cy="18" r="2" />]);
export const User = (p: P) => base(p, [<circle key="a" cx="12" cy="8" r="3.5" />, <path key="b" d="M5 20c1-4 4-6 7-6s6 2 7 6" />]);
export const Users = (p: P) =>
  base(p, [<circle key="a" cx="9" cy="8" r="3" />, <path key="b" d="M3 19c.8-3.4 3.2-5 6-5s5.2 1.6 6 5" />, <circle key="c" cx="17" cy="9" r="2.5" />, <path key="d" d="M16.5 14c2.4.2 4 1.7 4.5 4" />]);
export const Heart = (p: P) => base(p, <path d="M12 20s-7-4.4-7-10a4 4 0 017-2.6A4 4 0 0119 10c0 5.6-7 10-7 10z" />);
export const Family = (p: P) =>
  base(p, [<circle key="a" cx="8" cy="7" r="2.5" />, <circle key="b" cx="16" cy="7" r="2.5" />, <circle key="c" cx="12" cy="14" r="2" />, <path key="d" d="M4 20c.5-3 2-4.5 4-4.5M20 20c-.5-3-2-4.5-4-4.5M9 21c.3-2 1.4-3 3-3s2.7 1 3 3" />]);
export const Group = (p: P) =>
  base(p, [<circle key="a" cx="6" cy="9" r="2" />, <circle key="b" cx="12" cy="7" r="2.5" />, <circle key="c" cx="18" cy="9" r="2" />, <path key="d" d="M2 19c.4-2.6 2-4 4-4M8 20c.5-3 2-5 4-5s3.5 2 4 5M22 19c-.4-2.6-2-4-4-4" />]);
export const Walk = (p: P) =>
  base(p, [<circle key="a" cx="13" cy="4.5" r="1.5" />, <path key="b" d="M10 21l2-6-2-3 1-4 3 1 2 3M8 12l2-3M13 15l2 6" />]);
export const Transit = (p: P) =>
  base(p, [<rect key="a" x="5" y="4" width="14" height="13" rx="3" />, <path key="b" d="M5 11h14M8 20l1.5-3M16 20l-1.5-3" />, <circle key="c" cx="9" cy="14" r=".6" />, <circle key="d" cx="15" cy="14" r=".6" />]);
export const Download = (p: P) => base(p, <path d="M12 4v11m0 0l-4-4m4 4l4-4M5 20h14" />);
export const Pin = (p: P) =>
  base(p, [<path key="a" d="M12 21s-6-5.2-6-10a6 6 0 0112 0c0 4.8-6 10-6 10z" />, <circle key="b" cx="12" cy="11" r="2" />]);
export const Spark = (p: P) => base(p, <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM18 16l.8 2.2L21 19l-2.2.8L18 22l-.8-2.2L15 19l2.2-.8z" />);
export const Plane = (p: P) => base(p, <path d="M3 13l18-8-6 15-3-6z M12 14l9-9" />);
export const Mic = (p: P) =>
  base(p, [<path key="a" d="M12 3a3 3 0 00-3 3v6a3 3 0 006 0V6a3 3 0 00-3-3z" />, <path key="b" d="M6 11a6 6 0 0012 0M12 17v4" />]);
