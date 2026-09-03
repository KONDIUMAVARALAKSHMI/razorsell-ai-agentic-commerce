# Demo Script (5 minutes)

Setup beforehand: `docker compose up --build` (or the local dev setup in the README), backend seeded, both apps open in the browser — customer shop at `http://localhost:5173`, merchant dashboard logged in at `http://localhost:5173/merchant/overview` in a second tab.

## 0:00–0:30 — Problem

> "Merchants lose revenue because customers have to already know exactly what they want before they can even start checking out. RazorSell AI turns that into a conversation — but the part I actually want to show you is what happens *underneath* the conversation, because letting an AI agent get anywhere near a checkout flow is exactly the kind of thing that goes wrong quietly."

## 0:30–1:30 — Understanding &amp; recommendation

In the customer chat, type:

> "I need a laptop under 70000 for coding and gaming, something portable"

Point out: the "understood intent" line, the grounded product cards (real prices, real specs), and that each card's explanation cites something checkable — budget fit, use-case tags, portability score. Click **Compare** on two results to show the comparison table.

## 1:30–2:15 — Selection &amp; cross-sell

Click **Add to cart** on the top recommendation. The upsell card appears — point out it's capped (never more than 2 per checkout) and that it's an accept/reject action, not something silently added. Click **Add it**.

## 2:15–3:00 — Deterministic pricing

Open the cart panel. Emphasize: this subtotal was computed server-side from the live database, not from anything the chat model said. Click **Review checkout**.

## 3:00–3:30 — Explicit confirmation → Razorpay Test order

Show the order summary modal — every line item, the total, the "Razorpay Test Mode - no real money moves" notice. Click **Confirm & Proceed to Payment**.

> "That confirm click is the only thing in this entire codebase that can cause a payment order to be created. The AI never sees a tool that can do this on its own."

## 3:30–4:15 — Forced failure → graceful recovery

In the payment result panel, click **Force failure** (mock provider, clearly labeled as simulated in the UI).

> "The payment failed. Watch what doesn't happen: no duplicate order, no lost cart, no silent retry."

Point out the message: *"No additional payment has been initiated. Your order is still safe."* Click **Retry payment** → **Force success**. Order now shows `SUCCESS`.

## 4:15–4:45 — Audit trail

Switch to the merchant dashboard's **Audit trail** tab. Filter by the order id (visible in the payment result panel). Walk through the ledger top to bottom: `CHECKOUT_STARTED` → `USER_PAYMENT_CONFIRMATION` → `RAZORPAY_ORDER_CREATED` → `PAYMENT_ATTEMPTED` → `PAYMENT_FAILED` (with the simulated failure reason) → `RETRY_REQUESTED` → `PAYMENT_ATTEMPTED` → `PAYMENT_SUCCESS`. Every actor tag (`USER` / `AI` / `SYSTEM` / `RAZORPAY`) is visible per event.

Optionally: open **Failure center** to show the same failure surfaced in a merchant-facing, action-oriented view.

## 4:45–5:00 — Metrics

Switch to **Overview**. Point at real numbers computed from the database this session just wrote to — conversion rate, average order value, upsell acceptance, payment failures vs. successful recoveries. Mention the 105-scenario evaluation suite runs the same flows in batch and reports honestly, including the 5 known failures attributable to the demo AI parser (not to anything financial).

Close:

> "The goal isn't to let an AI move money freely. The goal is to let AI improve commerce while deterministic systems keep money movement safe, bounded, and auditable."
