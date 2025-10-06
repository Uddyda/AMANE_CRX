#!/usr/bin/env node
// send_alert.cjs — タイトル先頭APPEND＋サウンド既定＋Emergency/ACK対応（dotenvは__dirname基準）
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '.env') });

const https = require('https');
const fs = require('fs');
const { argv, exit } = require('process');

function arg(name, def = '') {
  const i = argv.indexOf(`--${name}`);
  if (i !== -1 && argv[i + 1] && !argv[i + 1].startsWith('--')) return argv[i + 1];
  return def;
}
function flag(name) { return argv.includes(`--${name}`); }

function postForm(host, p, formObj) {
  const body = new URLSearchParams(formObj).toString();
  return new Promise((resolve, reject) => {
    const req = https.request(
      { hostname: host, path: p, method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded',
                   'Content-Length': Buffer.byteLength(body) } },
      (res) => {
        let data = '';
        res.on('data', c => data += c);
        res.on('end', () => resolve({ status: res.statusCode, text: data }));
      }
    );
    req.on('error', reject);
    req.write(body); req.end();
  });
}
function getJson(host, p, qs) {
  const q = new URLSearchParams(qs).toString();
  const full = q ? `${p}?${q}` : p;
  return new Promise((resolve, reject) => {
    https.get({ hostname: host, path: full }, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        try { resolve({ status: res.statusCode, json: JSON.parse(data || '{}') }); }
        catch { resolve({ status: res.statusCode, json: { raw: data } }); }
      });
    }).on('error', reject);
  });
}

// ==== 引数 & 既定値（.envで上書き可）====
const priority  = String(arg('priority', process.env.PUSHOVER_PRIORITY || '2'));
const retry     = arg('retry',  process.env.PUSHOVER_RETRY  || '60');     // P2のみ使用
const expire    = arg('expire', process.env.PUSHOVER_EXPIRE || '3600');   // P2のみ使用
const waitAck   = flag('wait-for-ack') || process.env.PUSHOVER_WAIT_FOR_ACK === '1';

let   title     = arg('title',     process.env.PUSHOVER_TITLE   || 'Alert');
let   message   = arg('message',   process.env.PUSHOVER_MESSAGE || 'Alert triggered');
const url       = arg('url',       process.env.PUSHOVER_URL     || '');
const urlTitle  = arg('url-title', process.env.PUSHOVER_URL_TITLE || '');
const messageFile = arg('message-file', '');

// 追記メッセージはタイトル先頭（CLIと.envを合算）
const cliAppend = arg('append', '');
const envAppend = process.env.PUSHOVER_APPEND || '';
const titlePrefix = [cliAppend, envAppend].filter(Boolean).join(' / ');
if (titlePrefix) title = `${titlePrefix} — ${title}`;

// サウンド：CLI > .env
const sound = arg('sound', process.env.PUSHOVER_SOUND || '');

// 本文をファイルから読み込み可能
if (messageFile) {
  try { message = fs.readFileSync(path.resolve(messageFile), 'utf8'); }
  catch (e) { console.error('message-file 読み込み失敗:', e.message); exit(1); }
}

// ==== 認証（必須）====
const token = process.env.PUSHOVER_TOKEN;
const user  = process.env.PUSHOVER_GROUP || process.env.PUSHOVER_USER;
if (!token || !user) {
  console.error('PUSHOVER_TOKEN と PUSHOVER_GROUP（または PUSHOVER_USER）を .env に設定してください');
  exit(2);
}

// ==== 送信 ====
const form = { token, user, title, message, priority };
if (url) form.url = url;
if (urlTitle) form.url_title = urlTitle;
if (sound) form.sound = sound;

// Priority 2 の必須パラメータを“最終防衛線”として強制セット
if (priority === '2') {
  form.retry  = String(retry || '60');
  form.expire = String(expire || '3600');
}

(async () => {
  try {
    const res = await postForm('api.pushover.net', '/1/messages.json', form);
    if (res.status < 200 || res.status >= 300) {
      console.error('Pushover NG:', res.status, res.text);
      return exit(1);
    }
    let parsed = {};
    try { parsed = JSON.parse(res.text); } catch {}

    console.log('Pushover OK', parsed.request ? `(request: ${parsed.request})` : '');

    // Emergency: ACK待ち（任意）
    if (priority === '2' && waitAck && parsed.receipt) {
      const receipt = parsed.receipt;
      const interval = Math.max(15, Math.floor(Number(retry) / 2));
      const deadline = Date.now() + Number(expire) * 1000;
      while (Date.now() < deadline) {
        const r = await getJson('api.pushover.net', `/1/receipts/${receipt}.json`, { token });
        if (r.status === 200 && r.json.acknowledged) {
          console.log('ACKED at', new Date(r.json.acknowledged_at * 1000).toISOString());
          return exit(0);
        }
        await new Promise(f => setTimeout(f, interval * 1000));
      }
      console.warn('Expire reached without ACK.');
    }
    exit(0);
  } catch (e) {
    console.error('Pushover Error:', e.message);
    exit(1);
  }
})();
