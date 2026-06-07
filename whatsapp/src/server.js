'use strict';

const express = require('express');
const path = require('path');
const pino = require('pino');
const {
    default: makeWASocket,
    DisconnectReason,
    fetchLatestBaileysVersion,
    useMultiFileAuthState,
} = require('@whiskeysockets/baileys');

const app = express();
app.use(express.json({ limit: '10mb' }));

const PORT = parseInt(process.env.WA_PORT || '3000', 10);
const HOST = process.env.WA_HOST || '0.0.0.0';
const AUTH_PATH = process.env.WA_AUTH_PATH || './.wa_auth';

// Optional default number (country code + number), ex: 5511999999999
const DEFAULT_PAIRING_NUMBER = (process.env.WA_PAIRING_NUMBER || '').replace(/\D/g, '');

/** @type {'initializing'|'pairing_required'|'pairing_ready'|'authenticated'|'ready'|'disconnected'} */
let clientStatus = 'initializing';
let latestPairingCode = null;
let sock = null;
let reconnectTimer = null;
let startPromise = null;

const logger = pino({ level: process.env.LOG_LEVEL || 'info' });
function scheduleReconnect(delayMs = 5000) {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        startClient().catch((err) => {
            logger.error({ err }, '[WhatsApp] Failed to reconnect');
            scheduleReconnect(10000);
        });
    }, delayMs);
}

function normalizePhone(number) {
    return (number || '').replace(/\D/g, '');
}

function toUserJid(number) {
    return `${normalizePhone(number)}@s.whatsapp.net`;
}

async function requestPairingCode(number) {
    const normalized = normalizePhone(number || DEFAULT_PAIRING_NUMBER);
    if (!normalized) {
        throw new Error('Pairing number is required (DDI + numero)');
    }

    let lastErr = null;
    for (let attempt = 1; attempt <= 2; attempt += 1) {
        if (!sock || clientStatus === 'pairing_required' || sock.ws?.readyState === 3) {
            await startClient();
        }

        try {
            const code = await sock.requestPairingCode(normalized);
            latestPairingCode = code;
            clientStatus = 'pairing_ready';
            logger.info({ number: normalized }, '[WhatsApp] Pairing code generated');
            return code;
        } catch (err) {
            lastErr = err;
            const msg = String(err?.message || err || '');
            if (!msg.includes('Connection Closed') || attempt === 2) {
                throw err;
            }
            logger.warn('[WhatsApp] Pairing attempt failed with closed connection, retrying once');
            sock = null;
        }
    }

    throw lastErr || new Error('Unable to generate pairing code');
}

async function startClient() {
    if (startPromise) return startPromise;

    startPromise = (async () => {
    clientStatus = 'initializing';

    const authDir = path.resolve(AUTH_PATH);
    const { state, saveCreds } = await useMultiFileAuthState(authDir);
    const { version } = await fetchLatestBaileysVersion();

    sock = makeWASocket({
        version,
        auth: state,
        logger: pino({ level: 'silent' }),
        markOnlineOnConnect: false,
        browser: ['WhatZabbix', 'Chrome', '1.0.0'],
        syncFullHistory: false,
    });

    sock.ev.on('creds.update', saveCreds);

    if (!state.creds.registered) {
        clientStatus = 'pairing_required';
        if (DEFAULT_PAIRING_NUMBER) {
            setTimeout(async () => {
                try {
                    await requestPairingCode(DEFAULT_PAIRING_NUMBER);
                } catch (err) {
                    logger.error({ err }, '[WhatsApp] Failed to auto-generate pairing code');
                }
            }, 2000);
        }
    }

        sock.ev.on('connection.update', ({ connection, lastDisconnect }) => {
            if (connection === 'open') {
                clientStatus = 'ready';
                latestPairingCode = null;
                logger.info('[WhatsApp] Client ready - connected');
                return;
            }

            if (connection === 'close') {
                const statusCode = lastDisconnect?.error?.output?.statusCode;

                if (statusCode === DisconnectReason.loggedOut) {
                    clientStatus = 'pairing_required';
                    latestPairingCode = null;
                    sock = null;
                    logger.warn('[WhatsApp] Logged out, pairing required');
                } else {
                    clientStatus = 'disconnected';
                    logger.warn({ statusCode }, '[WhatsApp] Connection closed, scheduling reconnect');
                    // Keep socket lifecycle alive for transient disconnects.
                    scheduleReconnect(2500);
                }
            }
        });
    })();

    try {
        await startPromise;
    } finally {
        startPromise = null;
    }
}

startClient().catch((err) => {
    logger.error({ err }, '[WhatsApp] Startup failure');
    clientStatus = 'disconnected';
    scheduleReconnect(10000);
});

app.use((req, _res, next) => {
    logger.info({ method: req.method, path: req.path }, '[HTTP] request');
    next();
});

function assertReady(res) {
    if (!sock || clientStatus !== 'ready') {
        res.status(503).json({
            error: 'WhatsApp client not ready',
            status: clientStatus,
            pairingCode: latestPairingCode,
        });
        return false;
    }
    return true;
}

app.get('/health', (_req, res) => {
    res.json({ status: 'ok', whatsapp: clientStatus });
});

app.get('/status', (_req, res) => {
    res.json({
        status: clientStatus,
        pairingCode: latestPairingCode,
    });
});

app.get('/qr', (_req, res) => {
    // Backward-compatible route expected by API layer.
    res.status(404).json({
        message: 'QR flow disabled. Use pairing code endpoint instead.',
        status: clientStatus,
    });
});

app.post('/pair-code', async (req, res) => {
    try {
        const number = req.body?.number || req.query?.number || DEFAULT_PAIRING_NUMBER;
        const code = await requestPairingCode(number);
        res.json({ status: clientStatus, pairingCode: code });
    } catch (err) {
        res.status(400).json({ error: err.message || 'Unable to generate pairing code' });
    }
});

app.post('/send', async (req, res) => {
    const { number, message } = req.body;

    if (!number || !message) {
        return res.status(400).json({ error: '"number" and "message" are required' });
    }
    if (!assertReady(res)) return;

    try {
        const result = await sock.sendMessage(toUserJid(number), { text: String(message) });
        res.json({ success: true, messageId: result?.key?.id });
    } catch (err) {
        logger.error({ err }, '[send] Error');
        res.status(500).json({ error: err.message || 'Failed to send message' });
    }
});

app.post('/send-group', async (req, res) => {
    const { groupId, message } = req.body;

    if (!groupId || !message) {
        return res.status(400).json({ error: '"groupId" and "message" are required' });
    }
    if (!assertReady(res)) return;

    try {
        const result = await sock.sendMessage(groupId, { text: String(message) });
        res.json({ success: true, messageId: result?.key?.id });
    } catch (err) {
        logger.error({ err }, '[send-group] Error');
        res.status(500).json({ error: err.message || 'Failed to send group message' });
    }
});

app.get('/chats', (_req, res) => {
    // Kept for compatibility. Baileys does not expose chat list by default without a custom store.
    res.json([]);
});

app.listen(PORT, HOST, () => {
    logger.info(`[WhatsApp Service] Listening on ${HOST}:${PORT}`);
});
