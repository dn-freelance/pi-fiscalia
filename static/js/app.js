(function () {
    var DESKTOP_SIDEBAR_MEDIA_QUERY = '(min-width: 1025px)';
    var activeModalState = null;
    var sidebarState = {
        lastFocusedElement: null,
        open: false,
    };

    function getFocusableElements(container) {
        if (!container) {
            return [];
        }

        return Array.from(
            container.querySelectorAll(
                'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
            )
        ).filter(function (element) {
            return !element.hidden && element.getClientRects().length > 0;
        });
    }

    function trapFocus(container, event) {
        var focusableElements = getFocusableElements(container);
        var firstElement = focusableElements[0];
        var lastElement = focusableElements[focusableElements.length - 1];

        if (!firstElement || !lastElement) {
            return;
        }

        if (event.shiftKey && document.activeElement === firstElement) {
            event.preventDefault();
            lastElement.focus();
            return;
        }

        if (!event.shiftKey && document.activeElement === lastElement) {
            event.preventDefault();
            firstElement.focus();
        }
    }

    function updateScrollLock() {
        var shouldLock = Boolean(activeModalState) || sidebarState.open;
        document.body.classList.toggle('is-scroll-locked', shouldLock);
    }

    function refreshIcons() {
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    function focusModal(modal) {
        var modalBox = modal ? modal.querySelector('.modal-box') : null;
        var preferredElement = modalBox
            ? modalBox.querySelector('input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])')
            : null;
        var focusableElements = getFocusableElements(modalBox);

        if (preferredElement && preferredElement.getClientRects().length > 0) {
            preferredElement.focus();
            return;
        }

        if (focusableElements.length) {
            focusableElements[0].focus();
            return;
        }

        if (modalBox) {
            modalBox.focus();
        }
    }

    function showModal(modalId, triggerElement) {
        var modal = document.getElementById(modalId);

        if (!modal) {
            return;
        }

        if (activeModalState && activeModalState.modal !== modal) {
            hideModal(activeModalState.modal.id);
        }

        modal.hidden = false;
        activeModalState = {
            lastFocusedElement: triggerElement || document.activeElement,
            modal: modal,
        };
        updateScrollLock();
        focusModal(modal);
    }

    function hideModal(modalId) {
        var modal = document.getElementById(modalId);
        var lastFocusedElement = activeModalState ? activeModalState.lastFocusedElement : null;

        if (!modal) {
            return;
        }

        modal.hidden = true;

        if (activeModalState && activeModalState.modal === modal) {
            activeModalState = null;
        }

        updateScrollLock();

        if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
            lastFocusedElement.focus();
        }
    }

    function isDesktopSidebar() {
        return window.matchMedia(DESKTOP_SIDEBAR_MEDIA_QUERY).matches;
    }

    function syncSidebarState() {
        var sidebar = document.getElementById('app-sidebar');
        var toggle = document.querySelector('[data-sidebar-toggle]');
        var backdrop = document.querySelector('[data-sidebar-backdrop]');
        var isOpen = sidebarState.open || isDesktopSidebar();

        if (sidebar) {
            sidebar.setAttribute('aria-hidden', isDesktopSidebar() ? 'false' : String(!sidebarState.open));
        }

        if (toggle) {
            toggle.setAttribute('aria-expanded', String(sidebarState.open));
        }

        if (backdrop) {
            backdrop.hidden = !sidebarState.open;
        }

        document.body.classList.toggle('sidebar-open', sidebarState.open);
        updateScrollLock();
        return isOpen;
    }

    function openSidebar(triggerElement) {
        if (isDesktopSidebar()) {
            return;
        }

        sidebarState.lastFocusedElement = triggerElement || document.activeElement;
        sidebarState.open = true;
        syncSidebarState();

        var sidebar = document.getElementById('app-sidebar');
        var focusableElements = getFocusableElements(sidebar);
        if (focusableElements.length) {
            focusableElements[0].focus();
        }
    }

    function closeSidebar() {
        if (!sidebarState.open) {
            return;
        }

        sidebarState.open = false;
        syncSidebarState();

        if (sidebarState.lastFocusedElement && typeof sidebarState.lastFocusedElement.focus === 'function') {
            sidebarState.lastFocusedElement.focus();
        }
    }

    function setupSidebar() {
        syncSidebarState();

        document.addEventListener('click', function (event) {
            var toggle = event.target.closest('[data-sidebar-toggle]');
            var closeButton = event.target.closest('[data-sidebar-close]');
            var backdrop = event.target.closest('[data-sidebar-backdrop]');
            var sidebarLink = event.target.closest('.sidebar .nav-item');

            if (toggle) {
                event.preventDefault();
                if (sidebarState.open) {
                    closeSidebar();
                } else {
                    openSidebar(toggle);
                }
            }

            if (closeButton || backdrop || sidebarLink) {
                closeSidebar();
            }
        });

        window.addEventListener('resize', function () {
            if (isDesktopSidebar()) {
                sidebarState.open = false;
                syncSidebarState();
            }
        });
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

        window.setTimeout(function () {
            toast.classList.add('is-closing');
            window.setTimeout(function () {
                toast.remove();
            }, 300);
        }, 5000);
    }

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

        messagesContainer.style.display = 'none';
    }

    function getOrCreateEffectiveRemindersContainer() {
        var container = document.querySelector('.effective-reminders-container');

        if (!container) {
            container = document.createElement('div');
            container.className = 'effective-reminders-container';
            document.body.appendChild(container);
        }

        return container;
    }

    function reminderIconMarkup() {
        return '<svg class="effective-reminder-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>';
    }

    function closeIconMarkup() {
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="m18 6-12 12"></path><path d="m6 6 12 12"></path></svg>';
    }

    function linkIconMarkup() {
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"></path><path d="M10 14 21 3"></path><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path></svg>';
    }

    function removeReminderCard(card) {
        if (!card) {
            return;
        }

        card.classList.add('is-closing');
        window.setTimeout(function () {
            var container = card.parentElement;

            card.remove();
            if (container && !container.children.length) {
                container.remove();
            }
        }, 250);
    }

    function dismissEffectiveReminder(root, notificationId, card) {
        removeReminderCard(card);

        window.fetch(root.dataset.dismissUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || '',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({
                notification_id: notificationId
            })
        }).catch(function () {
            return null;
        });
    }

    function buildEffectiveReminderCard(root, notification) {
        var card = document.createElement('article');
        var top = document.createElement('div');
        var topMeta = document.createElement('div');
        var priority = document.createElement('span');
        var closeButton = document.createElement('button');
        var title = document.createElement('h3');
        var description = document.createElement('p');
        var actions = document.createElement('div');
        var effectiveDateChip = document.createElement('span');
        var link = document.createElement('a');

        card.className = 'effective-reminder';

        top.className = 'effective-reminder-top';
        topMeta.className = 'effective-reminder-meta';
        topMeta.insertAdjacentHTML('beforeend', reminderIconMarkup());

        priority.className = 'effective-reminder-priority ' + (notification.priority || 'medium');
        priority.textContent = notification.priority_label || 'ACOMPANHAR';
        topMeta.appendChild(priority);

        closeButton.className = 'effective-reminder-close';
        closeButton.type = 'button';
        closeButton.setAttribute('aria-label', 'Fechar notifica\u00e7\u00e3o');
        closeButton.innerHTML = closeIconMarkup();
        closeButton.addEventListener('click', function () {
            dismissEffectiveReminder(root, notification.id, card);
        });

        title.className = 'effective-reminder-title';
        title.textContent = notification.title || 'Vig\u00eancia acompanhada';

        description.className = 'effective-reminder-description';
        description.textContent = notification.description || 'Uma vig\u00eancia acompanhada alcan\u00e7ou um dos marcos que voc\u00ea pediu para monitorar.';

        actions.className = 'effective-reminder-actions';

        effectiveDateChip.className = 'effective-reminder-chip';
        effectiveDateChip.textContent = 'Vig\u00eancia: ' + (notification.effective_date_display || '-');

        link.className = 'effective-reminder-link';
        link.href = notification.href || '#';
        link.innerHTML = linkIconMarkup() + '<span>Ver mais</span>';

        actions.appendChild(effectiveDateChip);
        actions.appendChild(link);

        top.appendChild(topMeta);
        top.appendChild(closeButton);
        card.appendChild(top);
        card.appendChild(title);
        card.appendChild(description);
        card.appendChild(actions);

        return card;
    }

    function setupEffectiveDateReminders() {
        var root = document.getElementById('effective-date-reminders-root');

        if (!root || !root.dataset.listUrl) {
            return;
        }

        window.fetch(root.dataset.listUrl, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('HTTP ' + response.status);
                }

                return response.json();
            })
            .then(function (payload) {
                var notifications = payload && Array.isArray(payload.notifications) ? payload.notifications : [];
                var container;

                if (!notifications.length) {
                    return;
                }

                container = getOrCreateEffectiveRemindersContainer();
                container.innerHTML = '';

                notifications.forEach(function (notification) {
                    container.appendChild(buildEffectiveReminderCard(root, notification));
                });
            })
            .catch(function () {
                return null;
            });
    }

    function setupAssistantWidget() {
        var widget = document.querySelector('[data-assistant-widget]');
        if (!widget) {
            return;
        }

        var slides = Array.from(widget.querySelectorAll('[data-assistant-slide]'));
        var triggers = Array.from(widget.querySelectorAll('[data-assistant-trigger]'));
        var link = widget.querySelector('[data-assistant-link]');

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
                trigger.setAttribute('tabindex', isActive ? '0' : '-1');
            });

            if (link && slides[index] && slides[index].dataset.href) {
                link.href = slides[index].dataset.href;
            }
        }

        triggers.forEach(function (trigger, triggerIndex) {
            trigger.addEventListener('click', function (event) {
                event.preventDefault();
                event.stopPropagation();
                activateSlide(Number(trigger.dataset.index || triggerIndex));
            });

            trigger.addEventListener('keydown', function (event) {
                var nextIndex = null;

                if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
                    nextIndex = (triggerIndex + 1) % triggers.length;
                } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
                    nextIndex = (triggerIndex - 1 + triggers.length) % triggers.length;
                } else if (event.key === 'Home') {
                    nextIndex = 0;
                } else if (event.key === 'End') {
                    nextIndex = triggers.length - 1;
                }

                if (nextIndex === null) {
                    return;
                }

                event.preventDefault();
                activateSlide(nextIndex);
                triggers[nextIndex].focus();
            });
        });

        widget.addEventListener('click', function (event) {
            if (event.target.closest('[data-assistant-trigger]') || event.target.closest('[data-assistant-link]')) {
                return;
            }

            var activeSlide = widget.querySelector('.assistant-slide.is-active');
            if (!activeSlide || !activeSlide.dataset.href) {
                return;
            }

            window.location.href = activeSlide.dataset.href;
        });

        activateSlide(0);
    }

    document.addEventListener('click', function (event) {
        var opener = event.target.closest('[data-modal-open]');
        var closer = event.target.closest('[data-modal-close]');

        if (opener) {
            event.preventDefault();
            showModal(opener.dataset.modalOpen, opener);
        }

        if (closer) {
            event.preventDefault();
            hideModal(closer.dataset.modalClose);
        }

        if (activeModalState && event.target === activeModalState.modal) {
            hideModal(activeModalState.modal.id);
        }
    });

    document.addEventListener('keydown', function (event) {
        if (activeModalState) {
            if (event.key === 'Escape') {
                event.preventDefault();
                hideModal(activeModalState.modal.id);
                return;
            }

            if (event.key === 'Tab') {
                trapFocus(activeModalState.modal, event);
            }
            return;
        }

        if (sidebarState.open && !isDesktopSidebar()) {
            if (event.key === 'Escape') {
                event.preventDefault();
                closeSidebar();
                return;
            }

            if (event.key === 'Tab') {
                trapFocus(document.getElementById('app-sidebar'), event);
            }
        }
    });

    document.addEventListener('DOMContentLoaded', function () {
        refreshIcons();
        convertMessagesToToasts();
        setupEffectiveDateReminders();
        setupAssistantWidget();
        setupSidebar();
    });

    window.Fiscalia = {
        closeSidebar: closeSidebar,
        hideModal: hideModal,
        refreshIcons: refreshIcons,
        showModal: showModal,
        showToast: showToast,
    };
}());

