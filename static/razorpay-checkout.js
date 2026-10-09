const razorpayForm = document.getElementById('razorpay-test-checkout');

if (razorpayForm) {
  const button = razorpayForm.querySelector('button');
  const status = razorpayForm.querySelector('[role="status"]');
  const csrfToken = razorpayForm.querySelector('[name="csrfmiddlewaretoken"]').value;
  const report = (message, failed = false) => {
    status.textContent = message;
    status.setAttribute('role', failed ? 'alert' : 'status');
  };
  button.addEventListener('click', () => {
    if (typeof window.Razorpay !== 'function') {
      report('Razorpay Test Checkout could not load. Check your connection and try again.', true);
      return;
    }
    const checkout = new window.Razorpay({
      key: razorpayForm.dataset.key,
      amount: Number(razorpayForm.dataset.amount),
      currency: razorpayForm.dataset.currency,
      name: 'VedioOS',
      description: 'Video editing order — test payment',
      order_id: razorpayForm.dataset.orderId,
      prefill: {
        name: razorpayForm.dataset.clientName,
        email: razorpayForm.dataset.clientEmail,
      },
      theme: {color: '#173f35'},
      modal: {ondismiss: () => report('Test checkout closed. No payment was recorded.')},
      handler: async response => {
        button.disabled = true;
        report('Verifying the captured test payment…');
        try {
          const result = await fetch(razorpayForm.dataset.confirmUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
            body: JSON.stringify({
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_order_id: response.razorpay_order_id,
              razorpay_signature: response.razorpay_signature,
            }),
          });
          const body = await result.json();
          if (!result.ok) throw new Error(body.error || 'The test payment could not be verified.');
          window.location.assign(body.redirect);
        } catch (error) {
          report(error.message, true);
          button.disabled = false;
        }
      },
    });
    checkout.on('payment.failed', () => report('The Razorpay test payment failed. Try again.', true));
    checkout.open();
  });
}
