# Video.OS / BRIO UI and behavior audit

> **Purpose.** This is the source-of-truth inventory for a future visual redesign, including scroll storytelling, background treatments and parallax. It records what exists before any redesign. It does **not** authorize behavior, route, content, permission or control changes.
>
> **Status labels used below.** **Source-verified** means traced to checked-in code, templates, tests or project records. **Runtime-verified** means observed in the read-only local browser walkthrough on 2026-10-24. **Unverified** means the source exists but the current environment or account did not permit a safe live check. **Proposed** means a redesign idea only, not current behavior.

## 1. Audit scope and evidence

### Scope

The audit covers the complete Django URL configuration, public/authenticated layouts, all checked-in page templates, shared partials, front-end scripts, CSS, image assets, navigation construction, route guards, project/file authorization, feature/configuration surfaces and the documented integration boundaries. It also reconciles the implementation with `AGENTS.md`, `docs/PRODUCT_RULES.md`, `docs/ROADMAP.md`, `docs/DECISIONS.md`, `docs/DAY_1.md` and relevant sections of `docs/ORIGINAL_BRIEF.md`.

No form was submitted, no state-changing endpoint was called, and no application code, database row, storage object or production configuration was changed during this audit.

### Evidence ledger

| Evidence | Status | What it proves | Limits |
| --- | --- | --- | --- |
| `vedioos/urls.py` | Source-verified | Canonical route registry and error handlers | Catch-all page names still depend on view dispatch |
| `core/views.py`, `core/commerce_views.py`, `core/landing_views.py`, `core/message_views.py`, `core/delivery_views.py` | Source-verified | Public, client, commerce, communication, delivery and file behavior | External providers were not invoked |
| `operations/*.py` | Source-verified | Admin/editor pages, assignment, support, notifications, audit and earnings | Some features remain policy/provider gated |
| `core/permissions.py`, middleware and context processors | Source-verified | Role, project and notification visibility rules | Does not replace a deployment penetration test |
| `templates/**/*.html` | Source-verified | Page structure, visible content, forms, controls, empty/error states | Dynamic records vary by account and database |
| `static/app.css`, `static/app.js`, `static/account-controls.js`, `static/availability.js` | Source-verified | Tokens, responsive rules and client-side interactions | Browser/assistive-technology matrix remains incomplete |
| Local browser: `/` | Runtime-verified | Current BRIO public header, orange/beige landing hero and authenticated Workspace CTA at a 659×524 viewport | One browser and viewport only |
| Local browser: `/client/projects/` | Runtime-verified | Client shell, seven destinations, project filter/list, notification and logout controls | Existing record names/content deliberately omitted here |
| Automated verification recorded in project docs | Source-verified | Security, responsive, workflow and migration suites have recorded evidence | Historical evidence is not a fresh production certification |
| Supabase, private object storage, Razorpay, SMTP and production hosting | Unverified in this audit | Source contracts and configuration requirements are documented | No credentials or destructive/live-provider actions were used |

### Audit conventions

- Stable IDs such as `PUB-001` and `CL-003-EL-02` are documentation identifiers, not DOM IDs.
- Repeated database-driven rows are inventoried once as a component with all actions and states; private record values are not copied into this document.
- Text shown from a model or administrator setting is identified as dynamic rather than frozen to its current database value.
- A route may be implemented but intentionally absent from navigation. That is not permission to expose it.

## 2. Application overview

**Source-verified.** BRIO is a managed human video-editing service. Clients create briefs and upload private originals, commercial terms are snapshotted, confirmed paid work can be allocated to eligible editors, editors upload immutable versions, clients request revisions or accept a delivery, and administrators operate pricing, assignments, support, notifications, audit and payout review. The product does not automatically edit video and does not expose a public editor marketplace.

The application is a server-rendered Django monolith with progressive JavaScript enhancement. It uses a custom role-bearing user model and private application schema, Supabase PostgreSQL/Auth when shared configuration is present, a replaceable private S3-compatible object store, and a replaceable payment boundary with a Razorpay Test Mode adapter. SQLite and the local private store are explicit offline/test options, not shared production substitutes.

### Current experience map

| Audience | Primary entry | Shell | Core outcome |
| --- | --- | --- | --- |
| Public | `/` | Public header/footer | Understand the service, view configured offerings, register or sign in |
| Client | `/client/` | Client workspace | Create/edit briefs, upload files, review quotes/payments/projects, communicate and request support |
| Editor | `/editor/` | Editor workspace | Work only on currently assigned paid projects, submit versions, communicate and manage availability requests |
| Administrator | `/admin/` | Admin workspace | Operate records, pricing/content, allocation, support, notifications, audit and payout review |
| Service/health | `/health/*`, `/api/*` | JSON/no page shell | Readiness, protected data and state-changing workflow endpoints |

## 3. Complete route/page registry

The registry below reconciles every explicit route and the two role-specific catch-alls in `vedioos/urls.py`. `GET page` means it renders or redirects to a page; `action/API` means it is not a redesignable page.

### Public, authentication and shared routes

| ID | Route | Type | Access | Rendering/outcome | Status |
| --- | --- | --- | --- | --- | --- |
| SYS-001 | `/health/live/` | API | Public | Process liveness JSON | Source-verified |
| SYS-002 | `/health/ready/` | API | Public/operational | Dependency readiness JSON | Source-verified |
| PUB-001 | `/` | GET page | Public | `landing.html` | Runtime-verified |
| PUB-002 | `/landing/hero-video/` | media response | Public | Permissioned configured MP4 playback | Source-verified |
| AUTH-001 | `/register/` | GET/POST page | Anonymous | `auth.html`, client registration | Source-verified |
| AUTH-002 | `/verify-email/` | GET page | Verification session | `verification_pending.html` | Source-verified |
| AUTH-003 | `/verify-email/code/` | GET/POST page | Verification session | `verify_email_otp.html` | Source-verified |
| AUTH-004 | `/verify-email/resend/` | POST action | Verification session | Resend with throttling/provider handling | Source-verified |
| AUTH-005 | `/verify-email/success/` | GET page | Public | `verification_success.html` | Source-verified |
| AUTH-006 | `/register/editor/` | redirect | Public | Public editor application is disabled | Source-verified |
| AUTH-007 | `/login/` | GET/POST page | Anonymous | Client/admin login in `auth.html` | Source-verified |
| AUTH-008 | `/editor/signin/` | GET/POST page | Anonymous | Editor-focused login in `auth.html` | Source-verified |
| AUTH-009 | `/password-reset/` | GET/POST page | Anonymous | Reset request | Source-verified |
| AUTH-010 | `/password-reset/code/` | GET/POST page | Reset session | OTP verification | Source-verified |
| AUTH-011 | `/password-reset/new/` | GET/POST page | Verified reset session | New/confirm password | Source-verified |
| AUTH-012 | `/login/session/` | GET/POST page | Conflicting session | `session_conflict.html` | Source-verified |
| AUTH-013 | `/logout/` | POST/redirect action | Authenticated | Ends session | Source-verified |
| AUTH-014 | `/dashboard/` | redirect | Authenticated | Routes by role | Source-verified |
| SH-001 | `/orders/notifications/` | GET page | Authenticated | Full notification history | Source-verified |
| SH-002 | `/notifications/<notice>/` | GET page | Recipient | Notification detail/deep-link | Source-verified |
| SH-003 | `/notifications/mark-all-read/` | POST action | Authenticated | Marks recipient notices read | Source-verified |
| SH-004 | `/orders/notifications/<notice>/read/` | POST action | Recipient | Marks one read and redirects | Source-verified |
| SH-005 | `/notifications/posters/<campaign>/` | media response | Authorized recipient/admin | Private campaign poster | Source-verified |
| SH-006 | `/orders/<project>/delivery/` | POST action | Authorized project member | Delivery state transition | Source-verified |
| SH-007 | `/orders/<project>/messages/` | POST action | Authorized project member | Shared project message | Source-verified |

### Client and commerce routes

| ID | Route | Type | Access | Rendering/outcome | Status |
| --- | --- | --- | --- | --- | --- |
| CL-001 | `/client/` | GET page | Client | Dashboard | Source/runtime-verified shell |
| CL-002 | `/client/new-order/` | GET/POST page | Client | Create standard/custom brief | Source-verified |
| CL-003 | `/client/revisions/` | GET page | Client | Published revision-plan comparison | Source-verified |
| CL-004 | `/client/projects/` | GET page | Client | Project list/filter | Runtime-verified |
| CL-005 | `/client/projects/<project>/` | GET page | Owning client | Shared project detail, client variant | Source-verified |
| CL-006 | `/client/projects/<project>/edit/` | GET/POST page | Owning client; allowed state | Edit brief | Source-verified |
| CL-007 | `/client/communication/` | GET page | Client | Ongoing/completed project conversation chooser | Source-verified |
| CL-008 | `/client/communication/<project>/` | GET page | Owning client | Project communication | Source-verified |
| CL-009 | `/client/payments/` | GET page | Client | Search/date-filter payment history | Source-verified |
| CL-010 | `/client/support/` | GET page | Client | Support history plus create form | Source-verified |
| CL-011 | `/client/support/create/` | POST action | Client | Opens idempotent request | Source-verified |
| COM-001 | `/client/projects/<project>/quote/` | GET/POST page | Owning client | Select plan or custom quotation | Source-verified |
| COM-002 | `/client/checkout/<project>/` | GET/POST page | Owning client | Custom quotation checkout | Source-verified |
| COM-003 | `/client/projects/<project>/quotes/<quote>/` | GET/POST page | Owning client | Saved quote review/acceptance | Source-verified |
| COM-004 | `/orders/<project>/` | GET page | Authorized user | Order/project summary | Source-verified |
| COM-005 | `/orders/<project>/checkout/` | POST action | Owning client | Creates provider attempt from server snapshot | Source-verified |
| COM-006 | `/payments/<payment>/receipt/` | GET page | Authorized owner/admin | Payment receipt | Source-verified |
| COM-007 | `/payments/<payment>/razorpay/` | GET page | Owning client | Hosted-checkout handoff | Source-verified |
| COM-008 | `/api/custom-estimate/`, `/api/quote/` | API | Client | Server-calculated estimate | Source-verified |
| COM-009 | `/api/payments/<payment>/razorpay/confirm/` | API action | Owning client | Verifies provider signature/order/amount | Source-verified |
| COM-010 | `/api/payments/sandbox/webhook/` | API action | Verified sandbox boundary | Idempotent sandbox payment event | Source-verified |

