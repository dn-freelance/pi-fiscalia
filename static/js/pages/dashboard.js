(function () {
    var POLL_INTERVAL_MS = 2500;
    var MAX_RETRIES = 30;

    function setText(node, value) {
        if (!node) {
            return;
        }

        node.textContent = value || '';
    }

    function toggleVisibility(node, shouldShow) {
        if (!node) {
            return;
        }

        node.classList.toggle('is-hidden', !shouldShow);
    }

    function renderSummary(root, payload) {
        var feedback = root.querySelector('[data-weekly-summary-feedback]');
        var message = root.querySelector('[data-weekly-summary-message]');
        var content = root.querySelector('[data-weekly-summary-content]');
        var error = root.querySelector('[data-weekly-summary-error]');

        root.dataset.status = payload.status || 'pending';

        if (payload.status === 'completed') {
            setText(root.querySelector('[data-weekly-summary-overview]'), payload.overview);
            setText(root.querySelector('[data-weekly-summary-main-changes]'), payload.main_changes);
            setText(root.querySelector('[data-weekly-summary-attention]'), payload.attention);

            toggleVisibility(feedback, false);
            toggleVisibility(error, false);
            toggleVisibility(content, true);
            return;
        }

        if (payload.status === 'failed') {
            setText(error, payload.error_message || payload.message || 'Não foi possível gerar o resumo semanal.');
            toggleVisibility(feedback, false);
            toggleVisibility(content, false);
            toggleVisibility(error, true);
            return;
        }

        setText(message, payload.message || 'Gerando o resumo semanal com IA.');
        toggleVisibility(content, false);
        toggleVisibility(error, false);
        toggleVisibility(feedback, true);
    }

    function startPolling(root) {
        var statusUrl = root.dataset.statusUrl;
        var retryCount = 0;

        if (!statusUrl) {
            return;
        }

        function poll() {
            window.fetch(statusUrl, {
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
                    renderSummary(root, payload);

                    if (payload.status === 'completed' || payload.status === 'failed') {
                        return;
                    }

                    window.setTimeout(poll, POLL_INTERVAL_MS);
                })
                .catch(function () {
                    retryCount += 1;

                    if (retryCount >= MAX_RETRIES) {
                        renderSummary(root, {
                            status: 'failed',
                            error_message: 'Não foi possível atualizar o resumo semanal automaticamente.'
                        });
                        return;
                    }

                    window.setTimeout(poll, POLL_INTERVAL_MS);
                });
        }

        poll();
    }

    document.addEventListener('DOMContentLoaded', function () {
        var root = document.querySelector('[data-dashboard-weekly-summary]');
        if (!root) {
            return;
        }

        if (root.dataset.status === 'completed') {
            return;
        }

        startPolling(root);
    });
}());
