// Fade-in effect for page transitions
window.addEventListener('DOMContentLoaded', () => {
  document.body.classList.add('fade-in');
});

// Show spinner on form submit
function showSpinnerOnSubmit(formSelector) {
  const form = document.querySelector(formSelector);
  if (form) {
    form.addEventListener('submit', function() {
      let spinner = document.createElement('div');
      spinner.className = 'spinner';
      form.appendChild(spinner);
    });
  }
}
// Usage: showSpinnerOnSubmit('form'); 