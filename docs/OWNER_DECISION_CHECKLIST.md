# Owner decision checklist

The development workflows are implemented with safe disabled states. Production activation now depends on the decisions below. Approve exact values or explicitly exclude a feature from the first release; do not use demo fixtures as production policy.

Record approved answers in [DECISIONS.md](DECISIONS.md) using its decision template. A provider choice that requires a paid plan must also receive explicit purchase approval.

## Release-scope decision

Before selecting providers, identify which capabilities will be offered in the first public release:

- fixed plans;
- custom quotes;
- real online checkout;
- automatic assignment;
- AI complexity recommendations;
- editor coins and redemption;
- monthly creator packages;
- email notifications and consultations; and
- production analytics beyond operational counts.

A capability may remain disabled for a staged release only when public copy, navigation and terms describe that limitation accurately.

## Decisions to approve

| ID | Owner must provide | Activation effect |
| --- | --- | --- |
| D02 | Production object-storage provider and region; file-size/type policy; malware scanning; signed-link lifetime/revocation; retention, deletion, backup and restore rules | Enables production uploads and delivery testing |
| D03 | Three plan names, minor-unit prices, currency, included services, duration/revision limits, priority and delivery wording | Enables fixed-plan publication and quotes |
| D04 | Custom base price, prices for every selectable service, handling of unpriced requests and quote-expiry/change behavior | Enables complete custom estimates and quotes |
| D05 | Payment provider/methods, webhook contract, taxes/invoice fields, refunds, cancellations, disputes and reconciliation owner | Enables real checkout and financial reporting |
| D06 | Exact 24-hour clock start/end, calendar or working hours, pause rules, warning thresholds, override authority and breach handling | Enables automatic deadlines and early warnings |
| D07 | Approval/proficiency criteria, workload capacities, availability rules and the project states that consume capacity | Enables production editor eligibility |
| D08 | Whether AI ships; provider/model, shared data, classification labels/rules, evaluation set, confidence/failure behavior and admin override | Enables AI recommendations; manual assessment remains available if excluded |
| D09 | Busy-editor skip/wait choice, cross-level fallback, roster order, manual-assignment pointer behavior, queue priority and retry triggers | Enables automatic allocation |
| D10 | Coin precision/value, earning amounts/formula, release timing, reassignment/cancellation/refund effects, redemption minimum/method and payout provider | Enables real editor earnings and redemption |
| D11 | Revision counting, excess-revision handling, latest-version acceptance rule, cancellation permissions, finality and reopening | Enables production review terms for new agreements |
| D12 | Email/communication provider, verified domain, templates, preferences, consultation obligations/logistics, worker schedule and support ownership | Enables external notifications and production consultations |
| D13 | Package names/prices, billing period, included allowance, reservation/consumption, renewal, expiry, rollover, cancellation and dedicated-editor behavior | Enables monthly package sales |
| D14 | Approved branding/claims, testimonials and consent, public support contacts, service terms and privacy/contact content | Enables public launch content |
| D15 | Revenue/refund formulas, included payment states, reporting timezone, delivery/revision metrics, package performance and retention definition | Enables production business analytics |
| D16 | Hosting/environments, recovery-time and recovery-point targets, database/media backup ownership, monitoring/alert routes, incident owner and account lifecycle | Enables deployment and recovery approval |

## Approval record to send the development team

Copy one block per decision being approved:

```text
Decision ID:
Status: approved | excluded from first release
Approved date:
Owner:
Exact values, provider and policy:
Existing orders/data affected:
Migration or backfill allowed:
Required acceptance test:
Purchase/upgrade approved: yes | no | not required
```

Do not include passwords, database URLs, API keys or private certificates in the decision record. Provision credentials later through the approved secret channel.