### Editor routes

| ID | Route | Type | Access | Rendering/outcome | Status |
| --- | --- | --- | --- | --- | --- |
| ED-001 | `/editor/` | GET page | Editor | Assigned-project dashboard | Source-verified |
| ED-002 | `/editor/projects/<project>/` | GET page | Current approved assignee of paid project | Shared project detail, editor variant | Source-verified |
| ED-003 | `/editor/communication/` | GET page | Editor | Assigned project conversation chooser | Source-verified |
| ED-004 | `/editor/communication/<project>/` | GET page | Current assignee | Project communication | Source-verified |
| ED-005 | `/editor/communication/<project>/reply/` | POST action | Current assignee | Shared reply | Source-verified |
| ED-006 | `/editor/projects/` | catch-all page | Editor | Project details roster | Source-verified |
| ED-007 | `/editor/revisions/` | catch-all page | Editor | Revision queue | Source-verified |
| ED-008 | `/editor/availability/` | GET/POST page | Editor | Availability/request status | Source-verified |
| ED-009 | `/editor/calls/` | catch-all page | Editor | Consultation records/skeleton by dispatch | Source-verified |
| ED-010 | `/editor/wallet/` | GET page | Editor | Wallet (route retained, hidden from sidebar) | Source-verified |
| ED-011 | `/editor/wallet/redeem/` | POST action | Editor; policy gated | Reserve whole coins in sandbox workflow | Source-verified |
| ED-012 | `/api/editor/availability/` | API | Editor | Current workload-derived/override status | Source-verified |
| ED-013 | `/editor/<page>/` | catch-all | Editor | Dispatches known names; unknown names do not become features | Source-verified |

### Administrator routes

| ID | Route/group | Type | Access | Rendering/outcome | Status |
| --- | --- | --- | --- | --- | --- |
| AD-001 | `/admin/` | GET page | Admin | Operations dashboard | Source-verified |
| AD-002 | `/admin/orders/`, `/admin/orders/<order>/` | GET pages | Admin | Pending order roster/detail | Source-verified |
| AD-003 | `/admin/payments/` | GET page | Admin | Payment ledger | Source-verified |
| AD-004 | `/admin/projects/`, `/admin/projects/<project>/` | removed list/detail page | Admin | List path intentionally returns 404; protected detail remains reachable from orders/other operations | Source-verified |
| AD-005 | `/admin/editors/`, `/admin/editors/<editor>/` | GET pages | Admin | Editor roster/profile/operations | Source-verified |
| AD-006 | `/admin/editors/<editor>/approve/` | POST action | Admin | Approves proficiency | Source-verified |
| AD-007 | `/admin/editors/<editor>/availability/` | POST action | Admin | Applies override with reason | Source-verified |
| AD-008 | `/admin/editors/<editor>/operations/` | POST action | Admin | Protected editor operation | Source-verified |
| AD-009 | `/admin/clients/`, `/admin/clients/<client>/` | GET pages | Admin | Client roster/detail | Source-verified |
| AD-010 | `/admin/assignments/` | GET page | Admin | Paid allocation queues/rotation | Source-verified |
| AD-011 | `/admin/assignments/policy/` | GET/POST page | Admin | Allocation settings | Source-verified |
| AD-012 | `/admin/assignments/process/` | POST action | Admin | Runs bounded waiting queue | Source-verified |
| AD-013 | `/admin/assignments/<project>/` | GET/POST page | Admin | Complexity and manual/automatic assignment | Source-verified |
| AD-014 | `/admin/pricing/` | GET page | Admin | Catalog and policy overview | Source-verified |
| AD-015 | `/admin/pricing/plans/<slot>/`, `/revision-plans/<slot>/` | GET/POST pages | Admin | Fixed slots | Source-verified |
| AD-016 | `/admin/pricing/services/(new|<item>)/`, `/packages/(new|<item>)/` | GET/POST pages | Admin | Catalog item create/edit | Source-verified |
| AD-017 | `/admin/pricing/policy/` | GET/POST page | Admin | Commerce policy | Source-verified |
| AD-018 | `/admin/pricing/quotation-features/<code>/` | GET/POST page | Admin | Quotation feature pricing | Source-verified |
| AD-019 | `/admin/landing-page/` | GET/POST page | Admin | Every landing copy field, ordered FAQ and private hero MP4 control | Source-verified |
| AD-020 | `/admin/features/` | GET/POST page | Admin | Feature availability controls | Source-verified |
| AD-021 | `/admin/payouts/`, `/admin/payouts/action/` | page/action | Admin | Earnings release and sandbox redemption decisions | Source-verified |
| AD-022 | `/admin/earnings/` | GET/POST page | Admin | Earning settings | Source-verified |
| AD-023 | `/admin/support/` | GET page | Admin | Support queue | Source-verified |
| AD-024 | `/support/<request>/` | GET page | Owning client/admin | Shared support detail | Source-verified |
| AD-025 | `/support/<request>/messages/`, `/status/` | POST actions | Owning client/admin as applicable | Shared/internal replies and status | Source-verified |
| AD-026 | `/admin/notifications/`, `/new/`, `/<campaign>/edit/` | GET/POST pages | Admin | Campaign list/draft editor | Source-verified |
| AD-027 | `/admin/notifications/<campaign>/action/` | POST action | Admin | Publish/cancel permitted transition | Source-verified |
| AD-028 | `/admin/audit/` | GET page | Admin | Protected attributed event timeline | Source-verified |
| AD-029 | `/admin/calls/`, `/admin/calls/<call>/action/` | page/action | Admin | Consultation scheduling/completion | Source-verified |
| AD-030 | `/admin/analytics/` | GET page | Admin | Reconciled operational metrics | Source-verified |
| AD-031 | `/admin/<page>/` | catch-all | Admin | Known operational page dispatch; includes the paths above | Source-verified |

### Shared protected APIs and errors

| ID | Route | Outcome |
| --- | --- | --- |
| API-001 | `/api/projects/<project>/` | Authorized project JSON |
| API-002 | `/api/projects/<project>/uploads/` | Validates category/size/access and creates narrow private upload reservation |
| API-003 | `/api/files/<file>/complete/` | Verifies stored object metadata/integrity before ready state |
| API-004 | `/api/files/<file>/remove/` | Removes eligible unpaid brief file from private storage, then tombstones metadata |
| API-005 | `/api/files/<file>/download/` | Rechecks role/project access and returns short-lived access |
| API-006 | `/api/areas/<area>/` | Role-protected area data |
| ERR-403/404/500 | framework handlers | `error.html` variants with safe navigation; exact state depends on exception/environment |

## 4. Roles, permissions and member management

### Role matrix

| Capability | Client | Editor | Admin |
| --- | --- | --- | --- |
| Public marketing/auth | Yes | Yes | Yes |
| Own project/brief | Read/write while allowed | No | Operational read |
| Any other client's project | No | Only while current approved assignee of confirmed paid work | Yes, except archived records are removed from normal operational queries |
| Original/private file | Own authorized project and category rules | Current assignment and category rules | Authorized operational access |
| Assign work/approve editor | No | No | Yes |
| Pricing/landing/features | No | No | Yes |
| Shared project messages | Own project | Current assigned project | Project detail/internal operations as implemented |
| Support | Own requests/shared replies | No client support surface | All requests; shared reply plus admin-only internal note |
| Notifications | Recipient only | Recipient only | Recipient plus campaign administration |
| Audit timeline | No | No | Yes |

**Source-verified authorization rules.** Unauthenticated page requests redirect to login; unauthenticated API calls return 401; wrong roles raise 403. Client visibility is ownership-based. Editor visibility requires a confirmed payment, non-archived project, current non-ended assignment and approved editor profile. Admin project visibility excludes archived projects from normal queues. File visibility and upload categories are checked on the backend; hidden controls are never the security boundary.

Editor accounts are administrator-issued. Public `/register/editor/` does not create an applicant. Admin approval assigns authoritative proficiency; editors cannot self-approve. An explicit admin availability override takes precedence over workload-derived availability. Supabase Auth deletion reconciliation archives linked application identities while retaining attributable financial/audit history, unassigning editors safely and refusing to archive the last active admin.

## 5. Shared design system and UI primitives

### Tokens and typography

| Token/principle | Current value or behavior | Evidence |
| --- | --- | --- |
| `--ink` | `#17271f` | Source-verified |
| `--muted` | `#6f6b66` | Source-verified |
| `--paper` | `#faf7f2` | Source-verified |
| `--white` | `#fff` | Source-verified |
| `--line` | `#e7d8c4` | Source-verified |
| `--green` (legacy token name) | `#a44724`, rusty orange | Source/runtime-verified |
| `--lime` (legacy token name) | `#e8d7bd`, beige | Source/runtime-verified |
| `--radius` | `16px` | Source-verified |
| Body | DM Sans stack, 16px, line-height 1.65 | Source-verified; bundled/imported font availability unverified |
| Headings/brand | Manrope stack; emphasized landing phrases use Georgia | Source-verified |
| Keyboard focus | 3px rusty-orange outline with 4px offset | Source-verified |

The supplied `static/images/brio-logo.jpeg` is the single meaningful logo asset and favicon source. It renders at 34×34px (30×30px on narrow phones) with `object-fit: contain` and alt text `BRIO Logo` where meaningful.

### Shared primitives

