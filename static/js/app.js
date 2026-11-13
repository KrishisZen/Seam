document.addEventListener('DOMContentLoaded', () => {
  const input = document.querySelector('[data-image-input]');
  if (input) input.addEventListener('change', () => {
    const label = document.querySelector('[data-file-name]');
    if (label) label.textContent = input.files.length ? input.files[0].name : '';
  });
  document.querySelectorAll('.color-input input').forEach((field) => {
    field.addEventListener('input', () => {
      const swatch = field.parentElement.querySelector('.swatch-preview');
      if (swatch && /^#[0-9a-f]{6}$/i.test(field.value.trim())) swatch.style.setProperty('--swatch', field.value.trim());
    });
  });
});
