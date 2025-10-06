#!/usr/bin/env node
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '.env') });

const https = require('https');
const { argv, exit } = require('process');

function arg(name, def = '') {
  const i = argv.indexOf(`--${name}`);
  if (i !== -1 && argv[i + 1] && !argv[i + 1].startsWith('--')) return argv[i + 1];
  return def;
}

// 非同期のメイン関数を定義
async function main() {
  const webhookUrl = process.env.SLACK_WEBHOOK_URL;
  if (!webhookUrl) {
    console.error('エラー: SLACK_WEBHOOK_URLが.envファイルに設定されていません。');
    return exit(1);
  }

  const title = arg('title', 'GCN Alert');
  const message = arg('message', 'Alert triggered');

  const payload = JSON.stringify({
    text: `<!channel> 緊急警報: ${title}`,
    blocks: [
      { type: "section", text: { type: "mrkdwn", text: `🚨 *<!channel> 緊急警報: ${title}* 🚨` } },
      { type: "divider" },
      { type: "section", text: { type: "mrkdwn", text: "```\n" + message + "\n```" } }
    ]
  });

  try {
    // Promiseを使って非同期処理の結果を待つ
    const response = await sendRequest(webhookUrl, payload);
    console.log(`Slack API response: ${response}`);
    
    // Slackからの応答本文を解析してステータスコードを判断
    // Slackは成功すると "ok" というテキストを返す
    if (response.toLowerCase() !== 'ok') {
        console.error(`エラー: Slackから予期しない応答がありました: ${response}`);
        return exit(1); // 失敗として終了
    }
    
    // 成功
    return exit(0);

  } catch (error) {
    console.error('HTTPSリクエストエラー:', error);
    return exit(1);
  }
}

// HTTPSリクエストをPromiseでラップする関数
function sendRequest(urlString, payload) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlString);
    const options = {
      hostname: url.hostname,
      path: url.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(payload),
      },
    };

    const req = https.request(options, res => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        // ステータスコードが200番台でなければエラーとする
        if (res.statusCode < 200 || res.statusCode >= 300) {
          return reject(new Error(`API Error: Status ${res.statusCode}, Body: ${data}`));
        }
        resolve(data);
      });
    });

    req.on('error', reject);
    req.write(payload);
    req.end();
  });
}

// メイン関数を実行
main();