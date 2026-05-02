(function () {
    function selectColor(button, picker) {
        var colorFieldId = picker.dataset.colorField;
        var colorField = document.getElementById(colorFieldId);

        if (!colorField) {
            return;
        }

        picker.querySelectorAll('.tag-color-button').forEach(function (item) {
            item.classList.remove('is-selected');
        });

        button.classList.add('is-selected');
        colorField.value = button.dataset.color || '';
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
                selectColor(button, picker);
            });
        });
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
                    picker.querySelectorAll('.tag-color-button').forEach(function (item) {
                        item.classList.toggle('is-selected', item.dataset.color === selectedColor);
                    });
                }

                window.Fiscalia.showModal('div-tag-edit-modal');
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
                window.Fiscalia.showModal('div-tag-delete-modal');
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