// Stripe classic Elements (cardNumber, cardExpiry, cardCvc)
export async function initStripeCheckout() {
  const startBtn = document.getElementById('start-checkout'); // pricing page button (now optional)
  const directPayBtn = document.getElementById('stripe-pay');  // checkout page button
  let stripe, elements, cardNumber, cardExpiry, cardCvc;

  async function ensureStripe() {
    if (stripe && elements && cardNumber && cardExpiry && cardCvc) return { stripe, elements };
    const cfgResp = await fetch('/billing/config');
    const cfg = await cfgResp.json();
    if (!cfg.publishableKey) { console.error('Stripe not configured'); return null; }
    if (!window.Stripe) {
      await new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = 'https://js.stripe.com/v3';
        s.onload = resolve; s.onerror = reject; document.head.appendChild(s);
      });
    }
    stripe = window.Stripe(cfg.publishableKey);
    elements = stripe.elements();
    const style = { base: { fontSize: '16px', color: '#fff', '::placeholder': { color: '#999' } } };
    if (document.getElementById('card-number-element') && !cardNumber) {
      cardNumber = elements.create('cardNumber', { style });
      cardNumber.mount('#card-number-element');
    }
    if (document.getElementById('card-expiry-element') && !cardExpiry) {
      cardExpiry = elements.create('cardExpiry', { style });
      cardExpiry.mount('#card-expiry-element');
    }
    if (document.getElementById('card-cvc-element') && !cardCvc) {
      cardCvc = elements.create('cardCvc', { style });
      cardCvc.mount('#card-cvc-element');
    }
    const errorBox = document.getElementById('stripe-error');
    if (cardNumber && errorBox) {
      cardNumber.on('change', function(event) {
        if (event.error) { errorBox.textContent = event.error.message; errorBox.style.display = 'block'; }
        else { errorBox.style.display = 'none'; }
      });
    }
    return { stripe, elements };
  }

  // Checkout page flow: mount immediately and prepare intent
  if (directPayBtn) {
    const ready = await ensureStripe();
    if (!ready) return;
    const amount = 899, currency = 'usd';
    const resp = await fetch('/billing/create-payment-intent', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ amount_cents: amount, currency }) });
    const data = await resp.json();
    if (!data.clientSecret) { console.error('PI error', data); return; }
    const errorBox = document.getElementById('stripe-error');
    directPayBtn.onclick = async () => {
      directPayBtn.disabled = true;
      const { error, paymentIntent } = await stripe.confirmCardPayment(data.clientSecret, { payment_method: { card: cardNumber } });
      if (error) { errorBox.textContent = error.message || 'Payment failed'; errorBox.style.display='block'; directPayBtn.disabled=false; return; }
      if (paymentIntent && paymentIntent.status === 'succeeded') {
        await fetch('/billing/success', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ payment_intent_id: paymentIntent.id }) });
        window.location.href = '/me/dashboard';
      }
    };
  }
}

document.addEventListener('DOMContentLoaded', () => {
  try { initStripeCheckout(); } catch (e) { console.error(e); }
  // No local modals; management is done via Stripe Customer Portal
});


