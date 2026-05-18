(function () {
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

        updateSelectionState();
    });
}());
