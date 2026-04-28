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

    function refreshIcons() {
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    document.addEventListener('click', function (event) {
        var opener = event.target.closest('[data-modal-open]');
        var closer = event.target.closest('[data-modal-close]');

        if (opener) {
            event.preventDefault();
            showModal(opener.dataset.modalOpen);
        }

        if (closer) {
            event.preventDefault();
            hideModal(closer.dataset.modalClose);
        }
    });

    document.addEventListener('DOMContentLoaded', refreshIcons);

    window.Fiscalia = {
        hideModal: hideModal,
        refreshIcons: refreshIcons,
        showModal: showModal,
    };
}());
