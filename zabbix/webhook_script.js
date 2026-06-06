// ════════════════════════════════════════════════════════════
//  WhatZabbix — Media Type Webhook Script
//  Cole este script em: Administration > Media types > Webhook
//  Script type: JavaScript
// ════════════════════════════════════════════════════════════

try {
    var API_URL = params.api_url.replace(/\/+$/, '');
    var API_KEY = params.api_key;

    // Monta o payload com todos os campos disponíveis
    var payload = JSON.stringify({
        to:           params.to,
        subject:      params.subject,
        body:         params.body,
        severity:     params.severity,
        status:       params.status,
        event_id:     params.event_id,
        trigger_name: params.trigger_name,
        host:         params.host,
        event_date:   params.event_date,
        event_time:   params.event_time,
        is_group:     params.is_group === 'true'
    });

    var req = new HttpRequest();
    req.addHeader('Content-Type: application/json');
    req.addHeader('X-API-Key: ' + API_KEY);

    var resp = req.post(API_URL + '/api/v1/zabbix/alert', payload);
    var code = req.getStatus();

    Zabbix.log(4, '[WhatZabbix] HTTP ' + code + ' → ' + resp);

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
