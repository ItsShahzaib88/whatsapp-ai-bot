/**
 * WhatsApp Personal AI Bot — Unofficial Bridge
 * =============================================
 * Uses whatsapp-web.js to connect your personal WhatsApp
 * and route messages through a local Python AI backend.
 *
 * HOW TO USE:
 *  1. Run: node index.js
 *  2. Scan the QR code in terminal with WhatsApp > Linked Devices
 *  3. Bot will automatically reply to contacts with AI enabled
 *
 * NOTE: Per-contact AI toggle is controlled from the Admin Dashboard.
 *       Python backend checks each contact's `ai_enabled` flag.
 */

const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const readline = require('readline');
const fs = require('fs');
const path = require('path');

// ============================================================
//  CONFIGURATION
// ============================================================
const PYTHON_BACKEND_URL = process.env.PYTHON_BACKEND_URL
    || 'http://127.0.0.1:8000/api/v1/internal/message';

// Human-like delay range (milliseconds) before sending reply.
// Keeps behavior natural — avoids instant bot-like responses.
const REPLY_DELAY_MIN_MS = 1500;
const REPLY_DELAY_MAX_MS = 3500;

// ============================================================
//  WHATSAPP CLIENT SETUP
// ============================================================
console.log('\n🤖 WhatsApp Personal AI Bot — Starting...');
console.log('='.repeat(50));

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

const authPath = './.wwebjs_auth';
const sessionExists = fs.existsSync(authPath);

if (sessionExists) {
    console.log('\n==================================================');
    console.log('⚠️  SESSION ALREADY EXISTS:');
    console.log('1. Continue with saved session (Default)');
    console.log('2. Unlink and link a NEW number');
    console.log('==================================================');
    rl.question('\nEnter your choice [1/2]: ', (choice) => {
        if (choice.trim() === '2') {
            try {
                fs.rmSync(authPath, { recursive: true, force: true });
                console.log('\n✅ Previous session deleted. Ready to link new number.');
            } catch (e) {
                console.error('\n❌ Failed to delete old session:', e.message);
            }
            askLoginMethod();
        } else {
            console.log('\n✅ Continuing with saved session...');
            startClient(false, '');
        }
    });
} else {
    askLoginMethod();
}

function askLoginMethod() {
    console.log('\n==================================================');
    console.log('🔗 CHOOSE LINKING METHOD:');
    console.log('1. Link with QR Code (Default)');
    console.log('2. Link with Phone Number (Pairing Code)');
    console.log('==================================================');
    rl.question('\nEnter your choice [1/2]: ', (choice) => {
        if (choice.trim() === '2') {
            rl.question('\n📱 Enter your phone number (with country code, e.g. 923001234567): ', (phone) => {
                rl.close();
                const phoneNumber = phone.replace(/[^0-9]/g, '');
                if (phoneNumber.length < 5) {
                    console.log('\n❌ Invalid phone number format. Exiting.');
                    process.exit(1);
                }
                console.log(`\n⚙️  Will use Pairing Code for: ${phoneNumber}`);
                startClient(true, phoneNumber);
            });
        } else {
            rl.close();
            console.log('\n⚙️  Will use standard QR Code login.');
            startClient(false, '');
        }
    });
}

