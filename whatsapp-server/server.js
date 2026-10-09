/**
 * Servidor local WhatsApp — whatsapp-web.js
 * Expone POST /send para enviar mensajes desde el proyecto Python.
 *
 * Uso:
 *   1. npm install
 *   2. node server.js   (o usar Iniciar WhatsApp Server.bat)
 *   3. Escanear el QR con la app de WhatsApp (una sola vez)
 *   4. La sesion queda guardada en .wwebjs_auth/
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');

const PORT = process.env.PORT || 3000;

const app = express();
app.use(express.json());

// ─── Cliente WhatsApp ───────────────────────────────────────────────────────

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: '.wwebjs_auth' }),
    puppeteer: {
        headless: true,
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
        ],
    },
});

let isReady = false;

client.on('qr', (qr) => {
    console.log('\n======================================');
    console.log('  Escanee el QR con su telefono:');
    console.log('  WhatsApp > Dispositivos vinculados > Vincular dispositivo');
    console.log('======================================\n');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    isReady = true;
    console.log('\n[OK] WhatsApp conectado y listo para enviar mensajes.\n');
});

client.on('authenticated', () => {
    console.log('[OK] Sesion autenticada. El QR no sera necesario en proximas ejecuciones.');
});

client.on('auth_failure', (msg) => {
    console.error('[ERROR] Fallo de autenticacion:', msg);
    isReady = false;
});

client.on('disconnected', (reason) => {
    console.warn('[WARN] WhatsApp desconectado:', reason);
    isReady = false;
    console.log('[INFO] Reiniciando cliente en 5 segundos...');
    setTimeout(() => {
        client.initialize().catch((err) => {
            console.error('[ERROR] Fallo al reiniciar:', err.message);
        });
    }, 5000);
});

// Captura errores no manejados de Puppeteer (ej: detached frame) sin tirar el proceso
process.on('unhandledRejection', (reason) => {
    const msg = reason && reason.message ? reason.message : String(reason);
    if (
        msg.includes('detached Frame') ||
        msg.includes('Execution context was destroyed') ||
        msg.includes('Target closed')
    ) {
        console.warn('[WARN] Error de Puppeteer ignorado (reconectando):', msg);
    } else {
        console.error('[ERROR] Promesa no manejada:', msg);
    }
});

console.log('Iniciando cliente WhatsApp...');
client.initialize();

// ─── Endpoints HTTP ─────────────────────────────────────────────────────────

app.get('/status', (req, res) => {
    res.json({ ready: isReady });
});

/**
 * POST /send
 * Body: { "to": "5491112345678", "message": "Texto del mensaje" }
 * Retorna: { "success": true, "to": "..." }
 */
app.post('/send', async (req, res) => {
    if (!isReady) {
        return res.status(503).json({ error: 'WhatsApp no esta conectado. Espere el QR o reconecte.' });
    }

    const { to, message } = req.body;
    if (!to || !message) {
        return res.status(400).json({ error: 'Faltan campos requeridos: to, message' });
    }

    const number = String(to).replace(/\D/g, '');
    if (number.length < 10) {
        return res.status(400).json({ error: `Numero invalido: ${to}` });
    }

    // Argentina: probar con y sin el "9" (549XXXXXXXX vs 54XXXXXXXX)
    const candidates = number.startsWith('549')
        ? [number, '54' + number.slice(3)]
        : number.startsWith('54')
            ? ['54' + '9' + number.slice(2), number]
            : [number];

    let lastError = null;
    for (const candidate of candidates) {
        try {
            const numberId = await client.getNumberId(candidate);
            if (!numberId) {
                lastError = new Error(`${candidate} no esta registrado en WhatsApp`);
                continue;
            }
            const resolvedId = numberId._serialized;
            console.log(`[INFO] ${candidate} -> ${resolvedId}`);
            await client.sendMessage(resolvedId, message);
            console.log(`[ENVIADO] ${resolvedId}`);
            return res.json({ success: true, to: resolvedId });
        } catch (err) {
            console.warn(`[WARN] Fallo con ${candidate}: ${err.message}`);
            lastError = err;
        }
    }

    res.status(500).json({ error: lastError ? lastError.message : 'Error desconocido' });
});

// ─── Inicio del servidor ─────────────────────────────────────────────────────

app.listen(PORT, '0.0.0.0', () => {
    console.log(`Servidor HTTP escuchando en http://0.0.0.0:${PORT} (accesible desde la red local)`);
    console.log('Esperando conexion de WhatsApp...\n');
});