| Primitive | Stable ID | Structure and states | Preservation rule |
| --- | --- | --- | --- |
| Public header | SHARED-PUB-EL-01 | Logo/home, How it works, Services, conditional auth/workspace controls | Keep each destination exactly once and retain login/register conditional logic |
| Public footer | SHARED-PUB-EL-02 | BRIO, dynamic tagline, opposite login-type link | Never expose an admin sign-in link |
| Workspace sidebar/nav | SHARED-WS-EL-01 | Brand, role label, role-specific destinations, account block | Keep role inventory and hidden-route decisions intact |
| Workspace utility header | SHARED-WS-EL-02 | Back, privacy cue, notification bell/dropdown, mobile logout | Keep above content/nav in responsive reading order |
| Notices | SHARED-WS-EL-03 | Django messages in live/polite region | Retain severity and assistive announcement |
| Buttons/links | SHARED-CTL-EL-01 | Primary, secondary, small, text button/link, disabled state | Preserve labels/outcomes unless owner explicitly changes them |
| Panels/cards | SHARED-CARD-EL-01 | Panel, detail/form panel, stats, feature/file rows | Layout may change; grouping semantics must remain |
| Forms | SHARED-FORM-EL-01 | Labels, help/error text, CSRF, password visibility, money shell | Retain server errors, required states and keyboard behavior |
| Empty/loading/error states | SHARED-STATE-EL-01 | Empty-state icon/title/copy; inline status; retry/error text | Do not replace honest unavailable states with fabricated data |
| Badges | SHARED-STATE-EL-02 | Project/payment/version/availability/status labels | Preserve the underlying state, not necessarily pill styling |
| Private upload | SHARED-UP-EL-01 | Drop/select areas, progress, checksum completion, retry/removal | Never turn originals into public assets or alter bytes |
| Notification menu | SHARED-NOTICE-EL-01 | Toggle, unread count, latest ten, poster, deep links, mark-all/read history | Escape closes and returns focus; recipient filtering stays server-side |

### Responsive behavior

Desktop uses a fixed 236px workspace sidebar and a content body offset. At `max-width: 760px`, the shell changes reading order through `display: contents`: logo, 55px utility header, horizontally scrollable role navigation, then page content. The account block is hidden and the header exposes mobile logout. Controls receive a 44px minimum touch height. Safe-area padding is applied. Additional layout adjustments exist at 1350, 1050, 900, 700, 600 and 480px; a 1600px rule expands large displays. This is **Source-verified**; a full iOS/Android/tablet device-lab pass remains **Unverified**.

## 6. Detailed page-by-page inventory

Each entry uses: **A** purpose/audience; **B** hierarchy; **C** content; **D** controls/outcomes; **E** states; **F** responsive/accessibility; **G** data/security.

### Public and authentication

#### PUB-001 — Landing page

- **A.** Public marketing and conversion page; authenticated visitors receive a Workspace CTA.
- **B.** `SHARED-PUB-EL-01` → two-column hero → How it works → Services → Plans → reassurance/Why choose us → recurring/influencer package explanation → FAQ accordion → closing CTA → `SHARED-PUB-EL-02`.
- **C.** All navigation labels, hero microcopy, three hero lines, CTA labels, artwork labels/numbers/times, step/service/plan/reassurance/recurring/FAQ/closing copy and footer tagline are administrator-managed. Published plan data is dynamic. Defaults match the checked-in design.
- **D.** `PUB-001-EL-01` Start creating → registration; `EL-02` See how it works → anchor; `EL-03` plan action → registration; `EL-04` FAQ `<summary>` toggles; `EL-05` closing CTA → registration; public shell controls as above.
- **E.** Hero either shows `PUB-001-STATE-VIDEO` (autoplay, muted, loop, playsinline configured MP4) or `STATE-ILLUSTRATION` fallback. Plans have populated/empty states. FAQ list is dynamic.
- **F.** Hero collapses to one column; artwork/timeline scale; semantic sections/headings/details are present. Illustration has an accessible label while its timeline is decorative.
- **G.** Landing content and FAQ rows come from admin-managed persisted configuration. Video is private storage with a permissioned playback response, MP4 validation and a 100MB limit.

#### AUTH-001 / AUTH-007 / AUTH-008 — Register and sign-in variants

- **A.** Anonymous client registration, shared client/admin sign-in, and editor-focused sign-in.
- **B.** Public shell → intro eyebrow/title → form card → contextual recovery/account link → public footer.
- **C.** Form title/button are mode-driven. Client sign-in does not advertise administrator access. Editor page footer links to Client Sign In; all other public pages link to Editor Sign In.
- **D.** `AUTH-SHELL-EL-01` labelled fields; `EL-02` submit; `EL-03` password visibility toggle; `EL-04` Forgot password; registration/login alternate where applicable; footer opposite-role sign-in.
- **E.** Validation/non-field errors, removed-account/session-ended notices, unverified-account redirect and provider-unavailable errors are supported.
- **F.** Two-column auth layout collapses on mobile; intro loses sticky behavior; focus/error associations must remain.
- **G.** Credentials are server verified. Supabase users can provision only a client profile; role metadata is not trusted. Privileged/editor legacy paths remain constrained as documented.

#### AUTH-002–AUTH-005 — Email verification

- **A.** Client OTP activation.
- **B.** Pending instructions → six-digit code form/resend → success page.
- **C/D.** Email context, OTP input, Verify, Resend and return/login links; exact provider messages are dynamic.
- **E.** Missing/expired/invalid code, throttling, resend success/failure and already-authenticated redirects.
- **F/G.** OTP must remain labelled and pasteable. Supabase confirms the identity before the private profile activates.

#### AUTH-009–AUTH-011 — Password recovery

- **A.** Email-based OTP reset shared by client/editor entry points.
- **B.** Email request → code verification → new/confirm password → login.
- **D.** Send code, Verify, Resend where offered, Save new password and return navigation.
- **E.** Unknown email is handled without account enumeration; invalid/expired session/code and provider outages show recoverable errors.
- **G.** Reset state is session-bound and password policy is enforced server-side.

#### AUTH-012 / ERR-403/404/500 — Exceptional pages

- **A.** Resolve concurrent session ownership or safely recover from denied/missing/failing requests.
- **D.** Session decision actions continue here/end other session as implemented; error pages expose safe navigation only.
- **E/G.** Do not reveal private identifiers, stack traces or role-specific hidden destinations.

### Client pages

#### CL-001 — Client dashboard

- **A.** Client overview.
- **B.** Workspace shell → welcome heading/lead → Plan a new edit CTA → summary stats/cards → recent project/action content.
- **D.** `CL-001-EL-01` Plan a new edit; project/detail destinations from records.
- **E.** New-account and populated states; shared flash notices.
- **F/G.** Cards stack responsively; counts and records are ownership filtered.

#### CL-002 / CL-006 — Create or edit brief

- **A.** Create a standard/custom project draft or edit eligible project information.
- **B.** Heading → option/plan choice → structured brief fields → conditional creative-direction sections → private clips/inspiration/font upload panels → submit/status/retry.
- **C.** Title, description, platforms, duration, editing style, music, wording and plan/custom options are model/form driven.
- **D.** Select plan/custom, file select/remove, Save and Proceed/update details, retry failed upload. The authoritative next destination depends on standard/custom and saved state.
- **E.** Validation, conditional fields, progress, network/storage retry, server-invalid focus, existing files and immutable/paid restrictions.
- **F.** Field grids collapse; upload controls remain touch-sized. Programmatic labels, live status and focus-to-invalid behavior must remain.
- **G.** Upload is direct to private storage, then checksum/metadata completion is verified. Server recalculates any quotation; client prices are not trusted.

#### CL-003 — Revision plan comparison

- **A.** Compare three administrator-published revision offerings without changing an order.
- **B.** Heading/intro → three cards → live selection status.
- **D.** Reversible `aria-pressed` Select plan controls; one selected at a time.
- **E.** Published/unavailable slots and no-selection state.
- **G.** Comparison only; no payment/order mutation.

#### CL-004 — My projects

- **A.** Client-owned project history and navigation.
- **B.** Heading/count → status filter → summary → repeated project rows → filter-empty state.
- **D.** `CL-004-EL-01` status selector (All, Pending, Ongoing, Completed, Cancelled); `EL-02` row/detail link.
- **E.** No projects, populated, and no matching local filter result.
- **F.** Filter rearranges below 600px; rows adapt to mobile.
- **G.** Runtime-verified with existing data; private titles are intentionally not documented. Filtering is presentation-level over the server-owned client queryset.

#### CL-005 — Project detail, client variant

- **A.** Single source for project state, commercial next step, files, delivery and communication entry points.
- **B.** Heading/created date → state-specific next-step or summary content → detail columns → Project Files → delivery/version partial → messages/notes as permitted.
- **D.** Contextual Edit details, review quote/order/payment, upload/download/remove, request revision, accept explicit version, communication and support-adjacent links.
- **E.** Payment pending/paid; awaiting assignment/assigned/editing/revision/completed/cancelled; missing quote; file upload states; no/latest versions; revision limit/overdue; accepted delivery.
- **G.** Ownership on every request. The duplicate top payment badge was removed; authoritative status remains in the content block. Acceptance is explicit and version-specific.

#### CL-007 / CL-008 — Project Communication

- **A.** Choose an ongoing/completed owned project and communicate with its current team.
- **B.** Grouped chooser lists → conversation chronology → message form.
- **D.** Open conversation, post message, older history/back navigation.
- **E.** No eligible projects, no messages, validation failure.
- **G.** Six or more consecutive digits are rejected in browser and service; messages remain project scoped. Internal notes are not exposed.

#### CL-009 — Payment history

- **A.** Find own payment records without status-tab clutter.
- **B.** Heading → search → date-range filter (including All, Last 5 Days, Last 10 Days and useful longer ranges) → result list → older cursor.
- **D.** Search, date selection, receipt/order links.
- **E.** Empty/no-match, pending/failed/confirmed record presentation and pagination.
- **F.** Filter menu must remain above surrounding content and selectable on narrow screens.
- **G.** Server filters ownership and dates; payment state is not inferred from a redirect.

#### CL-010 / AD-023–AD-025 — Support

