/** Speech-bubble mark with a waveform, the "vaani" wordmark and its Devanagari name. */
export default function Logo() {
  return (
    <span className="logo">
      <svg className="logo-mark" viewBox="0 0 32 32" aria-hidden focusable="false">
        <path d="M16 2C8.27 2 2 7.82 2 15c0 3.63 1.6 6.9 4.18 9.26L5 30l6.06-2.9c1.55.5 3.21.9 4.94.9 7.73 0 14-5.82 14-13S23.73 2 16 2z" className="logo-bubble" />
        <g className="logo-bars">
          <rect x="8.5" y="12.5" width="2.4" height="5" rx="1.2" />
          <rect x="12.6" y="9.5" width="2.4" height="11" rx="1.2" />
          <rect x="16.7" y="7.5" width="2.4" height="15" rx="1.2" />
          <rect x="20.8" y="11" width="2.4" height="8" rx="1.2" />
        </g>
      </svg>
      <span className="logo-text">
        <span className="logo-word">vaani</span>
        <span className="logo-native" lang="hi">
          वाणी
        </span>
      </span>
    </span>
  );
}
