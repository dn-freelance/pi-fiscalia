(function () {
    function setText(id, value) {
        var element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }

    function setWidth(id, percent) {
        var element = document.getElementById(id);
        var shell = document.getElementById('bar-shell-' + id.replace('bar-', ''));
        var boundedPercent = Math.max(0, Math.min(100, percent || 0));
        if (element) {
            element.style.width = String(boundedPercent) + '%';
        }

        if (shell) {
            shell.setAttribute('aria-valuenow', String(Math.round(boundedPercent)));
        }
    }

    function setCardState(cardId, state) {
        var card = document.getElementById(cardId);
        if (!card) {
            return;
        }

        card.classList.remove('is-active', 'is-complete', 'is-paused');
        if (state) {
            card.classList.add(state);
        }
    }

    function setChip(id, label, appearance) {
        var element = document.getElementById(id);
        if (!element) {
            return;
        }

        element.textContent = label;
        element.classList.remove('secondary', 'success', 'warning');
        if (appearance) {
            element.classList.add(appearance);
        }
    }

    function renderPayload(payload) {
        var rss = payload.rss || {};
        var analysis = payload.analysis || {};
        var isFinished = Boolean(payload.is_finished);
        var isFailed = payload.status === 'failed';
        var isAnalysisStage = payload.current_stage === 'analysis';

        setText('heading-news-progress-title', payload.stage_title || 'Atualizando informativos');
        setText('paragraph-news-progress-message', payload.stage_message || 'Estamos preparando as próximas etapas.');
        setText('metric-news-progress-rss-count', (rss.processed_sources || 0) + ' / ' + (rss.total_sources || 0));
        setText('metric-news-progress-created', String(rss.created_count || 0));
        setText('metric-news-progress-existing', String(rss.existing_count || 0));
        setText('metric-news-progress-errors', String((rss.error_count || 0) + (rss.skipped_count || 0)));
        setText('metric-news-progress-analysis-count', (analysis.processed_items || 0) + ' / ' + (analysis.total_items || 0));
        setText('metric-news-progress-analysis-failures', String(analysis.failure_count || 0));
        setText('metric-news-progress-analysis-skipped', String(analysis.skipped_count || 0));
        setText(
            'paragraph-news-progress-analysis-copy',
            analysis.enabled
                ? 'Depois da importação, a IA calcula resumo, impacto, score, vigência e palavras-chave para cada notícia nova.'
                : 'Nesta atualização, a importação segue normalmente e a camada de IA fica pausada porque não está habilitada.'
        );

        setWidth('bar-news-progress-rss', rss.progress_percent || 0);
        setWidth('bar-news-progress-analysis', analysis.progress_percent || 0);

        if (isFailed) {
            setChip('chip-news-progress-rss-state', 'Interrompida', 'warning');
            setChip('chip-news-progress-analysis-state', 'Interrompida', 'warning');
            setCardState('card-news-progress-rss', 'is-paused');
            setCardState('card-news-progress-analysis', 'is-paused');
            setText('span-news-progress-pill-label', 'Ocorreu uma falha inesperada. Vamos te devolver para a listagem com o resumo do que aconteceu.');
        } else {
            setChip(
                'chip-news-progress-rss-state',
                (rss.progress_percent || 0) >= 100 ? 'Concluída' : 'Em andamento',
                (rss.progress_percent || 0) >= 100 ? 'success' : ''
            );
            setCardState(
                'card-news-progress-rss',
                (rss.progress_percent || 0) >= 100 ? 'is-complete' : 'is-active'
            );

            if (!analysis.enabled) {
                setChip('chip-news-progress-analysis-state', 'Desabilitada', 'secondary');
                setCardState('card-news-progress-analysis', isFinished ? 'is-complete' : '');
            } else if (analysis.total_items === 0 && isFinished) {
                setChip('chip-news-progress-analysis-state', 'Sem pendências', 'success');
                setCardState('card-news-progress-analysis', 'is-complete');
            } else if (analysis.failure_count > 0 && isFinished) {
                setChip('chip-news-progress-analysis-state', 'Concluída com alertas', 'warning');
                setCardState('card-news-progress-analysis', 'is-paused');
            } else if (isAnalysisStage && !isFinished) {
                setChip('chip-news-progress-analysis-state', 'Em andamento', '');
                setCardState('card-news-progress-analysis', 'is-active');
            } else if (isFinished) {
                setChip('chip-news-progress-analysis-state', 'Concluída', 'success');
                setCardState('card-news-progress-analysis', 'is-complete');
            } else {
                setChip('chip-news-progress-analysis-state', 'Aguardando', 'secondary');
                setCardState('card-news-progress-analysis', '');
            }

            if (isFinished) {
                setText('span-news-progress-pill-label', 'Tudo pronto. Você será redirecionado automaticamente em instantes.');
            } else if (isAnalysisStage) {
                setText('span-news-progress-pill-label', 'A importação já andou bem. Agora estamos enriquecendo as notícias com IA.');
            } else {
                setText('span-news-progress-pill-label', 'Estamos conferindo as fontes ativas e reunindo os informativos mais recentes.');
            }
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        var root = document.getElementById('section-news-import-progress');
        var payloadElement = document.getElementById('news-import-job-payload');
        var returnLink = document.getElementById('link-news-progress-return');
        var footerText = document.getElementById('paragraph-news-progress-footer');
        var pollHandle = null;
        var redirectHandle = null;

        if (!root || !payloadElement) {
            return;
        }

        function scheduleRedirect(finalizeUrl, isFailed) {
            if (!finalizeUrl || redirectHandle) {
                return;
            }

            if (returnLink) {
                returnLink.hidden = false;
                returnLink.href = finalizeUrl;
            }

            if (footerText) {
                footerText.textContent = isFailed
                    ? 'A atualização foi encerrada com um alerta. Você será levado de volta para a listagem para ver os detalhes.'
                    : 'Atualização encerrada. Você será levado de volta para a listagem para continuar o trabalho.';
            }

            redirectHandle = window.setTimeout(function () {
                window.location.href = finalizeUrl;
            }, isFailed ? 1800 : 1400);
        }

        function pollStatus() {
            window.fetch(root.dataset.statusUrl, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error('Falha ao consultar o progresso');
                    }
                    return response.json();
                })
                .then(function (payload) {
                    renderPayload(payload);

                    if (payload.is_finished) {
                        if (pollHandle) {
                            window.clearInterval(pollHandle);
                            pollHandle = null;
                        }
                        scheduleRedirect(payload.finalize_url || root.dataset.finalizeUrl, payload.status === 'failed');
                    }
                })
                .catch(function () {
                    setText(
                        'paragraph-news-progress-footer',
                        'Perdemos contato por um instante com a atualização, mas continuaremos tentando automaticamente.'
                    );
                });
        }

        var initialPayload = {};
        try {
            initialPayload = JSON.parse(payloadElement.textContent);
        } catch (error) {
            initialPayload = {};
        }

        renderPayload(initialPayload);

        if (initialPayload.is_finished) {
            scheduleRedirect(initialPayload.finalize_url || root.dataset.finalizeUrl, initialPayload.status === 'failed');
            return;
        }

        pollHandle = window.setInterval(pollStatus, 1200);
        pollStatus();
    });
}());