- **A.** Client creates requests and exchanges shared replies; admins triage and may keep internal notes.
- **B.** Client: create form then request list. Admin: filters then matching list. Detail: status (admin), shared conversation, reply/internal-note forms.
- **D.** Category, optional project, body, Open support request; open request; admin status; shared reply; admin-only internal note.
- **E.** Empty queues, idempotent retry, status variants, validation errors.
- **G.** Subject is generated rather than collected from clients. Clients see only their request and shared messages; internal notes are admin only.

### Commerce and delivery pages

#### COM-001–COM-004 — Quote, review, checkout and order summary

- **A.** Turn a saved brief into an immutable server-owned commercial snapshot and return to the same project summary.
- **B.** Plan/custom choice → breakdown/terms → explicit acceptance where required → original order summary layout with Additional Terms and Payment Link positions → payment handoff.
- **D.** Select, save/proceed, edit details, accept terms, make payment, return to project. The removed green information box and Refresh Quotation button must not reappear.
- **E.** Missing/unpublished configuration, stale draft, accepted quote, pending/confirmed attempt, provider disabled/error.
- **G.** Integer minor units/currency, server totals, order snapshots and superseded pending attempt cancellation. Returning from payment preserves the detailed quotation.

#### COM-006 / COM-007 — Receipt and Razorpay Test Mode handoff

- **A.** Show an attributable payment record or complete the provider handoff.
- **D.** Provider checkout, return/order navigation, receipt view.
- **E.** Pending, confirmed, failed, mismatched/invalid signature and provider unavailable.
- **G.** Test records are labelled; confirm fetches provider state and checks HMAC, order, amount and currency. No live checkout without an explicit production decision.

#### DELIVERY-001 — Shared version/revision/acceptance partial

- **A.** Editor submission and client review within a project detail page.
- **B.** V1 status → ordered immutable version history → role/state-specific action card → revision history.
- **D.** Editor Start editing/revision and upload deliverable; client Download, Request revision with notes and Accept version with explicit checkbox.
- **E.** V1 required/available/overdue, draft/final, revision used/available, completed/accepted.
- **G.** Every file remains private; versions are immutable and acceptance/earning credit are idempotent.

### Editor pages

#### ED-001 / ED-006 / ED-007 — Assigned work rosters

- **A.** Surface current eligible assignments and revision work only.
- **B.** Availability/workload summary → grouped project rows → empty/skeleton guidance as applicable.
- **D.** Open project, communication and permitted state actions.
- **E.** Awaiting approval, no assignments, busy/not available, active/revision queues.
- **G.** An editor loses visibility when an assignment ends or payment/approval requirements are absent.

#### ED-002 — Project detail, editor variant

- **A.** Obtain the brief/originals and submit immutable work versions.
- **B–F.** Shared project/detail and delivery primitives, with client-only commercial actions removed and editor upload/actions added.
- **G.** Current assignment is rechecked for page, file and message operations.

#### ED-003 / ED-004 — Editor communication

- Same component contract as client communication, limited to current assigned projects. Reply posts to the editor-specific protected action.

#### ED-008 — Availability

- **A.** Show workload-derived state and permit one pending Not Available request with reason.
- **D.** Submit/update request; status auto-refreshes every 30 seconds and on focus/visibility change.
- **E.** Available, Busy, Not Available override and pending request.
- **G.** An editor request does not itself change assignment eligibility; only admin applies the override.

#### ED-010 — Wallet (hidden navigation route)

- **A.** Historical/source-supported earning view, intentionally removed from editor sidebar.
- **B.** Pending/Earned/Redeemable/Redeemed stats → redemption form or disabled explanation → requests → transaction history.
- **G.** Whole coins only, policy gated, sandbox reservations, exactly-once ledger semantics. Do not reintroduce the nav item without owner approval.

### Administrator pages

#### AD-001 — Admin dashboard

- **A.** Operations overview for managers.
- **B.** Page heading → operational stats/queues/deep links.
- **E.** Empty and populated counts; reconciliation/provider errors may block stale presentation.
- **G.** Admin-only; Auth reconciliation may return retryable 503 rather than show stale member data.

#### AD-002–AD-004 — Orders, payments and project detail

- **A.** Reconcile commercial/payment/workflow state.
- **B.** Orders and payments use heading → search/filter controls → rows → cursor pagination; detail adds order/payment attempts or shared project detail. The former admin project-list path is intentionally absent and returns 404.
- **D.** Search; Pending-only visible order tab; workflow/payment filters; open order/project detail/receipt. Do not restore a Projects sidebar item or list page without explicit approval.
- **E.** Empty/no-match, payment/project states, older records.
- **G.** Payment ledger retains its existing status filters; order page intentionally exposes only Pending. Records are server-owned and archived clients are excluded from normal operations.

#### AD-005–AD-008 — Editor management

- **A.** Inspect profile, approve proficiency, manage capacity/operations and decide availability overrides.
- **B.** Roster → editor profile/details → operations and availability forms/history.
- **D.** Approve, choose authoritative proficiency, apply status with decision reason, protected operational actions.
- **E.** Awaiting review, approved, available/busy/not available, pending request, invalid capacity/eligibility.
- **G.** Every decision is admin-only and auditable; current assignments are not implicitly reassigned by availability override.

#### AD-009 — Client management

- **A.** Admin roster/detail for linked client identity and operational history.
- **E/G.** Active/archived synchronization states. Sensitive history remains attributable after archival.

#### AD-010–AD-013 — Assignment operations

- **A.** Review paid projects, set complexity, assign manually or by durable round robin.
- **B.** Queue/filter overview and persistent rotation → policy form → project detail with status, assessment, assignment, candidates and history.
- **D.** Configure allocation, Process waiting queue, filter Needs review/Waiting/Assigned/All paid work, Save assessment, Save assignment, Assign next in rotation.
- **E.** Disabled policy, unreviewed complexity, no eligible editor, unavailable/capacity full, waiting/assigned and previous assignment history.
- **G.** Unpaid projects never enter assignment. Transactions/locking preserve per-proficiency cursor fairness across restarts and races.

#### AD-014–AD-018 — Pricing and commerce configuration

- **A.** Manage plans, revision plans, custom services/packages, policy and feature prices.
- **B.** Catalog overview → kind-specific form page.
- **D.** Create/edit/publish configured items and save validated currency amounts/policy.
- **E.** Published/draft, incomplete policy and form validation.
- **G.** Money is integer minor units; accepted orders retain snapshots when configuration changes.

#### AD-019 — Landing page control

- **A.** Complete control of existing landing copy, ordered FAQs and hero MP4 without changing the public UI inventory.
- **B.** Grouped content fields → hero-video upload/current/remove state → repeatable FAQ editor → save.
- **D.** Edit text, Add FAQ, move up/down, delete FAQ, choose/remove MP4, Save.
- **E.** Default/overridden content, current/selected/no video, upload validation/errors.
- **F.** Dynamic FAQ buttons must remain real buttons and return focus appropriately.
- **G.** Admin-only, validated persistent settings; hero file remains private and original bytes are preserved.

#### AD-020 — Feature controls

- **A.** Explain and toggle only implemented, safely gateable product availability.
- **G.** Disabled integrations must show honest unavailable states and cannot bypass payment/security gates.

#### AD-021 / AD-022 — Earnings and payouts

- **A.** Configure prospective earning policy, release pending credits and decide sandbox redemption requests.
- **D.** Save settings, Release agreed coins, Reject & release, and sandbox-only failed/paid simulations with reference.
- **E.** Policy disabled, no priced earnings, requested/rejected/failed/paid.
- **G.** Real transfers are not configured; exactly-once ledger and reserved balance rules remain mandatory.

#### AD-026 / AD-027 — Notification campaigns

- **A.** Draft, preview, target and publish/cancel recipient-scoped notices.
- **B.** Campaign list → form with audience/optional user/poster preview → action controls.
- **D.** New/edit draft, Save draft, publish/cancel allowed state.
- **E.** Draft/published/cancelled, no poster/selected/current poster, empty list.
- **G.** Private poster access and recipient filtering; external email remains held unless separately enabled.

#### AD-028 — Audit timeline

- **A.** Attribute protected operational actions without exposing private raw payloads.
- **B.** Filters/cursor-driven event rows with action, actor, target and UTC time.
- **G.** Ordinary users cannot edit the timeline; secrets and signed URLs must never enter event details.

#### AD-029 — Consultations

- **A.** Schedule/complete calls selected at checkout; meetings occur outside the app.
- **D.** Select editor/time, Schedule/reschedule, Mark complete.
- **E.** Requested/scheduled/completed and empty queue.

#### AD-030 — Analytics

- **A.** Reconciled operational counts only.
- **E.** The Consultations card and Metrics awaiting policy placeholder were intentionally removed.
- **G.** Do not infer production business metrics that lack an approved definition.

## 7. Overlays, dialogs and transient UI

| ID | UI | Trigger/close | Focus and state contract |
| --- | --- | --- | --- |
| OV-001 | Notification dropdown | Bell click; outside click or Escape closes | `aria-expanded` mirrors visibility; Escape returns focus to toggle |
| OV-002 | Native details disclosure | FAQ summary click/keyboard | Preserve browser disclosure semantics |
| OV-003 | Password reveal | Button beside every password input | Label changes Show/Hide; never changes submitted value |
| OV-004 | Inline upload/progress/retry | File selection/submission | Announced status, retained errors and explicit retry |
| OV-005 | Flash messages | Server redirect/render | Live/polite status; must not depend on color alone |
| OV-006 | Provider checkout | Explicit Make payment path | External overlay/page controlled by provider; return state must be verified server-side |

There is no source-verified custom modal/dialog framework. A redesign must not invent modal copies of existing pages or create duplicate back/submit controls.

## 8. End-to-end workflows

