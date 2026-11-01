# DataTrace UI design system

DataTrace is an operational data-quality workspace. Its UI makes the evidence returned by the backend easy to scan and keeps unsupported operations visibly unavailable.

## Visual foundation

- **Navigation:** dark navy rail at desktop widths, with an accessible collapsed icon rail; small screens open a grouped navigation panel from the header.
- **Workspace:** cool blue-gray canvas with crisp white cards, clear borders and compact tabular typography.
- **Accent:** vivid indigo marks primary actions and selected controls; emerald marks accepted/published data. Cobalt, amber, coral and violet keep distinct informational, warning, failure and secondary meanings.
- **Typography:** system-first sans serif with a monospace stack for run IDs, checksums and rule codes. No remote fonts are loaded.
- **Themes:** shared semantic CSS variables support light and dark modes; the choice is saved under the versioned `datatrace-theme-v1` key.
- **Spacing and color values:** see [`design-tokens.json`](./design-tokens.json).

## Component patterns

- Page headers provide a clear title, context and one primary action.
- Status badges use text and color together; color is never the only status signal.
- Cards and metric values are populated from API responses. Missing data uses an explicit empty, loading or error state.
- Tables retain semantic captions and header scopes. On narrow screens, the table region scrolls independently and has an accessible name.
- Dashboard metrics and charts summarize run records returned by the API. The stacked area view and status ring respond to a 24-hour, 7-day, or 30-day filter within the latest 100 returned records; no score or historical comparison is invented.
- Source registry search, sorting, and paging apply to registered sources returned by the API. The schema inspector shows the server-returned column names and file identity; it does not imply row preview, column mapping, or geometry checks.
- Error callouts describe the failed request/action and expose a retry control when retrying the request is safe.
- Unsupported areas explain the backend capability gap rather than showing sample data or nonfunctional controls.

## Interaction and accessibility

- Every interactive element has a visible keyboard focus indicator. A skip link reaches the main landmark, and the page title is announced when the route changes.
- File selection is labeled, keyboard accessible and limited locally to `.csv` filenames; the backend validates file contents.
- Tables, navigation, headings and state messages use semantic landmarks and roles. Table pagination is a named navigation landmark.
- Motion is limited to small state transitions and spinners; `prefers-reduced-motion` is honored.
- Responsive layouts are checked at desktop, tablet and phone widths. Dense evidence remains inspectable through horizontal scrolling instead of being hidden.

## Library choices

Lucide React supplies the icon set. The chart is a compact inline SVG to keep the production bundle small. A pipeline graph editor, charting framework and table abstraction are deferred until persisted backend contracts and data volume justify them. See [`docs/design_decisions.md`](../docs/design_decisions.md) for the measured bundle comparison and product constraints.
