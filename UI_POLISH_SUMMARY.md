# GeoTrace Forensics X 12.5.0-ui-polish

Applied UI-focused improvements for the Review workspace:
- larger preview stage and calmer control rows
- wider decision rail with reduced text density
- simpler evidence cards with cleaner badges
- semantic action-button coloring and softer hover states
- stronger selected-card styling and lighter chrome
- concise confidence / verdict / next-step text to reduce nested scrolling
- semantic score-breakdown badges

No external UI library was bundled in this build to avoid introducing Windows runtime instability. The polish is implemented with PyQt5 plus refreshed styling.
