document.addEventListener('DOMContentLoaded', () => {
  const input = document.querySelector('[data-image-input]');
  const editor = document.querySelector('[data-selection-editor]');
  const canvas = document.querySelector('[data-selection-canvas]');
  const boxField = document.querySelector('[data-garment-box]');
  const help = document.querySelector('[data-selection-help]');
  let image = null;
  let start = null;
  let selection = null;

  if (input && editor && canvas && boxField) {
    const context = canvas.getContext('2d');
    const draw = () => {
      if (!image) return;
      context.clearRect(0, 0, canvas.width, canvas.height);
      context.drawImage(image, 0, 0, canvas.width, canvas.height);
      if (selection) {
        context.fillStyle = 'rgba(30, 34, 27, .38)';
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.save();
        context.beginPath();
        context.rect(selection.x, selection.y, selection.w, selection.h);
        context.clip();
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        context.restore();
        context.strokeStyle = '#fff';
        context.lineWidth = 2;
        context.setLineDash([7, 4]);
        context.strokeRect(selection.x, selection.y, selection.w, selection.h);
        context.setLineDash([]);
      }
    };
    const canvasPoint = (event) => {
      const bounds = canvas.getBoundingClientRect();
      return {x: (event.clientX - bounds.left) * canvas.width / bounds.width,
              y: (event.clientY - bounds.top) * canvas.height / bounds.height};
    };
    input.addEventListener('change', () => {
      const label = document.querySelector('[data-file-name]');
      if (label) label.textContent = input.files.length ? input.files[0].name : '';
      selection = null;
      boxField.value = '';
      if (!input.files.length) {
        editor.hidden = true;
        return;
      }
      image = new Image();
      image.onload = () => {
        const imageScale = Math.min(1, 640 / Math.max(image.naturalWidth, image.naturalHeight));
        canvas.width = Math.round(image.naturalWidth * imageScale);
        canvas.height = Math.round(image.naturalHeight * imageScale);
        editor.hidden = false;
        if (help) help.textContent = 'Drag a close box around the garment. Leaving it empty uses automatic detection.';
        draw();
      };
      image.src = URL.createObjectURL(input.files[0]);
    });
    canvas.addEventListener('pointerdown', (event) => {
      if (!image) return;
      canvas.setPointerCapture(event.pointerId);
      start = canvasPoint(event);
      selection = {x: start.x, y: start.y, w: 1, h: 1};
      draw();
    });
    canvas.addEventListener('pointermove', (event) => {
      if (!start) return;
      const point = canvasPoint(event);
      const x = Math.min(start.x, point.x);
      const y = Math.min(start.y, point.y);
      selection = {x, y, w: Math.abs(point.x - start.x), h: Math.abs(point.y - start.y)};
      draw();
    });
    canvas.addEventListener('pointerup', () => {
      if (!start || !selection) return;
      start = null;
      if (selection.w < 12 || selection.h < 12) {
        selection = null;
        boxField.value = '';
        if (help) help.textContent = 'No box selected; automatic detection will be used.';
      } else {
        const x = selection.x / canvas.width;
        const y = selection.y / canvas.height;
        const w = selection.w / canvas.width;
        const h = selection.h / canvas.height;
        boxField.value = [x, y, w, h].map((part) => part.toFixed(5)).join(',');
        if (help) help.textContent = 'Selection set. Submit to analyze these pixels.';
      }
      draw();
    });
    document.querySelector('[data-clear-selection]')?.addEventListener('click', () => {
      selection = null;
      boxField.value = '';
      if (help) help.textContent = 'Automatic detection selected. Drag a box again if the cutout needs help.';
      draw();
    });
  } else if (input) {
    input.addEventListener('change', () => {
      const label = document.querySelector('[data-file-name]');
      if (label) label.textContent = input.files.length ? input.files[0].name : '';
    });
  }

  document.querySelectorAll('.color-input input').forEach((field) => {
    field.addEventListener('input', () => {
      const swatch = field.parentElement.querySelector('.swatch-preview');
      if (swatch && /^#[0-9a-f]{6}$/i.test(field.value.trim())) swatch.style.setProperty('--swatch', field.value.trim());
    });
  });

  const categorySelect = document.querySelector('select[name="category"]');
  const categoryOptions = document.querySelectorAll('[data-category-option]');
  if (categorySelect && categoryOptions.length) {
    const updateCategoryFields = () => {
      const category = categorySelect.value;
      const type = ['Tops', 'Bottoms', 'Outerwear'].includes(category) ? 'apparel'
        : category === 'Footwear' ? 'footwear'
        : category === 'Accessories' ? 'accessories' : '';
      categoryOptions.forEach((option) => {
        const visible = option.dataset.categoryOption === type;
        option.hidden = !visible;
        option.querySelector('[data-category-control]')?.toggleAttribute('disabled', !visible);
      });
    };
    categorySelect.addEventListener('change', updateCategoryFields);
    updateCategoryFields();
  }

  document.querySelectorAll('input[type="file"][multiple]').forEach((field) => {
    field.addEventListener('change', () => {
      const summary = document.querySelector('[data-batch-summary]');
      if (!summary) return;
      const count = Array.from(document.querySelectorAll('input[type="file"][multiple]'))
        .reduce((sum, upload) => sum + (upload.files ? upload.files.length : 0), 0);
      if (count) summary.textContent = `${count} photo${count === 1 ? '' : 's'} selected${count > 25 ? ' (maximum is 25)' : ''}.`;
      else summary.textContent = 'No photos selected yet.';
    });
  });

  const toast = document.querySelector('[data-validation-toast]');
  const toastMessage = document.querySelector('[data-validation-message]');
  let toastTimer;
  const showToast = (message) => {
    if (!toast || !toastMessage) return;
    toastMessage.textContent = message;
    toast.hidden = false;
    requestAnimationFrame(() => toast.classList.add('visible'));
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toast.classList.remove('visible');
      setTimeout(() => { toast.hidden = true; }, 250);
    }, 7000);
  };
  document.querySelector('[data-dismiss-validation]')?.addEventListener('click', () => {
    clearTimeout(toastTimer);
    toast.classList.remove('visible');
    setTimeout(() => { toast.hidden = true; }, 250);
  });

  const tooltipButtons = Array.from(document.querySelectorAll('[data-tooltip-trigger]'));
  const closeTooltips = (except = null) => {
    tooltipButtons.forEach((button) => {
      if (button !== except) button.setAttribute('aria-expanded', 'false');
    });
  };
  tooltipButtons.forEach((button) => {
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      const shouldOpen = button.getAttribute('aria-expanded') !== 'true';
      closeTooltips(button);
      button.setAttribute('aria-expanded', String(shouldOpen));
    });
  });
  document.addEventListener('click', (event) => {
    if (!event.target.closest('[data-tooltip-trigger]')) closeTooltips();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      closeTooltips();
      if (document.activeElement.matches('[data-tooltip-trigger]')) document.activeElement.blur();
    }
  });

  document.querySelectorAll('[data-inline-validate]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      const missing = [];
      let firstInvalid = null;
      form.querySelectorAll('[required]').forEach((field) => {
        const invalid = field.type === 'checkbox' ? !field.checked : !String(field.value || '').trim();
        if (!invalid) return;
        firstInvalid ||= field;
        const label = field.closest('label');
        label?.classList.add('field-invalid');
        if (label && !label.querySelector('[data-inline-error]')) {
          const message = document.createElement('span');
          message.className = 'inline-field-error';
          message.dataset.inlineError = 'true';
          message.textContent = `Please enter ${field.dataset.requiredLabel || 'a value'}.`;
          label.append(message);
        }
        missing.push(field.dataset.requiredLabel || 'a required field');
      });
      form.querySelectorAll('[data-required-checkbox-group]').forEach((group) => {
        if (group.querySelector('input[type="checkbox"]:checked')) return;
        firstInvalid ||= group.querySelector('input[type="checkbox"]');
        group.classList.add('group-invalid');
        if (!group.nextElementSibling?.matches('[data-inline-error]')) {
          const message = document.createElement('p');
          message.className = 'inline-field-error group-error';
          message.dataset.inlineError = 'true';
          message.textContent = 'Select at least one garment for this outfit.';
          group.insertAdjacentElement('afterend', message);
        }
        missing.push('at least one garment');
      });
      const files = form.querySelectorAll('input[type="file"]');
      if (form.querySelector('[data-required-file-group]') && !Array.from(files).some((field) => field.files?.length)) {
        const group = form.querySelector('[data-required-file-group]');
        group.classList.add('field-invalid');
        if (!form.querySelector('[data-file-inline-error]')) {
          const message = document.createElement('p');
          message.className = 'inline-field-error group-error';
          message.dataset.fileInlineError = 'true';
          message.textContent = 'Choose at least one photo or folder.';
          group.insertAdjacentElement('afterend', message);
        }
        missing.push('a photo');
      }
      if (missing.length) {
        event.preventDefault();
        showToast(`Please complete: ${Array.from(new Set(missing)).join(', ')}.`);
        firstInvalid?.focus({preventScroll: true});
        firstInvalid?.scrollIntoView({behavior: 'smooth', block: 'center'});
      }
    });
    form.addEventListener('input', clearFieldError);
    form.addEventListener('change', clearFieldError);
  });

  function clearFieldError(event) {
    const field = event.target;
    const label = field.closest('label');
    if (label) {
      label.classList.remove('field-invalid');
      label.querySelector('[data-inline-error]')?.remove();
    }
    const group = field.closest('[data-required-checkbox-group]');
    if (group && group.querySelector('input[type="checkbox"]:checked')) {
      group.classList.remove('group-invalid');
      group.nextElementSibling?.matches('[data-inline-error]') && group.nextElementSibling.remove();
    }
    if (field.type === 'file' && field.files?.length) {
      document.querySelector('[data-required-file-group]')?.classList.remove('field-invalid');
      document.querySelector('[data-file-inline-error]')?.remove();
    }
  }

  const dialog = document.querySelector('[data-delete-dialog]');
  const dialogMessage = dialog?.querySelector('[data-delete-message]');
  const dialogConfirm = dialog?.querySelector('[data-delete-confirm]');
  let deleteForm = null;
  const selectedForDelete = (form) => form.id === 'bulk-delete-form'
    ? document.querySelectorAll('input[name="garment_ids"][form="bulk-delete-form"]:checked')
    : form.querySelectorAll('input[name="garment_ids"]:checked');
  document.querySelectorAll('form[data-delete-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      if (form.id === 'bulk-delete-form' && !selectedForDelete(form).length) {
        showToast('Select at least one garment to delete.');
        return;
      }
      deleteForm = form;
      const count = selectedForDelete(form).length;
      dialogMessage.textContent = count
        ? `Delete ${count} selected garment${count === 1 ? '' : 's'} and remove them from saved outfits? This cannot be undone.`
        : (form.dataset.deleteMessage || 'This action cannot be undone.');
      dialogConfirm.textContent = form.dataset.deleteLabel || 'Delete';
      dialog.showModal();
    });
  });
  dialog?.querySelector('[data-delete-cancel]')?.addEventListener('click', () => dialog.close());
  dialogConfirm?.addEventListener('click', () => {
    if (deleteForm) deleteForm.submit();
  });

  const garmentChecks = Array.from(document.querySelectorAll('.garment-select'));
  const selectAll = document.querySelector('[data-select-all]');
  const countLabel = document.querySelector('[data-selected-count]');
  const bulkDeleteButton = document.querySelector('[data-bulk-delete-button]');
  const updateSelection = () => {
    const selectedCount = garmentChecks.filter((checkbox) => checkbox.checked).length;
    if (countLabel) countLabel.textContent = `${selectedCount} selected`;
    if (bulkDeleteButton) bulkDeleteButton.hidden = selectedCount === 0;
    if (selectAll) {
      selectAll.checked = selectedCount > 0 && selectedCount === garmentChecks.length;
      selectAll.indeterminate = selectedCount > 0 && selectedCount < garmentChecks.length;
    }
  };
  garmentChecks.forEach((checkbox) => checkbox.addEventListener('change', updateSelection));
  selectAll?.addEventListener('change', () => {
    garmentChecks.forEach((checkbox) => { checkbox.checked = selectAll.checked; });
    updateSelection();
  });

  document.querySelectorAll('[data-rename-toggle]').forEach((button) => {
    button.addEventListener('click', () => {
      const card = button.closest('.garment-info');
      const display = card.querySelector('.name-display');
      const form = card.querySelector('.rename-form');
      display.hidden = true;
      form.hidden = false;
      form.querySelector('input[name="name"]').focus();
      form.querySelector('input[name="name"]').select();
    });
  });
  document.querySelectorAll('[data-cancel-rename]').forEach((button) => {
    button.addEventListener('click', () => {
      const card = button.closest('.garment-info');
      card.querySelector('.rename-form').reset();
      card.querySelector('.rename-form').hidden = true;
      card.querySelector('.name-display').hidden = false;
      card.querySelector('.rename-form').classList.remove('field-invalid');
      card.querySelector('[data-inline-error]')?.remove();
    });
  });
});
