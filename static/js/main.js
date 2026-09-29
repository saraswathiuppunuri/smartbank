/**
 * SmartBank Core Interactive JavaScript
 */

document.addEventListener('DOMContentLoaded', function () {
    // 1. Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            try {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            } catch (e) {
                // Ignore if already closed
            }
        }, 5000);
    });

    // 2. Initialize Bootstrap Tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // 3. Beneficiary Quick-Select on Fund Transfer Page
    const beneficiarySelect = document.getElementById('beneficiaryQuickSelect');
    const recipientInput = document.getElementById('recipient_account_number');
    if (beneficiarySelect && recipientInput) {
        beneficiarySelect.addEventListener('change', function () {
            if (this.value) {
                recipientInput.value = this.value;
                recipientInput.classList.add('is-valid');
                setTimeout(() => recipientInput.classList.remove('is-valid'), 1500);
            }
        });
    }

    // 4. Live Currency Preview for Amount Inputs
    const amountInputs = document.querySelectorAll('input[type="number"][name="amount"], input[name="initial_deposit"]');
    amountInputs.forEach(function (input) {
        const previewElementId = input.dataset.preview;
        if (previewElementId) {
            const previewEl = document.getElementById(previewElementId);
            if (previewEl) {
                input.addEventListener('input', function () {
                    const val = parseFloat(this.value);
                    if (!isNaN(val) && val > 0) {
                        previewEl.textContent = '₹' + val.toLocaleString('en-IN', {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2
                        });
                        previewEl.parentElement.classList.remove('d-none');
                    } else {
                        previewEl.parentElement.classList.add('d-none');
                    }
                });
            }
        }
    });

    // 5. Copy to Clipboard Utility
    window.copyToClipboard = function (text, btnElement) {
        navigator.clipboard.writeText(text).then(function () {
            if (btnElement) {
                const originalHtml = btnElement.innerHTML;
                btnElement.innerHTML = '<i class="bi bi-check2 text-success"></i> Copied!';
                btnElement.classList.add('btn-light');
                setTimeout(function () {
                    btnElement.innerHTML = originalHtml;
                    btnElement.classList.remove('btn-light');
                }, 2000);
            }
        }).catch(function (err) {
            console.error('Copy failed', err);
        });
    };
});
