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

    function getOrCreateToastContainer() {
        var container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    function showToast(message, type) {
        type = type || 'info';
        var container = getOrCreateToastContainer();
        var toast = document.createElement('div');
        toast.className = 'toast ' + type;

        var iconSvg = '';
        if (type === 'success') {
            iconSvg = '<svg class="toast-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
        } else if (type === 'error') {
            iconSvg = '<svg class="toast-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>';
        }

        toast.innerHTML = iconSvg + '<div class="toast-content">' + message + '</div>';
        container.appendChild(toast);

        // Auto-remove after 5 seconds
        setTimeout(function () {
            toast.classList.add('is-closing');
            setTimeout(function () {
                toast.remove();
            }, 300);
        }, 5000);
    }

    function convertMessagesToToasts() {
        var messagesContainer = document.querySelector('.feedback-messages');
        if (!messagesContainer) {
            return;
        }

        var messages = messagesContainer.querySelectorAll('.feedback-message');
        messages.forEach(function (message) {
            var type = 'info';
            if (message.classList.contains('success')) {
                type = 'success';
            } else if (message.classList.contains('error')) {
                type = 'error';
            }
            showToast(message.textContent.trim(), type);
        });

        // Hide the original messages container
        messagesContainer.style.display = 'none';
    }

    function setupAssistantWidget() {
        var widget = document.querySelector('[data-assistant-widget]');
        if (!widget) {
            return;
        }

        var slides = Array.from(widget.querySelectorAll('[data-assistant-slide]'));
        var triggers = Array.from(widget.querySelectorAll('[data-assistant-trigger]'));

        if (!slides.length || !triggers.length) {
            return;
        }

        function activateSlide(index) {
            slides.forEach(function (slide, slideIndex) {
                var isActive = slideIndex === index;
                slide.hidden = !isActive;
                slide.classList.toggle('is-active', isActive);
            });

            triggers.forEach(function (trigger, triggerIndex) {
                var isActive = triggerIndex === index;
                trigger.classList.toggle('active', isActive);
                trigger.setAttribute('aria-selected', isActive ? 'true' : 'false');
            });
        }

        triggers.forEach(function (trigger) {
            trigger.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();
                activateSlide(Number(trigger.dataset.index || 0));
            });
        });

        widget.addEventListener('click', function (event) {
            if (event.target.closest('[data-assistant-trigger]')) {
                return;
            }

            var activeSlide = widget.querySelector('.assistant-slide.is-active');
            if (!activeSlide || !activeSlide.dataset.href) {
                return;
            }

            window.location.href = activeSlide.dataset.href;
        });
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

    document.addEventListener('DOMContentLoaded', function () {
        refreshIcons();
        convertMessagesToToasts();
        setupAssistantWidget();
    });

    window.Fiscalia = {
        hideModal: hideModal,
        refreshIcons: refreshIcons,
        showModal: showModal,
        showToast: showToast,
    };
}());
