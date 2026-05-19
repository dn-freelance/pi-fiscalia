(function () {
    function getCookie(name) {
        var cookieValue = null;

        if (!document.cookie) {
            return cookieValue;
        }

        document.cookie.split(';').forEach(function (cookie) {
            var trimmedCookie = cookie.trim();

            if (trimmedCookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(trimmedCookie.substring(name.length + 1));
            }
        });

        return cookieValue;
    }

    function clearSelection(checkboxes, selectAllInput) {
        checkboxes.forEach(function (checkbox) {
            checkbox.checked = false;
        });

        if (selectAllInput) {
            selectAllInput.checked = false;
            selectAllInput.indeterminate = false;
        }
    }

    function updateSelectionState() {
        var checkboxes = Array.from(document.querySelectorAll('.js-news-item-checkbox'));
        var selectedCheckboxes = checkboxes.filter(function (checkbox) {
            return checkbox.checked;
        });
        var bulkBar = document.getElementById('div-news-bulk-bar');
        var selectedCount = document.getElementById('span-news-selected-count');
        var selectedLabel = document.getElementById('span-news-selected-label');
        var selectAllInput = document.getElementById('input-news-select-all');

        checkboxes.forEach(function (checkbox) {
            var card = document.getElementById(checkbox.dataset.cardId || '');
            if (card) {
                card.classList.toggle('is-selected', checkbox.checked);
            }
        });

        if (selectedCount) {
            selectedCount.textContent = String(selectedCheckboxes.length);
        }

        if (selectedLabel) {
            selectedLabel.textContent = selectedCheckboxes.length === 1 ? 'item selecionado' : 'itens selecionados';
        }

        if (bulkBar) {
            bulkBar.hidden = selectedCheckboxes.length === 0;
        }

        if (selectAllInput) {
            selectAllInput.checked = checkboxes.length > 0 && selectedCheckboxes.length === checkboxes.length;
            selectAllInput.indeterminate = selectedCheckboxes.length > 0 && selectedCheckboxes.length < checkboxes.length;
        }

        if (window.Fiscalia && typeof window.Fiscalia.refreshIcons === 'function') {
            window.Fiscalia.refreshIcons();
        }
    }

    function renderFollowButton(button, isFollowing) {
        if (!button) {
            return;
        }

        button.classList.toggle('is-active', Boolean(isFollowing));
        button.setAttribute('aria-pressed', isFollowing ? 'true' : 'false');
        button.innerHTML = '<i data-lucide="' + (isFollowing ? 'bell-ring' : 'bell') + '"></i><span>Acompanhar</span>';

        if (window.Fiscalia && typeof window.Fiscalia.refreshIcons === 'function') {
            window.Fiscalia.refreshIcons();
        }
    }

    function setupFollowForms() {
        var followForms = Array.from(document.querySelectorAll('.news-follow-form'));

        followForms.forEach(function (form) {
            form.addEventListener('submit', function (event) {
                var button = form.querySelector('.news-follow-button');
                var formData;

                event.preventDefault();

                if (!button || button.disabled) {
                    return;
                }

                button.disabled = true;
                formData = new window.FormData(form);

                window.fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken') || '',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                    .then(function (response) {
                        return response.json().then(function (payload) {
                            if (!response.ok) {
                                throw payload;
                            }

                            return payload;
                        });
                    })
                    .then(function (payload) {
                        renderFollowButton(button, payload.is_following);

                        if (window.Fiscalia && typeof window.Fiscalia.showToast === 'function' && payload.message) {
                            window.Fiscalia.showToast(payload.message, 'success');
                        }
                    })
                    .catch(function (errorPayload) {
                        if (window.Fiscalia && typeof window.Fiscalia.showToast === 'function') {
                            window.Fiscalia.showToast(
                                (errorPayload && errorPayload.message) || 'Não foi possível atualizar o acompanhamento agora.',
                                'error'
                            );
                        }
                    })
                    .finally(function () {
                        button.disabled = false;
                    });
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var filterForm = document.getElementById('form-news-filters');
        var refreshForm = document.getElementById('form-news-refresh');
        var selectAllInput = document.getElementById('input-news-select-all');
        var clearSelectionButton = document.getElementById('btn-news-clear-selection');
        var itemCheckboxes = Array.from(document.querySelectorAll('.js-news-item-checkbox'));

        if (filterForm) {
            filterForm.querySelectorAll('.js-news-filter-select').forEach(function (field) {
                field.addEventListener('change', function () {
                    filterForm.submit();
                });
            });

            filterForm.querySelectorAll('.news-date-field input').forEach(function (field) {
                field.addEventListener('change', function () {
                    filterForm.submit();
                });
            });
        }

        if (refreshForm) {
            refreshForm.addEventListener('submit', function () {
                var button = refreshForm.querySelector('button[type="submit"]');
                if (!button) {
                    return;
                }

                button.disabled = true;
                button.dataset.originalText = button.textContent.trim();
                button.querySelector('span').textContent = button.dataset.loadingText || 'Atualizando...';
            });
        }

        itemCheckboxes.forEach(function (checkbox) {
            checkbox.addEventListener('change', updateSelectionState);
        });

        if (selectAllInput) {
            selectAllInput.addEventListener('change', function () {
                itemCheckboxes.forEach(function (checkbox) {
                    checkbox.checked = selectAllInput.checked;
                });
                updateSelectionState();
            });
        }

        if (clearSelectionButton) {
            clearSelectionButton.addEventListener('click', function (event) {
                event.preventDefault();
                clearSelection(itemCheckboxes, selectAllInput);
                updateSelectionState();
            });
        }

        setupFollowForms();
        updateSelectionState();
    });
}());
