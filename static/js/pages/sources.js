(function () {
    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('.js-open-edit-source').forEach(function (button) {
            button.addEventListener('click', function () {
                var form = document.getElementById('form-source-edit');

                if (!form) {
                    return;
                }

                form.action = button.dataset.sourceUpdateUrl;
                form.elements.name.value = button.dataset.sourceName || '';
                form.elements.url.value = button.dataset.sourceUrl || '';
                form.elements.description.value = button.dataset.sourceDescription || '';
                form.elements.category.value = button.dataset.sourceCategory || 'Federal';
                window.Fiscalia.showModal('div-source-edit-modal', button);
            });
        });

        document.querySelectorAll('.js-open-delete-source').forEach(function (button) {
            button.addEventListener('click', function () {
                var form = document.getElementById('form-source-delete');

                if (!form) {
                    return;
                }

                form.action = button.dataset.sourceDeleteUrl;
                form.elements.name.value = button.dataset.sourceName || '';
                window.Fiscalia.showModal('div-source-delete-modal', button);
            });
        });

        document.querySelectorAll('.js-source-status-input').forEach(function (input) {
            input.addEventListener('change', function () {
                input.setAttribute('aria-checked', input.checked ? 'true' : 'false');
                input.form.submit();
            });
        });
    });
}());