1. **Client identity:** Register → receive/enter email OTP → activation success → log in → client dashboard. Existing confirmed Supabase identities may be securely linked/provisioned as clients.
2. **Password recovery:** Forgot password from client or editor sign-in → email → OTP → new/confirm password → correct sign-in page.
3. **Brief to payment:** Plan a new edit → select standard/custom path → save brief → private upload/verification → quote/order summary → accept applicable terms → server-created payment attempt → provider verification → paid project.
4. **Assignment:** Confirmed payment → admin complexity review → eligible proficiency queue → manual or persistent round robin → current editor assignment. Unavailable/full editors are skipped/waited according to saved policy.
5. **Editing and review:** Editor opens assigned project → downloads private originals → starts work → uploads verified version → client downloads/reviews → revision or explicit acceptance → final version remains attributable.
6. **Communication:** Client/editor chooses eligible project → shared project chronology → validated message → recipient notification. Access ends with ownership/current assignment rules.
7. **Support:** Client opens categorized request → admin sees queue → admin shared reply appears to client; internal notes never do → admin updates status.
8. **Notifications:** Admin drafts campaign → targets eligible audience/user → publishes → recipient sees dropdown/history/detail; external dispatch remains held unless configured.
9. **Earnings:** Explicit accepted version → pending credit under snapshotted approved terms → admin release → wallet ledger → policy-gated sandbox redemption. No real transfer is implied.
10. **Member deletion:** Server reconciles Supabase Auth → archives linked profile/history → queues private cleanup where applicable → ends editor assignments or hides client projects → audit event; last admin is protected.

## 9. Data, integrations and configuration dependencies

| Boundary | Current contract | UI dependency | Production caveat |
| --- | --- | --- | --- |
| Supabase PostgreSQL | Private `vedioos` schema, Django migrations | All persistent records | Shared preview must bind to project `lmwvoniiykmfzuxigzqf`; migration sync requires backup and verification |
| Supabase Auth | Client OTP/password verification and immutable Auth UUID linking | Register/login/reset/member reconciliation | Custom SMTP/verified sender required for dependable inbox delivery |
| Private S3-compatible storage | Originals, inspiration, versions, notification posters and hero video | Upload/download/playback/previews | Buckets/objects must remain private; signed access is temporary |
| Razorpay | Test Mode adapter | Checkout and receipt state | Live checkout is not approved/configured |
| Notification outbox | Durable retry-safe records; held by default | In-app notification plus optional external delivery | Provider, sender, templates and release policy remain owner decisions |
| Admin-managed settings | Landing, catalog, commerce, assignment, earning and feature controls | Dynamic copy/availability/price | Never hard-code unresolved values; snapshot order terms |
| Feature flags | Disable unfinished integrations safely | Honest unavailable/disabled controls | A disabled flag cannot weaken authorization or payment gates |

## 10. Accessibility baseline and risks

### Source-verified baseline

- Skip link targets the main content.
- Landmark headers/nav/main/footer and labelled workspace/public navigation are present.
- Forms use server-rendered labels/errors; password visibility uses a labelled button.
- Keyboard focus is visibly outlined; notification dropdown supports Escape.
- Status messages use live/polite regions in the shared shell.
- Touch controls receive a 44px minimum on mobile.
- FAQ uses native `<details>/<summary>` and revision selection uses `aria-pressed` plus a status region.
- Meaningful logo images have alt text; decorative timeline content is hidden from assistive technology.

### Risks and required redesign checks

- **Source-verified risk:** reduced-motion handling disables smooth scrolling only. Any proposed parallax or scroll-linked motion needs a complete `prefers-reduced-motion` static alternative.
- **Unverified:** full keyboard order, screen-reader announcements, 200–400% zoom/reflow, contrast of every state, iOS VoiceOver and Android TalkBack.
- Dynamic badge/status meaning must not depend on rusty orange/beige alone.
- Horizontally scrolling mobile workspace navigation needs a visible current item and discoverable overflow.
- Uploaded poster/video content needs meaningful adjacent text; autoplay video must remain muted and must not flash.
- Focus must not be lost after dynamic FAQ reorder/delete, upload completion, notification close or validation scroll.

## 11. Redesign preservation contract

These are hard constraints for the next visual implementation:

1. Preserve every current authorized control, destination and outcome exactly once. Do not add, duplicate, rename or remove buttons, links or actions without explicit owner approval.
2. Preserve conditional visibility: login vs registration CTA, client vs editor footer link, role navigation, state-specific project/payment/delivery actions, policy/provider-disabled controls and the hidden Wallet navigation decision.
3. Preserve all backend authorization. Visual hiding, disabled styling and route obscurity are not security controls.
4. Preserve form names, submitted values, CSRF, validation messages, idempotency keys, file categories, upload completion checks and server-calculated commerce values.
5. Preserve honest loading, empty, unavailable, error, retry, permission-denied and archived states.
6. Preserve private-media boundaries. Never use public asset URLs for client originals, versions, posters or configured hero media.
7. Preserve responsive information order, keyboard focus, live announcements, labels, error associations, touch targets and reduced-motion alternatives.
8. Preserve immutable order terms, payment verification, version history, explicit acceptance and attributable audit history.
9. Reposition existing controls when layout changes; never create a second control to solve placement.
10. Treat the stable IDs in this audit as the redesign traceability checklist. A redesign is incomplete until every applicable ID is mapped to a new implementation and verified.

## 12. PROPOSED future scroll narrative

> Everything in this section is **Proposed** and is not implemented or approved behavior. It is a visual direction that must obey section 11.

### Public landing sequence

1. **Opening frame — `PUB-001-SCENE-01`.** Keep the existing hero copy and two actions. Let the existing editing frame become the visual anchor; use subtle depth between copy, frame and timeline.
2. **Process reveal — `SCENE-02`.** The existing three How it works steps enter in sequence as the scroll passes one shared section, without changing labels or destinations.
3. **Craft layers — `SCENE-03`.** Existing service cards move at slightly different speeds against a non-interactive background texture. No new service claims.
4. **Commercial clarity — `SCENE-04`.** Existing published plan rows remain ordinary links/content; a sticky section title may accompany them, but prices and actions remain server rendered.
5. **Trust and continuity — `SCENE-05`.** Existing reassurance and recurring-package content progress as two readable scenes.
6. **Questions and close — `SCENE-06`.** Keep native FAQ disclosures and the existing closing CTA/footer.

### Motion rules

- Transform/opacity only for decorative layers; never animate layout-dependent form controls, payment state or error messages.
- Cap foreground travel and avoid continuous motion after content settles.
- At `prefers-reduced-motion: reduce`, remove parallax, scroll scrubbing and entrance movement; render all content immediately in normal document order.
- On small/touch devices, use a flat single-column composition and static backgrounds. Never require hover or precision dragging.
- Keep video autoplay muted/looping/playsinline and provide the current fallback when no video is configured or playback fails.
- Do not intercept browser scrolling, break anchor links, trap focus or create scroll-jacking.

### Workspace direction

Use background depth and restrained section transitions only around existing panels. Operational tables, forms, filters, uploads, notifications and destructive/financial decisions should remain visually stable while in use. Preserve the 236px desktop information architecture or replace it only with an equally direct single-instance navigation mapping.

## 13. Coverage ledger and known gaps

### Coverage

- [x] Every explicit Django route and both catch-all route families reconciled.
- [x] Public, client, editor, admin and shared shells inventoried.
- [x] Checked-in page templates and shared partial categories mapped to page IDs.
- [x] Shared CSS tokens, fonts, breakpoints and responsive shell behavior recorded.
- [x] Global JavaScript interactions, upload lifecycle, notification menu, password toggle, filters, availability polling and FAQ editor accounted for.
- [x] Role, project, file and support/notification visibility boundaries recorded.
- [x] Dynamic landing content and hero-video administration recorded.
- [x] Major workflows and external configuration boundaries reconciled with project decisions.
- [x] Existing useful project/developer README preserved below.

### Known gaps

- [ ] **Unverified:** visual runtime walkthrough for every role and every state; this audit had one authenticated client session and did not create or mutate data.
- [ ] **Unverified:** production Supabase, storage, SMTP, notification worker and Razorpay credentials/health.
- [ ] **Unverified:** exhaustive real-device/browser/assistive-technology matrix.
- [ ] **Unverified:** representative screenshots for all empty, error, loading, policy-disabled, overdue, archived and provider-failure states.
- [ ] **Unverified:** exact copy currently persisted in production-admin settings; source defaults and field coverage are verified.
- [ ] **Unverified:** final production legal cancellation/refund text, tax invoice fields, coin value, earning terms, notification policy and live checkout/provider decisions remain governed by `docs/DECISIONS.md` and the owner checklist.

## 14. Ready-to-use next Codex prompt

```text
Redesign the Video.OS / BRIO interface using README.md sections 1–13 as the source of truth.

Before editing, read AGENTS.md, README.md, docs/PRODUCT_RULES.md, docs/ROADMAP.md, docs/DECISIONS.md and docs/DAY_1.md. Work on a dedicated redesign branch and keep the main branch intact. First produce a traceability table mapping every applicable stable page/element ID in README.md to the intended implementation file and redesigned location.

Preserve every existing authorized button, link, field, route, state, permission, outcome and role-specific visibility exactly once. Do not add, duplicate, rename or remove controls. Do not expose hidden routes. Keep all backend authorization, CSRF, field names/values, server validation, idempotency, private upload/download behavior, server-calculated prices, order snapshots, payment verification, immutable versions, explicit acceptance, notification filtering and audit attribution unchanged.

Implement the proposed scroll narrative only as visual enhancement. Use restrained transform/opacity effects, a complete prefers-reduced-motion static fallback, normal document scrolling, working anchor links and flat mobile/touch layouts. Do not scroll-jack, trap focus, animate important forms/status/errors, or make hover the only interaction.

Proceed in small verified slices: shared tokens/primitives, public shell/landing, auth, client, editor, admin, then overlays and exceptional states. After each slice, run focused tests and inspect desktop, tablet and phone widths. Test keyboard order, visible focus, zoom/reflow, empty/loading/error/permission states and role isolation. Stop and report any conflict between the proposed design and the preservation contract instead of inventing behavior.
```

---

# Preserved project and developer documentation

The remainder of this file is the pre-audit README preserved verbatim for setup, architecture, operations, verification and historical context.

# BRIO

A managed video-editing service connecting clients with our internal team of human editors. Editors work in their own editing software; BRIO manages ordering, payments, files, assignment, communication, review, delivery, and editor earnings.

