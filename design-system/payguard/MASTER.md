# PayGuard interface

PayGuard is a transaction firewall for AI agents. The interface helps hackathon
judges and developers inspect the same payment proposal with and without the
firewall, then understand the policy decision and its audit trail.

## Visual direction

A dark security console with light glassmorphism: a deep indigo canvas carrying
soft blue and violet glows, translucent glass panels for every transaction
surface, and a gradient protection path connecting the agent to PayPal. The
brand mark is a gradient shield with a glass core, a white P monogram and a
mint verification tick. Decisions use explicit words and icons as well as
color. No invented activity or results.

| Token | Value | Purpose |
| --- | --- | --- |
| Canvas | #0A0F2C | Main workspace, deep indigo with fixed radial glows |
| Glass | rgba(255,255,255,.05–.075) | Cards, panels, sidebar, blurred 10–18px |
| Border | rgba(255,255,255,.09–.16) | Hairline edges on glass surfaces |
| Blue | #5E8BFF | Primary actions, protection path, keyboard focus |
| Violet | #7C5CFF | Gradient end, agent accents |
| Teal | #34D399 | Authorized and protected states |
| Red | #FB7185 | Blocked and unsafe states |
| Amber | #FBBF24 | Approval required, untrusted sources |
| Text | #E8EEFC / #9AA8C8 | Primary text / muted text |

The brand gradient (135°, #3E7BFA → #5E8BFF → #7C5CFF) is reserved for the
logo, the primary button and the active navigation pill; status colors stay
translucent and never compete with it.

Typography: locally bundled Ubuntu Sans, a humanist family with open forms and
distinctive headings. One family keeps the workspace coherent. Use tabular
figures for amounts and events; monospace only for inspectable identifiers.
Spacing follows an 8px base. Inputs have at least a 44px touch target. Glass
borders group data; shadows only separate floating controls. No animated
status loops.

## Layout

```text
Desktop
┌────────────────┬─────────────────────────────────────────────┐
│ PayGuard       │ Workspace                    Environment     │
│ Section links  │ Purpose                       Protection path│
│                │ Policy facts, derived from configuration     │
│ Scenario       │ Selected scenario                 Run action │
│ Agent / target │ Trusted request        External document     │
│ Test settings  │ Direct execution       Protected execution   │
│ Policy note    │ Activity / audit                             │
└────────────────┴─────────────────────────────────────────────┘

Mobile: collapsible navigation; single-column workspace; stacked source and
result panels; audit table scrolls within its own labeled region.
```

All prose and transaction content is left-aligned. The central protection path
is the one distinctive graphic. Main sections are reachable by anchor links.
Scenario selection is reflected in the URL. Long documents and identifiers
wrap, while result payloads and policy rules use progressive disclosure.

## Review against the brief

The financial-dashboard reference confirms contrast and auditability needs; its
sales-page structure and pure-OLED palette do not fit a demo console. The final
design keeps the scenario and its two execution paths as the centerpiece, on a
dark glass canvas that stays readable: panels stay translucent (never pitch
black), text keeps AAA-scale contrast on the indigo base, and blue is reserved
for PayGuard and actions while teal, red and amber identify actual outcomes.
Animation answers interaction, rather than decorating every panel. Existing
policy, confirmation and replay behavior remain the source of truth.

## Delivery checks

Check initial, blocked, pending, approved, refused and replay states. Verify long
content, mobile navigation, keyboard focus, reduced motion, HTML escaping and
empty/corrupt audit entries. Run existing Streamlit interaction tests and the
security evaluation. Inspect the actual rendered interface on desktop and mobile.

Verified on 10 November 2026:
- 148 automated tests passed; all 13 scripted security scenarios matched policy.
- Chrome review of pending, approved, refused, blocked and reused-result states
  on the local simulator. Sensitive replay still requires approval before reuse.
- No page overflow at 1440px, 375px, 812px landscape, or 200% text size.
- Mobile sidebar opens and closes; keyboard focus is visible; reduced motion
  disables smooth scrolling and interface transitions.
- Escaped transaction and audit content, invalid audit entries and UTC dates
  checked directly. Real PayPal and LLM calls were not part of the browser review.
