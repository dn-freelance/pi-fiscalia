(function () {
    document.addEventListener('DOMContentLoaded', function () {
        var panel = document.querySelector('.api-test-panel');
        var button = document.getElementById('btn-teste-api');
        var response = document.getElementById('api-response');

        if (!panel || !button || !response) {
            return;
        }

        button.addEventListener('click', function () {
            response.hidden = false;
            response.textContent = 'Enviando requisição...';

            fetch(panel.dataset.apiTestUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    mensagem: 'Olá do Frontend! Esta é uma mensagem de teste enviada pela Dashboard.',
                }),
            })
                .then(function (fetchResponse) {
                    return fetchResponse.json();
                })
                .then(function (data) {
                    response.textContent = JSON.stringify(data, null, 2);
                })
                .catch(function (error) {
                    response.textContent = 'Erro na requisição: ' + error;
                });
        });
    });
}());