**Core principle: high-quality video + privacy + fair editor allocation + human editing + a simple client experience.**

## Project status

Day 1 includes core and operational database migrations, client registration, administrator-issued editor access, shared login/logout, protected dashboards, admin editor approval, project drafts, and private direct uploads/downloads. The Django backend is configured for [the selected Supabase PostgreSQL project](docs/SUPABASE.md), with SQLite retained as an explicit offline/test option. Media storage remains the separate private S3-compatible local service.

Phase 3 includes admin plans/custom pricing, commercial terms, client quotes, saved order agreements, paid/unpaid order filters, payment history and an isolated signed-payment sandbox. See [Phase 3 behavior, tests and remaining decisions](docs/PHASE_3.md). Real checkout and production deployment remain inactive. See also [Day 1 evidence](docs/DAY_1_VERIFICATION.md) and [architecture](docs/ARCHITECTURE.md).

Administrators manage all public landing-page copy and the hero MP4 at `/admin/landing-page/`. Defaults exactly match the checked-in design until an administrator saves changes. Hero videos must be valid MP4 files no larger than 100 MB; they use the configured private S3-compatible store and expiring signed playback addresses. Plan names, prices, revisions and features remain under `/admin/pricing/`.

Clients can compare published revision plans at `/client/revisions/`. The three revision-plan slots are configured independently under `/admin/pricing/` with direct currency entry, descriptive details and explicit publish controls. Selecting a card is currently a reversible comparison choice only; it does not alter an order, quotation or payment.

Phase 4 adds editor capacity controls, manual complexity review, paid queues, audited assignment/reassignment and persistent round robin with configurable skip/wait behavior. See [Phase 4 evidence and activation settings](docs/PHASE_4.md). Allocation is implemented but remains disabled in the connected environment until operating policies are configured; AI classification is not integrated.

Phase 5 adds private editor submissions, version history, revision requests, explicit client acceptance and in-app notifications. [Phase 5 verification and activation](docs/PHASE_5.md) includes real storage/browser checks and PostgreSQL concurrency checks. Review requires an agreed rule in the order snapshot; it remains unconfigured for existing orders.

Phase 6 adds prospective coin rules, acceptance-linked pending credits, admin release, an editor wallet and a sandbox redemption flow with reserved balances. See [Phase 6 evidence and activation limits](docs/PHASE_6.md). The connected project's earning and redemption policy remains disabled; real coin value and payout method await owner decisions.

Phase 7 now includes admin status queues, paid consultation tracking, recipient-scoped in-app notifications with older-history pages, alerts for already-recorded overdue deadlines, and a durable external-delivery outbox held safely by default. See [Phase 7 scope and remaining work](docs/PHASE_7.md). The full Phase 7 gate remains open.

The owner-requested password, editor-ID, navigation, email verification, inspiration-upload and four-block plan/custom changes are verified. See [the change record](docs/OWNER_CHANGES_2026_09_19.md).

Project details also support client/team messages and separate internal notes with protected older-message pages. Current project access is checked on the backend; the [Phase 7 evidence](docs/PHASE_7.md) records the remaining launch work.

Admins can inspect a protected audit timeline at `/admin/audit/`. It shows action, actor, target and time; raw private event details stay out of the page.

Phase 8 is in progress. Admins have reconciled operational analytics, and clients can open private support requests with shared replies while administrators keep separate internal notes and manage status. See [Phase 8 evidence](docs/PHASE_8.md). Monthly package sales and production business metrics remain disabled pending owner policy.

## Read before developing

| Document | Purpose |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Required working instructions for coding agents and contributors |
| [Product rules](docs/PRODUCT_RULES.md) | Product scope, restrictions, workflow, and acceptance requirements |
| [Development pathway](docs/ROADMAP.md) | Dependency-ordered phases and completion gates |
| [Day 1 plan](docs/DAY_1.md) | Hamsa and Dheeraj's foundation tasks, integration contract, and mandatory proof |
| [Day 1 verification](docs/DAY_1_VERIFICATION.md) | Implemented behavior, actual checks, and remaining limits |
| [Phase 3 milestone](docs/PHASE_3.md) | Catalog/quote workflow, payment sandbox, verification and live-checkout blockers |
| [Phase 4 milestone](docs/PHASE_4.md) | Editor workload, paid queues, allocation policy, concurrency and reassignment |
| [Phase 5 milestone](docs/PHASE_5.md) | Version review, revisions, acceptance and private delivery |
| [Phase 6 milestone](docs/PHASE_6.md) | Coin ledger, wallet, release and sandbox redemption |
| [Phase 7 milestone](docs/PHASE_7.md) | Operations queues, consultations, notices and deadline alerts |
| [Phase 8 milestone](docs/PHASE_8.md) | Analytics, support, feature controls and protected payment history |
| [Phase 9 readiness](docs/PHASE_9.md) | Production configuration audit, evidence and remaining release gates |
| [First-version traceability](docs/FIRST_VERSION_TRACEABILITY.md) | Evidence and remaining work for all 28 brief priorities |
| [Architecture](docs/ARCHITECTURE.md) | Stack, models, session/permission flow, and private storage contract |
| [Supabase connection](docs/SUPABASE.md) | Selected cloud project, private schema, configuration, and verification |
| [Codex live-preview prompt](docs/CODEX_LIVE_PREVIEW_PROMPT.md) | Copy-paste prompt for safely running and verifying the current Supabase-backed preview |
| [Owner decision checklist](docs/OWNER_DECISION_CHECKLIST.md) | Exact policy and provider answers required to activate the remaining production features |
| [Open decisions](docs/DECISIONS.md) | Unresolved business and architecture choices; decision record |
| [Team workflow](docs/TEAM_WORKFLOW.md) | Current Git branch, safe collaboration, local setup and publishing cadence |
| [Original brief](docs/ORIGINAL_BRIEF.md) | Complete, unmodified source requirements, sections 1–35 |

The original brief is the baseline. The rules operationalize it, and the roadmap sequences it. Sequencing a feature later does not remove it from scope. Record subsequent explicit owner decisions in the decision log. If documents conflict and no later owner decision resolves them, flag the conflict before implementing the affected behavior.

## Service journey

1. Client registers, uploads source files/assets/references, and describes the edit and song preference.
2. Client selects one of three configurable plans or chooses a custom order and sees the price.
3. The backend confirms payment and activates a uniquely identified order/project.
4. AI recommends complexity; an admin can override it. Eligible editors receive assignments through persistent round-robin allocation or admin assignment.
5. The assigned editor downloads original files, edits externally, and uploads a versioned draft.
6. The client reviews, requests revisions, or accepts a specific version.
7. Acceptance completes the project, makes the accepted final file downloadable, and credits editor coins under the applicable earning rules.

## Users

- **Client:** ordering, private files, progress, communication, calls, review, delivery, history, invoices, and recurring packages.
- **Presenter/admin:** initially two managers; orders, editors, assignment, deadlines, support, configuration, payouts, and analytics.
- **Editor:** approved proficiency, availability, assigned projects, external editing, version submissions, revisions, and coin wallet.

## Non-negotiable boundaries

- No automatic video-editing engine. AI supports complexity classification and assignment only.
- Preserve uploaded source and editor-output bytes exactly. Previews are separate derivatives.
- Private storage and backend role/project authorization are mandatory.
- Editing and assignment require confirmed payment.
- Allocation must persist a separate round-robin pointer per proficiency group and respect capacity.
- Never invent production prices, plan terms, coin values, or unresolved business policies.
- Preserve version history and audit sensitive operations.

## Clone and preview locally — Windows / PowerShell

Use **Python 3.13**, **Node.js 22+**, Git, installed **Microsoft Edge**, and internet access to install dependencies. Docker and a paid subscription are not needed for the local preview. Run these commands in PowerShell. The current team branch is `codex/foundation-and-commerce` (also the repository's current default branch).

### 1. Clone and install

```powershell
git clone --branch codex/foundation-and-commerce https://github.com/Dheeraj1301/VedioOS.git
cd VedioOS
py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.lock.txt
npm.cmd ci
npm.cmd run vendor
.venv/Scripts/python.exe scripts/setup_local.py
.venv/Scripts/python.exe scripts/install_storage.py
.venv/Scripts/python.exe manage.py migrate --settings=vedioos.local_settings
.venv/Scripts/python.exe manage.py init_local --settings=vedioos.local_settings
```

If `py -3.13` is unavailable but `python --version` reports Python 3.13, use `python -m venv .venv` for the third command. `setup_local.py` generates a private `.env` and preserves one that already exists. `install_storage.py` downloads the pinned Windows AMD64 SeaweedFS 4.47 binary and verifies its SHA-256. Other operating systems need their matching SeaweedFS binary at `.runtime/seaweedfs/weed`. Run the remaining commands from the repository root.

`--settings=vedioos.local_settings` keeps preview data in ignored `.runtime/db.sqlite3`, even if a developer later adds a cloud `DATABASE_URL`. Do not put Supabase credentials or real media into Git. `.env`, `.runtime`, virtual environments and `node_modules` are ignored.

### 2. Start the private storage service

For an offline preview, open **PowerShell terminal A** in the cloned repository and leave it running:

```powershell
.venv/Scripts/python.exe scripts/start_storage.py
```

The service listens on `127.0.0.1:9000`. In **PowerShell terminal B**, initialize its private, versioned bucket and start Django:

```powershell
.venv/Scripts/python.exe manage.py init_storage --settings=vedioos.local_settings
.venv/Scripts/python.exe manage.py runserver 127.0.0.1:8000 --settings=vedioos.local_settings
```

Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)**. Keep both terminals running during the preview and full browser test. Stop each with Ctrl+C. Django reloads Python changes in this mode; use `--noreload` only when you want to restart it manually. If ports 8000 or 9000 are occupied, stop the conflicting local service first; the browser and CORS tests expect these exact ports.

### 3. Create preview accounts

Clients register at `/register/`. Editor accounts are issued by an administrator and public editor application is disabled. All roles log in at `/login/`; editors may enter their generated editor ID instead of email. Create an admin in **terminal C** with a password entered at the hidden prompt:

