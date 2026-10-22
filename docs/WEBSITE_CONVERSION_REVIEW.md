# Membership and referral journey review

**Review date:** October 22, 2026, America/Los_Angeles.  
**Status:** review-ready website edit specification plus an offline, synthetic journey model. No website edit, deployment, real enrollment, payment, refund, provider verification or customer-data storage was performed by this implementation.

## Observed public behavior and proposed changes

Public pages were read on October 22. The AI Evolutionary Evolutions pages below and the funding business-line-of-credit page were marked crawled that day. The funding homepage extract was marked four weeks old. Public page retrieval does not verify Hostinger administration, delivery of contact forms, billing, member access, or referral tracking.

| Page | Observed behavior | Concrete edit specification |
|---|---|---|
| [Membership](https://aievolutionaryevolutions.com/membership) | Both the $5/month Join button and the five-day challenge button lead to the general Contact page. | Keep the current inquiry destination and change button text to **Ask About $5/Month Membership** and **Request the Free 5-Day Challenge**. Use the supporting copy below. A checkout label can return only after its actual destination and operation are verified. |
| [Contact](https://aievolutionaryevolutions.com/contact) | The destination contains name/email/message inputs and a general inquiry submit button. | Identify the selected request clearly. A success message must reflect a real backend acknowledgement; do not announce paid membership or immediate access from an inquiry submission. |
| [Home](https://aievolutionaryevolutions.com/) and [Membership](https://aievolutionaryevolutions.com/membership) | Home/footer describe weekly build sessions, while the membership benefits describe monthly interactive sessions. | Confirm the actual delivery schedule. Pending that confirmation, replace both frequency claims with **Build sessions — ask about the current schedule before enrolling.** Do not choose weekly or monthly without evidence. |
| [Projects](https://aievolutionaryevolutions.com/projects) | Hermes Fabric and MemPalace are research/in-development concepts. | Preserve that stage. Claims of deployed shared memory, self-repair or account-to-account AI synchronization require separate runtime evidence. |
| [Affiliate program](https://aievolutionaryevolutions.com/affiliate) | Requires active membership, terms acceptance and manual approval; distinguishes the internal program from Hostinger's program. | Preserve those distinctions. Label the CTA **Request Affiliate Program Review** when it leads to an inquiry form. Do not describe a submitted inquiry as partner approval. |
| [Funding business line of credit](https://lippytmai.getbizfunds.com/business-line-of-credit-7841) | One FAQ answer uses $4,000/month and another uses $5,000/month as minimum revenue. | Obtain current product-specific requirements from the provider. Until confirmed, remove both unsupported threshold claims and use the replacement copy below. Do not select either number by inference. |
| [Funding homepage](https://lippytmai.getbizfunds.com/) | In the older retrieved homepage, Invoice Factoring's Read More link leads to the business line of credit page. The destination was confirmed by following that link. | Recheck the current homepage in the editor. If still present, change only the Invoice Factoring card link to the existing [Invoice Factoring page](https://lippytmai.getbizfunds.com/invoice-factoring-2609), then verify its displayed heading and keyboard activation. |

### Copy ready for the existing inquiry route

**Membership card**

> Founding Builder Membership — $5/month. Send an inquiry for membership details and the current build-session schedule. Submitting this form does not create a subscription or take a payment.

Button: **Ask About $5/Month Membership** → existing `/contact` destination.

**Free challenge card**

> Request access to the free five-day beginner challenge through our contact form. No payment is required to submit your inquiry.

Button: **Request the Free 5-Day Challenge** → existing `/contact` destination.

**Funding requirements FAQ replacement, pending provider confirmation**

> Eligibility requirements vary by provider and funding product. Ask the provider to confirm the current business-history, revenue and other requirements for the option you are considering. An inquiry is not an approval or a guarantee of funding.

This is proposed wording for the existing pages. No provider policy, eligibility threshold, session cadence, commission rate or new refund policy is established by this document. Existing refund-policy claims and terms links must be reconciled with the actual approved membership terms before checkout is launched.

## Accessible inquiry form acceptance criteria

These are implementation requirements for the existing Hostinger page or a supported form integration, not claims that the present form already satisfies them.

1. Every input has a visible programmatically associated label. Required fields are identified in text. Email uses the correct type and autocomplete. Name and message are optional unless operationally necessary.
2. The request purpose is visible: membership information, free challenge, funding-customer inquiry, or referral-partner inquiry. Customer funding and partner recruitment must never share an ambiguous submission label.
3. All controls work with a keyboard, focus is visible, and focus moves to a useful error summary after an unsuccessful submission. Errors are associated with the affected input and do not erase valid entries.
4. Service-request wording explains how submitted details are used to answer that request. **Optional marketing** uses a distinct, initially unchecked choice. Declining or later withdrawing marketing permission must not prevent a requested service response or cancel a paid membership.
5. The displayed operator and linked privacy/terms documents must match the actual service. Use the real, reviewed documents; do not add invented policy URLs.
6. The form does not solicit passwords, card data, government identifiers, credit reports or detailed financing records. Financial applications remain on the appropriate provider's supported flow.
7. A success message is announced accessibly only after a real, accepted submission. A backend failure must present a retry/help state without fabricating a received request, enrollment, payment or entitlement.
8. The inquiry confirmation says **Request received** only when receipt is confirmed. It does not say **Membership active**, **Payment successful**, **Funding approved** or **Affiliate approved**.
9. Confirm the actual destination on desktop and mobile. Verify labels, zoom/reflow, error handling, screen-reader announcements, and focus order in the supported published environment before marking the form accepted.

## Offline journey contract

Implementation: `control_tower/journeys.py`. Example: `examples/membership_journey.json`.

```python
import json
from pathlib import Path
from control_tower.journeys import reconcile_journeys

events = json.loads(Path("examples/membership_journey.json").read_text())
report = reconcile_journeys(events)
assert report["mode"] == "synthetic_only"
assert report["external_actions"] == 0
```

All events are flat, allowlisted fixtures. They require `event_id`, `journey_id`, `kind`, `event_type`, timezone-aware `occurred_at`, `source`, and literal `synthetic: true`. IDs must begin `synthetic-` and satisfy a bounded ASCII pattern. Unknown fields, nested values and unbounded free text are rejected. Only approved source labels and fixed provider destinations are accepted; no user-supplied redirect URLs are evaluated.

| Event type | Additional fields | State effect in the fixture model |
|---|---|---|
| `member_signup` | `service_consent: true`; optional Boolean `marketing_opt_in` (defaults false) | Creates an unpaid signup with no access. |
| `member_payment_confirmed` | Synthetic `payment_id` and `provider_event_id`, `confirmation_kind: simulated_provider`, positive integer `amount_minor`, `currency: USD` | Records one simulated provider confirmation for an existing unpaid signup. |
| `member_access_granted` | Matching `payment_id` and synthetic `entitlement_id` | Grants simulated access only after the matching simulated payment. |
| `member_cancelled` | None | Immediately revokes simulated access; does not fabricate a refund. |
| `member_refunded` | Payment fields with the original payment ID and full original amount, plus a distinct synthetic provider event ID | Records a full simulated refund and revokes simulated access. Partial refunds and proration are unsupported. |
| `marketing_preference_updated` | Boolean `marketing_opt_in` | Updates optional marketing preference without changing service access. |
| `funding_referral_click` | `kind: funding_customer`, service consent, optional marketing choice, a customer provider key | Records a customer redirect candidate, not a completed application or funded loan. |
| `funding_partner_signup` | `kind: funding_partner`, service consent, optional marketing choice, a partner provider key | Records a partner request, not provider approval or commission. |

Customer provider keys are `getbizfunds` and `7figures_customer`. Partner keys are `lendtrack_partner` and `7figures_partner`. These map to the existing user-supplied destinations in `control_tower/funnels.py`. Their presence in code does not prove referral attribution or provider authorization. The exact 7 Figures affiliate link and LendTrack join route could not be verified by the public retrieval check; that is not proof of downtime.

### Reconciliation rules

- Processing is bounded to 1,000 input fixtures and happens only in memory.
- Exact event-ID and provider-event-ID retries are duplicates. Conflicting reuse is rejected. Reused payment receipts cannot fund another journey.
- Events are processed in their supplied delivery order. A nonduplicate event earlier than a journey's last accepted timestamp is rejected, not silently reordered. Equal timestamps retain supplied order.
- Rejected events do not change accepted state. Reports contain sanitized error codes, not rejected payload values.
- Changing optional marketing preference does not manufacture service consent or alter paid access.
- This is deliberately a one-payment, full-refund model. Immediate cancellation revocation is a **fixture assumption**, not an adopted production cancellation policy. Renewals, paid-through dates, cancellations at period end, taxes, fees, partial refunds, chargebacks and external reconciliation need a separate provider-backed design.
- Reported amounts and counts are explicitly synthetic. Live memberships, revenue and commissions remain `unavailable`. A simulated confirmation neither authenticates a provider nor proves that a real webhook was received.

## Acceptance evidence and remaining deployment gates

Focused checks are in `tests/test_journeys.py`. They cover paid access without marketing opt-in, service consent, unpaid access, receipt matching, provider/event replay, conflicting identities, receipt reuse, cancellation, refund matching, marketing opt-out, role-specific referrals, out-of-order events and nested sensitive data.

Before connecting real billing or member access, independently verify the provider's supported integration, credential scope, server-side webhook authentication, replay protection, durable idempotency, identity-to-subscription matching, price/currency, signed-in access checks and actual cancellation/refund policy. The fixture validator supplies none of those production guarantees.

Website publication remains a separate step using the existing site's supported editor and reviewed destinations. Recheck the older funding homepage finding before changing it. Record the resulting page version, actual form acknowledgement and supported rollback after publication.
