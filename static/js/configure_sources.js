(function () {
    function showModal(modalId) {
        var modal = document.getElementById(modalId);

        if (modal) {
            modal.style.display = 'flex';
        }
    }

    function hideModal(modalId) {
        var modal = document.getElementById(modalId);

        if (modal) {
            modal.style.display = 'none';
        }
    }

    document.querySelectorAll('[data-source-modal-open]').forEach(function (button) {
        button.addEventListener('click', function (event) {
            event.preventDefault();
            showModal(button.dataset.sourceModalOpen);
        });
    });

    document.querySelectorAll('[data-source-modal-close]').forEach(function (button) {
        button.addEventListener('click', function () {
            hideModal(button.dataset.sourceModalClose);
        });
    });

    document.querySelectorAll('.js-open-edit-source').forEach(function (button) {
        button.addEventListener('click', function () {
            var modal = document.getElementById('div-source-edit-modal');
            var form = document.getElementById('form-source-edit');

            form.action = button.dataset.sourceUpdateUrl;
            form.elements.name.value = button.dataset.sourceName || '';
            form.elements.url.value = button.dataset.sourceUrl || '';
            form.elements.description.value = button.dataset.sourceDescription || '';
            form.elements.category.value = button.dataset.sourceCategory || 'Federal';
            modal.style.display = 'flex';
        });
    });

    document.querySelectorAll('.js-open-delete-source').forEach(function (button) {
        button.addEventListener('click', function () {
            var modal = document.getElementById('div-source-delete-modal');
            var form = document.getElementById('form-source-delete');

            form.action = button.dataset.sourceDeleteUrl;
            form.elements.name.value = button.dataset.sourceName || '';
            modal.style.display = 'flex';
        });
    });

    document.querySelectorAll('.js-source-status-input').forEach(function (input) {
        input.addEventListener('change', function () {
            input.form.submit();
        });
    });
}());