function startClient(usePairingCode, phoneNumber) {
    if (!rl.closed) {
        rl.close();
    }
    const client = new Client({
        authStrategy: new LocalAuth({
            dataPath: './.wwebjs_auth',  // Session stored locally — won't need to re-scan QR
        }),
        puppeteer: {
            headless: true,
            // Use system-installed Chrome to avoid Puppeteer download issues on Windows
            // If Chrome is not at this path, Puppeteer will try its own cached browser
            executablePath: (
                process.env.CHROME_PATH ||
                'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
            ),
            args: [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu',
            ],
        },
    });

    let pairingCodeRequested = false;

    // ============================================================
    //  EVENT: QR CODE — Scan with phone to link
    // ============================================================
    client.on('qr', async (qr) => {
        if (usePairingCode) {
            if (pairingCodeRequested) return;
            pairingCodeRequested = true;
            
            console.log('\n⏳ Requesting Pairing Code (please wait a few seconds)...');
            try {
                const code = await client.requestPairingCode(phoneNumber);
                console.log('\n📱 YOUR PAIRING CODE IS:');
                console.log('=============================');
                console.log(`   ${code}`);
                console.log('=============================');
                console.log('1. Open WhatsApp on your phone');
                console.log('2. Go to Linked Devices > Link a Device');
                console.log('3. Tap "Link with phone number instead"');
                console.log('4. Enter the code above\n');
            } catch (err) {
                console.error('\n❌ Failed to get pairing code. Check the phone number or try again.', err);
                pairingCodeRequested = false; // allow retry on next QR tick
            }
        } else {
            console.log('\n📱 SCAN THIS QR CODE WITH YOUR WHATSAPP');
            console.log('   Go to: WhatsApp > Settings > Linked Devices > Link a Device\n');
            qrcode.generate(qr, { small: true });
            console.log('\n⏳ Waiting for scan...\n');
        }
    });

    // ============================================================
    //  EVENT: AUTHENTICATED — Session saved
    // ============================================================
    client.on('authenticated', () => {
        console.log('🔐 Authenticated! Session saved. No re-scan needed next time.');
    });

    // ============================================================
    //  EVENT: READY — Bot is live
    // ============================================================
    client.on('ready', () => {
        console.log('\n' + '='.repeat(50));
        console.log('✅ WhatsApp AI Bot is READY and CONNECTED!');
        console.log('   Listening for messages...');
        console.log('   Dashboard: http://localhost:8000/dashboard');
        console.log('='.repeat(50) + '\n');
    });

    // ============================================================
    //  EVENT: DISCONNECTED
    // ============================================================
    client.on('disconnected', async (reason) => {
        console.log('\n⚠️  WhatsApp disconnected:', reason);
        if (reason === 'LOGOUT') {
            console.log('   You have been logged out from your phone.');
            console.log('   Please restart the bot and select Option 2 to link again.\n');
            process.exit(1);
        } else {
            console.log('   Attempting to reconnect...\n');
            try { await client.destroy(); } catch (e) {}
            client.initialize();
        }
    });

    // ============================================================
    //  EVENT: AUTH FAILURE
    // ============================================================
    client.on('auth_failure', (msg) => {
        console.error('\n❌ Authentication failed:', msg);
        console.error('   Please delete the .wwebjs_auth folder and restart to re-scan QR.\n');
        process.exit(1);
    });

    // ============================================================
    //  EVENT: MESSAGE — Core bot logic
    // ============================================================
    client.on('message', async (message) => {

        // ---- Ignore non-relevant messages ----
        // Skip status broadcasts
        if (message.isStatus || message.from === 'status@broadcast') return;

        // Skip messages sent BY us (our own messages in other chats)
        if (message.fromMe) return;

        // Skip empty messages unless they have media
        if ((!message.body || message.body.trim() === '') && !message.hasMedia) return;

        const senderPhone = message.from.replace('@c.us', '');  // e.g. "923001234567"
        let senderName = 'User';
        try {
            senderName = (await message.getContact()).pushname || 'User';
        } catch (err) {
            // Ignore if contact name cannot be fetched
        }

        console.log(`\n📩 [RECEIVED] ${senderName} (${senderPhone}): ${message.body || '<media>'}`);

        let mediaData = null;
        let mediaMimetype = null;
        if (message.hasMedia) {
            try {
                const media = await message.downloadMedia();
                if (media) {
                    mediaData = media.data;
                    mediaMimetype = media.mimetype;
                    console.log(`   📎 [ATTACHMENT] Received media: ${media.mimetype}`);
                }
            } catch (err) {
                console.error(`   ❌ [MEDIA ERROR]: Failed to download media`, err.message);
            }
        }

        let chat = null;
        try {
            chat = await message.getChat();
            // ---- Show "Typing..." indicator ----
            await chat.sendStateTyping();
        } catch (err) {
            // Ignore chat state errors during initial sync
        }

        try {
            // ---- Send to Python AI Backend ----
            // Python backend will:
            //   1. Look up the contact
            //   2. Check if ai_enabled = True (set from Dashboard)
            //   3. Generate AI reply using Gemini
            //   4. Return reply text (or null if ai disabled)
            const response = await axios.post(
                PYTHON_BACKEND_URL,
                {
                    phone: senderPhone,
                    text: message.body || "",
                    name: senderName,
                    media_data: mediaData,
                    media_mimetype: mediaMimetype,
                },
                {
                    timeout: 120000,  // 120 second timeout for AI/Video generation
                }
            );

            const aiReply = response.data?.reply;
            const mediaUrl = response.data?.media_url;

            // Python backend returns null/empty if AI is disabled for this contact
            if (!aiReply && !mediaUrl) {
                console.log(`   ⏭️  [SKIPPED] AI disabled for ${senderPhone} (toggled off from Dashboard)`);
                if (chat) {
                    try { await chat.clearState(); } catch (e) {}
                }
                return;
            }

            // ---- Human-like delay before replying ----
            const delay = Math.floor(Math.random() * (REPLY_DELAY_MAX_MS - REPLY_DELAY_MIN_MS)) + REPLY_DELAY_MIN_MS;

            setTimeout(async () => {
                try {
                    if (mediaUrl) {
                        const { MessageMedia } = require('whatsapp-web.js');
                        const media = await MessageMedia.fromUrl(mediaUrl, { unsafeMime: true });
                        await message.reply(media, undefined, { caption: aiReply });
                        console.log(`   🤖 [REPLIED] (${(delay / 1000).toFixed(1)}s delay) with media: ${mediaUrl}`);
                    } else {
                        await message.reply(aiReply);
                        console.log(`   🤖 [REPLIED] (${(delay / 1000).toFixed(1)}s delay): ${aiReply?.substring(0, 80)}...`);
                    }
                } catch (sendError) {
                    console.error(`   ❌ [SEND ERROR]:`, sendError.message);
                } finally {
                    if (chat) {
                        try { await chat.clearState(); } catch (e) {}
                    }
                }
            }, delay);

        } catch (error) {
            console.error(`   ❌ [BACKEND ERROR]: ${error.message}`);
            if (error.code === 'ECONNREFUSED') {
                console.error(`   💡 Make sure Python backend is running: uvicorn app.main:app --port 8000`);
            }
            if (chat) {
                try { await chat.clearState(); } catch (e) {}
            }
        }
    });

    // ============================================================
    //  GRACEFUL SHUTDOWN
    // ============================================================
    process.on('SIGINT', async () => {
        console.log('\n\n🛑 Shutting down bot gracefully...');
        await client.destroy();
        console.log('👋 Goodbye!\n');
        process.exit(0);
    });

    // ============================================================
    //  START
    // ============================================================
    client.initialize().catch((err) => {
        console.error('❌ Failed to initialize WhatsApp client:', err.message);
        process.exit(1);
    });
}