```powershell
.venv/Scripts/python.exe manage.py create_admin --email manager@example.com --name "Studio Manager" --settings=vedioos.local_settings
```

Use your own email and name. The command will not silently turn an existing client/editor into an admin.

Issue an editor ID and initial password from the same trusted terminal. The editor workspace has no password-change control:

```powershell
.venv/Scripts/python.exe manage.py create_editor --email editor@example.com --name "Editor Name" --settings=vedioos.local_settings
```

An editor can log in before approval, but an admin must approve proficiency at `/admin/editors/` before assignment. Client and administrator-issued passwords require at least 8 characters with an uppercase letter, lowercase letter, number and special character.

New client accounts remain inactive until the client enters the six digit code sent to the registered email. Supabase Auth creates, sends and validates that client verification OTP; BRIO activates the matching private application profile only after Supabase confirms the email. Confirmed email/password identities created in the selected Supabase Auth project can also sign in through `/login/`: the backend verifies the password with Supabase, validates the returned session against `/auth/v1/user`, links the immutable Auth UUID, and provisions a client application profile on first login. Supabase tokens are discarded and Auth metadata cannot select a role. When Supabase password login is enabled, confirmed linked clients and administrators authenticate against Supabase Auth and must match the immutable Auth UUID stored on their private application identity; unknown confirmed identities can only be provisioned as clients. Administrator-issued editor IDs and unlinked privileged legacy accounts retain the private application credential path, while all server-side role/project authorization remains in BRIO. Real inbox delivery requires a custom SMTP provider and verified sender configured in the Supabase Auth dashboard; automated tests mock the external Auth boundary and never send email.

Every team preview intended to use shared data must set `SHARED_PREVIEW_REQUIRED=true`, `SUPABASE_PROJECT_REF=lmwvoniiykmfzuxigzqf`, and the privately supplied Supabase connection settings in its ignored `.env`. Confirm the binding before starting the server:

```powershell
.venv/Scripts/python.exe scripts/start_shared_preview.py
```

In VS Code, **always use** `Terminal > Run Build Task` (`Ctrl+Shift+B`) and select
`BRIO: Start shared preview`. It runs the same verified command. Do not use the
Python Run button on `manage.py` or start `runserver` with
`--settings=vedioos.local_settings` for team-account testing: that explicit offline
mode uses a separate SQLite user database, so shared client/editor credentials will
correctly be rejected there.

If a client deletes and recreates the same Supabase Auth identity while the private
BRIO profile still exists, an operator can safely restore the immutable link with
`manage.py reconcile_supabase_client --email client@example.com`. The command accepts
only one confirmed same-email Auth identity, preserves the existing client/profile and
project history, records an audit event, and refuses to overwrite a different link.

This is the required team command for shared testing. When `S3_ENDPOINT_URL` is loopback and storage is not already running, the command starts the repository's private storage automatically, initializes it, and stops that child service when the preview exits. It then verifies the database, schema, migration state, matching Supabase Auth project, transactional login/logout and role isolation, and a private-storage byte-integrity round trip before starting Django. It refuses to start against SQLite, an incomplete environment, the wrong auth/database binding, a failed login verifier, or unavailable storage. Use `--check-only` when you only want to verify the complete binding. In Supabase Studio, select schema **vedioos**; client/editor/admin credentials are hashed in `vedioos.users`, while Supabase Auth's `auth.users` records the separate email-OTP identity. A teammate can use the same application login only when this command passes against the same project. Git cannot distribute the ignored database URL, CA, storage credentials, or payment secret; supply the same approved `.env` values through the team's private secret channel.

External notification delivery is held by default. In-app notices work without a provider. After approving an email provider, sender domain, templates and notification policy, set `NOTIFICATION_EMAIL_ENABLED=true` and schedule this bounded command from a trusted worker:

```powershell
.venv/Scripts/python.exe manage.py dispatch_notifications --limit 100
```

New notices enter the retry-safe outbox. Older held notices require the explicit `--release-held` option; review their age and relevance before releasing them. Failed attempts use bounded exponential retry state, and current project access is checked immediately before sending.

| Area | Local URL | What to check |
| --- | --- | --- |
| Public landing | `/` | Service sections and responsive layout |
| Client | `/client/`, `/client/new-order/`, `/client/projects/`, `/client/payments/` | Verified registration, four-option brief, custom direction, separate private source/inspiration uploads and order history |
| Editor | `/editor/`, `/editor/revisions/`, `/editor/wallet/`, `/editor/availability/` | Assigned work, version submissions, revision queue and wallet |
| Admin | `/admin/`, `/admin/editors/`, `/admin/assignments/`, `/admin/pricing/`, `/admin/payouts/`, `/admin/earnings/` | Approval, allocation, catalog and earning settings |

Fresh local settings intentionally contain **no plan prices, payment gateway, assignment policy, review agreement or coin values**. Registration, drafts, uploads and role checks work immediately. Payment, assignment, review and wallet flows are exercised end to end by the isolated synthetic tests below. To explore them manually, configure the corresponding admin settings and development sandboxes first; never treat synthetic payments or payouts as real transactions. See [Phase 3](docs/PHASE_3.md), [Phase 4](docs/PHASE_4.md), [Phase 5](docs/PHASE_5.md) and [Phase 6](docs/PHASE_6.md).

Razorpay Test Mode is available as the hosted checkout adapter. Put a test key in the ignored `.env` as `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`, keep the official API base unchanged, and set `PAYMENT_MODE=razorpay_test`. The key ID must begin with `rzp_test_`; live keys are rejected by this mode. For Plan 1/2/3, Save and Proceed snapshots the administrator-configured fixed price and the checkout page moves directly from Project Files to Make Payment; the hosted gateway opens without a separate BRIO payment-method choice. Customize Your Edit retains its quotation, breakdown and explicit acceptance flow. In both paths, the backend creates the Razorpay order from the accepted server-owned snapshot, verifies the returned HMAC signature, fetches the payment from Razorpay, and records confirmation only when the captured amount, currency and order ID match. Test receipts remain labeled as test records and cannot be treated as production revenue. Team members must obtain credentials through the private team channel; credentials are never stored in Git.

For an end-to-end test when production prices are still undecided, an administrator can persist an explicitly test-only weighted policy. Amounts are integer minor units and must be supplied deliberately; the command has no price defaults:

```powershell
.venv/Scripts/python.exe manage.py configure_test_quotation --confirm-test-only --base-minor 75000 --point-minor 15000 --minimum-minor 100000 --maximum-minor 800000
```

This example means a ₹750 base, ₹150 per weighted point, ₹1,000 minimum and ₹8,000 maximum. It is a market-reference preview range for individual short-form edits; final business rates remain admin-managed. Preview policy values are identified as provisional and are rejected unless Django is in `DEBUG` with the sandbox or Razorpay test gateway. Replace the policy through `/admin/pricing/policy/` with owner-approved values and select `Production` before launch.

The custom-order estimate supports the existing custom base plus administrator-priced service mappings and an opt-in seven-feature weighted engine. Configure its base, per-point amount, min/max bounds, currency and weights under `/admin/pricing/policy/`; feature scores and multipliers are managed from `/admin/pricing/`. No production prices are seeded, and incomplete configuration keeps the weighted engine disabled rather than inventing a price. Configured custom submissions retain a server-owned estimate snapshot so later pricing edits apply prospectively.

Administrators may also prepare inactive monthly-package drafts from `/admin/pricing/`. Draft configuration does not publish or sell a subscription. Renewal, expiry, rollover, allowance accounting and dedicated-editor rules must be approved before that feature can be activated.

## Verify the whole application

Run these commands in **terminal C** from the repository root. `manage.py test` automatically uses `vedioos.test_settings` and a separate, temporary SQLite database; it does **not** drop or flush the preview database or Supabase. The optional browser tests below create synthetic accounts and fixtures in their own temporary database.

GitHub Actions checks Django configuration, migration drift, Ruff, the isolated backend suite, JavaScript syntax and reproducible vendored assets on every push and pull request. The workflow uses no repository secrets and cannot connect to Supabase or private storage. Real-storage and browser walkthroughs remain explicit local/integration checks because they require their isolated services.

### Backend, migrations and code checks

```powershell
.venv/Scripts/python.exe manage.py check --settings=vedioos.local_settings
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run --settings=vedioos.local_settings
.venv/Scripts/ruff.exe check .
.venv/Scripts/python.exe manage.py test
npm.cmd run check:javascript
npm.cmd run check:vendor
```

Audit an intended production configuration without printing secret values:

```powershell
.venv/Scripts/python.exe manage.py check_release
```

Use `--report-only` for a development baseline or `--json` for CI. A passing configuration audit does not replace the manual policy, provider, backup/restore, accessibility and end-to-end gates in [Phase 9](docs/PHASE_9.md).

Deployment probes are available at `/health/live/` for process liveness and `/health/ready/` for database/migration readiness. They return generic uncached JSON and do not verify external providers.

Verify the configured private-storage transport with synthetic bytes:

```powershell
.venv/Scripts/python.exe manage.py collect_release_evidence
.venv/Scripts/python.exe manage.py reconcile_accounts
.venv/Scripts/python.exe manage.py reconcile_assignments
.venv/Scripts/python.exe manage.py reconcile_audit_history
.venv/Scripts/python.exe manage.py reconcile_notification_outbox
.venv/Scripts/python.exe manage.py reconcile_commerce
.venv/Scripts/python.exe manage.py reconcile_communications
.venv/Scripts/python.exe manage.py reconcile_delivery
.venv/Scripts/python.exe manage.py reconcile_earnings
.venv/Scripts/python.exe manage.py check_private_storage
.venv/Scripts/python.exe manage.py reconcile_private_storage
.venv/Scripts/python.exe manage.py inventory_private_storage
.venv/Scripts/python.exe manage.py reconcile_workflows
```

`collect_release_evidence` is the recommended connected-environment summary. It verifies database/migration readiness, account/profile/session consistency, quote/order/payment consistency, the private Supabase schema and RLS, cross-record workflow consistency, and every ready private-storage record. It also verifies the latest manifested snapshot when one exists. Use `--json` for machine-readable output or `--report-only` to record failures without a nonzero exit. Add `--active-storage` only when a synthetic write exercise is intended.

