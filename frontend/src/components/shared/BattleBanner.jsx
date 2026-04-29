import "./BattleBanner.css";

export default function BattleBanner({ pageName = "Knowledge Base" }) {
  return (
    <div className="battle-banner" aria-hidden="true">
      <div className="battle-banner__scan" />

      <svg
        className="battle-banner__svg"
        viewBox="0 0 1200 180"
        preserveAspectRatio="none"
      >
        <defs>
          <filter
            id="battle-green-glow"
            x="-50%"
            y="-50%"
            width="200%"
            height="200%"
          >
            <feGaussianBlur stdDeviation="2.2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          <filter
            id="battle-gold-glow"
            x="-50%"
            y="-50%"
            width="200%"
            height="200%"
          >
            <feGaussianBlur stdDeviation="2.8" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <text x="50%" y="32" textAnchor="middle" className="battle-banner__label">
            {pageName}
        </text>

        

        <line className="battle-banner__ground" x1="0" y1="145" x2="1200" y2="145" />
        <line
            className="battle-banner__ground-glow"
            x1="0"
            y1="145"
            x2="1200"
            y2="145"
        />

        {/* Left tank group */}
        <g className="battle-banner__tank-group">
          <g className="battle-banner__tank">
            <rect x="110" y="108" width="122" height="22" rx="4" className="battle-banner__tank-body" />
            <rect x="138" y="93" width="54" height="18" rx="4" className="battle-banner__tank-turret" />
            <line x1="189" y1="101" x2="260" y2="96" className="battle-banner__tank-barrel" />

            <circle cx="132" cy="132" r="7" className="battle-banner__tank-wheel" />
            <circle cx="160" cy="132" r="7" className="battle-banner__tank-wheel" />
            <circle cx="188" cy="132" r="7" className="battle-banner__tank-wheel" />
            <circle cx="216" cy="132" r="7" className="battle-banner__tank-wheel" />

            <line x1="118" y1="132" x2="228" y2="132" className="battle-banner__tank-track" />

            <circle cx="265" cy="96" r="6" className="battle-banner__tank-flash" />
        </g>

          {/* Friendly infantry */}
          <g className="battle-banner__soldier battle-banner__soldier--friendly">
            {/* head + helmet */}
            <circle cx="312" cy="96" r="7" className="battle-banner__body" />
            <path
                className="battle-banner__helmet"
                d="M305 92 Q312 86 319 92"
             />

            {/* torso */}
            <line x1="312" y1="103" x2="312" y2="126" className="battle-banner__body" />

            {/* back arm */}
            <line x1="312" y1="110" x2="324" y2="114" className="battle-banner__body" />
            <line x1="324" y1="114" x2="334" y2="112" className="battle-banner__body" />

            {/* front arm / support hand */}
            <line x1="312" y1="108" x2="325" y2="104" className="battle-banner__body" />
            <line x1="325" y1="104" x2="342" y2="103" className="battle-banner__body" />

            {/* legs */}
            <line x1="312" y1="126" x2="300" y2="145" className="battle-banner__body" />
            <line x1="312" y1="126" x2="325" y2="145" className="battle-banner__body" />

             {/* rifle */}
            <polyline
                points="330,112 340,108 356,107 372,104"
                className="battle-banner__rifle"
            />
            <line x1="337" y1="110" x2="341" y2="116" className="battle-banner__rifle-detail" />
            <line x1="345" y1="108" x2="351" y2="108" className="battle-banner__rifle-detail" />
            <line x1="329" y1="112" x2="324" y2="116" className="battle-banner__rifle-stock" />
            <circle cx="372" cy="104" r="3.6" className="battle-banner__muzzle battle-banner__muzzle--friendly" />
        </g>
    </g>
        {/* Enemy */}
        <g className="battle-banner__soldier battle-banner__soldier--enemy">
            {/* head + helmet */}
            <circle cx="970" cy="94" r="7" className="battle-banner__body" />
            <path
                className="battle-banner__helmet"
                d="M963 90 Q970 84 977 90"
            />

            {/* torso */}
            <line x1="970" y1="101" x2="970" y2="125" className="battle-banner__body" />

            {/* back arm */}
            <line x1="970" y1="109" x2="958" y2="113" className="battle-banner__body" />
            <line x1="958" y1="113" x2="948" y2="111" className="battle-banner__body" />

             {/* front arm / support hand */}
            <line x1="970" y1="107" x2="957" y2="103" className="battle-banner__body" />
            <line x1="957" y1="103" x2="940" y2="102" className="battle-banner__body" />

            {/* legs */}
            <line x1="970" y1="125" x2="957" y2="145" className="battle-banner__body" />
            <line x1="970" y1="125" x2="983" y2="145" className="battle-banner__body" />

            {/* rifle */}
            <polyline
                points="952,111 942,107 926,106 910,103"
                className="battle-banner__rifle"
            />
            <line x1="945" y1="109" x2="941" y2="115" className="battle-banner__rifle-detail" />
            <line x1="937" y1="107" x2="931" y2="107" className="battle-banner__rifle-detail" />
            <line x1="953" y1="111" x2="958" y2="115" className="battle-banner__rifle-stock" />
            <circle cx="910" cy="103" r="3.6" className="battle-banner__muzzle battle-banner__muzzle--enemy" />
        </g>

        

        {/* Actual moving bullets */}
        <circle cx="266" cy="96" r="2.8" className="battle-banner__bullet battle-banner__bullet--tank" />
        <circle cx="362" cy="103" r="2.6" className="battle-banner__bullet battle-banner__bullet--friendly" />
        <circle cx="914" cy="101" r="2.6" className="battle-banner__bullet battle-banner__bullet--enemy" />

        {/* Impact / explosion */}
        <g className="battle-banner__explosion-group">
          <circle cx="858" cy="105" r="7" className="battle-banner__impact-core" />
          <circle cx="858" cy="105" r="16" className="battle-banner__impact-ring" />
          <circle cx="844" cy="96" r="3" className="battle-banner__debris battle-banner__debris--a" />
          <circle cx="874" cy="94" r="3" className="battle-banner__debris battle-banner__debris--b" />
          <circle cx="842" cy="118" r="3" className="battle-banner__debris battle-banner__debris--c" />
          <circle cx="877" cy="119" r="3" className="battle-banner__debris battle-banner__debris--d" />
        </g>
      </svg>
    </div>
  );
}