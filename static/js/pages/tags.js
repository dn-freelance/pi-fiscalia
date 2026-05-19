(function () {
    function updatePickerState(picker, selectedColor) {
        picker.querySelectorAll('.tag-color-button').forEach(function (item) {
            var isSelected = item.dataset.color === selectedColor;
            item.classList.toggle('is-selected', isSelected);
            item.setAttribute('aria-checked', isSelected ? 'true' : 'false');
            item.setAttribute('tabindex', isSelected ? '0' : '-1');
        });
    }

    function selectColor(button, picker, shouldFocus) {
        var colorFieldId = picker.dataset.colorField;
        var colorField = document.getElementById(colorFieldId);

        if (!colorField) {
            return;
        }

        colorField.value = button.dataset.color || '';
        updatePickerState(picker, colorField.value);

        if (shouldFocus) {
            button.focus();
        }
    }

    function bindColorPicker(formId) {
        var form = document.getElementById(formId);

        if (!form) {
            return;
        }

        var picker = form.querySelector('.tag-color-picker');

        if (!picker) {
            return;
        }

        picker.querySelectorAll('.tag-color-button').forEach(function (button) {
            button.addEventListener('click', function () {
                selectColor(button, picker, false);
            });

            button.addEventListener('keydown', function (event) {
                var buttons = Array.from(picker.querySelectorAll('.tag-color-button'));
                var currentIndex = buttons.indexOf(button);
                var nextIndex = null;

                if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
                    nextIndex = (currentIndex + 1) % buttons.length;
                } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
                    nextIndex = (currentIndex - 1 + buttons.length) % buttons.length;
                } else if (event.key === 'Home') {
                    nextIndex = 0;
                } else if (event.key === 'End') {
                    nextIndex = buttons.length - 1;
                }

                if (nextIndex === null) {
                    return;
                }

                event.preventDefault();
                selectColor(buttons[nextIndex], picker, true);
            });
        });

        updatePickerState(picker, form.querySelector('input[type="hidden"]').value);
    }

    document.addEventListener('DOMContentLoaded', function () {
        bindColorPicker('form-tag-create');
        bindColorPicker('form-tag-edit');

        document.querySelectorAll('.js-open-edit-tag').forEach(function (button) {
            button.addEventListener('click', function () {
                var form = document.getElementById('form-tag-edit');
                var selectedColor = button.dataset.tagColor || 'blue';

                if (!form) {
                    return;
                }

                form.action = button.dataset.tagUpdateUrl;
                form.elements.name.value = button.dataset.tagName || '';
                form.elements.color.value = selectedColor;

                var picker = form.querySelector('.tag-color-picker');
                if (picker) {
                    updatePickerState(picker, selectedColor);
                }

                window.Fiscalia.showModal('div-tag-edit-modal', button);
            });
        });

        document.querySelectorAll('.js-open-delete-tag').forEach(function (button) {
            button.addEventListener('click', function () {
                var form = document.getElementById('form-tag-delete');

                if (!form) {
                    return;
                }

                form.action = button.dataset.tagDeleteUrl;
                form.elements.name.value = button.dataset.tagName || '';
                
                // Save scroll position before showing modal
                form.dataset.scrollY = window.scrollY;
                window.Fiscalia.showModal('div-tag-delete-modal', button);
            });
        });

        // Handle form submission to preserve scroll position
        var deleteForm = document.getElementById('form-tag-delete');
        if (deleteForm) {
            deleteForm.addEventListener('submit', function (e) {
                var scrollY = parseInt(deleteForm.dataset.scrollY, 10) || 0;
                sessionStorage.setItem('scrollY', scrollY);
            });
        }
    });

    // Restore scroll position after page load
    window.addEventListener('load', function () {
        var scrollY = sessionStorage.getItem('scrollY');
        if (scrollY) {
            window.scrollTo(0, parseInt(scrollY, 10));
            sessionStorage.removeItem('scrollY');
        }
    });
}());
