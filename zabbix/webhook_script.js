var CWebhook = function(value) {
    try {
        var p = JSON.parse(value);

        var API_URL = p.api_url.replace(/\/+$/, '');
        var API_KEY = p.api_key;

        var payload = JSON.stringify({
            to:                  p.to,
            subject:             p.subject,
            body:                p.body,
            severity:            p.severity,
            event_nseverity:     p.event_nseverity,
            status:              p.status,
            event_value:         p.event_value,
            event_update_status: p.event_update_status,
            event_id:            p.event_id,
            trigger_name:        p.trigger_name,
            host:                p.host,
            event_date:          p.event_date,
            event_time:          p.event_time,
            zabbix_url:          p.zabbix_url,
            is_group:            p.is_group === 'true'
        });

        var req = new HttpRequest();
        req.addHeader('Content-Type: application/json');
        req.addHeader('X-API-Key: ' + API_KEY);

        var resp = req.post(API_URL + '/api/v1/zabbix/alert', payload);
        var code = req.getStatus();

        Zabbix.log(4, '[WhatZabbix] HTTP ' + code + ' response: ' + resp);

        if (code !== 200) {
            throw 'HTTP ' + code + ': ' + resp;
        }

        var result = JSON.parse(resp);
        if (!result.success) {
            throw 'API error: ' + (result.error || resp);
        }

        return 'OK: message_id=' + result.message_id;

    } catch (e) {
        Zabbix.log(3, '[WhatZabbix] ERRO: ' + e);
        throw 'WhatZabbix falhou: ' + e;
    }
};

return new CWebhook(value);

