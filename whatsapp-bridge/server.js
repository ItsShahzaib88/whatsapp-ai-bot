const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode');
const axios = require('axios');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
    cors: { origin: '*' }
});

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Health check endpoint to keep Render free tier awake
app.get('/ping', (req, res) => {
    res.status(200).send('pong');
});

const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL || 'https://whatsapp-ai-bot-ftku.onrender.com/api/v1/internal/message';

// Store active sessions: { sessionId: clientInstance }
const sessions = {};

// Handle Socket.io connections for the web interface
io.on('connection', (socket) => {
    console.log('User connected to Web UI:', socket.id);

    socket.on('start_session', async (data) => {
        const { sessionId } = data;
        if (!sessionId) {
            socket.emit('message', { text: 'Session ID is required' });
            return;
        }

        if (sessions[sessionId]) {
            socket.emit('message', { text: 'Session already exists and is active.' });
            return;
        }

        console.log(`Starting new session: ${sessionId}`);
        socket.emit('message', { text: 'Initializing WhatsApp Client...' });

        try {
            const client = new Client({
                authStrategy: new LocalAuth({ clientId: sessionId }),
                puppeteer: {
                    headless: true,
                    args: ['--no-sandbox', '--disable-setuid-sandbox']
                }
            });

            sessions[sessionId] = client;

            client.on('qr', async (qr) => {
                console.log(`[${sessionId}] QR Code generated`);
                try {
                    const qrDataUrl = await qrcode.toDataURL(qr);
                    socket.emit('qr', { src: qrDataUrl });
                    socket.emit('message', { text: 'Scan this QR code with WhatsApp' });
                } catch (err) {
                    console.error('Error generating QR code data URL', err);
                }
            });

            client.on('ready', () => {
                console.log(`[${sessionId}] Client is READY!`);
                socket.emit('ready', { sessionId });
                socket.emit('message', { text: 'WhatsApp Connected Successfully!' });
            });

            client.on('authenticated', () => {
                console.log(`[${sessionId}] Client is authenticated`);
                socket.emit('authenticated', { sessionId });
            });

            client.on('auth_failure', (msg) => {
                console.error(`[${sessionId}] Auth failure:`, msg);
                socket.emit('message', { text: 'Authentication failed. Please try again.' });
                delete sessions[sessionId];
            });

            client.on('disconnected', (reason) => {
                console.log(`[${sessionId}] Client was disconnected:`, reason);
                socket.emit('message', { text: 'WhatsApp Disconnected.' });
                delete sessions[sessionId];
            });

            client.on('message', async (message) => {
                // Ignore status updates and groups
                if (message.isStatus || message.from === 'status@broadcast') return;
                const chat = await message.getChat();
                if (chat.isGroup) return;

                console.log(`\n[${sessionId}] [RECEIVED] From: ${message.from} | Text: ${message.body}`);
                chat.sendStateTyping();

                try {
                    // Send to Python AI Backend with bot_id (sessionId)
                    const response = await axios.post(PYTHON_BACKEND_URL, {
                        bot_id: sessionId,
                        phone: message.from.replace('@c.us', ''),
                        text: message.body,
                        name: (await message.getContact()).pushname || "User"
                    });

                    const aiReply = response.data.reply;

                    // Add a small human-like delay before sending (1.5-3.5 seconds)
                    setTimeout(() => {
                        message.reply(aiReply);
                        console.log(`[${sessionId}] [SENT AI REPLY]: ${aiReply}`);
                        chat.clearState();
                    }, Math.floor(Math.random() * 2000) + 1500);

                } catch (error) {
                    console.error(`[${sessionId}] [ERROR] Failed to get response from AI Backend:`, error.message);
                    chat.clearState();
                }
            });

            await client.initialize();

        } catch (error) {
            console.error('Failed to initialize client:', error);
            socket.emit('message', { text: 'Error initializing client.' });
        }
    });

    socket.on('disconnect', () => {
        console.log('User disconnected:', socket.id);
    });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
    console.log(`WhatsApp Bridge Server running on http://localhost:${PORT}`);
});