`reconcile_accounts` checks role/profile relationships, editor availability/wallet foundations, administrator flags and authenticated sessions without printing names, emails, IDs or session keys. Existing active clients created before mandatory verification are aggregate lifecycle warnings; the command does not deactivate or rewrite accounts.

`reconcile_assignments` checks enabled policy completeness, admin complexity reviews, paid queue state, assignment snapshots, editor capacity and persistent round-robin pointers. It reports aggregate counts without printing project, editor or queue identifiers. It is read-only and does not classify projects, assign work or advance a rotation.

`reconcile_audit_history` checks that sensitive workflow records have the expected lifecycle events, that attributable actions have actors, and that nested audit details contain no credentials, URLs, message bodies or private media identifiers. Imported identities without historical onboarding events are reported as aggregate legacy warnings; the command never creates replacement history.

`reconcile_notification_outbox` checks the one-delivery-per-notice contract, held/pending/processing/retry/sent/cancelled state metadata, retry limits, expired leases, current recipient/project eligibility and safe error/provider references. It reports aggregate state counts without printing recipients or message content and never sends email.

`reconcile_commerce` checks quote snapshots, accepted-order terms, integer payment totals and currencies, payment-event evidence, payment state transitions, and paid consultation requests. It reports aggregate counts without printing commercial records or provider references. It is read-only and does not activate a gateway, collect money or invent prices.

`reconcile_communications` checks project-message authorship and audience rules plus private support-case ownership, state, opening messages and replies. It reports aggregate counts without printing message text or user, project, support or message identifiers. It is read-only and does not send notices, reply to clients or change case status.

`reconcile_delivery` checks submitted-version numbering and private-file links, assignment attribution, revision ownership/allowances/state, and explicit acceptance of the latest version. It reports aggregate counts without printing project, version or file identifiers. It is read-only and does not change project status, revise files or accept delivery.

`reconcile_earnings` checks accepted-work earning snapshots, append-only coin entries, wallet balances, redemption reservations and final payout records. It reports aggregate counts without printing wallet, project or payout identifiers. It is read-only and does not assign coin values, release earnings, enable redemptions or contact a payout provider.

`check_private_storage` requires bucket versioning, uploads a unique 128 KiB synthetic object, verifies its signed byte-identical download and anonymous denial, then removes every probe version. The storage reconciliation command performs a read-only comparison of every ready database file against its exact private object version, size and SHA-256 checksum. The inventory command paginates every immutable bucket version and compares it with database references; missing referenced media and leftover probes fail, while unreferenced versions and delete markers remain warnings until D02 defines retention. Workflow reconciliation checks payment activation, assignment eligibility, file/version/revision links and delivery acceptance. These commands omit credentials, signed URLs and private record identifiers from output.

Before an approved additive Supabase migration, capture and verify the ignored private row snapshot:

```powershell
.venv/Scripts/python.exe manage.py snapshot_database
.venv/Scripts/python.exe manage.py verify_database_snapshot --against-database
.venv/Scripts/python.exe manage.py rehearse_database_restore
```

The rehearsal verifies the manifest, migrates a disposable SQLite database, restores every captured row, checks schema columns, migration history, foreign keys and database integrity, then deletes the temporary database. It never writes to Supabase. The snapshot and `.sha256` manifest are migration safeguards containing private rows. They are not full PostgreSQL/media backups and must never be committed or shared through GitHub.

The last command runs the foundation, commerce, assignment, delivery and earnings backend suites. Browser and real-storage tests are intentionally opt-in, so run the commands in the next two sections for the complete check.

### Real private-storage integrity tests

With storage running and initialized in terminals A/B:

```powershell
$env:RUN_STORAGE_TESTS='1'
.venv/Scripts/python.exe manage.py test tests.test_storage_live

# Optional Edge check for custom-form validation, forced upload interruption, retry, limits and removal
$env:RUN_CUSTOM_FORM_BROWSER='1'
.venv/Scripts/python.exe manage.py test tests.test_custom_form_recovery_browser --settings=vedioos.test_settings
Remove-Item Env:RUN_STORAGE_TESTS
Remove-Item Env:RUN_CUSTOM_FORM_BROWSER
```

These tests upload synthetic bytes to the local private bucket, verify exact downloads, rejection of altered uploads, URL expiry and unauthorized access, then remove their test objects. They do not use client media.

### Browser walkthroughs in Microsoft Edge

The first walkthrough uses the **running local preview** and leaves its synthetic records in the local SQLite database for inspection. Create its separate local admin fixture once, then run it:

```powershell
.venv/Scripts/python.exe manage.py browser_fixture --settings=vedioos.local_settings
npm.cmd run test:browser
```

It checks registration, all three roles, a project, direct upload/download, authorization and mobile layout. The fixture credentials are stored in ignored `.runtime/browser-fixture.json`. Screenshots go to ignored `.runtime/screenshots/`.

Run the later feature walkthroughs one at a time. They each start their **own temporary Django test server** and database, so the main preview server is not required for these four commands. The delivery walkthrough does require terminal A's private storage service.

```powershell
$env:RUN_COMMERCE_BROWSER='1'
.venv/Scripts/python.exe manage.py test tests.test_commerce_browser
Remove-Item Env:RUN_COMMERCE_BROWSER

$env:RUN_ASSIGNMENT_BROWSER='1'
.venv/Scripts/python.exe manage.py test tests.test_assignment_browser
Remove-Item Env:RUN_ASSIGNMENT_BROWSER

$env:RUN_DELIVERY_BROWSER='1'
.venv/Scripts/python.exe manage.py test tests.test_delivery_browser
Remove-Item Env:RUN_DELIVERY_BROWSER

$env:RUN_EARNING_BROWSER='1'
.venv/Scripts/python.exe manage.py test tests.test_earning_browser
Remove-Item Env:RUN_EARNING_BROWSER

$env:RUN_PHASE7_BROWSER='1'
.venv/Scripts/python.exe manage.py test tests.test_phase7_browser
Remove-Item Env:RUN_PHASE7_BROWSER
```

These cover admin catalog → client quote → signed sandbox payment; complexity/round-robin assignment and reassignment; draft → revision → version acceptance with byte-identical private downloads; coin release → reservation → failed/paid **sandbox** outcomes; and mobile direct upload plus project-message isolation. The synthetic browser tests do not charge cards or transfer money. Inspect `.runtime/screenshots/` for desktop/mobile captures.

### Optional checks against the shared Supabase database

The local setup above needs **no Supabase access**. Only teammates who have separately received the dedicated server-side database URL and trusted CA should use this section. Never paste credentials into code, tickets or commits. Follow [the private schema and connection guide](docs/SUPABASE.md). Set `DATABASE_URL`, `DATABASE_SCHEMA=vedioos` and `POSTGRES_SSLROOTCERT` in your ignored `.env`; keep local SeaweedFS separate because media is not shared by the database connection.

These are read-only or rollback/synthetic verification commands against the **configured PostgreSQL database**. The concurrency commands require `DEBUG=true`, remove only their exact synthetic fixtures and should be coordinated with the team if live policies have been activated:

```powershell
.venv/Scripts/python.exe manage.py check_database
.venv/Scripts/python.exe manage.py audit_database_security
.venv/Scripts/python.exe manage.py migrate --check
.venv/Scripts/python.exe manage.py verify_cloud
.venv/Scripts/python.exe manage.py verify_commerce_cloud
.venv/Scripts/python.exe manage.py verify_assignment_concurrency
.venv/Scripts/python.exe manage.py verify_delivery_concurrency
.venv/Scripts/python.exe manage.py verify_wallet_concurrency
```

For an operator-run Phase 7 deadline alert pass, use `.venv/Scripts/python.exe manage.py notify_overdue` against the intended database. It writes in-app notices only for paid, open projects with a recorded past deadline; rerunning it does not duplicate the same alert. No automatic schedule is configured yet.

`check_database` should identify PostgreSQL, the private `vedioos` schema, RLS on all application tables and no browser-role schema access. `audit_database_security` additionally fails on elevated runtime-role privileges, unbounded connections, schema/table ownership drift, public or browser grants, missing RLS, and unsafe default grants. It prints the extension/version/schema inventory needed for recovery planning without printing credentials or private rows. The shared database is already migrated. **Do not run `migrate`, `flush`, `browser_fixture` or `init_local` against it just to preview the app.** Schema changes follow the backup, review and migration procedure in [team workflow](docs/TEAM_WORKFLOW.md). The optional `node tests/cloud_browser.mjs` script expects an existing synthetic admin fixture and existing projects in that specific shared project; a fresh clone will not have those credentials, so it is not part of the standard checks.

### Stay current with the team

On a clean integration branch, update without overwriting teammates' changes:

```powershell
git status
git fetch origin
git pull --ff-only origin codex/foundation-and-commerce
```

Hamsa owns Client + Core Platform; Dheeraj owns Admin + Editor Operations. Follow [AGENTS.md](AGENTS.md), [the pathway](docs/ROADMAP.md) and [the team workflow](docs/TEAM_WORKFLOW.md) before changing shared models or migrations. Push verified major changes with code, migrations and docs together. Keep secrets and real client media out of Git.

## Repository layout

```text
core/          Hamsa: identity, client/project models, auth, permissions, S3 endpoints
operations/    Dheeraj: operational models, editor application, admin/editor routes
vedioos/       Django settings and URL routing
templates/     Landing, auth, client, editor, and admin server-rendered pages
static/        Responsive styling, direct upload/download JS, licensed hash library
scripts/       Local setup, verified storage installation, and startup helpers
tests/         Foundation, real storage, and browser checks
docs/          Requirements, decisions, pathway, architecture, and evidence
```

## Release definition

The first version includes all 28 priorities in original brief section 34. A landing page, mocked checkout, manual-only assignment, or incomplete wallet is an intermediate milestone. A production release requires the end-to-end and security gates in the roadmap, configured business terms, and working production integrations.
