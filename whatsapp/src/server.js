'use strict';

const express = require('express');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode');

const app = express();
app.use(express.json({ limit: '10mb' }));

const PORT = parseInt(process.env.WA_PORT || '3000', 10);
const HOST = '127.0.0.1'; // Never expose externally — only the Python API talks to this

// ─── State ───────────────────────────────────────────────────────────────────

let client = null;
let qrCodeDataURL = null;

/**
 * @type {'initializing'|'qr_ready'|'authenticated'|'ready'|'disconnected'}
 */
let clientStatus = 'initializing';

// ─── Client initialization ───────────────────────────────────────────────────

function initializeClient() {
    clientStatus = 'initializing';
    qrCodeDataURL = null;

    client = new Client({
        authStrategy: new LocalAuth({
            dataPath: process.env.WA_AUTH_PATH || './.wwebjs_auth',
        }),
        puppeteer: {
            headless: true,
            executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--single-process',
                '--disable-gpu',
            ],
        },
    });

    client.on('qr', async (qr) => {
        console.log('[WhatsApp] QR Code received — scan it with your phone');
        clientStatus = 'qr_ready';
        qrCodeDataURL = await qrcode.toDataURL(qr);
    });

    client.on('authenticated', () => {
        console.log('[WhatsApp] Authenticated successfully');
        clientStatus = 'authenticated';
        qrCodeDataURL = null;
    });

    client.on('auth_failure', (msg) => {
        console.error('[WhatsApp] Authentication failure:', msg);
        clientStatus = 'disconnected';
    });

    client.on('ready', () => {
        console.log('[WhatsApp] Client ready — connected to WhatsApp');
        clientStatus = 'ready';
    });

    client.on('disconnected', (reason) => {
        console.warn('[WhatsApp] Disconnected:', reason);
        clientStatus = 'disconnected';
        // Reinitialize after 5 s
        setTimeout(initializeClient, 5000);
    });

    client.initialize().catch((err) => {
        console.error('[WhatsApp] Initialization error:', err.message);
        clientStatus = 'disconnected';
        setTimeout(initializeClient, 10000);
    });
}

initializeClient();

// ─── Middleware ───────────────────────────────────────────────────────────────

app.use((req, _res, next) => {
    console.log(`[HTTP] ${req.method} ${req.path}`);
    next();
});

// ─── Helpers ─────────────────────────────────────────────────────────────────

/**
 * Normalize a phone number to WhatsApp chat ID format.
 * Accepts: 5511999999999, +55 (11) 99999-9999, etc.
 */
function toChatId(number) {
    const digits = number.replace(/\D/g, '');
    return `${digits}@c.us`;
}

function assertReady(res) {
    if (clientStatus !== 'ready') {
        res.status(503).json({
            error: 'WhatsApp client not ready',
            status: clientStatus,
        });
        return false;
    }
    return true;
}

// ─── Routes ──────────────────────────────────────────────────────────────────

app.get('/health', (_req, res) => {
    res.json({ status: 'ok', whatsapp: clientStatus });
});

app.get('/status', (_req, res) => {
    res.json({ status: clientStatus });
});

app.get('/qr', (_req, res) => {
    if (clientStatus === 'qr_ready' && qrCodeDataURL) {
        return res.json({ qr: qrCodeDataURL, status: clientStatus });
    }
    if (clientStatus === 'ready' || clientStatus === 'authenticated') {
        return res.json({ message: 'Already authenticated', status: clientStatus });
    }
    return res.status(202).json({ message: 'QR not ready yet', status: clientStatus });
});

app.post('/send', async (req, res) => {
    const { number, message } = req.body;

    if (!number || !message) {
        return res.status(400).json({ error: '"number" and "message" are required' });
    }
    if (!assertReady(res)) return;

    try {
        const chatId = toChatId(number);
        const sent = await client.sendMessage(chatId, message);
        res.json({ success: true, messageId: sent.id._serialized });
    } catch (err) {
        console.error('[send] Error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

app.post('/send-group', async (req, res) => {
    const { groupId, message } = req.body;

    if (!groupId || !message) {
        return res.status(400).json({ error: '"groupId" and "message" are required' });
    }
    if (!assertReady(res)) return;

    try {
        const sent = await client.sendMessage(groupId, message);
        res.json({ success: true, messageId: sent.id._serialized });
    } catch (err) {
        console.error('[send-group] Error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

app.get('/chats', async (_req, res) => {
    if (!assertReady(res)) return;

    try {
        const chats = await client.getChats();
        const list = chats.map((c) => ({
            id: c.id._serialized,
            name: c.name,
            isGroup: c.isGroup,
            unreadCount: c.unreadCount,
        }));
        res.json(list);
    } catch (err) {
        console.error('[chats] Error:', err.message);
        res.status(500).json({ error: err.message });
    }
});

// ─── Start ───────────────────────────────────────────────────────────────────

app.listen(PORT, HOST, () => {
    console.log(`[WhatsApp Service] Listening on ${HOST}:${PORT}`);
});
